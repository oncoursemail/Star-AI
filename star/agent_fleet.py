"""Opt-in agent fleet: resource-sized worker slots, one git worktree per task, independent test receipts.

Off by default (set STAR_AGENT_FLEET=1 or pass enabled=True). Never merges, pushes or publishes: a task that passes its
own independent test run only yields a *proposal* (branch + diffstat) for the owner to review.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from star import resource_probes as probes

PROTECTED_MARKERS = ("paintball", os.path.join("appdata", "roaming", "star").lower())
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


def fleet_enabled(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return enabled
    return os.environ.get("STAR_AGENT_FLEET", "") == "1"


def sample_resources(interval: float = 0.2) -> dict:
    """Live total/available RAM (MiB), CPU busy share and logical CPUs. Missing probes give None, never a guess."""
    mem = probes.windows_memory() or probes.proc_meminfo()
    if os.name == "nt":
        read = probes.windows_cpu_times
    else:
        read = probes.proc_cpu_times
    before = read()
    time.sleep(interval)
    busy = probes.cpu_busy_share(before, read())
    return {"ram_total_mib": mem[0] if mem else None, "ram_free_mib": mem[1] if mem else None,
            "cpu_busy": busy, "cpus": os.cpu_count() or 1}


def plan_slots(res: dict, *, mib_per_agent: int = 2048, reserve_mib: int = 4096, max_busy: float = 0.85,
               cap: int = 4) -> tuple[int, str]:
    """Number of worker slots the live resources allow, plus an honest reason when it is 0 or reduced."""
    free, busy = res.get("ram_free_mib"), res.get("cpu_busy")
    if free is None or busy is None:
        return 0, "blocked: RAM or CPU could not be measured"
    if busy > max_busy:
        return 0, f"waiting: CPU busy {busy:.0%} > {max_busy:.0%}"
    by_ram = max(0, (free - reserve_mib) // mib_per_agent)
    by_cpu = max(0, int(res["cpus"] * (1 - busy)) // 2)
    n = min(by_ram, by_cpu, cap)
    if n == 0:
        return 0, f"waiting: free RAM {free} MiB, {res['cpus']} CPUs at {busy:.0%} leave no slot"
    why = "" if n == cap else f"limited by {'RAM' if by_ram <= by_cpu else 'CPU'}"
    return n, why


@dataclass
class FleetTask:
    task_id: str
    agent_cmd: list[str]   # the CLI agent, run with cwd = its worktree
    test_cmd: list[str]    # run by the fleet itself after the agent exits; the agent is never trusted on tests
    enabled: bool = True


@dataclass
class Receipt:
    task_id: str
    status: str            # disabled | cancelled | agent_failed | no_changes | tests_failed | proposed | error
    branch: str = ""
    worktree: str = ""
    detail: str = ""
    test_rc: int | None = None
    diffstat: str = ""
    test_tail: str = ""
    seconds: float = 0.0


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120)


def is_protected(path: Path) -> bool:
    low = str(path.resolve()).lower()
    return any(m in low for m in PROTECTED_MARKERS)


def _run(cmd: list[str], cwd: Path, timeout: float, cancel: threading.Event) -> tuple[int | None, str]:
    """Run cmd (no shell); poll so cancel and timeout kill the process. rc None = killed."""
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            errors="replace")
    out: list[str] = []
    reader = threading.Thread(target=lambda: out.append(proc.stdout.read()), daemon=True)
    reader.start()
    end = time.monotonic() + timeout
    while proc.poll() is None:
        if cancel.is_set() or time.monotonic() > end:
            proc.kill()
            proc.wait()
            reader.join(2)
            return None, "cancelled" if cancel.is_set() else "timeout"
        time.sleep(0.05)
    reader.join(5)
    return proc.returncode, "".join(out)


def run_task(repo: Path, base_ref: str, task: FleetTask, worktrees: Path, cancel: threading.Event,
             timeout: float = 1800) -> Receipt:
    t0 = time.monotonic()
    rec = Receipt(task.task_id, "error")
    if not task.enabled:
        rec.status = "disabled"
        return rec
    if cancel.is_set():
        rec.status = "cancelled"
        return rec
    if not _ID.match(task.task_id):
        rec.detail = "bad task id"
        return rec
    if not task.test_cmd:
        rec.detail = "no test command: a pass cannot be proven"
        return rec
    rec.branch = f"star/fleet-{task.task_id}"
    wt = worktrees / task.task_id
    rec.worktree = str(wt)
    try:
        add = _git(repo, "worktree", "add", "-b", rec.branch, str(wt), base_ref)
        if add.returncode:
            rec.detail = add.stderr.strip()[-300:]
            return rec
        rc, out = _run(task.agent_cmd, wt, timeout, cancel)
        if rc is None:
            rec.status, rec.detail = "cancelled", out
            return rec
        if rc != 0:
            rec.status, rec.detail = "agent_failed", f"agent exit {rc}: {out[-300:]}"
            return rec
        _git(wt, "add", "-A")
        stat = _git(wt, "diff", "--cached", "--stat").stdout.strip()
        if not stat:
            rec.status = "no_changes"
            return rec
        rec.diffstat = stat
        trc, tout = _run(task.test_cmd, wt, timeout, cancel)
        rec.test_rc, rec.test_tail = trc, tout[-600:]
        if trc is None:
            rec.status, rec.detail = "cancelled", tout
        elif trc != 0:
            rec.status = "tests_failed"
        else:
            rec.status = "proposed"
            rec.detail = "review the diff; the fleet never merges"
    except Exception as exc:  # a crashed worker must not take the fleet down
        rec.status, rec.detail = "error", f"{type(exc).__name__}: {exc}"[:300]
    finally:
        rec.seconds = round(time.monotonic() - t0, 2)
    return rec


@dataclass
class FleetResult:
    slots: int
    reason: str
    receipts: list[Receipt] = field(default_factory=list)


def run_fleet(repo: str | Path, tasks: list[FleetTask], *, base_ref: str = "HEAD", worktrees: str | Path | None = None,
              enabled: bool | None = None, resources: dict | None = None, cancel: threading.Event | None = None,
              timeout: float = 1800, **plan_kw) -> FleetResult:
    """Run every enabled task in its own worktree, at most as many at once as live resources allow."""
    if not fleet_enabled(enabled):
        return FleetResult(0, "disabled: set STAR_AGENT_FLEET=1 to opt in")
    repo = Path(repo)
    if is_protected(repo):
        return FleetResult(0, "refused: protected project")
    n, reason = plan_slots(resources or sample_resources(), **plan_kw)
    if n == 0:
        return FleetResult(0, reason)
    wts = Path(worktrees) if worktrees else repo.parent / (repo.name + "-fleet")
    wts.mkdir(parents=True, exist_ok=True)
    cancel = cancel or threading.Event()
    with ThreadPoolExecutor(max_workers=n) as pool:
        recs = list(pool.map(lambda t: run_task(repo, base_ref, t, wts, cancel, timeout), tasks))
    return FleetResult(n, reason, recs)
