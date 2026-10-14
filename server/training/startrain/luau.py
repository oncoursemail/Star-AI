"""Luau tools for the gates: compile and strict/non-strict type analysis (the knowledge service's checker) and a
sandboxed run of test scripts in the standalone Luau VM.

Everything that executes model-written code goes through `run_vm`: a fresh private directory, an empty
environment, own session, address-space / CPU / file-size / open-file limits, a wall-clock kill, and an output
cap. Nothing from a candidate ever reaches a shell. Linux only (the limits use `resource`); on other systems
the unit tests inject fakes.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

OUTPUT_CAP = 64 * 1024
PRELUDE = Path(__file__).with_name("prelude.luau")


@dataclass
class VmResult:
    rc: int | None
    stdout: str
    timed_out: bool
    seconds: float
    killed_by_limit: bool = False


def _limits(cpu_s: int, mem_bytes: int):
    def apply() -> None:    # runs in the child between fork and exec
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    return apply


def run_vm(luau_bin: str, script: str, *, wall_s: int, cpu_s: int, mem_mb: int) -> VmResult:
    workdir = Path(tempfile.mkdtemp(prefix="startrain-vm-"))
    started = time.monotonic()
    timed_out = False
    try:
        (workdir / "t.luau").write_text(script, encoding="utf-8")
        out_path = workdir / "out.txt"
        with open(out_path, "wb") as sink:
            proc = subprocess.Popen([luau_bin, "t.luau"], cwd=str(workdir), stdin=subprocess.DEVNULL, stdout=sink,
                                    stderr=subprocess.STDOUT, env={"LANG": "C.UTF-8"}, close_fds=True,
                                    start_new_session=True, shell=False,
                                    preexec_fn=_limits(cpu_s, mem_mb * 1024 * 1024))
            try:
                code: int | None = proc.wait(timeout=wall_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    proc.kill()
                proc.wait(timeout=5)
                code = None
        text = out_path.read_bytes()[:OUTPUT_CAP].decode("utf-8", "replace")
        limit_kill = code is not None and (code < 0 or code in (137, 152)) or "not enough memory" in text
        return VmResult(code, text, timed_out, round(time.monotonic() - started, 3), bool(limit_kill))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class LuauTools:
    """Compile + analyse (via starkb.luaucheck of the deployed knowledge service) and run test scripts."""

    def __init__(self, settings):
        self.s = settings
        self.prelude = PRELUDE.read_text(encoding="utf-8").replace("\r\n", "\n")
        path = str(Path(settings.kb_app))
        if path not in sys.path:
            sys.path.insert(0, path)
        self._luaucheck = importlib.import_module("starkb.luaucheck")
        self._db = None
        try:
            import sqlite3
            self._db = sqlite3.connect(f"file:{settings.kb_db}?mode=ro", uri=True, check_same_thread=False)
        except Exception:
            self._db = None
        if not self._luaucheck.available():
            raise RuntimeError("luau-compile / luau-analyze are not installed for the knowledge service")
        if not Path(settings.luau_vm).is_file():
            raise RuntimeError("the standalone Luau VM is missing: " + settings.luau_vm)
        self.versions = {"analyzer": self._luaucheck.tool_version()}

    def _known_type(self, name: str) -> bool:
        return self._db is not None and self._luaucheck.is_engine_type(self._db, name)

    def analyse(self, code: str, mode: str) -> dict:
        """mode "strict": the code is checked as written (it must start with --!strict).
        mode "nonstrict": Roblox-flavoured code, checked non-strict with engine type names accepted."""
        if mode == "strict":
            return self._luaucheck.check(code)
        return self._luaucheck.check(code, mode="nonstrict", known_type=self._known_type)

    def run_script(self, script: str, *, mutant: bool = False) -> VmResult:
        s = self.s
        return run_vm(s.luau_vm, script, wall_s=s.mutant_wall_s if mutant else s.vm_wall_s,
                      cpu_s=s.mutant_cpu_s if mutant else s.vm_cpu_s, mem_mb=s.vm_mem_mb)
