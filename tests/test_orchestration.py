"""Contract validation and resource-safe scheduling without starting workers."""
import pytest

from star.orchestration import Task, TaskPlan, overlaps


def task(identifier, *, reads=(), writes=(), dependencies=(), goal="Build the game", role="luau"):
    return Task(identifier, role, goal, dependencies=dependencies, reads=reads, writes=writes)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("game/map", "game/map", True),
        ("game/map", "game/map/terrain", True),
        ("game/map/terrain", "game/map", True),
        ("game/map", "game/maps", False),
        ("game/ui", "game/world", False),
    ],
)
def test_resource_overlap_has_path_component_boundaries(left, right, expected):
    assert overlaps(left, right) is expected


@pytest.mark.parametrize("invalid", ["", "/root", "a//b", "a/../b", "a/./b", "a\\b", 42])
def test_resource_scopes_reject_unsafe_paths(invalid):
    with pytest.raises(ValueError, match="resource|Resource|path"):
        overlaps(invalid, "game")
    with pytest.raises(ValueError, match="resource|Resource|path"):
        task("safe", writes=(invalid,))


@pytest.mark.parametrize(
    "values",
    [
        {"identifier": ""},
        {"identifier": "-leading"},
        {"identifier": "a" * 81},
        {"role": "administrator"},
        {"goal": " \n "},
        {"dependencies": ("same",)},
        {"goal": "x" * 12001},
        {"dependencies": tuple(f"dep{i}" for i in range(41))},
    ],
)
def test_task_rejects_invalid_contracts(values):
    with pytest.raises(ValueError):
        task(values.pop("identifier", "same"), **values)


def test_task_accepts_documented_limits():
    large = task("a" * 80, goal="x" * 12000, dependencies=tuple(f"dep{i}" for i in range(40)))
    assert len(large.id) == 80
    assert len(large.goal) == 12000
    assert len(large.dependencies) == 40


@pytest.mark.parametrize("parallel", [0, 9])
def test_plan_rejects_parallelism_outside_one_to_eight(parallel):
    with pytest.raises(ValueError, match="Parallelism"):
        TaskPlan([task("one")], max_parallel=parallel)


def test_plan_rejects_duplicate_missing_and_cyclic_dependencies():
    with pytest.raises(ValueError, match="Duplicate"):
        TaskPlan([task("same"), task("same")])
    with pytest.raises(ValueError, match="Missing dependency"):
        TaskPlan([task("one", dependencies=("gone",))])
    with pytest.raises(ValueError, match="Cyclic"):
        TaskPlan([task("a", dependencies=("b",)), task("b", dependencies=("a",))])
    with pytest.raises(ValueError, match="excessive"):
        TaskPlan([task(f"t{i}") for i in range(201)])


def test_plan_respects_parallel_limit_and_existing_read_write_locks():
    plan = TaskPlan(
        [
            task("writer", writes=("game/world",)),
            task("reader", reads=("game/world/trees",)),
            task("independent", writes=("game/ui",)),
            task("after", dependencies=("writer",), writes=("game/world/trees",)),
        ],
        max_parallel=2,
    )
    assert [t.id for t in plan.ready(set())] == ["writer", "independent"]
    assert [t.id for t in plan.ready(set(), running={"writer"})] == ["independent"]
    assert plan.ready(set(), running={"writer", "independent"}) == []
    assert [t.id for t in plan.ready({"writer"})] == ["reader", "independent"]
    assert [t.id for t in plan.ready({"writer", "reader"}, finished={"independent"})] == ["after"]


def test_running_read_lock_prevents_overlapping_writer():
    plan = TaskPlan(
        [task("read", reads=("world",)), task("write", writes=("world/props",)),
         task("other", writes=("hud",))],
        max_parallel=3,
    )
    assert [t.id for t in plan.ready(set())] == ["read", "other"]
    assert [t.id for t in plan.ready(set(), running={"read"})] == ["other"]


@pytest.mark.parametrize("status", ["completed", "running", "finished"])
def test_unknown_task_status_is_rejected(status):
    plan = TaskPlan([task("known")])
    options = {"completed": set(), "running": set(), "finished": set()}
    options[status] = {"unknown"}
    with pytest.raises(ValueError, match="Unknown task status"):
        plan.ready(options["completed"], running=options["running"], finished=options["finished"])


def test_empty_plan_has_no_ready_tasks():
    assert TaskPlan([]).ready(set()) == []
