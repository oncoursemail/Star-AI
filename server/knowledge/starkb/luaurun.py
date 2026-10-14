"""Opt-in, Linux-only standalone Luau execution. No code ever runs on the desktop.

Use an unprivileged, isolated service account/container. prlimit is not an OS
sandbox against a VM exploit; the allowlisted Luau environment is the language
boundary. No preexec_fn is used in the threaded HTTP server. Missing tools,
unsupported platforms and root execution fail closed.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

MAX_SOURCE_BYTES = 64 * 1024   # code and tests combined
OUTPUT_BYTES = 64 * 1024
DEFAULT_TIME_SECONDS = 3.0
MAX_TIME_SECONDS = 10.0
MAX_CPU_SECONDS = 8           # retain the evaluation harness CPU ceiling
DEFAULT_MEMORY_MB = 256
MIN_MEMORY_MB = 32
MAX_MEMORY_MB = 256           # no looser than the evaluation harness
QUEUE_SIZE = 4
QUEUE_TIMEOUT_SECONDS = 2.0
TOOLS_DIR = Path(os.environ.get("STAR_LUAU_TOOLS", "/opt/star/knowledge/tools"))
_DIAGNOSTIC = re.compile(r"(?:^|\n)(?:\[string \"(code|tests)\"\]|(code|tests)):(\d{1,7}):\s*([^\n]*)")


class Unavailable(RuntimeError):
    """The sandbox could not start. Never a verdict on submitted code."""


class Busy(RuntimeError):
    """Admission was refused before running any submitted code."""


def validate(body: dict) -> tuple[str, str, float, int]:
    code, tests = body.get("code"), body.get("tests", "")
    seconds = body.get("time_limit_s", DEFAULT_TIME_SECONDS)
    memory = body.get("memory_limit_mb", DEFAULT_MEMORY_MB)
    if not isinstance(code, str) or not code.strip() or not isinstance(tests, str):
        raise ValueError("code must be non-empty text and tests must be text")
    try:
        size = len(code.encode("utf-8")) + len(tests.encode("utf-8"))
    except UnicodeError:
        raise ValueError("code and tests must be valid UTF-8") from None
    if size > MAX_SOURCE_BYTES or "\x00" in code or "\x00" in tests:
        raise ValueError(f"code and tests must total at most {MAX_SOURCE_BYTES} bytes, without NUL")
    if (type(seconds) not in (int, float) or not 0 < seconds <= MAX_TIME_SECONDS
            or not math.isfinite(seconds)):
        raise ValueError("time_limit_s must be greater than 0 and at most 10")
    if type(memory) is not int or not MIN_MEMORY_MB <= memory <= MAX_MEMORY_MB:
        raise ValueError(f"memory_limit_mb must be an integer in {MIN_MEMORY_MB}..{MAX_MEMORY_MB}")
    return code, tests, float(seconds), memory


def _literal(text: str) -> str:
    # Numeric UTF-8 escapes, not long brackets or JSON: quotes, backslashes and
    # attacker-chosen closing delimiters can never become bootstrap instructions.
    return '"' + ''.join(f"\\{byte:03d}" for byte in text.encode("utf-8")) + '"'


def bootstrap(code: str, tests: str) -> str:
    """Compile separate named chunks. Tests see exported globals and `result`.

    Never merely shadow require: getfenv/setfenv would recover the CLI environment.
    This table has no metatable or pointer to that environment; privileged loaders
    and environment/debug APIs are not exposed, even through _G.
    """
    return '''local safe = {
    assert=assert, error=error, ipairs=ipairs, next=next, pairs=pairs,
    pcall=pcall, xpcall=xpcall, select=select, tonumber=tonumber,
    tostring=tostring, type=type, typeof=typeof, print=print,
    rawequal=rawequal, rawget=rawget, rawset=rawset, rawlen=rawlen,
    setmetatable=setmetatable,
    unpack=unpack, _VERSION=_VERSION,
}
-- Copy only pure standard libraries; no io, os, require, network or filesystem.
for name, library in pairs({math=math, string=string, table=table,
                           utf8=utf8, bit32=bit32, buffer=buffer,
                           vector=vector, coroutine=coroutine}) do
    local copy = {}
    for key, value in pairs(library) do copy[key] = value end
    safe[name] = table.freeze(copy)
end
safe._G = safe
local builtins = table.clone(safe)
local function run(source, name, safe)
    local chunk, message = loadstring(source, name)
    if not chunk then error(message, 0) end
    setfenv(chunk, safe)
    return chunk()
end
local result = run(''' + _literal(code) + ''', "code", safe)
-- Tests have their own builtins: code cannot replace assert to forge a pass.
local checks = {}
for key, value in next, safe do checks[key] = value end
for key, value in next, builtins do checks[key] = value end
checks._G = checks
checks.result = result
run(''' + _literal(tests) + ''', "tests", checks)
'''


class RunQueue:
    """One VM globally, four FIFO waiters, at most one request per peer.

    Client identity comes from the socket, never JSON or forwarding headers.
    Queued requests expire instead of holding a request thread indefinitely.
    """
    def __init__(self, capacity: int = QUEUE_SIZE, wait: float = QUEUE_TIMEOUT_SECONDS):
        self.capacity, self.wait = capacity, wait
        self._condition = threading.Condition()
        self._clients: set[str] = set()
        self._waiting: deque = deque()
        self._running = False

    @contextmanager
    def slot(self, client: str):
        token = object()
        admitted = False
        with self._condition:
            if client in self._clients:
                raise Busy("a run for this client is already active or queued")
            if (self._running or self._waiting) and len(self._waiting) >= self.capacity:
                raise Busy("run queue is full")
            self._clients.add(client)
            self._waiting.append(token)
            deadline = time.monotonic() + self.wait
            waited = False
            try:
                while self._running or self._waiting[0] is not token:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise Busy("run queue deadline exceeded")
                    waited = True
                    self._condition.wait(left)
                if waited and time.monotonic() >= deadline:
                    raise Busy("run queue deadline exceeded")
                self._waiting.popleft()
                self._running = admitted = True
            finally:
                if not admitted:
                    self._waiting.remove(token)
                    self._clients.remove(client)
                    self._condition.notify_all()
        try:
            yield
        finally:
            with self._condition:
                self._running = False
                self._clients.remove(client)
                self._condition.notify_all()


def available(tools_dir: Path = TOOLS_DIR) -> bool:
    return (sys.platform == "linux" and hasattr(os, "wait4") and os.geteuid() != 0
            and shutil.which("prlimit") is not None
            and (tools_dir / "luau").is_file() and os.access(tools_dir / "luau", os.X_OK))


def _kill_group(proc) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _execute(argv: list[str], cwd: Path, *, seconds: float, memory_mb: int) -> dict:
    """Bounded child execution; also exercised with local OS-limit test probes.

    wait4 collects this child's usage, not cumulative RUSAGE_CHILDREN (which races
    other HTTP workers). Output is a regular file subject to RLIMIT_FSIZE, not
    communicate()'s unbounded in-memory buffer. Stderr shares the same 64 KiB cap.
    """
    prlimit = shutil.which("prlimit")
    if sys.platform != "linux" or not prlimit or not hasattr(os, "wait4"):
        raise Unavailable("Linux prlimit and wait4 are required")
    command = [prlimit, f"--as={memory_mb * 1024 * 1024}",
               f"--cpu={min(MAX_CPU_SECONDS, max(1, math.ceil(seconds)))}", f"--fsize={OUTPUT_BYTES}",
               "--nofile=32", "--core=0", "--nproc=0", "--", *argv]
    start = time.monotonic()
    timed_out, usage = False, None
    output_path = cwd / "output.txt"
    with output_path.open("wb") as sink:
        try:
            proc = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                    stdout=sink, stderr=subprocess.STDOUT, env={"LANG": "C.UTF-8"},
                                    close_fds=True, start_new_session=True, shell=False)
        except OSError:
            raise Unavailable("could not start the Luau sandbox") from None
        try:
            deadline = start + seconds
            while True:
                pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    _kill_group(proc)
                    _, status, usage = os.wait4(proc.pid, 0)
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    break
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        finally:
            _kill_group(proc)
            if proc.returncode is None:
                _, status, usage = os.wait4(proc.pid, 0)
                proc.returncode = os.waitstatus_to_exitcode(status)
    if proc.returncode in (126, 127):
        raise Unavailable("could not execute the Luau VM")
    with output_path.open("rb") as source:
        raw = source.read(OUTPUT_BYTES)
    # Trimming after decoding also caps replacement characters from invalid UTF-8.
    output = raw.decode("utf-8", "replace").encode("utf-8")[:OUTPUT_BYTES].decode("utf-8", "ignore")
    limited = len(raw) >= OUTPUT_BYTES or proc.returncode == -signal.SIGXFSZ
    ok = proc.returncode == 0 and not timed_out and not limited
    if timed_out:
        reason = "timeout"
    elif limited:
        reason = "output_limit"
    elif proc.returncode < 0:
        reason = "resource_limit"
    else:
        reason = "passed" if ok else "runtime_error"
    errors = []
    # Successful code may print text that resembles an error. Its exit status,
    # not untrusted printed lines, determines the verdict.
    for match in _DIAGNOSTIC.finditer(output if not ok else ""):
        if not 1 <= int(match[3]) < 1_000_000:
            continue
        errors.append({"source": match[1] or match[2], "line": int(match[3]),
                       "message": match[4][:500]})
        if len(errors) == 12:
            break
    return {"ok": ok, "status": "pass" if ok else "fail", "executed": True,
            "output": output, "error": "" if ok else reason, "errors": errors,
            "exit_code": proc.returncode, "timed_out": timed_out, "output_limited": limited,
            "usage": {"wall_seconds": round(time.monotonic() - start, 4),
                      "cpu_seconds": round(usage.ru_utime + usage.ru_stime, 4),
                      "max_rss_bytes": usage.ru_maxrss * 1024,
                      "output_bytes": len(raw)},
            "limits": {"time_limit_s": seconds, "memory_limit_mb": memory_mb,
                       "cpu_limit_s": min(MAX_CPU_SECONDS, max(1, math.ceil(seconds))),
                       "output_bytes": OUTPUT_BYTES}, "untrusted": True,
            "roblox_engine": False}


def run(code: str, tests: str = "", *, time_limit_s: float = DEFAULT_TIME_SECONDS,
        memory_limit_mb: int = DEFAULT_MEMORY_MB, tools_dir: Path = TOOLS_DIR) -> dict:
    code, tests, seconds, memory = validate({"code": code, "tests": tests,
                                           "time_limit_s": time_limit_s,
                                           "memory_limit_mb": memory_limit_mb})
    if not available(tools_dir):
        raise Unavailable("Luau run needs Linux, prlimit, an installed VM and a non-root service")
    # Tools are operator configuration only. No source, path or argv comes from JSON.
    binary = (tools_dir / "luau").resolve()
    with tempfile.TemporaryDirectory(prefix="star-luau-run-") as directory:
        cwd = Path(directory)
        (cwd / "runner.luau").write_text(bootstrap(code, tests), encoding="utf-8")
        return _execute([str(binary), "runner.luau"], cwd, seconds=seconds, memory_mb=memory)


class RunService:
    def __init__(self, *, enabled: bool | None = None, runner=run, queue: RunQueue | None = None):
        self.enabled = os.environ.get("STAR_KB_LUAU_RUN") == "1" if enabled is None else enabled
        self.runner = runner
        self.queue = queue if queue is not None else RunQueue()

    def handle(self, body: dict, client: str) -> tuple[int, dict]:
        if not self.enabled:
            return 503, {"error": "Luau run is disabled on this server", "executed": False}
        try:
            code, tests, seconds, memory = validate(body)
            with self.queue.slot(client):
                return 200, self.runner(code, tests, time_limit_s=seconds, memory_limit_mb=memory)
        except ValueError as exc:
            return 400, {"error": str(exc), "executed": False}
        except Busy as exc:
            return 429, {"error": str(exc), "executed": False}
        except Unavailable:
            return 503, {"error": "Luau sandbox is unavailable", "executed": False}
