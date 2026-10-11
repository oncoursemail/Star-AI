"""Bounded, actual async agent-task execution using STAR's existing DAG/ownership plan.

This runs *trusted application-defined workers*, not arbitrary model-produced Python.
Workers receive only their own task contract and completed, bounded evidence.
Tool permissions and credentials are NOT inherited from another agent.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import MappingProxyType
from typing import Awaitable, Callable, Mapping
from time import monotonic
import math

from .orchestration import Task, TaskPlan


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    role: str
    status: str
    answer: str = ""
    evidence: tuple[str, ...] = ()
    elapsed_ms: int = 0
    error: str = ""


@dataclass(frozen=True)
class TeamResult:
    results: tuple[TaskResult, ...]
    elapsed_ms: int
    peak_concurrency: int

    @property
    def completed(self) -> bool:
        return all(r.status == "completed" for r in self.results)

    def for_id(self, task_id: str) -> TaskResult:
        return next(r for r in self.results if r.task_id == task_id)

    def summary(self, max_chars: int = 18000) -> str:
        """Synthesis input with task identities/provenance; never an instruction stream."""
        lines = []
        for item in self.results:
            if item.status == "completed":
                body = item.answer[:4000]
            elif item.status == "incomplete":
                body = "INCOMPLETE (deadline exceeded): " + item.answer[:4000]
            else:
                body = item.status + ": " + item.error[:250]
            lines.append(f"[TASK {item.task_id} / {item.role} / {item.status}]\n{body}")
            if item.evidence:
                lines.append("Evidence references: " + ", ".join(item.evidence[:8]))
        return "\n\n".join(lines)[:max_chars]


Worker = Callable[[Task, Mapping[str, TaskResult]], Awaitable[dict | str]]
Observer = Callable[[dict], None]


async def run_plan(
    plan: TaskPlan,
    worker: Worker,
    *,
    task_timeout: float | Callable[[Task], float] = 45.0,
    total_timeout: float = 180.0,
    allow_writes: bool = False,
    on_event: Observer | None = None,
    partial_answers: Mapping[str, str] | None = None,
) -> TeamResult:
    """Execute eligible tasks concurrently, isolating failures and enforcing scopes.

    - Real parallel async work; dependencies and read/write conflicts are held
      by TaskPlan.ready(), not inferred by a model.
    - Default is read-only. No tool execution, retries of mutations, or implicit
      privilege inheritance.
    - Each worker gets a read-only snapshot of *finished* results.
    - A failed dependency blocks descendants; independent tasks may finish.
    - Global/per-task timeouts and a hard concurrency limit prevent recursive
      swarms from growing unchecked.
    """
    seconds = {t.id: task_timeout(t) if callable(task_timeout) else task_timeout
               for t in plan.tasks.values()}
    if (any(type(v) not in (int, float) or not math.isfinite(v) or not 0.1 <= v <= 1800
            for v in seconds.values()) or type(total_timeout) not in (int, float)
            or not math.isfinite(total_timeout) or not 0.1 <= total_timeout <= 3600):
        raise ValueError("Agent time budget is outside safe bounds")
    if not callable(worker):
        raise TypeError("A trusted async worker callable is required")
    if not allow_writes and any(t.writes for t in plan.tasks.values()):
        raise PermissionError("Parallel agent writes require explicit authorization")
    if len(plan.tasks) > 32:
        raise ValueError("Live team runs are limited to 32 tasks")

    started = monotonic()
    deadline = started + total_timeout
    running: dict[str, asyncio.Task] = {}
    results: dict[str, TaskResult] = {}
    peak = 0

    def partial_for(task_id: str) -> str:
        value = (partial_answers or {}).get(task_id, "")
        return value[:12000].strip() if isinstance(value, str) else ""

    def observe(event: dict) -> None:
        if on_event:
            try:
                on_event(dict(event))
            except Exception:
                # UI notifications are best effort; completion records stay true.
                pass

    async def execute_one(task: Task, snapshot: Mapping[str, TaskResult]):
        began = monotonic()
        try:
            # A later synthesis can use a rate learned from earlier specialists.
            budget = task_timeout(task) if callable(task_timeout) else seconds[task.id]
            raw = await asyncio.wait_for(worker(task, snapshot), timeout=budget)
            if isinstance(raw, str):
                answer, evidence = raw, ()
            elif isinstance(raw, dict):
                answer = raw.get("answer", "")
                evidence = raw.get("evidence", ())
            else:
                raise TypeError("Worker must return text or a structured answer")
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 12000:
                raise ValueError("Agent result must be nonempty text (max 12,000 chars)")
            if not isinstance(evidence, (list, tuple)) or len(evidence) > 20 or any(
                not isinstance(v, str) or len(v) > 500 for v in evidence
            ):
                raise ValueError("Agent evidence list exceeds budget")
            return TaskResult(task.id, task.role, "completed", answer,
                              tuple(evidence), int((monotonic() - began) * 1000))
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            partial = partial_for(task.id)
            return TaskResult(task.id, task.role, "incomplete" if partial else "timed_out",
                              answer=partial, elapsed_ms=int((monotonic() - began) * 1000),
                              error="Stage time budget exceeded")
        except Exception as exc:
            # Do not echo raw tool outputs, local paths or potential secrets.
            return TaskResult(task.id, task.role, "failed",
                              elapsed_ms=int((monotonic() - began) * 1000),
                              error=type(exc).__name__)

    def block_dependents() -> bool:
        changed = False
        for task in plan.tasks.values():
            if task.id in results or task.id in running:
                continue
            if any(dep in results and results[dep].status != "completed" for dep in task.dependencies):
                results[task.id] = TaskResult(task.id, task.role, "blocked",
                                              error="An upstream dependency did not complete")
                observe({"event": "agent_blocked", "task": task.id, "role": task.role})
                changed = True
        return changed

    try:
        while len(results) < len(plan.tasks):
            if monotonic() >= deadline:
                break
            while block_dependents():
                pass
            successful = {tid for tid, entry in results.items() if entry.status == "completed"}
            # Terminal non-successes must not occupy ready() slots repeatedly.
            ready = plan.ready(successful, set(running), finished=set(results))
            for item in ready:
                if item.id in results:
                    continue
                # A plan.ready() result may depend on an already failed task.
                if any(dep in results and results[dep].status != "completed" for dep in item.dependencies):
                    continue
                available = MappingProxyType(dict(results))
                running[item.id] = asyncio.create_task(execute_one(item, available), name=f"star-{item.role}-{item.id}")
                peak = max(peak, len(running))
                observe({"event": "agent_started", "task": item.id, "role": item.role,
                         "active": len(running)})
            if not running:
                # No runnable tasks remain: unexpected planner state or failed dependencies.
                for item in plan.tasks.values():
                    if item.id not in results:
                        results[item.id] = TaskResult(item.id, item.role, "blocked",
                                                      error="No runnable dependency-safe tasks remain")
                break
            complete, _ = await asyncio.wait(
                set(running.values()), timeout=max(0, deadline - monotonic()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not complete:
                break
            # Process in plan declaration order so the outcome is deterministic.
            for item in plan.tasks.values():
                job = running.get(item.id)
                if job not in complete:
                    continue
                try:
                    entry = job.result()
                except asyncio.CancelledError:
                    entry = TaskResult(item.id, item.role, "cancelled", error="Worker cancelled")
                results[item.id] = entry
                del running[item.id]
                observe({"event": "agent_finished", "task": item.id, "role": item.role,
                         "status": entry.status, "elapsed_ms": entry.elapsed_ms})
    finally:
        if running:
            for task in running.values():
                task.cancel()
            await asyncio.gather(*running.values(), return_exceptions=True)
            for item in plan.tasks.values():
                if item.id in running and item.id not in results:
                    partial = partial_for(item.id)
                    status = "incomplete" if partial else "cancelled"
                    results[item.id] = TaskResult(item.id, item.role, status,
                                                  answer=partial, error="Global team time budget exceeded")
                    observe({"event": "agent_finished", "task": item.id,
                             "role": item.role, "status": status})
    for item in plan.tasks.values():
        if item.id not in results:
            results[item.id] = TaskResult(item.id, item.role, "blocked",
                                          error="Uncompleted dependency")
    return TeamResult(tuple(results[t] for t in plan.tasks),
                      int((monotonic() - started) * 1000), peak)
