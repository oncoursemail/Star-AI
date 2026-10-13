"""Client of the STAR resource planner (star/resource_planner_service.py). Standard library only, no STAR imports,
so night school, the knowledge jobs and the PC's training scripts can all use it.

Fail-safe contract: every call returns a Grant. When the planner is not configured, not reachable, slow, or has no
fresh data, the action is "fallback" and the caller does exactly what it did before the planner existed (its own
idle gate, the quiet lock, the RAM floor). After a failed call the client stays quiet for `down_for` seconds, so a
dead planner costs one short timeout, not one per request.

Where the planner is: `url=` argument, else $STAR_PLANNER_URL, else the one line in ~/.star/planner_url (operator
configuration; never in the repository). The key: `key=`/`key_file=`, else $STAR_PLANNER_KEY_FILE, else
~/.star/server_api_key (the brain key). The key is kept in memory and never printed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable
import urllib.error
import urllib.request


@dataclass
class Grant:
    action: str                      # run | wait | yield | fallback | refuse
    reason: str = ""
    lease_id: str = ""
    duty: float = 1.0
    retry_after_s: float = 10.0
    job_class: str = ""
    request: dict = field(default_factory=dict)

    @property
    def go(self) -> bool:
        """True when the job may work now: admitted by the planner, or the planner is out (old rules apply)."""
        return self.action in ("run", "fallback")

    @property
    def planned(self) -> bool:
        return self.action == "run" and bool(self.lease_id)


def _first_line(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.strip().startswith("#"):
                return line.strip()
    except OSError:
        pass
    return ""


def configured_url() -> str:
    url = os.environ.get("STAR_PLANNER_URL", "")
    if url.lower() in ("off", "0", "none"):
        return ""
    return url or _first_line(Path.home() / ".star" / "planner_url")


class PlannerClient:
    def __init__(self, url: str | None = None, *, key: str | None = None, key_file: str | None = None,
                 timeout: float = 2.0, down_for: float = 30.0, snapshot: Callable[[], dict] | None = None,
                 opener=None, clock=time.monotonic):
        self.url = (configured_url() if url is None else url).rstrip("/")
        if key is None:
            path = key_file or os.environ.get("STAR_PLANNER_KEY_FILE") or str(Path.home() / ".star" / "server_api_key")
            key = _first_line(Path(os.path.expanduser(path)))
        self._key = key
        self.timeout, self.down_for = timeout, down_for
        self.snapshot = snapshot                  # machines without their own reporter send a snapshot each time
        self._open = opener or urllib.request.urlopen
        self._clock = clock
        self._down_until = -1e18
        self.last_error = ""

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def _call(self, method: str, path: str, body: dict | None = None) -> dict | None:
        if not self.url or self._clock() < self._down_until:
            return None
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        if self._key:
            request.add_header("Authorization", "Bearer " + self._key)
        try:
            with self._open(request, timeout=self.timeout) as reply:
                answer = json.loads(reply.read(1 << 20).decode("utf-8", "replace"))
            return answer if isinstance(answer, dict) else None
        except (OSError, ValueError, urllib.error.URLError) as exc:
            self.last_error = type(exc).__name__           # never the text: it can hold the address
            self._down_until = self._clock() + self.down_for
            return None

    def _with_snapshot(self, body: dict) -> dict:
        if self.snapshot is not None:
            try:
                body["snapshot"] = self.snapshot()
            except Exception:          # a failing probe must not break the job; the planner then has no fresh data
                pass
        return body

    @staticmethod
    def _grant(answer: dict | None, job_class: str, request: dict, fallback_reason: str) -> Grant:
        if answer is None or answer.get("action") not in ("run", "wait", "yield", "fallback", "refuse"):
            return Grant("fallback", fallback_reason, job_class=job_class, request=request)
        return Grant(answer["action"], str(answer.get("reason", ""))[:200], str(answer.get("lease_id") or ""),
                     float(answer.get("duty", 1.0) or 1.0), float(answer.get("retry_after_s", 10) or 10),
                     job_class, request)

    def admit(self, job_class: str, holder: str, job_id: str, **extra) -> Grant:
        request = {"job_class": job_class, "holder": holder, "job_id": job_id, **extra}
        answer = self._call("POST", "/v1/admit", self._with_snapshot(dict(request)))
        return self._grant(answer, job_class, request, "planner unreachable" if self.url else "planner not configured")

    def renew(self, grant: Grant) -> Grant:
        if not grant.planned:
            return grant if grant.action == "fallback" else Grant("refuse", "no lease", job_class=grant.job_class,
                                                                  request=grant.request)
        answer = self._call("POST", "/v1/renew", self._with_snapshot({"lease_id": grant.lease_id}))
        new = self._grant(answer, grant.job_class, grant.request, "planner unreachable")
        if new.action in ("run", "fallback") and not new.lease_id:
            new.lease_id = grant.lease_id          # a fallback keeps the lease: the planner may come back
        return new

    def release(self, grant: Grant | None) -> None:
        if grant is not None and grant.lease_id:
            self._call("POST", "/v1/release", {"lease_id": grant.lease_id})
            grant.lease_id = ""

    def interactive(self, machine: str = "brain1", source: str = "") -> None:
        self._call("POST", "/v1/interactive", {"machine": machine, "source": source})

    def status(self) -> dict | None:
        return self._call("GET", "/v1/status")

    def wait_for(self, job_class: str, holder: str, job_id: str, *, stop=lambda: False, max_wait: float | None = None,
                 sleep=time.sleep, log=None, **extra) -> Grant:
        """Ask until the answer is run or fallback (or stop/max_wait: then the last "wait" grant is returned)."""
        waited, said = 0.0, ""
        while True:
            grant = self.admit(job_class, holder, job_id, **extra)
            if grant.go or grant.action == "refuse" or stop():
                return grant
            if log and grant.reason != said:
                log(f"planner: {job_class} waits ({grant.reason})")
                said = grant.reason
            pause = max(1.0, min(60.0, grant.retry_after_s))
            if max_wait is not None and waited + pause > max_wait:
                return grant
            sleep(pause)
            waited += pause


class Pacer:
    """Keeps a lease for a long batch job and paces it: `step(work_seconds)` after each unit of work renews the lease
    (re-admitting when it was lost) and sleeps so the job keeps the machine busy only `duty` of the time. Returns False
    when the job should stop for now (yield); the caller then calls `wait()` before going on."""

    def __init__(self, client: PlannerClient, job_class: str, holder: str, job_id: str, *, sleep=time.sleep,
                 log=None, stop=lambda: False, **extra):
        self.client, self.job_class, self.holder, self.job_id = client, job_class, holder, job_id
        self.extra, self._sleep, self._log, self._stop = extra, sleep, log, stop
        self.grant: Grant | None = None
        self.paused_s = 0.0

    def wait(self, max_wait: float | None = None) -> Grant:
        started = time.monotonic()
        self.grant = self.client.wait_for(self.job_class, self.holder, self.job_id, stop=self._stop,
                                          max_wait=max_wait, sleep=self._sleep, log=self._log, **self.extra)
        self.paused_s += time.monotonic() - started
        return self.grant

    def step(self, work_seconds: float, base_duty: float = 1.0) -> bool:
        if self.grant is None:
            self.wait()
        grant = self.client.renew(self.grant)
        if grant.action == "refuse":                      # lease lost: ask again
            grant = self.client.admit(self.job_class, self.holder, self.job_id, **self.extra)
        self.grant = grant
        if grant.action in ("yield", "wait"):
            if self._log:
                self._log(f"planner: {self.job_class} pauses ({grant.reason})")
            self.grant = None
            return False
        duty = min(base_duty, grant.duty if grant.action == "run" else 1.0)
        if 0 < duty < 1 and work_seconds > 0:
            pause = work_seconds * (1 / duty - 1)
            self._sleep(pause)
            self.paused_s += pause
        return True

    def close(self) -> None:
        self.client.release(self.grant)
        self.grant = None


def format_status(data: dict) -> str:
    """Per-machine load and the queue, for `star planner` and the CLI."""
    lines = []
    for name, m in sorted((data.get("machines") or {}).items()):
        busy = {model: sum(1 for s in slots if s.get("processing")) for model, slots in (m.get("models") or {}).items()}
        slots = ", ".join(f"{model} {busy[model]}/{len(s)}" for model, s in sorted((m.get("models") or {}).items())
                          if model in busy)
        text = (f"{name:<7} cpu {m.get('cpu_busy', 0):>4.0%}  RAM free {m.get('mem_available_mib', 0) / 1024:5.1f}/"
                f"{m.get('mem_total_mib', 0) / 1024:.0f} GiB  data {m.get('age_s', 0):.0f}s old")
        if m.get("vram_total_mib"):
            text += f"  GPU {m.get('gpu_util') or 0:.0%} VRAM {m.get('vram_used_mib', 0)}/{m['vram_total_mib']} MiB"
        if m.get("owner_busy"):
            text += f"  OWNER BUSY: {m['owner_busy']}"
        if m.get("lock_owner"):
            text += f"  quiet lock: {m['lock_owner']}"
        if m.get("chat_active"):
            text += f"  CHAT ACTIVE ({m.get('chat_reason', '')})"
        lines.append(text)
        if slots:
            lines.append(f"        slots busy: {slots}")
        if m.get("studios"):
            lines.append(f"        Studio attached: {len(m['studios'])}")
    leases = data.get("leases") or []
    lines.append(f"running jobs: {len(leases)}")
    for lease in leases:
        lines.append(f"  {lease['job_class']:<12} {lease['holder']:<14} on {lease['machine']:<6} "
                     f"{lease['age_s']:>6.0f}s  duty {lease.get('duty', 1):.2f}")
    waiting = data.get("waiting") or []
    lines.append(f"queue: {len(waiting)}")
    for p in waiting:
        lines.append(f"  {p['job_class']:<12} {p['holder']:<14} for {p['machine']} (asked {p['s_ago']:.0f}s ago)")
    averages = data.get("cpu_average") or {}
    if averages.get("15min"):
        lines.append("cpu average 15 min: " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(averages["15min"].items())))
    if averages.get("60min"):
        lines.append("cpu average 60 min: " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(averages["60min"].items())))
    counters = data.get("counters") or {}
    if counters:
        lines.append("since start: " + ", ".join(f"{k} {v}" for k, v in counters.items()))
    return "\n".join(lines)


def run_window(client: PlannerClient, holder: str, command: list[str], *, minutes: float = 10.0,
               max_wait: float = 1800.0, log=print) -> int:
    """Run `command` inside an exclusive timing window on brain 1 (the planner sets the quiet lock). Planner out:
    the command runs anyway and the caller is told to take the lock by hand (`star lock take`)."""
    grant = client.wait_for("eval-timing", holder, "window", max_wait=max_wait, log=log,
                            ttl_s=int(max(60, min(600, minutes * 60))))
    if grant.action == "fallback":
        log(f"planner: {grant.reason}; take the quiet lock yourself (star lock take) - running without a window")
    elif not grant.go:
        log(f"planner: no timing window ({grant.reason})")
        return 3
    else:
        log("planner: timing window open (quiet lock set)")
    process = subprocess.Popen(command)
    deadline = time.monotonic() + minutes * 60
    try:
        while process.poll() is None:
            time.sleep(min(20.0, max(1.0, grant.retry_after_s / 2)) if grant.planned else 2.0)
            if grant.planned:
                grant = client.renew(grant)
            if time.monotonic() > deadline:
                log("planner: window time is up, stopping the command")
                process.terminate()
        return process.wait()
    finally:
        client.release(grant)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.planner_client")
    parser.add_argument("--url", default=None)
    parser.add_argument("--key-file", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    w = sub.add_parser("window", help="run a command inside an exclusive timing window on brain 1")
    w.add_argument("--holder", required=True)
    w.add_argument("--minutes", type=float, default=10.0)
    w.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    client = PlannerClient(url=args.url, key_file=args.key_file, timeout=5.0)
    if args.cmd == "status":
        data = client.status()
        if data is None:
            print("planner: not reachable" if client.enabled else "planner: not configured (STAR_PLANNER_URL)")
            return 1
        print(json.dumps(data, indent=1) if args.json else format_status(data))
        return 0
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("window needs a command after --")
    return run_window(client, args.holder, command, minutes=args.minutes)


if __name__ == "__main__":
    sys.exit(main())
