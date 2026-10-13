"""Dry-run resource admission for concurrent STAR specialists.

This module plans assignments; it NEVER starts a model, runs a tool, accesses
credentials, changes permissions, edits a Studio place or contacts a network.
The existing TaskPlan and trusted app host remain responsible for execution.

A ResourcePool groups workers that share physical CPU/RAM (for example
STAR's fast and main models on one EPYC). Counting each model separately
would pretend the machine has twice the compute it actually possesses.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .orchestration import TaskPlan, overlaps

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_BOUNDARIES = frozenset({"private", "cloud"})
_MAX_TASKS = 32


def _identifier(value: str) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


@dataclass(frozen=True)
class ResourcePool:
    id: str
    memory_mib: int
    cpu_threads: int
    max_jobs: int = 1
    boundary: str = "private"

    def __post_init__(self) -> None:
        if not _identifier(self.id):
            raise ValueError("Invalid resource pool id")
        if type(self.memory_mib) is not int or not 1 <= self.memory_mib <= 2_000_000:
            raise ValueError("Invalid memory capacity")
        if type(self.cpu_threads) is not int or not 1 <= self.cpu_threads <= 4096:
            raise ValueError("Invalid CPU capacity")
        if type(self.max_jobs) is not int or not 1 <= self.max_jobs <= 8:
            raise ValueError("Invalid worker concurrency")
        if self.boundary not in _BOUNDARIES:
            raise ValueError("Unknown trust boundary")


@dataclass(frozen=True)
class ModelWorker:
    id: str
    pool_id: str
    capabilities: frozenset[str]
    slots: int = 1

    def __post_init__(self) -> None:
        if not _identifier(self.id) or not _identifier(self.pool_id):
            raise ValueError("Invalid worker id")
        if type(self.slots) is not int or not 1 <= self.slots <= 8:
            raise ValueError("Invalid model slot count")
        if not isinstance(self.capabilities, frozenset) or any(
            not _identifier(x) for x in self.capabilities
        ):
            raise ValueError("Invalid worker capabilities")


@dataclass(frozen=True)
class TaskDemand:
    task_id: str
    memory_mib: int
    cpu_threads: int
    capabilities: frozenset[str]
    interactive: bool = False
    allow_cloud: bool = False
    priority: int = 0

    def __post_init__(self) -> None:
        if not _identifier(self.task_id):
            raise ValueError("Invalid demand task id")
        if type(self.memory_mib) is not int or not 1 <= self.memory_mib <= 2_000_000:
            raise ValueError("Invalid memory demand")
        if type(self.cpu_threads) is not int or not 1 <= self.cpu_threads <= 4096:
            raise ValueError("Invalid CPU demand")
        if not isinstance(self.capabilities, frozenset) or any(
            not _identifier(x) for x in self.capabilities
        ):
            raise ValueError("Invalid task capabilities")
        if type(self.priority) is not int or not -100 <= self.priority <= 100:
            raise ValueError("Invalid priority")
        if type(self.interactive) is not bool or type(self.allow_cloud) is not bool:
            raise ValueError("Explicit boolean permissions required")


@dataclass(frozen=True)
class Assignment:
    task_id: str
    worker_id: str


@dataclass(frozen=True)
class AdmissionPreview:
    assignments: tuple[Assignment, ...]
    waiting: tuple[str, ...]
    """No work was started by this dry-run."""


def preview_assignments(
    plan: TaskPlan,
    demands: Mapping[str, TaskDemand],
    pools: tuple[ResourcePool, ...],
    workers: tuple[ModelWorker, ...],
    *,
    completed: frozenset[str] = frozenset(),
    running: Mapping[str, str] | None = None,
    finished: frozenset[str] = frozenset(),
    enable_cloud: bool = False,
) -> AdmissionPreview:
    """Plan non-mutating, resource-bounded parallel read-only assignments.

    - Independent tasks can run concurrently, respecting DAG dependencies.
    - All model roles on one machine debit the SAME pool of RAM/CPU/slots.
    - Interactive tasks are admitted ahead of batch work.
    - Cloud tasks need BOTH trusted host opt-in and task opt-in.
    - Every result is advisory; the runtime must recheck capacity/permissions.
    """
    if type(enable_cloud) is not bool:
        raise ValueError("External-provider consent must be explicit")
    if not isinstance(plan, TaskPlan) or len(plan.tasks) > _MAX_TASKS:
        raise ValueError("Invalid or excessively large plan")
    if any(task.writes for task in plan.tasks.values()):
        raise PermissionError("Resource planner only admits read-only tasks")
    if set(demands) != set(plan.tasks) or any(
        not isinstance(v, TaskDemand) or v.task_id != k for k, v in demands.items()
    ):
        raise ValueError("Every task requires exactly one matching demand")
    if len({p.id for p in pools}) != len(pools):
        raise ValueError("Duplicate resource pool")
    if len({w.id for w in workers}) != len(workers):
        raise ValueError("Duplicate model worker")
    pool_by_id = {p.id: p for p in pools}
    worker_by_id = {w.id: w for w in workers}
    if any(w.pool_id not in pool_by_id for w in workers):
        raise ValueError("Worker references an unknown resource pool")
    running = dict(running or {})
    active = set(running)
    if not (set(completed) | active | set(finished)) <= set(plan.tasks):
        raise ValueError("Unknown task status")
    if (set(completed) & active) or (set(completed) & set(finished)) or (active & set(finished)):
        raise ValueError("Contradictory task statuses")
    if any(wid not in worker_by_id for wid in running.values()):
        raise ValueError("Unknown running model worker")
    if len(active) > plan.max_parallel:
        raise ValueError("Running above the plan's concurrency limit")

    # Copy resource counts; never mutate a caller's state.
    slot_used = {w.id: 0 for w in workers}
    usage = {p.id: {"mem": 0, "cpu": 0, "jobs": 0} for p in pools}

    def reserve(task_id: str, worker_id: str) -> bool:
        d = demands[task_id]
        w = worker_by_id[worker_id]
        p = pool_by_id[w.pool_id]
        u = usage[p.id]
        if not d.capabilities <= w.capabilities:
            return False
        if p.boundary == "cloud" and not (enable_cloud and d.allow_cloud):
            return False
        if (slot_used[w.id] >= w.slots or u["jobs"] >= p.max_jobs
            or u["mem"] + d.memory_mib > p.memory_mib
            or u["cpu"] + d.cpu_threads > p.cpu_threads):
            return False
        slot_used[w.id] += 1
        u["jobs"] += 1
        u["mem"] += d.memory_mib
        u["cpu"] += d.cpu_threads
        return True

    for task_id, worker_id in running.items():
        if not reserve(task_id, worker_id):
            raise ValueError("Running assignments exceed declared capacity or permissions")

    locked_reads = [path for tid in active for path in plan.tasks[tid].reads]
    locked_writes = [path for tid in active for path in plan.tasks[tid].writes]

    # Plan.order is a deterministic tie breaker. Deadlines and live load remain
    # the trusted orchestrator's responsibility, not model-generated advice.
    order = {tid: i for i, tid in enumerate(plan.tasks)}
    eligible = [t for t in plan.tasks.values()
                if t.id not in active and t.id not in completed and t.id not in finished
                and set(t.dependencies) <= set(completed)]
    eligible.sort(key=lambda t: (
        not demands[t.id].interactive, -demands[t.id].priority, order[t.id]
    ))

    selected: list[Assignment] = []
    waiting: list[str] = []
    for task in eligible:
        demand = demands[task.id]
        if len(active) + len(selected) >= plan.max_parallel:
            waiting.append(task.id)
            continue
        if any(overlaps(w, lock) for w in task.writes
               for lock in locked_reads + locked_writes):
            waiting.append(task.id)
            continue
        if any(overlaps(r, lock) for r in task.reads for lock in locked_writes):
            waiting.append(task.id)
            continue

        # When a high-priority foreground task is awaiting resources, avoid
        # launching more background work (conservative fairness policy).
        foreground_waiting = any(demands[tid].interactive for tid in waiting)
        if foreground_waiting and not demand.interactive:
            waiting.append(task.id)
            continue
        accepted = False
        for worker in sorted(workers, key=lambda x: (
            pool_by_id[x.pool_id].boundary == "cloud",
            slot_used[x.id], x.id
        )):
            if reserve(task.id, worker.id):
                selected.append(Assignment(task.id, worker.id))
                locked_reads.extend(task.reads)
                locked_writes.extend(task.writes)
                accepted = True
                break
        if not accepted:
            waiting.append(task.id)
    return AdmissionPreview(tuple(selected), tuple(waiting))


# =====================================================================================================================
# Live job-class admission (resource-planner-20261013).
#
# The dry-run planner above decides how independent tasks share a pool of RAM/CPU/slots. The functions below feed it
# LIVE numbers (probes of /proc, llama-server /slots + /metrics, nvidia-smi) and add the house rules of STAR's three
# machines: interactive chat always first, the quiet lock and exclusive timing windows, night school yielding to chat,
# the knowledge re-index slowing down while chat is active, Studio tests on brain 2 (one test per Studio, via the
# test-farm preview of star/studio_test_farm.py) and GPU training on the owner's PC only while he is not gaming and
# above his free-RAM floor. Still pure: nothing here starts, stops or contacts anything. The service
# (star/resource_planner_service.py) owns the leases and the probes; clients fall back to their old behaviour when it
# cannot be reached.
# =====================================================================================================================

ACTIONS = frozenset({"run", "wait", "yield", "fallback", "refuse"})
HELPER_MODELS = frozenset({"star-embed", "star-embed-ft1", "star-rerank"})
STUDIO_TEST_PLACE = (10770312935, 128074805767678)     # STAR Test Place (universe, place): see star/studio_remote.py


@dataclass(frozen=True)
class JobClass:
    """A kind of background work and where it may run. `capability` names the worker it needs: a model's slots
    ("star-fast"), "studio" (one test per attached Studio), "gpu" or "cpu" (a plain process)."""
    name: str
    machine: str
    priority: int
    capability: str
    cpu_threads: int = 1
    memory_mib: int = 256
    vram_mib: int = 0
    yields_to_chat: bool = False     # stop (cancel the request in flight) while chat is active
    chat_duty: float = 1.0           # share of time it may keep the machine busy while chat is active
    exclusive: bool = False          # a timing window: nothing else batch on the machine, quiet lock held
    max_ttl_s: int = 120             # a lease not renewed within this time is gone
    machines: tuple = ()             # alternatives, best first: the job goes to the first one with headroom

    def __post_init__(self) -> None:
        if not _identifier(self.name) or not _identifier(self.machine) or not _identifier(self.capability):
            raise ValueError("Invalid job class")
        if not -100 <= self.priority <= 100 or not 0.0 < self.chat_duty <= 1.0 or not 5 <= self.max_ttl_s <= 600:
            raise ValueError("Invalid job class limits")


# Demands are estimates: star-fast jobs share the star-fast process (24 generation threads, 2 slots), so each slot
# counts for half of it. Memory is the job's own process, not the model (the model is resident anyway).
DEFAULT_CLASSES: dict[str, JobClass] = {c.name: c for c in (
    JobClass("eval-timing", "brain1", 90, "star-fast", cpu_threads=24, memory_mib=512, exclusive=True, max_ttl_s=600),
    JobClass("eval", "brain1", 60, "star-fast", cpu_threads=12, memory_mib=1024, max_ttl_s=600),
    JobClass("nightschool", "brain1", 40, "star-fast", cpu_threads=12, memory_mib=3072, yields_to_chat=True,
             max_ttl_s=120),
    JobClass("reindex", "brain1", 20, "cpu", cpu_threads=8, memory_mib=2048, chat_duty=0.25, max_ttl_s=300),
    JobClass("studio-test", "brain2", 50, "studio", cpu_threads=2, memory_mib=2048, max_ttl_s=600),
    JobClass("gpu-train", "pc", 30, "gpu", cpu_threads=4, memory_mib=4096, vram_mib=2048, max_ttl_s=300),
    # Non-LLM CPU work (Luau VM test runs, luau-analyze, linters, grading/verify scripts): brain 2's CPU-worker
    # pool first (beside Studio, inside its RAM budget), brain 1 only when brain 2 has no headroom.
    JobClass("cpu-work", "brain2", 35, "cpu", cpu_threads=1, memory_mib=512, max_ttl_s=300,
             machines=("brain2", "brain1")),
)}


@dataclass(frozen=True)
class LivePolicy:
    chat_quiet_s: float = 120.0                       # batch that yields to chat waits this long after the last sign
    exclusive_quiet_s: float = 30.0                   # a timing window needs this much quiet first
    exclusive_pending_s: float = 90.0                 # a waiting timing request blocks new batch work this long
    preempt_window_s: float = 30.0                    # a refused higher-priority request makes lower leases yield
    reserve_slots: Mapping[str, int] | None = None    # slots of a model kept free for chat
    mem_reserve_mib: Mapping[str, int] | None = None  # RAM never handed to batch work (pc: the owner's floor)
    cpu_reserve_threads: Mapping[str, int] | None = None  # hardware threads never handed to batch work
    stale_s: Mapping[str, float] | None = None        # a machine snapshot older than this is not trusted
    cpu_busy_max: float = 0.95                        # sustained CPU above this: no new batch process on the machine
    min_free_mib: Mapping[str, int] | None = None     # running batch yields below this much available RAM
    studio_reserve_mib: int = 2560                    # kept free for an attached Studio's playtests (brain 2 measured:
                                                      # Studio + WebView ~5.8 GiB of a 12 GiB container, peaks at it)
    helper_models: frozenset = HELPER_MODELS          # used by batch jobs themselves: never a sign of chat

    def __post_init__(self) -> None:
        defaults = {
            "reserve_slots": {"star-fast": 1},
            "mem_reserve_mib": {"brain1": 24576, "brain2": 1024, "pc": 6144},
            "cpu_reserve_threads": {"brain1": 12, "brain2": 1, "pc": 2},
            "stale_s": {"brain1": 20.0, "brain2": 120.0, "pc": 120.0},
            "min_free_mib": {"brain1": 4096, "brain2": 512, "pc": 6144},
        }
        for name, value in defaults.items():
            if getattr(self, name) is None:
                object.__setattr__(self, name, value)


@dataclass(frozen=True)
class SlotState:
    id: int
    processing: bool
    task: int = -1


@dataclass(frozen=True)
class MachineSnapshot:
    """What the probes saw on one machine at `taken_at` (wall clock, seconds). `models` lists LOADED models only."""
    machine: str
    taken_at: float
    cpu_threads: int
    cpu_busy: float
    mem_total_mib: int
    mem_available_mib: int
    models: Mapping[str, tuple] | None = None
    deferred: Mapping[str, int] | None = None        # requests queued per model (llama-server /metrics)
    lock_owner: str = ""                             # fresh quiet-lock owner, "" when free
    gpu_util: float | None = None                    # 0..1
    vram_total_mib: int = 0
    vram_used_mib: int = 0
    owner_busy: str = ""                             # PC: why the owner needs the machine (a game, fullscreen), or ""
    studios: tuple = ()                              # brain 2: attached Studio processes {"studio_id", "place_id", ...}

    def __post_init__(self) -> None:
        if not _identifier(self.machine):
            raise ValueError("Invalid machine id")
        object.__setattr__(self, "models", dict(self.models or {}))
        object.__setattr__(self, "deferred", dict(self.deferred or {}))

    @staticmethod
    def from_dict(data: Mapping) -> "MachineSnapshot":
        """Build from untrusted JSON: types checked, numbers clamped, unknown keys ignored."""
        if not isinstance(data, Mapping):
            raise ValueError("snapshot must be an object")

        def num(key, low, high, default=0.0):
            value = data.get(key, default)
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                return default
            return min(high, max(low, value))

        models = {}
        raw_models = data.get("models")
        for name, slots in (raw_models.items() if isinstance(raw_models, Mapping) else ()):
            if _identifier(str(name)) and isinstance(slots, list):
                models[str(name)] = tuple(
                    SlotState(s["id"], bool(s.get("processing")), s.get("task", -1))
                    for s in slots[:16] if isinstance(s, Mapping) and type(s.get("id")) is int
                    and type(s.get("task", -1)) is int)
        raw_deferred = data.get("deferred")
        deferred = ({str(k): v for k, v in raw_deferred.items() if _identifier(str(k)) and type(v) is int and v >= 0}
                    if isinstance(raw_deferred, Mapping) else {})
        raw_studios = data.get("studios")
        studios = tuple({k: v for k, v in s.items() if k in ("studio_id", "universe_id", "place_id")
                         and isinstance(v, (str, int)) and not isinstance(v, bool)}
                        for s in (raw_studios[:8] if isinstance(raw_studios, list) else []) if isinstance(s, Mapping))
        gpu = data.get("gpu_util")
        return MachineSnapshot(
            machine=str(data.get("machine", "")), taken_at=float(num("taken_at", 0, 1e11)),
            cpu_threads=int(num("cpu_threads", 1, 4096, 1)), cpu_busy=float(num("cpu_busy", 0, 1)),
            mem_total_mib=int(num("mem_total_mib", 0, 2_000_000)),
            mem_available_mib=int(num("mem_available_mib", 0, 2_000_000)),
            models=models, deferred=deferred, lock_owner=re.sub(r"[^A-Za-z0-9_.-]", "", str(data.get("lock_owner") or ""))[:40],
            gpu_util=None if gpu is None else float(num("gpu_util", 0, 1)),
            vram_total_mib=int(num("vram_total_mib", 0, 1_000_000)),
            vram_used_mib=int(num("vram_used_mib", 0, 1_000_000)),
            owner_busy=str(data.get("owner_busy") or "")[:80], studios=studios)

    def to_dict(self) -> dict:
        return {"machine": self.machine, "taken_at": self.taken_at, "cpu_threads": self.cpu_threads,
                "cpu_busy": round(self.cpu_busy, 3), "mem_total_mib": self.mem_total_mib,
                "mem_available_mib": self.mem_available_mib,
                "models": {m: [{"id": s.id, "processing": s.processing, "task": s.task} for s in slots]
                           for m, slots in self.models.items()},
                "deferred": dict(self.deferred), "lock_owner": self.lock_owner, "gpu_util": self.gpu_util,
                "vram_total_mib": self.vram_total_mib, "vram_used_mib": self.vram_used_mib,
                "owner_busy": self.owner_busy, "studios": [dict(s) for s in self.studios]}


@dataclass
class Lease:
    lease_id: str
    job_class: str
    machine: str
    holder: str
    job_id: str
    capability: str
    granted_at: float
    expires_at: float
    memory_mib: int
    cpu_threads: int
    slot: int | None = None            # a pinned model slot (night school), None = any one slot
    studio_id: str = ""
    vram_mib: int = 0
    duty: float = 1.0

    def public(self, now: float) -> dict:
        return {"lease_id": self.lease_id, "job_class": self.job_class, "machine": self.machine,
                "holder": self.holder, "job_id": self.job_id, "capability": self.capability, "slot": self.slot,
                "studio_id": self.studio_id, "age_s": round(now - self.granted_at, 1),
                "expires_in_s": round(self.expires_at - now, 1), "duty": self.duty}


@dataclass(frozen=True)
class JobRequest:
    job_class: str
    holder: str
    job_id: str
    slot: int | None = None
    memory_mib: int | None = None
    vram_mib: int | None = None
    ttl_s: int | None = None
    studio_id: str = ""
    universe_id: int = 0
    place_id: int = 0
    identity_verified: bool = False
    clients: int = 1

    def __post_init__(self) -> None:
        if not _identifier(self.job_class) or not _identifier(self.holder) or not _identifier(self.job_id):
            raise ValueError("Invalid job request")
        if self.slot is not None and (type(self.slot) is not int or not 0 <= self.slot <= 64):
            raise ValueError("Invalid slot")
        for value in (self.memory_mib, self.vram_mib):
            if value is not None and (type(value) is not int or not 1 <= value <= 2_000_000):
                raise ValueError("Invalid memory demand")
        if self.ttl_s is not None and (type(self.ttl_s) is not int or not 5 <= self.ttl_s <= 600):
            raise ValueError("Invalid lease time")
        if self.studio_id and not _identifier(self.studio_id):
            raise ValueError("Invalid Studio id")
        if (type(self.identity_verified) is not bool or type(self.clients) is not int or not 1 <= self.clients <= 8
                or type(self.universe_id) is not int or type(self.place_id) is not int):
            raise ValueError("Invalid Studio request")


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    duty: float = 1.0
    retry_after_s: float = 10.0

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError("Unknown decision")


@dataclass(frozen=True)
class Pending:
    """A request that was refused recently (for pre-emption and timing windows)."""
    job_class: str
    machine: str
    capability: str
    priority: int
    holder: str
    at: float


def chat_signs(before: MachineSnapshot | None, after: MachineSnapshot, leases: list,
               policy: LivePolicy = LivePolicy()) -> list[str]:
    """Signs of interactive use: busy slots that no lease explains, a queue in front of a model, or (on a model
    with no unpinned lease) a slot that served a new request since the last look. Helper models never count."""
    signs = []
    for model, slots in after.models.items():
        if model in policy.helper_models:
            continue
        mine = [l for l in leases if l.machine == after.machine and l.capability == model]
        pinned = {l.slot for l in mine if l.slot is not None}
        unpinned = sum(1 for l in mine if l.slot is None)
        busy = [s for s in slots if s.processing and s.id not in pinned]
        if len(busy) > unpinned:
            signs.append(f"{model}: {len(busy) - unpinned} busy slot(s) without a lease")
        elif before is not None and not unpinned:
            old = {s.id: s.task for s in before.models.get(model, ())}
            moved = [s.id for s in slots if s.id not in pinned and s.id in old and old[s.id] != s.task]
            if moved:
                signs.append(f"{model}: slot {moved[0]} served a request without a lease")
        if after.deferred.get(model, 0) > 0:
            signs.append(f"{model}: {after.deferred[model]} request(s) queued")
    return signs


def planner_lock_owner(holder: str) -> str:
    """The owner name the service writes into the quiet lock for a timing window (fits star.py's lock rules)."""
    return ("planner-" + re.sub(r"[^a-z0-9_-]", "", holder.lower()))[:31]


def _snapshot_problem(snap, machine: str, now: float, policy: LivePolicy) -> str:
    if snap is None:
        return f"no load data from {machine}"
    if now - snap.taken_at > policy.stale_s.get(machine, 60.0):
        return f"load data from {machine} is {int(now - snap.taken_at)} s old"
    return ""


def _blocked_by_window(cls: JobClass, holder: str, leases: list, pending: list, now: float, policy: LivePolicy,
                       classes: Mapping[str, JobClass]) -> str:
    if cls.exclusive:
        return ""
    for lease in leases:
        other = classes.get(lease.job_class)
        if other and other.exclusive and lease.machine == cls.machine and lease.holder != holder:
            return f"timing window of {lease.holder} in progress"
    for p in pending:
        other = classes.get(p.job_class)
        if (other and other.exclusive and p.machine == cls.machine and p.holder != holder
                and now - p.at < policy.exclusive_pending_s):
            return f"timing window requested by {p.holder}"
    return ""


def _lock_problem(snap: MachineSnapshot, holder: str, cls: JobClass) -> str:
    if not snap.lock_owner:
        return ""
    if cls.exclusive and snap.lock_owner == planner_lock_owner(holder):
        return ""
    return f"quiet lock held by {snap.lock_owner}"


def _chat_active(machine: str, last_chat: Mapping[str, float], now: float, window: float) -> bool:
    at = last_chat.get(machine)
    return at is not None and now - at < window


def _capacity_check(req: JobRequest, cls: JobClass, snap: MachineSnapshot, leases: list, policy: LivePolicy) -> str:
    """Run the dry-run planner above on the live numbers. "" when the request fits, else why not."""
    from .orchestration import Task
    mine = [l for l in leases if l.machine == cls.machine]
    if len(mine) >= 7:
        return "too many jobs on this machine"
    memory = snap.mem_available_mib - policy.mem_reserve_mib.get(cls.machine, 0) + sum(l.memory_mib for l in mine)
    if snap.studios and cls.capability != "studio":     # the CPU-worker pool never eats Studio's playtest headroom
        memory -= policy.studio_reserve_mib
    cpu = snap.cpu_threads - policy.cpu_reserve_threads.get(cls.machine, 0)
    if memory < 1:
        return f"not enough free RAM on {cls.machine} ({snap.mem_available_mib} MiB available)"
    if cpu < 1:
        return f"no CPU threads left on {cls.machine}"
    caps: dict[str, int] = {"cpu": 8, "studio": len(snap.studios), "gpu": 1 if snap.vram_total_mib > 0 else 0}
    for model, slots in snap.models.items():
        caps[model] = len(slots) - (0 if model in policy.helper_models else policy.reserve_slots.get(model, 0))
    workers = tuple(ModelWorker(cap, cls.machine, frozenset({cap}), slots=min(8, n))
                    for cap, n in sorted(caps.items()) if n >= 1 and _identifier(cap))
    known = {w.id for w in workers}
    if cls.capability not in known:
        if cls.capability in snap.models or cls.capability in ("studio", "gpu"):
            return f"no {cls.capability} slot may be used by batch work"
        return f"{cls.capability} is not available on {cls.machine}"
    pool = ResourcePool(cls.machine, memory_mib=min(memory, 2_000_000), cpu_threads=min(cpu, 4096), max_jobs=8)
    tasks, demands, running = [], {}, {}
    for i, lease in enumerate(mine):
        if lease.capability not in known:       # its worker vanished (model unloaded, Studio closed): holds nothing
            continue
        tid = f"lease{i}"
        tasks.append(Task(tid, "research", lease.job_class))
        demands[tid] = TaskDemand(tid, max(1, lease.memory_mib), max(1, lease.cpu_threads),
                                  frozenset({lease.capability}))
        running[tid] = lease.capability
    tasks.append(Task("request", "research", cls.name))
    demands["request"] = TaskDemand("request", req.memory_mib or cls.memory_mib, cls.cpu_threads,
                                    frozenset({cls.capability}), priority=cls.priority)
    try:
        preview = preview_assignments(TaskPlan(tasks, max_parallel=8), demands, (pool,), workers, running=running)
    except ValueError:
        return f"{cls.machine} is already at its limit"
    if any(a.task_id == "request" for a in preview.assignments):
        return ""
    return f"{cls.machine} has no free {cls.capability} capacity"


def _studio_check(req: JobRequest, snap: MachineSnapshot, leases: list) -> str:
    """One test per Studio and only on STAR Test Place or a blank place, via the test-farm preview (#207)."""
    from .studio_test_farm import StudioInstance, StudioScenario, preview_studio_farm
    if not snap.studios:
        return "no Studio is attached on brain 2"
    busy = {l.studio_id for l in leases if l.capability == "studio"}
    instances = []
    for i, s in enumerate(snap.studios):
        sid = str(s.get("studio_id") or f"studio{i}")
        target = req.studio_id or sid
        # Identity: brain 2's reporter reads the place from Studio's launch line (observed); the requester may also
        # have verified it in-session (the pin check). Either counts here; the pin is repeated at dispatch anyway.
        observed = (s.get("universe_id"), s.get("place_id"))
        known = all(type(x) is int for x in observed)
        place = observed if known else (req.universe_id, req.place_id)
        verified = sid == target and (req.identity_verified or (known and observed == (req.universe_id, req.place_id)))
        try:
            instance = StudioInstance(sid, int(place[0]), int(place[1]), identity_verified=verified,
                                      active_test=sid in busy)
        except ValueError:
            instance = StudioInstance(sid, req.universe_id, req.place_id, identity_verified=False,
                                      active_test=sid in busy)
        instances.append(instance)
    scenario = StudioScenario(req.job_id, req.studio_id or instances[0].studio_id, req.universe_id, req.place_id,
                              req.clients)
    try:
        preview = preview_studio_farm(tuple(instances), (scenario,),
                                      approved_places=frozenset({STUDIO_TEST_PLACE, (0, 0)}),
                                      max_parallel_studios=max(1, len(instances)),
                                      max_total_clients=min(128, 8 * max(1, len(instances))))
    except ValueError as exc:
        return f"Studio request refused ({exc})"
    if preview.admitted:
        return ""
    reason = (preview.waiting or preview.rejected)[0].reason
    return {"studio_busy": "a test is already running in that Studio",
            "identity_mismatch": "the Studio's place was not verified as the requested place",
            "place_not_approved": "only STAR Test Place or a blank place may be tested",
            "studio_unavailable": "that Studio is not attached"}.get(reason, reason)


def resolve_studio(req: JobRequest, snap: MachineSnapshot | None, leases: list) -> JobRequest:
    """A Studio test that names no Studio gets the first attached Studio without a running test (or the first one,
    which then waits): the PC knows the connector's ids, brain 2's reporter knows its processes."""
    from dataclasses import replace
    if req.studio_id or snap is None or not snap.studios:
        return req
    busy = {l.studio_id for l in leases if l.capability == "studio"}
    ids = [str(s.get("studio_id") or f"studio{i}") for i, s in enumerate(snap.studios)]
    ids = [i for i in ids if _identifier(i)]
    if not ids:
        return req
    free = [i for i in ids if i not in busy]
    return replace(req, studio_id=(free or ids)[0])


def decide_admit_any(req: JobRequest, snapshots: Mapping[str, MachineSnapshot], leases: list, *, now: float,
                     last_chat: Mapping[str, float], pending=(), classes: Mapping[str, JobClass] = DEFAULT_CLASSES,
                     policy: LivePolicy = LivePolicy()) -> tuple[Decision, str]:
    """For a class with alternative machines: the first machine that admits it (best first), else the first
    machine's answer. Returns (decision, machine)."""
    from dataclasses import replace
    cls = classes.get(req.job_class)
    if cls is None:
        return Decision("refuse", f"unknown job class {req.job_class}", retry_after_s=600), ""
    answers = []
    for machine in (cls.machines or (cls.machine,)):
        local = {**classes, cls.name: replace(cls, machine=machine)}
        decision = decide_admit(req, snapshots.get(machine), leases, now=now, last_chat=last_chat, pending=pending,
                                classes=local, policy=policy)
        if decision.action == "run":
            return decision, machine
        answers.append((decision, machine))
    waits = [a for a in answers if a[0].action == "wait"]
    return (waits or answers)[0]


def decide_admit(req: JobRequest, snap: MachineSnapshot | None, leases: list, *, now: float,
                 last_chat: Mapping[str, float], pending=(), classes: Mapping[str, JobClass] = DEFAULT_CLASSES,
                 policy: LivePolicy = LivePolicy()) -> Decision:
    """May this job start now? "run", "wait" (ask again after retry_after_s), "fallback" (the planner cannot judge:
    use your own rules) or "refuse" (a request the planner will never grant)."""
    cls = classes.get(req.job_class)
    if cls is None:
        return Decision("refuse", f"unknown job class {req.job_class}", retry_after_s=600)
    problem = _snapshot_problem(snap, cls.machine, now, policy)
    if problem:
        return Decision("fallback", problem, retry_after_s=30)
    problem = _lock_problem(snap, req.holder, cls) or _blocked_by_window(cls, req.holder, leases, list(pending), now,
                                                                          policy, classes)
    if problem:
        return Decision("wait", problem, retry_after_s=15)
    if cls.exclusive:
        others = [l for l in leases if l.machine == cls.machine and l.holder != req.holder]
        if others:
            return Decision("wait", f"waiting for {len(others)} job(s) to step aside", retry_after_s=5)
        if _chat_active(cls.machine, last_chat, now, policy.exclusive_quiet_s):
            return Decision("wait", "chat is active; a timing window needs quiet", retry_after_s=10)
        busy = sorted(m for m, slots in snap.models.items()
                      if m not in policy.helper_models and any(s.processing for s in slots))
        if busy:
            return Decision("wait", "requests still running on " + ", ".join(busy[:3]), retry_after_s=5)
        return Decision("run", "timing window granted (the quiet lock is set for you)")
    if cls.yields_to_chat and _chat_active(cls.machine, last_chat, now, policy.chat_quiet_s):
        left = policy.chat_quiet_s - (now - last_chat[cls.machine])
        return Decision("wait", "chat is active", retry_after_s=max(5.0, min(60.0, left)))
    for p in pending:                      # a higher-priority job is waiting for the same worker: it goes first
        other = classes.get(p.job_class)
        if (other is not None and not other.exclusive and p.machine == cls.machine
                and p.capability == cls.capability and p.priority > cls.priority and p.holder != req.holder
                and now - p.at < policy.preempt_window_s):
            return Decision("wait", f"{p.job_class} ({p.holder}) is waiting for the {cls.capability} slot",
                            retry_after_s=20)
    if cls.machine == "pc":
        if snap.owner_busy:
            return Decision("wait", f"the owner is using the PC ({snap.owner_busy})", retry_after_s=60)
        if cls.vram_mib and snap.vram_total_mib - snap.vram_used_mib < (req.vram_mib or cls.vram_mib):
            return Decision("wait", "not enough free GPU memory", retry_after_s=60)
    if snap.cpu_busy >= policy.cpu_busy_max and cls.capability not in snap.models:
        return Decision("wait", f"CPU on {cls.machine} is saturated ({snap.cpu_busy:.0%})", retry_after_s=20)
    problem = ""
    if cls.capability == "studio":         # the test-farm rules first: their reasons are the precise ones
        req = resolve_studio(req, snap, leases)
        problem = _studio_check(req, snap, leases)
    problem = problem or _capacity_check(req, cls, snap, leases, policy)
    if problem:
        return Decision("wait", problem, retry_after_s=15)
    duty = cls.chat_duty if _chat_active(cls.machine, last_chat, now, policy.chat_quiet_s) else 1.0
    return Decision("run", "admitted", duty=duty)


def decide_renew(lease: Lease, snap: MachineSnapshot | None, leases: list, *, now: float,
                 last_chat: Mapping[str, float], pending=(), classes: Mapping[str, JobClass] = DEFAULT_CLASSES,
                 policy: LivePolicy = LivePolicy()) -> Decision:
    """May this running job go on? "run" (with a duty factor), "yield" (stop at the next safe point and ask again
    later), "fallback" (no fresh load data) or "refuse" (the lease is gone: ask for a new one)."""
    cls = classes.get(lease.job_class)
    if cls is not None and cls.machines and lease.machine in cls.machines and lease.machine != cls.machine:
        from dataclasses import replace
        cls = replace(cls, machine=lease.machine)
        classes = {**classes, cls.name: cls}
    if cls is None or now > lease.expires_at:
        return Decision("refuse", "lease expired or unknown", retry_after_s=1)
    problem = _snapshot_problem(snap, cls.machine, now, policy)
    if problem:
        return Decision("fallback", problem, retry_after_s=30)
    others = [l for l in leases if l.lease_id != lease.lease_id]
    problem = _lock_problem(snap, lease.holder, cls) or _blocked_by_window(cls, lease.holder, others, list(pending),
                                                                            now, policy, classes)
    if problem:
        return Decision("yield", problem, retry_after_s=15)
    if cls.yields_to_chat and _chat_active(cls.machine, last_chat, now, policy.chat_quiet_s):
        return Decision("yield", "chat is active", retry_after_s=30)
    floor = policy.min_free_mib.get(cls.machine, 0)
    if snap.mem_available_mib < floor:
        return Decision("yield", f"free RAM on {cls.machine} below {floor} MiB", retry_after_s=60)
    if cls.machine == "pc" and snap.owner_busy:
        return Decision("yield", f"the owner is using the PC ({snap.owner_busy})", retry_after_s=60)
    for p in pending:
        other = classes.get(p.job_class)
        if (other is not None and not other.exclusive and p.machine == cls.machine
                and p.capability == cls.capability and p.priority > cls.priority and p.holder != lease.holder
                and now - p.at < policy.preempt_window_s):
            return Decision("yield", f"{p.job_class} ({p.holder}) needs the {cls.capability} slot", retry_after_s=30)
    duty = cls.chat_duty if _chat_active(cls.machine, last_chat, now, policy.chat_quiet_s) else 1.0
    return Decision("run", "go on", duty=duty)
