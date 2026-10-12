"""Disposable Linux workbench. Never deploy beside the model or its secrets."""
from __future__ import annotations

import asyncio
import contextvars
import functools
import hashlib
import hmac
import inspect
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from importlib.metadata import version

REPOSITORY = "https://github.com/oncoursemail/Star-AI"
TAIL = 60 * 1024
REQUEST = 1024 * 1024
RESPONSE = 256 * 1024
DENIED = frozenset("sudo su mount umount iptables nft ssh scp nc ncat netcat curl wget "
                   "sh bash dash zsh fish csh ksh busybox env".split())
AUTHORIZED = contextvars.ContextVar("workbench_authorized", default=False)
TOOLS = ("ws_list", "ws_read", "ws_write", "ws_apply_patch", "ws_delete", "ws_search",
         "run", "job_start", "job_status", "job_output", "job_stop", "repo_sync",
         "repo_status", "repo_diff", "test_python", "test_frontend", "info")


@dataclass(frozen=True)
class Limits:
    timeout_s: int = 120
    max_timeout_s: int = 900
    memory_bytes: int = 8 * 1024**3
    file_bytes: int = 64 * 1024**2
    processes: int = 128
    jobs: int = 3
    retained_jobs: int = 32
    requests_per_minute: int = 120
    audit_bytes: int = 128 * 1024**2


def digest(value):
    """Hash ALL argument strings, including inline programs and environment values."""
    if isinstance(value, str):
        data = value.encode("utf-8")
        return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if isinstance(value, dict):
        # Even user-supplied dictionary keys may contain secrets.
        return [{"key": digest(k), "value": digest(v)} for k, v in value.items()]
    if isinstance(value, (list, tuple)):
        return [digest(v) for v in value]
    return value


def validate_argv(argv):
    if not isinstance(argv, list) or not argv or len(argv) > 256:
        raise ValueError("argv must be a nonempty list with at most 256 entries")
    if any(not isinstance(a, str) or "\0" in a for a in argv):
        raise ValueError("invalid argument")
    if not argv[0] or sum(len(a.encode()) for a in argv) > 65536:
        raise ValueError("argument size limit")
    executable = Path(argv[0])
    if executable.name.lower() in DENIED or executable.resolve().name.lower() in DENIED:
        raise PermissionError("program denied; use workspace tools instead")
    if executable.name == "git" and "push" in argv[1:]:
        raise PermissionError("pushing is not provided by this connector")


class Workspace:
    """Descriptor-relative operations: never follow links, including intermediate ones."""
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def parts(self, path):
        if not isinstance(path, str) or len(path.encode()) > 4096 or "\0" in path or "\\" in path:
            raise ValueError("invalid workspace path")
        p = Path(path)
        if p.is_absolute():
            try:
                p = p.relative_to(self.root)
            except ValueError:
                raise PermissionError("outside workspace") from None
        if ".." in p.parts:
            raise PermissionError("parent traversal refused")
        return p.parts

    @contextmanager
    def parent(self, path, create=False):
        parts = self.parts(path)
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            yield fd, parts[-1] if parts else "."
        finally:
            os.close(fd)

    def open(self, path, directory=False):
        with self.parent(path) as (fd, name):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            opened = os.open(name, flags | (os.O_DIRECTORY if directory else 0), dir_fd=fd)
        meta = os.fstat(opened)
        if not directory and (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1):
            os.close(opened)
            raise PermissionError("only single-link regular files are supported")
        return opened

    def read(self, path):
        with os.fdopen(self.open(path), "rb") as stream:
            data = stream.read(REQUEST + 1)
        if len(data) > REQUEST:
            raise ValueError("file exceeds 1 MiB read/patch limit")
        return data.decode("utf-8")

    def write(self, path, content):
        data = content.encode("utf-8")
        if len(data) > REQUEST or not self.parts(path):
            raise ValueError("write size/path limit")
        with self.parent(path, create=True) as (fd, name):
            try:
                meta = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                    raise PermissionError("refusing to replace link or special file")
            except FileNotFoundError:
                pass
            temporary = ".workbench-" + uuid.uuid4().hex
            out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=fd)
            try:
                with os.fdopen(out, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=fd)
                except FileNotFoundError:
                    pass
        return digest(content)

    def entries(self, path, depth):
        if not 0 <= depth <= 8:
            raise ValueError("depth must be between 0 and 8")
        result = []
        def walk(fd, prefix, remaining):
            with os.scandir(fd) as entries:
                for item in entries:
                    if len(result) >= 4000:
                        raise ValueError("listing limit; choose a narrower path")
                    name = (Path(prefix) / item.name).as_posix()
                    kind = "link" if item.is_symlink() else "file"
                    if item.is_dir(follow_symlinks=False):
                        kind = "directory"
                    result.append({"path": name, "kind": kind})
                    if kind == "directory" and remaining > 1:
                        child = os.open(item.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                        dir_fd=fd)
                        try:
                            walk(child, name, remaining - 1)
                        finally:
                            os.close(child)
        fd = self.open(path, directory=True)
        try:
            if depth:
                walk(fd, Path(*self.parts(path)).as_posix(), depth)
        finally:
            os.close(fd)
        return sorted(result, key=lambda row: row["path"])


