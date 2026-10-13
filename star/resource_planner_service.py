"""STAR resource planner: a small admission service that knows each machine's live load and hands out leases.

Runs on brain 1 (container starai, unit star-planner, port 8098). Every two seconds it probes its own machine
(/proc, the quiet lock, the brain's /slots and /metrics of LOADED models only) and notices chat: a busy slot that no
lease explains, or a request queued in front of a model. Brain 2 reports its own snapshot (`agent` mode, every
10 s); jobs on the owner's PC send theirs with each request. The decisions are the pure functions in
star/agent_resource_planner.py (PR #206, extended): interactive chat first, timing windows exclusive (the service
sets the quiet lock /opt/star/lock for the window and removes only its own lock), night school yields to chat, the
re-index slows down while chat is active, Studio tests on brain 2 (test-farm preview, PR #207), GPU training on the PC
only while the owner is not gaming and above his free-RAM floor.

Fail-safe by design: the service never starts or stops a job. Clients (star/planner_client.py) ask; when the service
cannot be reached or has no fresh data they get "fallback" and do exactly what they did before the planner existed.

HTTP (JSON): GET /health; GET /v1/status (no key needed from the same machine, else the brain key);
POST /v1/admit, /v1/renew, /v1/release, /v1/report, /v1/interactive (brain key). Nothing secret is logged.
"""
from __future__ import annotations

import argparse
from collections import deque
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.request

from .agent_resource_planner import (DEFAULT_CLASSES, Decision, JobRequest, Lease, LivePolicy, MachineSnapshot,
                                     Pending, chat_signs, decide_admit, decide_admit_any, decide_renew,
                                     planner_lock_owner,
                                     resolve_studio)
from . import resource_probes as probes

DEFAULT_PORT = 8098
MAX_BODY = 64 * 1024
HISTORY_EVERY_S = 30.0
HISTORY_LEN = 480            # 4 hours of 30-second samples


