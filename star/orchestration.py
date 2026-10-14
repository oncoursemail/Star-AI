"""Validated task contracts and a deterministic, non-executing dependency scheduler.

This module does not yet spawn subagents. It refuses ambiguous resource ownership,
cycles and invalid task identifiers before a worker runtime is introduced.
"""
from dataclasses import dataclass
import re

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
ROLES = frozenset({"planner", "research", "luau", "ui", "animation", "environment", "review", "integration"})


def _normalized_resource(s: str) -> str:
    if not isinstance(s, str) or not s or "\\" in s or s.startswith("/") or "//" in s:
        raise ValueError("Resource scope must be a relative forward-slash path")
    parts = s.split("/")
    if any(p in (".", "..", "") for p in parts):
        raise ValueError("No path traversal in task resource scopes")
    return s.rstrip("/")


def overlaps(a: str, b: str) -> bool:
    a, b = _normalized_resource(a), _normalized_resource(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


@dataclass(frozen=True)
class Task:
    id: str
    role: str
    goal: str
    dependencies: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self):
        if not IDENTIFIER.fullmatch(self.id) or self.role not in ROLES or not self.goal.strip():
            raise ValueError("Invalid task contract")
        for s in self.reads + self.writes:
            _normalized_resource(s)
        if len(self.goal) > 12000 or len(self.dependencies) > 40:
            raise ValueError("Task contract exceeds limits")
        if self.id in self.dependencies:
            raise ValueError("Task cannot depend on itself")


class TaskPlan:
    def __init__(self, tasks: list[Task], *, max_parallel: int = 2):
        if not 1 <= max_parallel <= 8:
            raise ValueError("Parallelism must be within 1..8")
        if len(tasks) > 200 or len({t.id for t in tasks}) != len(tasks):
            raise ValueError("Duplicate IDs or excessive tasks")
        self.tasks = {t.id: t for t in tasks}
        self.max_parallel = max_parallel
        for t in tasks:
            if any(d not in self.tasks for d in t.dependencies):
                raise ValueError("Missing dependency")
        # Detect cycles by iterative topological removal.
        done: set[str] = set()
        while len(done) < len(tasks):
            ready = [t for t in tasks if t.id not in done and set(t.dependencies) <= done]
            if not ready:
                raise ValueError("Cyclic dependency graph")
            done.update(t.id for t in ready)

    def ready(self, completed: set[str], running: set[str] | None = None,
              *, finished: set[str] | None = None) -> list[Task]:
        running = running or set()
        finished = finished or set()
        if (not completed <= self.tasks.keys() or not running <= self.tasks.keys()
                or not finished <= self.tasks.keys()):
            raise ValueError("Unknown task status")
        slots = max(0, self.max_parallel - len(running))
        locked_writes = [res for task_id in running for res in self.tasks[task_id].writes]
        locked_reads = [res for task_id in running for res in self.tasks[task_id].reads]
        output = []
        for t in self.tasks.values():
            if (t.id in completed or t.id in running or t.id in finished
                    or not set(t.dependencies) <= completed):
                continue
            if any(overlaps(p, held) for p in t.writes for held in locked_writes + locked_reads):
                continue
            if any(overlaps(p, held) for p in t.reads for held in locked_writes):
                continue
            output.append(t)
            locked_writes.extend(t.writes)
            locked_reads.extend(t.reads)
            if len(output) >= slots:
                break
        return output[:slots]
