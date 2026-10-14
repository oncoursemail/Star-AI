"""Run model-written Luau on the STAR server, never on this PC.

The unit tests of an evaluation task execute the model's code, so they run inside the server's LXD
container as the unprivileged user `star`, in the standalone Luau VM (no `io`, no `os.execute`, no
network library) under `prlimit` (address space, CPU seconds, file size, open files) and a hard
wall-clock `timeout`, in a fresh empty directory that is deleted afterwards.

The PC only sends a script over SSH key authentication and reads the printed result lines. Nothing is
written outside the container's /tmp, and the host is only used to reach the container.

The SSH target (user@address) is operator configuration (environment variable STAR_EVAL_SSH or a
command-line option) and is never stored in the repository or in result files.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import re
import subprocess
from time import monotonic

LUAU_BIN = "/opt/star/bench/tools/luau/build/release/luau"
LOCK_DIR = "/opt/star/lock"
OUTPUT_CAP = 65_536
_SSH_TARGET = re.compile(r"^[A-Za-z0-9._-]{1,32}@[A-Za-z0-9._:-]{1,80}$")
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
_PATH = re.compile(r"^/[A-Za-z0-9._/-]{1,200}$")


@dataclass
class SandboxResult:
    rc: int = -1
    stdout: str = ""
    timed_out: bool = False
    seconds: float = 0.0
    error: str = ""          # the sandbox itself could not be reached or started


def build_remote_script(source: str, *, mem_mb: int = 256, cpu_s: int = 8, wall_s: int = 15,
                        luau: str = LUAU_BIN) -> str:
    """The bash script that runs `source` under limits. Pure, so its limits can be unit-tested."""
    for value in (mem_mb, cpu_s, wall_s):
        if type(value) is not int or not 1 <= value <= 4096:
            raise ValueError("sandbox limits must be small positive integers")
    if not _PATH.fullmatch(luau):
        raise ValueError("invalid Luau path")
    payload = base64.b64encode(source.encode("utf-8")).decode("ascii")
    return "\n".join([
        "D=$(mktemp -d /tmp/starev.XXXXXXXX) || exit 97",
        'cd "$D" || exit 97',
        "trap 'cd /; rm -rf \"$D\"' EXIT",
        "base64 -d > t.luau <<'STAR_EOF'",
        payload,
        "STAR_EOF",
        # No --nproc: user `star` already runs the model servers and a low limit makes fork fail.
        f"prlimit --as={mem_mb * 1024 * 1024} --cpu={cpu_s} --fsize=1048576 --nofile=32 --core=0 -- "
        f"timeout -s KILL {wall_s} {luau} t.luau 2>&1 | head -c {OUTPUT_CAP}",
        'echo "@@RC ${PIPESTATUS[0]}"',   # the Luau process' own status (137 = killed by a limit)
        "",
    ])


def parse_status(stdout: str) -> tuple[int, str]:
    """(exit status, output without the status line)."""
    lines = stdout.rstrip("\n").split("\n")
    if lines and lines[-1].startswith("@@RC "):
        try:
            return int(lines[-1][5:]), "\n".join(lines[:-1])
        except ValueError:
            pass
    return -1, stdout


class ContainerSandbox:
    """SSH to the host, `lxc exec` into the container, run as user `star`."""

    def __init__(self, target: str, *, container: str = "starai", user: str = "star",
                 mem_mb: int = 256, cpu_s: int = 8, wall_s: int = 15, runner=subprocess.run,
                 ssh: str = "ssh"):
        if not _SSH_TARGET.fullmatch(target or ""):
            raise ValueError("SSH target must look like user@address")
        if not _NAME.fullmatch(container) or not _NAME.fullmatch(user):
            raise ValueError("invalid container or user name")
        self._argv = [ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", target,
                      f"lxc exec {container} -- runuser -u {user} -- bash -s"]
        self.limits = {"mem_mb": mem_mb, "cpu_s": cpu_s, "wall_s": wall_s}
        self._runner = runner

    def _exec(self, script: str, timeout: float):
        return self._runner(self._argv, input=script.encode("utf-8"), capture_output=True, timeout=timeout)

    def run(self, source: str) -> SandboxResult:
        started = monotonic()
        try:
            done = self._exec(build_remote_script(source, **self.limits),
                              self.limits["wall_s"] + 40)
        except subprocess.TimeoutExpired:
            return SandboxResult(error="ssh to the sandbox timed out", seconds=monotonic() - started)
        except OSError as exc:
            return SandboxResult(error="could not start ssh (" + type(exc).__name__ + ")", seconds=monotonic() - started)
        text = done.stdout.decode("utf-8", "replace")
        if done.returncode != 0 and "@@RC" not in text:
            return SandboxResult(error=f"ssh/lxc failed (status {done.returncode})", seconds=monotonic() - started)
        rc, output = parse_status(text)
        return SandboxResult(rc=rc, stdout=output, timed_out=rc in (124, 137, 9) and "@@DONE" not in output,
                             seconds=round(monotonic() - started, 2))

    def lock_present(self, path: str = LOCK_DIR) -> bool | None:
        """True when the server lock ("quiet please") exists; None when it could not be asked."""
        if not _PATH.fullmatch(path):
            raise ValueError("invalid lock path")
        try:
            done = self._exec(f"test -e {path} && echo LOCKED || echo FREE\n", 30)
        except (subprocess.TimeoutExpired, OSError):
            return None
        out = done.stdout.decode("utf-8", "replace")
        if done.returncode != 0 or ("LOCKED" not in out and "FREE" not in out):
            return None
        return "LOCKED" in out
