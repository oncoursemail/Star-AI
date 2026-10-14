"""Offline acceptance tests for resource-bounded concurrent STAR agent plans.

No live models, network requests, Roblox Studio, files, or credentials are used.
"""
import pytest

from star.agent_resource_planner import (
    ResourcePool, ModelWorker, TaskDemand, preview_assignments,
)
from star.orchestration import Task, TaskPlan


def task(task_id, *, deps=(), reads=(), writes=()):
    return Task(task_id, "research", f"Analyze {task_id} with evidence",
                dependencies=deps, reads=reads, writes=writes)


def demand(task_id, *, memory=100, cpu=2, capability="research",
           interactive=False, allow_cloud=False, priority=0):
    return TaskDemand(task_id, memory, cpu, frozenset({capability}),
                      interactive, allow_cloud, priority)


def worker(worker_id, pool="server", *, slots=1, capability="research"):
    return ModelWorker(worker_id, pool, frozenset({capability}), slots)


def pool(pool_id="server", *, mem=1000, cpu=16, jobs=2, boundary="private"):
    return ResourcePool(pool_id, mem, cpu, jobs, boundary)


def ids(preview):
    return [x.task_id for x in preview.assignments]


def test_independent_agents_run_in_parallel_on_separate_models():
    plan = TaskPlan([task("research"), task("design")], max_parallel=2)
    result = preview_assignments(
        plan,
        {"research": demand("research", cpu=8),
         "design": demand("design", cpu=8)},
        (pool(cpu=16),),
        (worker("fast"), worker("main")),
    )
    assert ids(result) == ["research", "design"]
    assert {x.worker_id for x in result.assignments} == {"fast", "main"}
    assert result.waiting == ()


def test_models_on_same_cpu_share_real_resource_pool():
    plan = TaskPlan([task("a"), task("b")], max_parallel=2)
    result = preview_assignments(
        plan, {"a": demand("a"), "b": demand("b")},
        (pool(jobs=1),),
        (worker("main", slots=2), worker("fast", slots=2)),
    )
    assert ids(result) == ["a"]
    assert result.waiting == ("b",)


def test_explicit_cpu_memory_cap_prevents_oversubscription():
    plan = TaskPlan([task("a"), task("b")], max_parallel=2)
    result = preview_assignments(
        plan, {"a": demand("a", memory=700, cpu=10),
               "b": demand("b", memory=700, cpu=10)},
        (pool(mem=1200, cpu=12, jobs=2),),
        (worker("main", slots=2),),
    )
    assert ids(result) == ["a"]
    assert result.waiting == ("b",)


def test_interactive_foreground_precedes_background():
    plan = TaskPlan([task("night_school"), task("owner")], max_parallel=1)
    result = preview_assignments(
        plan, {"night_school": demand("night_school"),
               "owner": demand("owner", interactive=True)},
        (pool(jobs=1),),
        (worker("main"),),
    )
    assert ids(result) == ["owner"]
    assert result.waiting == ("night_school",)


def test_waiting_foreground_prevents_new_background_work():
    plan = TaskPlan([task("night_school"), task("owner")], max_parallel=2)
    result = preview_assignments(
        plan, {"night_school": demand("night_school", capability="research"),
               "owner": demand("owner", capability="studio", interactive=True)},
        (pool(jobs=2),),
        (worker("main"),),
    )
    assert result.assignments == ()
    assert result.waiting == ("owner", "night_school")


def test_dependent_review_waits_until_upstream_completes():
    plan = TaskPlan([task("write"), task("review", deps=("write",))], max_parallel=2)
    requests = {"write": demand("write"), "review": demand("review")}
    before = preview_assignments(plan, requests, (pool(),), (worker("main", slots=2),))
    assert ids(before) == ["write"]
    after = preview_assignments(plan, requests, (pool(),), (worker("main", slots=2),),
                                completed=frozenset({"write"}))
    assert ids(after) == ["review"]


