"""Executable team-runtime tests: real async overlap, scoped DAG order, failure and bounds."""
import asyncio
from time import monotonic

import pytest

from star.orchestration import Task, TaskPlan
from star.agent_runtime import run_plan


def test_true_parallel_read_only_tasks_overlap():
    async def scenario():
        active = 0
        peak = 0
        async def worker(task, past):
            nonlocal active, peak
            assert not past
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.065)
            active -= 1
            return {"answer": task.goal, "evidence": ["test:source"]}
        plan = TaskPlan([Task("a", "research", "Find references"),
                         Task("b", "review", "Check assumptions")], max_parallel=2)
        events = []
        before = monotonic()
        result = await run_plan(plan, worker, on_event=events.append)
        assert result.completed and result.peak_concurrency == peak == 2
        assert monotonic() - before < .20
        assert [r.task_id for r in result.results] == ["a", "b"]
        assert all(r.evidence == ("test:source",) for r in result.results)
        assert sum(e["event"] == "agent_started" for e in events) == 2
    asyncio.run(scenario())


def test_dependencies_wait_for_evidence():
    async def scenario():
        started = []
        async def worker(task, previous):
            started.append(task.id)
            if task.id == "synthesis":
                assert previous["a"].status == "completed"
                assert previous["b"].status == "completed"
            return task.goal
        plan = TaskPlan([
            Task("a", "research", "Gather A"),
            Task("b", "review", "Gather B"),
            Task("synthesis", "integration", "Merge", dependencies=("a", "b")),
        ], max_parallel=3)
        result = await run_plan(plan, worker)
        assert result.completed
        assert started.index("synthesis") > started.index("a")
        assert started.index("synthesis") > started.index("b")
    asyncio.run(scenario())


def test_dependency_failure_blocks_downstream_but_not_independent_work():
    async def scenario():
        async def worker(task, previous):
            if task.id == "bad":
                raise RuntimeError("secret=do-not-echo")
            return task.goal
        plan = TaskPlan([
            Task("bad", "research", "Fail upstream"),
            Task("dependent", "review", "Unreachable", dependencies=("bad",)),
            Task("independent", "ui", "Finish independent"),
        ], max_parallel=2)
        result = await run_plan(plan, worker)
        assert result.for_id("bad").status == "failed"
        assert result.for_id("bad").error == "RuntimeError"
        assert "secret" not in result.summary()
        assert result.for_id("dependent").status == "blocked"
        assert result.for_id("independent").status == "completed"
        assert not result.completed
    asyncio.run(scenario())


def test_default_writes_denied_and_conflict_held():
    plan = TaskPlan([
        Task("write", "luau", "Change approved file", writes=("src/Module.luau",)),
    ])
    async def worker(task, past):
        return "done"
    with pytest.raises(PermissionError):
        asyncio.run(run_plan(plan, worker))
    async def allowed():
        running = 0
        max_active = 0
        async def scoped(task, previous):
            nonlocal running, max_active
            running += 1
            max_active = max(max_active, running)
            await asyncio.sleep(.025)
            running -= 1
            return "approved external worker"
        p = TaskPlan([
            Task("edit", "luau", "Edit code", writes=("src",)),
            Task("read", "review", "Read code", reads=("src/Module.luau",)),
        ], max_parallel=2)
        result = await run_plan(p, scoped, allow_writes=True)
        assert result.completed and max_active == 1
    asyncio.run(allowed())


def test_timeout_cancels_and_blocks():
    async def scenario():
        cancelled = False
        async def slow(task, previous):
            nonlocal cancelled
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return "not reached"
        p = TaskPlan([Task("slow", "research", "Timebox"),
                      Task("next", "review", "Wait", dependencies=("slow",))], max_parallel=2)
        result = await run_plan(p, slow, task_timeout=.3, total_timeout=.12)
        assert cancelled
        assert result.for_id("slow").status == "cancelled"
        assert result.for_id("next").status == "blocked"
    asyncio.run(scenario())


def test_worker_output_and_configuration_are_bounded():
    async def bad_return(task, past):
        return {"answer": "x" * 12001}
    p = TaskPlan([Task("task", "research", "Output")])
    result = asyncio.run(run_plan(p, bad_return))
    assert result.for_id("task").status == "failed"
    assert result.for_id("task").error == "ValueError"
    with pytest.raises(ValueError):
        asyncio.run(run_plan(p, bad_return, total_timeout=0))