class Planner:
    """Leases, snapshots and chat signs. Thread-safe; `clock` is wall-clock seconds (tests hand in a fake)."""

    def __init__(self, *, local_machine: str = "brain1", lock_dir: str = probes.LOCK_DIR, classes=DEFAULT_CLASSES,
                 policy: LivePolicy = LivePolicy(), clock=time.time, log=print):
        self.local_machine, self.lock_dir = local_machine, lock_dir
        self.classes, self.policy, self.clock, self.log = classes, policy, clock, log
        self.snapshots: dict[str, MachineSnapshot] = {}
        self.leases: dict[str, Lease] = {}
        self.pending: list[Pending] = []
        self.last_chat: dict[str, float] = {}
        self.chat_reason: dict[str, str] = {}
        self.history: deque = deque(maxlen=HISTORY_LEN)
        self.counters = {"admitted": 0, "waited": 0, "yielded": 0, "fallback": 0, "chat_signs": 0}
        self._history_at = 0.0
        self._lock = threading.RLock()

    # --- observations --------------------------------------------------------------------------------------------
    def observe(self, data: dict, *, remote: bool = False) -> MachineSnapshot:
        """Take a snapshot. `remote` ones (sent by clients and reporters) may never replace this machine's own
        probes."""
        snap = MachineSnapshot.from_dict(data)
        if remote and snap.machine == self.local_machine:
            raise ValueError("a report may not replace the planner's own machine")
        with self._lock:
            before = self.snapshots.get(snap.machine)
            if before is not None and snap.taken_at < before.taken_at:
                return before                         # an old report arriving late never replaces a newer one
            signs = chat_signs(before, snap, list(self.leases.values()), self.policy)
            if signs:
                self._chat(snap.machine, signs[0], snap.taken_at)
            self.snapshots[snap.machine] = snap
            self._expire()
            self._sample()
        return snap

    def interactive(self, machine: str, source: str = "") -> None:
        with self._lock:
            self._chat(machine, f"chat client {source}".strip(), self.clock())

    def _chat(self, machine: str, reason: str, at: float) -> None:
        if machine not in self.last_chat or at - self.last_chat[machine] > 5:
            self.counters["chat_signs"] += 1
        self.last_chat[machine] = max(at, self.last_chat.get(machine, 0.0))
        self.chat_reason[machine] = reason[:120]

    # --- leases --------------------------------------------------------------------------------------------------
    def admit(self, payload: dict) -> dict:
        req = JobRequest(**{k: payload[k] for k in JobRequest.__dataclass_fields__ if k in payload})
        with self._lock:
            if isinstance(payload.get("snapshot"), dict):
                self.observe(payload["snapshot"], remote=True)
            self._expire()
            now = self.clock()
            cls = self.classes.get(req.job_class)
            for lease in self.leases.values():        # the same job asking again keeps its lease
                if lease.holder == req.holder and lease.job_id == req.job_id and lease.job_class == req.job_class:
                    return self._answer(Decision("run", "already admitted", duty=lease.duty), lease)
            snap = self.snapshots.get(cls.machine) if cls else None
            if cls is not None and cls.capability == "studio":
                req = resolve_studio(req, snap, list(self.leases.values()))
            machine = cls.machine if cls else ""
            if cls is not None and cls.machines:
                decision, machine = decide_admit_any(req, self.snapshots, list(self.leases.values()), now=now,
                                                     last_chat=self.last_chat, pending=self.pending,
                                                     classes=self.classes, policy=self.policy)
            else:
                decision = decide_admit(req, snap, list(self.leases.values()), now=now, last_chat=self.last_chat,
                                        pending=self.pending, classes=self.classes, policy=self.policy)
            lease = None
            if decision.action == "run" and cls is not None:
                if cls.exclusive and not self._take_lock(req.holder):
                    decision = Decision("wait", "could not set the quiet lock", retry_after_s=15)
                else:
                    ttl = min(cls.max_ttl_s, req.ttl_s or cls.max_ttl_s)
                    lease = Lease(secrets.token_hex(8), cls.name, machine or cls.machine, req.holder, req.job_id,
                                  cls.capability,
                                  now, now + ttl, req.memory_mib or cls.memory_mib, cls.cpu_threads, slot=req.slot,
                                  studio_id=req.studio_id, vram_mib=req.vram_mib or cls.vram_mib, duty=decision.duty)
                    self.leases[lease.lease_id] = lease
                    self.pending = [p for p in self.pending if not (p.holder == req.holder
                                                                    and p.job_class == req.job_class)]
                    self.counters["admitted"] += 1
                    self.log(f"admit {cls.name} for {req.holder} on {cls.machine} ({decision.reason})")
            if decision.action == "wait" and cls is not None:
                self.pending = [p for p in self.pending if not (p.holder == req.holder and p.job_class == cls.name)]
                self.pending.append(Pending(cls.name, cls.machine, cls.capability, cls.priority, req.holder, now))
                self.pending = self.pending[-32:]
                self.counters["waited"] += 1
            if decision.action == "fallback":
                self.counters["fallback"] += 1
            return self._answer(decision, lease)

    def renew(self, payload: dict) -> dict:
        with self._lock:
            if isinstance(payload.get("snapshot"), dict):
                self.observe(payload["snapshot"], remote=True)
            self._expire()
            lease = self.leases.get(str(payload.get("lease_id", "")))
            if lease is None:
                return self._answer(Decision("refuse", "lease expired or unknown", retry_after_s=1), None)
            cls = self.classes[lease.job_class]
            now = self.clock()
            decision = decide_renew(lease, self.snapshots.get(lease.machine), list(self.leases.values()), now=now,
                                    last_chat=self.last_chat, pending=self.pending, classes=self.classes,
                                    policy=self.policy)
            if decision.action == "run":
                lease.expires_at = now + cls.max_ttl_s
                lease.duty = decision.duty
            elif decision.action == "yield":
                self._drop(lease, "yield: " + decision.reason)
                self.counters["yielded"] += 1
            elif decision.action == "fallback":
                lease.expires_at = now + cls.max_ttl_s          # keep it: the job goes on under its own rules
            return self._answer(decision, lease if decision.action in ("run", "fallback") else None)

    def release(self, payload: dict) -> dict:
        with self._lock:
            lease = self.leases.get(str(payload.get("lease_id", "")))
            if lease is not None:
                self._drop(lease, "released")
            return {"ok": True, "released": lease is not None}

    def _drop(self, lease: Lease, why: str) -> None:
        self.leases.pop(lease.lease_id, None)
        if self.classes.get(lease.job_class) and self.classes[lease.job_class].exclusive:
            self._free_lock(lease.holder)
        self.log(f"end {lease.job_class} of {lease.holder} ({why})")

    def _expire(self) -> None:
        now = self.clock()
        for lease in [l for l in self.leases.values() if l.expires_at < now]:
            self._drop(lease, "expired")
        self.pending = [p for p in self.pending if now - p.at < max(self.policy.exclusive_pending_s,
                                                                    self.policy.preempt_window_s)]
        # A planner lock with no window behind it (service restarted, client vanished) is removed after 60 s.
        owner = probes.lock_owner(self.lock_dir, clock=self.clock)
        if owner.startswith("planner-") and not any(
                planner_lock_owner(l.holder) == owner for l in self.leases.values()):
            try:
                age = now - (Path(self.lock_dir) / "owner").stat().st_mtime
            except OSError:
                age = 0
            if age > 60:
                self._free_lock_named(owner)

    # --- the quiet lock for timing windows ---------------------------------------------------------------------
    def _take_lock(self, holder: str) -> bool:
        owner = planner_lock_owner(holder)
        current = probes.lock_owner(self.lock_dir, clock=self.clock)
        if current == owner:
            return True
        if current:
            return False
        base = Path(self.lock_dir)
        try:
            if base.exists():           # a stale lock: the same rule as `star lock take` (replace after 15 min)
                (base / "owner").unlink(missing_ok=True)
                base.rmdir()
            base.mkdir()
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))
            (base / "owner").write_text(f"{owner} {stamp}\n", encoding="utf-8")
        except OSError:
            return False
        self.log(f"quiet lock set for {owner}")
        return True

    def _free_lock(self, holder: str) -> None:
        self._free_lock_named(planner_lock_owner(holder))

    def _free_lock_named(self, owner: str) -> None:
        base = Path(self.lock_dir)
        try:
            words = (base / "owner").read_text(encoding="utf-8").split()
            if words and words[0] == owner:
                (base / "owner").unlink()
                base.rmdir()
                self.log(f"quiet lock of {owner} removed")
        except OSError:
            pass

    # --- answers and status --------------------------------------------------------------------------------------
    def _answer(self, decision: Decision, lease: Lease | None) -> dict:
        out = {"action": decision.action, "reason": decision.reason, "duty": decision.duty,
               "retry_after_s": decision.retry_after_s}
        if lease is not None:
            out.update(lease_id=lease.lease_id, ttl_s=round(lease.expires_at - self.clock(), 1), machine=lease.machine)
        return out

    def _sample(self) -> None:
        now = self.clock()
        if now - self._history_at < HISTORY_EVERY_S:
            return
        self._history_at = now
        row = {"t": round(now), "chat": {m: now - t < self.policy.chat_quiet_s for m, t in self.last_chat.items()},
               "jobs": {}, "machines": {}}
        for lease in self.leases.values():
            row["jobs"][lease.job_class] = row["jobs"].get(lease.job_class, 0) + 1
        for machine, snap in self.snapshots.items():
            if now - snap.taken_at < 300:
                row["machines"][machine] = {"cpu": round(snap.cpu_busy, 3), "mem_free_mib": snap.mem_available_mib,
                                            "busy_slots": sum(s.processing for slots in snap.models.values()
                                                              for s in slots)}
        self.history.append(row)

    def status(self) -> dict:
        with self._lock:
            self._expire()
            now = self.clock()
            machines = {}
            for machine, snap in sorted(self.snapshots.items()):
                info = snap.to_dict()
                info["age_s"] = round(now - snap.taken_at, 1)
                info["chat_active"] = now - self.last_chat.get(machine, -1e12) < self.policy.chat_quiet_s
                info["last_chat_s_ago"] = (round(now - self.last_chat[machine], 1)
                                           if machine in self.last_chat else None)
                info["chat_reason"] = self.chat_reason.get(machine, "")
                machines[machine] = info
            averages = {}
            for window in (900, 3600):
                rows = [r for r in self.history if now - r["t"] <= window]
                per = {}
                for row in rows:
                    for machine, m in row["machines"].items():
                        per.setdefault(machine, []).append(m["cpu"])
                averages[f"{window // 60}min"] = {m: round(sum(v) / len(v), 3) for m, v in per.items() if v}
                averages[f"{window // 60}min_jobs"] = {
                    c: round(sum(r["jobs"].get(c, 0) for r in rows) / len(rows), 2)
                    for c in sorted({c for r in rows for c in r["jobs"]})} if rows else {}
            return {"now": now, "machines": machines,
                    "leases": [l.public(now) for l in sorted(self.leases.values(), key=lambda l: l.granted_at)],
                    "waiting": [{"job_class": p.job_class, "holder": p.holder, "machine": p.machine,
                                 "s_ago": round(now - p.at, 1)} for p in self.pending],
                    "counters": dict(self.counters), "cpu_average": averages,
                    "classes": {c.name: {"machine": c.machine, "priority": c.priority, "capability": c.capability}
                                for c in self.classes.values()}}