class Workbench:
    def __init__(self, root, state, audit, kill_switch, *, limits=None, sandbox=True):
        self.ws = Workspace(root)
        self.state, self.audit_path, self.kill_switch = map(Path, (state, audit, kill_switch))
        if any(p.resolve().is_relative_to(self.ws.root) for p in
               (self.state, self.audit_path, self.kill_switch)):
            raise ValueError("control state must be outside workspace")
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.limits, self.sandbox = limits or Limits(), sandbox
        self.jobs, self.lock, self.audit_lock = {}, threading.RLock(), threading.Lock()
        self.audit_fd = os.open(self.audit_path, os.O_APPEND | os.O_WRONLY | os.O_CREAT |
                                os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        if not stat.S_ISREG(os.fstat(self.audit_fd).st_mode):
            raise ValueError("audit log must be a regular file")
        self.repo_lock = threading.RLock()
        for stale in self.state.glob("*.log"):
            if re.fullmatch(r"[a-f0-9]{32}\.log", stale.name):
                stale.unlink()

    def audit(self, tool, args, exit_code, event="finish"):
        record = {"time": time.time(), "tool": tool, "arguments": digest(args),
                  "exit_code": exit_code, "event": event}
        data = (json.dumps(record, ensure_ascii=True) + "\n").encode()
        with self.audit_lock:
            if os.fstat(self.audit_fd).st_size + len(data) > self.limits.audit_bytes:
                raise RuntimeError("audit capacity reached; operator intervention required")
            offset = 0
            while offset < len(data):
                offset += os.write(self.audit_fd, data[offset:])
            os.fsync(self.audit_fd)

    def paused(self):
        try:
            self.kill_switch.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        return True

    def check(self):
        if self.paused():
            raise PermissionError("workbench paused by operator")

    def invoke(self, name, args):
        if name not in TOOLS:
            raise ValueError("unknown tool")
        if len(json.dumps(args).encode()) > REQUEST:
            raise ValueError("request too large")
        self.audit(name, args, None, "start")
        code = -1
        try:
            self.check()
            result = getattr(self, name)(**args)
            if len(json.dumps(result).encode()) > RESPONSE:
                raise ValueError("result too large; narrow the request")
            code = result.get("exit_code", 0) if isinstance(result, dict) else 0
            return result
        finally:
            self.audit(name, args, code)

    def ws_list(self, path: str = ".", depth: int = 1) -> list:
        """List up to 4000 entries; symlinks are displayed but never followed."""
        return self.ws.entries(path, depth)

    def ws_read(self, path: str, start_line: int = 1, max_lines: int = 200) -> dict:
        """Read UTF-8 text, with one-based line numbers and a 60 KiB response cap."""
        if start_line < 1 or not 1 <= max_lines <= 2000:
            raise ValueError("invalid line range")
        lines = self.ws.read(path).splitlines(keepends=True)
        selected = "".join(lines[start_line - 1:start_line - 1 + max_lines]).encode()
        return {"text": selected[:TAIL].decode("utf-8", "replace"), "total_lines": len(lines),
                "truncated": len(selected) > TAIL or len(lines) >= start_line + max_lines}

    def ws_write(self, path: str, content: str) -> dict:
        """Atomically write UTF-8 text; creates parent directories, never follows links."""
        return self.ws.write(path, content)

    def ws_delete(self, path: str) -> dict:
        """Delete a regular file or EMPTY directory, never recursively or through links."""
        if not self.ws.parts(path):
            raise PermissionError("cannot delete workspace root")
        with self.ws.parent(path) as (fd, name):
            meta = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(meta.st_mode):
                os.rmdir(name, dir_fd=fd)
            elif stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1:
                os.unlink(name, dir_fd=fd)
            else:
                raise PermissionError("link or special file refused")
        return {"deleted": True}

    def ws_search(self, pattern: str, path: str = ".", max_results: int = 100) -> dict:
        """Bounded literal (not regex) UTF-8 search; report skipped/limited coverage."""
        if not pattern or len(pattern) > 1024 or not 1 <= max_results <= 500:
            raise ValueError("invalid search bounds")
        try:
            entries = self.ws.entries(path, 8)
        except NotADirectoryError:
            entries = [{"path": path, "kind": "file"}]
        hits, skipped, scanned = [], 0, 0
        depth_limited = any(item["kind"] == "directory" and
                            len(self.ws.parts(item["path"])) - len(self.ws.parts(path)) >= 8
                            for item in entries)
        for item in entries:
            if item["kind"] != "file":
                skipped += 1
                continue
            try:
                text = self.ws.read(item["path"])
            except (OSError, ValueError, UnicodeError):
                skipped += 1
                continue
            scanned += len(text.encode())
            if scanned > 16 * REQUEST:
                return {"matches": hits, "skipped": skipped, "limited": True}
            for number, line in enumerate(text.splitlines(), 1):
                if pattern in line:
                    hits.append({"path": item["path"], "line": number, "text": line[:500]})
                    if len(hits) >= max_results:
                        return {"matches": hits, "skipped": skipped, "limited": True}
        return {"matches": hits, "skipped": skipped, "limited": depth_limited}

    def ws_apply_patch(self, unified_diff: str) -> dict:
        """Apply strict UTF-8 unified hunks; no renames, binary patches or mode changes."""
        if len(unified_diff.encode()) > REQUEST:
            raise ValueError("patch too large")
        lines = unified_diff.splitlines(keepends=True)
        # Normalize the standard marker without changing actual file line endings.
        normalized = []
        for line in lines:
            if line.rstrip("\r\n") == "\\ No newline at end of file":
                if not normalized or normalized[-1][:1] not in (" ", "+", "-"):
                    raise ValueError("invalid newline marker")
                normalized[-1] = normalized[-1].removesuffix("\n")
            else:
                normalized.append(line)
        lines, index, edits = normalized, 0, {}
        while index < len(lines):
            if lines[index].startswith("diff --git ") or lines[index].startswith("index "):
                index += 1
                continue
            if index + 1 >= len(lines) or not lines[index].startswith("--- ") or not lines[index+1].startswith("+++ "):
                raise ValueError("expected unified file headers")
            old, new = [s[4:].rstrip("\r\n").split("\t")[0] for s in lines[index:index+2]]
            old = old[2:] if old.startswith("a/") else old
            new = new[2:] if new.startswith("b/") else new
            path = old if new == "/dev/null" else new
            if old != "/dev/null" and new != "/dev/null" and old != new:
                raise ValueError("renames are not supported")
            if not self.ws.parts(path) or path in edits:
                raise ValueError("invalid or duplicate patch path")
            if old == "/dev/null":
                with self.ws.parent(path, create=True) as (fd, name):
                    try:
                        os.stat(name, dir_fd=fd, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        raise ValueError("new file already exists")
                source = []
            else:
                source = self.ws.read(path).splitlines(keepends=True)
            index += 2
            cursor, output, hunks = 0, [], 0
            while index < len(lines) and lines[index].startswith("@@ "):
                match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n?", lines[index])
                if not match:
                    raise ValueError("invalid hunk header")
                start, count, target, added = [int(v) if v is not None else 1 for v in match.groups()]
                position = start - (1 if count else 0)
                if position < cursor or position > len(source):
                    raise ValueError("overlapping or out-of-range hunk")
                output.extend(source[cursor:position])
                if target - (1 if added else 0) != len(output):
                    raise ValueError("incorrect new-file hunk position")
                cursor, removed, inserted = position, 0, 0
                index += 1
                while index < len(lines) and (removed < count or inserted < added):
                    entry = lines[index]
                    tag, text = entry[:1], entry[1:]
                    if tag not in (" ", "+", "-"):
                        raise ValueError("invalid hunk line")
                    if tag in (" ", "-"):
                        if cursor >= len(source) or source[cursor] != text:
                            raise ValueError("patch context does not match")
                        cursor += 1
                        removed += 1
                    if tag in (" ", "+"):
                        output.append(text)
                        inserted += 1
                    index += 1
                if removed != count or inserted != added:
                    raise ValueError("hunk counts do not match")
                hunks += 1
            if not hunks:
                raise ValueError("patch must contain hunks")
            output.extend(source[cursor:])
            text = "".join(output)
            if len(text.encode()) > REQUEST or (new == "/dev/null" and text):
                raise ValueError("invalid patch result")
            edits[path] = None if new == "/dev/null" else text
        if not edits:
            raise ValueError("empty patch")
        # Validate every hunk before modifying anything; each replacement is atomic.
        for path, content in edits.items():
            self.ws_delete(path) if content is None else self.ws.write(path, content)
        return {"changed": list(edits)}

    def command(self, argv, cwd, timeout_s, env, metadata=False):
        validate_argv(argv)
        if not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s) or not 0 < timeout_s <= self.limits.max_timeout_s:
            raise ValueError("timeout must be positive and at most 900 seconds")
        fd = self.ws.open(cwd, directory=True)
        os.close(fd)
        clean = {"PATH": "/work/.venv/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/work",
                 "TMPDIR": "/tmp", "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_CONFIG_GLOBAL": "/dev/null", "CI": "1",
                 "NODE_OPTIONS": "--max-old-space-size=1024 --disable-wasm-trap-handler"}
        if env and (set(env) - {"CI", "TERM", "NO_COLOR", "PYTHONHASHSEED"}):
            raise PermissionError("environment key not allow-listed")
        if any(not isinstance(v, str) or "\0" in v or len(v) > 256 for v in (env or {}).values()):
            raise ValueError("invalid environment value")
        clean.update(env or {})
        command = ["/usr/bin/prlimit", f"--as={self.limits.memory_bytes}",
                   f"--cpu={max(1, math.ceil(timeout_s))}", f"--fsize={self.limits.file_bytes}",
                   f"--nproc={self.limits.processes}", "--nofile=128", "--core=0", "--"]
        relative = Path(*self.ws.parts(cwd))
        if self.sandbox:
            command += ["/usr/bin/bwrap", "--unshare-all", "--share-net", "--die-with-parent",
                        "--new-session", "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr"]
            for directory in ("/bin", "/sbin", "/lib", "/lib64"):
                if Path(directory).exists():
                    command += ["--ro-bind", directory, directory]
            command += ["--ro-bind", "/etc/ssl/certs", "/etc/ssl/certs", "--ro-bind",
                        "/opt/star-workbench/resolv.conf", "/etc/resolv.conf", "--proc", "/proc",
                        "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(self.ws.root), "/work"]
            if metadata:
                command += ["--bind", str(self.state / "repo.git"), "/repo-meta"]
            command += ["--chdir", str(Path("/work") / relative), "--"]
        else:
            # Only unit tests instantiate sandbox=False; the CLI never exposes this option.
            clean["PATH"] = os.defpath
            clean["HOME"] = str(self.ws.root)
        return command + argv, str(self.ws.root / relative), clean

    def start(self, argv, cwd, timeout_s, env=None, metadata=False):
        with self.repo_lock, self.lock:
            self.check()
            if sum(not j["done"].is_set() for j in self.jobs.values()) >= self.limits.jobs:
                raise RuntimeError("three jobs are already running")
            command, directory, clean = self.command(argv, cwd, timeout_s, env, metadata)
            while len(self.jobs) >= self.limits.retained_jobs:
                oldest = next((key for key, value in self.jobs.items() if value["done"].is_set()), None)
                if oldest is None:
                    raise RuntimeError("job retention capacity reached")
                self.jobs.pop(oldest)["file"].unlink(missing_ok=True)
            identifier = uuid.uuid4().hex
            log = self.state / (identifier + ".log")
            with log.open("xb") as output:
                proc = subprocess.Popen(command, cwd=directory, env=clean, stdin=subprocess.DEVNULL,
                                        stdout=output, stderr=subprocess.STDOUT, shell=False,
                                        close_fds=True, start_new_session=True)
            job = {"id": identifier, "file": log, "process": proc, "done": threading.Event(),
                   "stop": threading.Event(), "began": time.monotonic(), "state": "running"}
            self.jobs[identifier] = job
            thread = threading.Thread(target=self.watch, args=(job, timeout_s), daemon=True)
            job["thread"] = thread
            thread.start()
            return job

    @staticmethod
    def kill(job):
        try:
            os.killpg(job["process"].pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def watch(self, job, timeout_s):
        reason = "finished"
        while True:
            pid, status, usage = os.wait4(job["process"].pid, os.WNOHANG)
            if pid:
                break
            if job["stop"].is_set() or self.paused():
                reason = "stopped"
            elif time.monotonic() - job["began"] >= timeout_s:
                reason = "timed_out"
            if reason != "finished":
                self.kill(job)
            time.sleep(.02)
        self.kill(job)  # Also remove children that outlive their parent.
        code = os.waitstatus_to_exitcode(status)
        job["process"].returncode = code
        job.update(state=reason, exit_code=code, duration_s=time.monotonic() - job["began"],
                   usage={"user_s": usage.ru_utime, "system_s": usage.ru_stime,
                          "max_rss_kib": usage.ru_maxrss})
        try:
            self.audit("job_complete", {"id": job["id"]}, code)
        finally:
            job["done"].set()

    def lookup(self, identifier):
        with self.lock:
            if identifier not in self.jobs:
                raise ValueError("unknown or expired job")
            return self.jobs[identifier]

    def job_start(self, argv: list[str], cwd: str = ".", timeout_s: int = 120) -> dict:
        """Start a bounded background process; at most three processes/jobs at once."""
        job = self.start(argv, cwd, timeout_s)
        return {"id": job["id"], "state": "running"}

    def job_status(self, id: str) -> dict:
        """Return job state and, on completion, exit code and wait4 resource usage."""
        job = self.lookup(id)
        return {key: job[key] for key in ("id", "state", "exit_code", "duration_s", "usage") if key in job}

    def job_output(self, id: str, tail_bytes: int = TAIL) -> dict:
        """Read the captured output tail; report full captured size and any file limit."""
        if not 1 <= tail_bytes <= TAIL:
            raise ValueError("tail_bytes must be between 1 and 61440")
        job = self.lookup(id)
        with job["file"].open("rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            stream.seek(max(0, size - tail_bytes))
            data = stream.read(tail_bytes)
        return {"output": data.decode("utf-8", "replace"), "output_bytes": size,
                "truncated": size > tail_bytes, "file_limit_reached": size >= self.limits.file_bytes,
                "note": f"Returned last {len(data)} of {size} captured bytes; retained until eviction/restart."}

    def job_stop(self, id: str) -> dict:
        """Stop the process group and wait for its supervisor to reap it."""
        job = self.lookup(id)
        job["stop"].set()
        job["done"].wait(5)
        return self.job_status(id)

    def execute(self, argv, cwd=".", timeout_s=120, env=None, metadata=False):
        job = self.start(argv, cwd, timeout_s, env, metadata)
        job["done"].wait()
        return {**self.job_status(job["id"]), **self.job_output(job["id"])}

    def run(self, argv: list[str], cwd: str = ".", timeout_s: int = 120,
            env: dict[str, str] | None = None) -> dict:
        """Run argv without a shell, with a scrubbed environment and enforced limits."""
        return self.execute(argv, cwd, timeout_s, env)

    def git(self, arguments):
        metadata = self.state / "repo.git"
        metadata.mkdir(exist_ok=True, mode=0o700)
        directory = "/repo-meta" if self.sandbox else str(metadata)
        worktree = "/work/Star-AI" if self.sandbox else str(self.ws.root / "Star-AI")
        args = ["git", "--no-pager", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                "-c", "credential.helper=", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
                "-c", "http.followRedirects=false", "-c", "submodule.recurse=false",
                f"--git-dir={directory}", f"--work-tree={worktree}", *arguments]
        return self.execute(args, timeout_s=120, metadata=True)

    def repo_sync(self, branch: str) -> dict:
        """Fetch only the fixed public repository; refuse to overwrite a dirty worktree."""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_/-]{0,199}", branch) or "//" in branch or branch.endswith("/"):
            raise ValueError("invalid branch")
        with self.repo_lock:
            if any(not j["done"].is_set() for j in self.jobs.values()):
                raise RuntimeError("stop running jobs before syncing")
            target = self.ws.root / "Star-AI"
            if not target.exists():
                target.mkdir(mode=0o700)
            fd = self.ws.open("Star-AI", directory=True)
            os.close(fd)
            if not (self.state / "repo.git" / "HEAD").exists():
                if any(target.iterdir()):
                    raise RuntimeError("initial repository directory must be empty")
                result = self.git(["init"])
                if result["exit_code"]:
                    return result
            else:
                status = self.repo_status()
                if status["exit_code"] or status["output"].strip():
                    raise RuntimeError("worktree is dirty; sync refused")
            result = self.git(["fetch", "--no-tags", "--no-recurse-submodules", REPOSITORY,
                               "refs/heads/" + branch])
            if result["exit_code"]:
                return result
            return self.git(["checkout", "--no-guess", "-B", branch, "FETCH_HEAD"])

    def repo_status(self) -> dict:
        """Read porcelain worktree status using protected Git metadata; no credentials."""
        return self.git(["status", "--porcelain=v1", "--untracked-files=normal"])

    def repo_diff(self) -> dict:
        """Return bounded tracked-file diff; untracked files are listed by repo_status."""
        return self.git(["diff", "--no-ext-diff", "--no-textconv", "HEAD", "--"])

    def test_python(self, path_or_k: str = "") -> dict:
        """Run prepared pytest -q; accept a workspace-relative test path OR -k expression."""
        args = ["/work/.venv/bin/python", "-m", "pytest", "-q"]
        if path_or_k:
            if Path(path_or_k).is_absolute() or path_or_k.startswith("-") or len(path_or_k) > 1024:
                raise ValueError("invalid test selector")
            if "/" in path_or_k or path_or_k.endswith(".py"):
                self.ws.parts("Star-AI/" + path_or_k)
                args += [path_or_k]
            else:
                args += ["-k", path_or_k]
        return self.run(args, "Star-AI", 900, {"PYTHONHASHSEED": "0"})

    def test_frontend(self) -> dict:
        """Run npm test -- --reporter=dot against the prepared frontend install."""
        return self.run(["npm", "test", "--", "--reporter=dot"], "Star-AI/frontend", 900)

    def info(self) -> dict:
        """Report versions, free workspace disk, running jobs and enforced limits."""
        versions = {"python": sys.version.split()[0]}
        try:
            versions["mcp"] = version("mcp")
        except Exception:
            versions["mcp"] = "not installed"
        return {"versions": versions, "disk_free_bytes": shutil.disk_usage(self.ws.root).free,
                "running_jobs": [key for key, job in self.jobs.items() if not job["done"].is_set()],
                "limits": {**asdict(self.limits), "request_bytes": REQUEST, "response_bytes": RESPONSE,
                           "output_tail_bytes": TAIL}, "sandbox": self.sandbox}

    def close(self):
        for job in list(self.jobs.values()):
            job["stop"].set()
            job["thread"].join(5)
        os.close(self.audit_fd)
        os.close(self.ws.fd)


def load_token(path):
    """Read the private systemd credential copy, never an environment token."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077 or meta.st_nlink != 1 or meta.st_uid not in (0, os.geteuid()):
            raise PermissionError("credential file must be private and owned by root/service")
        token = stream.read(130).strip()
    if not re.fullmatch(rb"[a-f0-9]{64}", token):
        raise ValueError("credential must contain 32 random hex-encoded bytes")
    return token


class Gate:
    """Pure ASGI gate: authenticate BEFORE routing; never log URLs, headers or bodies."""
    def __init__(self, app, token, rate=120, delay=.2):
        self.app, self.secret = app, hashlib.sha256(token).digest()
        self.rate, self.delay, self.requests = rate, delay, deque()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        async def respond(status):
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"text/plain"), (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b"Request refused"})
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"")
        path = scope.get("path", "")
        match = re.fullmatch(r"/mcp/([^/]+)/", path)
        path_token = match.group(1).encode() if match else b""
        bearer = auth[7:] if auth.startswith(b"Bearer ") else b""
        header_ok = hmac.compare_digest(hashlib.sha256(bearer).digest(), self.secret)
        path_ok = hmac.compare_digest(hashlib.sha256(path_token).digest(), self.secret)
        valid = (path_ok and (not auth or header_ok)) if match else (path in ("/mcp", "/mcp/") and header_ok)
        now = time.monotonic()
        while self.requests and self.requests[0] < now - 60:
            self.requests.popleft()
        limited = len(self.requests) >= self.rate
        if not limited:
            self.requests.append(now)
        if not valid:
            await asyncio.sleep(self.delay)
            return await respond(404)
        if limited:
            return await respond(429)
        if b"origin" in headers:
            from urllib.parse import urlsplit
            try:
                origin = urlsplit(headers[b"origin"].decode())
                valid_origin = origin.scheme in ("https", "http") and origin.netloc.encode() == headers.get(b"host")
            except (ValueError, UnicodeError):
                valid_origin = False
            if not valid_origin:
                return await respond(403)
        if scope["method"] not in ("POST", "DELETE"):
            return await respond(405)  # Stateless JSON; no SSE stream required.
        body = bytearray()
        try:
            deadline = time.monotonic() + 10
            while True:
                message = await asyncio.wait_for(receive(), max(.001, deadline - time.monotonic()))
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > REQUEST:
                    return await respond(413)
                if not message.get("more_body"):
                    break
        except TimeoutError:
            return await respond(408)
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        safe = {**scope, "path": "/mcp/", "raw_path": b"/mcp/", "query_string": b""}
        safe["headers"] = [(k, v) for k, v in scope.get("headers", []) if k not in (b"authorization", b"referer")]
        marker = AUTHORIZED.set(True)
        try:
            await self.app(safe, replay, send)
        finally:
            AUTHORIZED.reset(marker)


def create_server(workbench, token):
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    server = FastMCP("STAR Workbench", stateless_http=True, json_response=True,
                     streamable_http_path="/mcp/", host="127.0.0.1",
                     transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    def register(name):
        method = getattr(workbench, name)
        @functools.wraps(method)
        async def call(*args, **kwargs):
            if not AUTHORIZED.get():
                raise PermissionError("authenticated HTTP request required")
            bound = inspect.signature(method).bind(*args, **kwargs)
            return await asyncio.to_thread(workbench.invoke, name, bound.arguments)
        server.add_tool(call, name=name)
    for name in TOOLS:
        register(name)
    return server, Gate(server.streamable_http_app(), token, workbench.limits.requests_per_minute)


def main():
    if os.geteuid() == 0:
        raise SystemExit("Refusing root: use the installed unprivileged service")
    if not Path("/usr/bin/bwrap").exists() or not Path("/usr/bin/prlimit").exists():
        raise SystemExit("bubblewrap and prlimit are mandatory")
    workbench = Workbench(os.environ.get("WORKBENCH_ROOT", "/work"), "/var/lib/star-workbench",
                          "/var/log/star-workbench/audit.jsonl", "/etc/star-workbench/PAUSED")
    try:
        if sys.argv[1:] == ["--prepare"]:
            steps = [lambda: workbench.repo_sync("star/next"),
                     lambda: workbench.run(["python3", "-m", "venv", "/work/.venv"], timeout_s=900),
                     lambda: workbench.run(["/work/.venv/bin/python", "-m", "pip", "install", "-r",
                                            "/work/Star-AI/requirements.txt", "pytest", "pytest-asyncio"], timeout_s=900),
                     lambda: workbench.run(["npm", "ci"], "Star-AI/frontend", 900)]
            for step in steps:
                result = step()
                if result["exit_code"]:
                    raise SystemExit("Preparation failed; inspect retained job output as operator")
            return
        credential = Path(os.environ["CREDENTIALS_DIRECTORY"]) / "token"
        token = load_token(credential)
        _, application = create_server(workbench, token)
        import uvicorn
        # SDK/ASGI error logs can include validation inputs or secret-path URLs.
        logging.disable(logging.CRITICAL)
        uvicorn.run(application, host="127.0.0.1", port=int(os.environ.get("WORKBENCH_PORT", "8765")),
                    access_log=False, log_config=None, proxy_headers=False, limit_concurrency=32)
    finally:
        workbench.close()


if __name__ == "__main__":
    main()
