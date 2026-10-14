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
from .validation_messages import describe_invalid

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
            raise ValueError(f"Invalid resource pool id: id must start alphanumeric and contain 1-80 letters, digits, dots, hyphens or underscores (got {describe_invalid(self.id)}). Choose a valid id.")
        if type(self.memory_mib) is not int or not 1 <= self.memory_mib <= 2_000_000:
            raise ValueError("Invalid memory capacity: memory_mib must be an integer between 1 and 2000000 MiB. Set a supported capacity.")
        if type(self.cpu_threads) is not int or not 1 <= self.cpu_threads <= 4096:
            raise ValueError("Invalid CPU capacity: cpu_threads must be an integer between 1 and 4096. Set a supported capacity.")
        if type(self.max_jobs) is not int or not 1 <= self.max_jobs <= 8:
            raise ValueError("Invalid worker concurrency: max_jobs must be an integer between 1 and 8. Reduce concurrency.")
        if self.boundary not in _BOUNDARIES:
            raise ValueError("Unknown trust boundary: boundary must be private or cloud. Select a supported boundary.")


@dataclass(frozen=True)
class ModelWorker:
    id: str
    pool_id: str
    capabilities: frozenset[str]
    slots: int = 1

    def __post_init__(self) -> None:
        if not _identifier(self.id) or not _identifier(self.pool_id):
            raise ValueError("Invalid worker id: worker id and pool_id must be 1-80 character valid identifiers. Correct the invalid id.")
        if type(self.slots) is not int or not 1 <= self.slots <= 8:
            raise ValueError("Invalid model slot count: slots must be an integer between 1 and 8. Set a supported slot count.")
        if not isinstance(self.capabilities, frozenset) or any(
            not _identifier(x) for x in self.capabilities
        ):
            raise ValueError("Invalid worker capabilities: capabilities must be a frozenset of 1-80 character identifiers. Fix invalid names or type.")


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
            raise ValueError("Invalid demand task id: task_id must be a valid 1-80 character identifier. Match a planned task.")
        if type(self.memory_mib) is not int or not 1 <= self.memory_mib <= 2_000_000:
            raise ValueError("Invalid memory demand: memory_mib must be an integer between 1 and 2000000 MiB. Reduce demand.")
        if type(self.cpu_threads) is not int or not 1 <= self.cpu_threads <= 4096:
            raise ValueError("Invalid CPU demand: cpu_threads must be an integer between 1 and 4096. Reduce demand.")
        if not isinstance(self.capabilities, frozenset) or any(
            not _identifier(x) for x in self.capabilities
        ):
            raise ValueError("Invalid task capabilities: capabilities must be a frozenset of 1-80 character identifiers. Fix invalid names or type.")
        if type(self.priority) is not int or not -100 <= self.priority <= 100:
            raise ValueError("Invalid priority: priority must be an integer between -100 and 100. Choose a supported value.")
        if type(self.interactive) is not bool or type(self.allow_cloud) is not bool:
            raise ValueError("Explicit boolean permissions required: interactive and allow_cloud must both be bool. Use True or False.")


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
        raise ValueError("External-provider consent must be explicit: enable_cloud must be bool. Use True or False.")
    if not isinstance(plan, TaskPlan) or len(plan.tasks) > _MAX_TASKS:
        raise ValueError("Invalid or excessively large plan: plan must be TaskPlan with no more than 32 tasks. Supply a valid smaller plan.")
    if any(task.writes for task in plan.tasks.values()):
        raise PermissionError("Resource planner only admits read-only tasks: plan.tasks must not request writes. Remove mutations or use an authorized executor.")
    if set(demands) != set(plan.tasks) or any(
        not isinstance(v, TaskDemand) or v.task_id != k for k, v in demands.items()
    ):
        raise ValueError("Every task requires exactly one matching demand: demands must match the plan task ids and each TaskDemand.task_id. Supply one demand per task.")
    if len({p.id for p in pools}) != len(pools):
        raise ValueError("Duplicate resource pool: ResourcePool.id must be unique. Rename or remove duplicate pools.")
    if len({w.id for w in workers}) != len(workers):
        raise ValueError("Duplicate model worker: ModelWorker.id must be unique. Rename or remove duplicate workers.")
    pool_by_id = {p.id: p for p in pools}
    worker_by_id = {w.id: w for w in workers}
    if any(w.pool_id not in pool_by_id for w in workers):
        raise ValueError("Worker references an unknown resource pool: worker.pool_id must reference an existing ResourcePool.id. Supply or correct its pool.")
    running = dict(running or {})
    active = set(running)
    if not (set(completed) | active | set(finished)) <= set(plan.tasks):
        raise ValueError("Unknown task status: completed, running and finished ids must exist in plan.tasks. Remove unknown ids.")
    if (set(completed) & active) or (set(completed) & set(finished)) or (active & set(finished)):
        raise ValueError("Contradictory task statuses: task ids must occur in only one of completed, running and finished. Resolve the overlap.")
    if any(wid not in worker_by_id for wid in running.values()):
        raise ValueError("Unknown running model worker: running worker ids must match ModelWorker.id. Correct the mapping.")
    if len(active) > plan.max_parallel:
        raise ValueError("Running above the plan's concurrency limit: number of running tasks must not exceed plan.max_parallel. Reduce assignments.")

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
            raise ValueError("Running assignments exceed declared capacity or permissions: running assignments must fit pool RAM, CPU, job slots and consent. Reduce reservations.")

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