# --- HTTP ---------------------------------------------------------------------------------------------------------------

def _loopback(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def make_handler(planner: Planner, key: str, report_token: str = ""):
    class Handler(BaseHTTPRequestHandler):
        server_version = "star-planner/1"

        def log_message(self, *_args):            # no request log: paths and addresses stay out of the journal
            pass

        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self) -> bool:
            if not key:
                return _loopback(self.client_address[0])
            given = self.headers.get("Authorization", "")
            return hmac.compare_digest(given.encode("utf-8"), ("Bearer " + key).encode("utf-8"))

        def _reporter(self) -> bool:
            """The report token (brain 2's reporter) allows /v1/report and nothing else."""
            given = self.headers.get("Authorization", "")
            return bool(report_token) and hmac.compare_digest(given.encode("utf-8"),
                                                              ("Bearer " + report_token).encode("utf-8"))

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/health":
                return self._send(200, {"ok": True})
            if path == "/v1/status":
                if not (_loopback(self.client_address[0]) or self._authorised()):
                    return self._send(401, {"error": "key required"})
                return self._send(200, planner.status())
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if not (self._authorised() or (path == "/v1/report" and self._reporter())):
                return self._send(401, {"error": "key required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= MAX_BODY:
                    return self._send(413, {"error": "body too large"})
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("body must be an object")
                if path == "/v1/admit":
                    return self._send(200, planner.admit(payload))
                if path == "/v1/renew":
                    return self._send(200, planner.renew(payload))
                if path == "/v1/release":
                    return self._send(200, planner.release(payload))
                if path == "/v1/report":
                    planner.observe(payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else payload,
                                    remote=True)
                    return self._send(200, {"ok": True})
                if path == "/v1/interactive":
                    planner.interactive(str(payload.get("machine", planner.local_machine))[:20],
                                        str(payload.get("source", ""))[:40])
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "not found"})
            except (ValueError, TypeError, KeyError) as exc:
                return self._send(400, {"error": type(exc).__name__ + ": " + str(exc)[:160]})
    return Handler