def test_failed_dependency_is_not_scheduled():
    plan = TaskPlan([task("write"), task("review", deps=("write",))], max_parallel=2)
    result = preview_assignments(
        plan, {"write": demand("write"), "review": demand("review")},
        (pool(),), (worker("main"),),
        finished=frozenset({"write"}),
    )
    assert result.assignments == ()


def test_live_running_slots_and_budget_are_counted():
    plan = TaskPlan([task("a"), task("b")], max_parallel=2)
    result = preview_assignments(
        plan, {"a": demand("a", cpu=9), "b": demand("b", cpu=9)},
        (pool(cpu=12, jobs=2),), (worker("main", slots=2),),
        running={"a": "main"},
    )
    assert result.assignments == ()
    assert result.waiting == ("b",)


def test_cloud_requires_both_host_and_task_opt_in():
    plan = TaskPlan([task("a")])
    cloud = pool("remote", boundary="cloud")
    cloud_worker = worker("cloud-agent", "remote")
    denied = preview_assignments(
        plan, {"a": demand("a", allow_cloud=False)},
        (cloud,), (cloud_worker,), enable_cloud=True,
    )
    assert denied.assignments == ()
    denied2 = preview_assignments(
        plan, {"a": demand("a", allow_cloud=True)},
        (cloud,), (cloud_worker,), enable_cloud=False,
    )
    assert denied2.assignments == ()
    allowed = preview_assignments(
        plan, {"a": demand("a", allow_cloud=True)},
        (cloud,), (cloud_worker,), enable_cloud=True,
    )
    assert allowed.assignments[0].worker_id == "cloud-agent"


def test_trusted_local_worker_is_preferred_to_cloud_even_if_cloud_is_listed_first():
    plan = TaskPlan([task("a")])
    result = preview_assignments(
        plan, {"a": demand("a", allow_cloud=True)},
        (pool("cloud", boundary="cloud"), pool("local")),
        (worker("aa-cloud", "cloud"), worker("zz-local", "local")),
        enable_cloud=True,
    )
    assert result.assignments[0].worker_id == "zz-local"


def test_writes_are_not_silently_approved_for_agents():
    plan = TaskPlan([task("change", writes=("src/app.py",))])
    with pytest.raises(PermissionError):
        preview_assignments(plan, {"change": demand("change")},
                            (pool(),), (worker("main"),))


def test_unknown_worker_running_refused_instead_of_overallocating():
    plan = TaskPlan([task("a")])
    with pytest.raises(ValueError):
        preview_assignments(plan, {"a": demand("a")},
                            (pool(),), (worker("main"),),
                            running={"a": "untrusted-worker"})


def test_invalid_worker_pool_and_task_contracts_fail_closed():
    with pytest.raises(ValueError):
        ResourcePool("server", 0, 48)
    with pytest.raises(ValueError):
        ResourcePool("server", 1024, 48, boundary="unknown")
    with pytest.raises(ValueError):
        ModelWorker("broken", "server", frozenset({"research"}), 0)
    with pytest.raises(ValueError):
        TaskDemand("bad", 1, 1, frozenset({"research"}), allow_cloud="yes")
    with pytest.raises(ValueError):
        preview_assignments(TaskPlan([task("a")]),
                            {"a": demand("another")},
                            (pool(),), (worker("main"),))


def test_status_contradictions_fail_closed():
    plan = TaskPlan([task("a")])
    with pytest.raises(ValueError):
        preview_assignments(
            plan, {"a": demand("a")}, (pool(),), (worker("main"),),
            completed=frozenset({"a"}), running={"a": "main"},
        )


def test_idempotent_pure_planning_does_not_mutate_inputs():
    plan = TaskPlan([task("a"), task("b")], max_parallel=2)
    requests = {"a": demand("a"), "b": demand("b")}
    running = {}
    kwargs = dict(plan=plan, demands=requests, pools=(pool(),), workers=(worker("main", slots=2),),
                  running=running)
    first = preview_assignments(**kwargs)
    second = preview_assignments(**kwargs)
    assert first == second
    assert running == {}
    assert requests["a"].memory_mib == 100