def probe_loop(planner: Planner, brain: probes.BrainProbe, *, interval: float = 2.0, stop: threading.Event,
               log=print) -> None:
    cpu = probes.CpuMeter()
    said = ""
    while not stop.is_set():
        try:
            planner.observe(probes.linux_snapshot(planner.local_machine, cpu=cpu, brain=brain,
                                                  lock_dir=planner.lock_dir))
            text = "probing"
        except (OSError, ValueError) as exc:          # brain unreachable: the snapshot goes stale -> clients fall back
            text = f"probe failed ({type(exc).__name__})"
        if text != said:
            log(text)
            said = text
        stop.wait(interval)


def serve(args) -> int:
    key = probes.read_key(args.key_file) if args.key_file else ""
    planner = Planner(local_machine=args.machine, lock_dir=args.lock_dir, log=lambda m: print(m, flush=True))
    brain = probes.BrainProbe(args.brain_url, key)
    stop = threading.Event()
    threading.Thread(target=probe_loop, args=(planner, brain), kwargs={"stop": stop, "interval": args.interval,
                     "log": lambda m: print(m, flush=True)}, daemon=True).start()
    token = probes.read_key(args.report_token_file) if args.report_token_file else ""
    server = ThreadingHTTPServer((args.host, args.port), make_handler(planner, key, token))
    server.daemon_threads = True
    print(f"star-planner listening on port {args.port} (machine {args.machine})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
    return 0


def agent(args) -> int:
    """Report this machine's snapshot to the planner every `interval` seconds (brain 2)."""
    key = probes.read_key(args.key_file) if args.key_file else ""
    cpu = probes.CpuMeter()
    said = ""
    while True:
        try:
            snap = probes.linux_snapshot(args.machine, cpu=cpu, lock_dir=args.lock_dir, with_studios=args.studios)
            request = urllib.request.Request(args.report_to.rstrip("/") + "/v1/report",
                                             data=json.dumps({"snapshot": snap}).encode("utf-8"),
                                             headers={"Content-Type": "application/json"})
            if key:
                request.add_header("Authorization", "Bearer " + key)
            with urllib.request.urlopen(request, timeout=5) as reply:
                reply.read()
            text = "reporting"
        except OSError as exc:
            text = f"report failed ({type(exc).__name__})"
        if text != said:
            print(text, flush=True)
            said = text
        time.sleep(args.interval)


def show_status(args) -> int:
    from .planner_client import PlannerClient, format_status
    client = PlannerClient(url=args.url, key_file=args.key_file)
    data = client.status()
    if data is None:
        print("planner: not reachable")
        return 1
    print(json.dumps(data, indent=1) if args.json else format_status(data))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.resource_planner_service", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the planner (brain 1)")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--machine", default="brain1")
    s.add_argument("--brain-url", default="http://127.0.0.1:8080")
    s.add_argument("--key-file", default=os.environ.get("STAR_PLANNER_KEY_FILE", "/opt/star/secrets/api_keys"))
    s.add_argument("--lock-dir", default=probes.LOCK_DIR)
    s.add_argument("--interval", type=float, default=2.0)
    s.add_argument("--report-token-file", default="", help="token that allows only /v1/report (brain 2's reporter)")
    a = sub.add_parser("agent", help="report this machine's load to the planner (brain 2)")
    a.add_argument("--machine", default="brain2")
    a.add_argument("--report-to", required=True, help="the planner's URL (operator configuration)")
    a.add_argument("--key-file", default=os.environ.get("STAR_PLANNER_KEY_FILE", "/opt/star/secrets/api_keys"))
    a.add_argument("--lock-dir", default=probes.LOCK_DIR)
    a.add_argument("--studios", action="store_true", help="report attached Roblox Studio processes")
    a.add_argument("--interval", type=float, default=10.0)
    t = sub.add_parser("status", help="show machines, leases and the queue")
    t.add_argument("--url", default=None)
    t.add_argument("--key-file", default=None)
    t.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    return {"serve": serve, "agent": agent, "status": show_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
