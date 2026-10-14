"""Real-input validation messages contain repair guidance and never expose values."""
import pytest

from star.agent_resource_planner import ResourcePool, ModelWorker, TaskDemand, preview_assignments
from star.agent_skills import SkillLibrary, _frontmatter
from star.asset_forge import plan_building, terrain_height
from star.autonomous_research import EvidenceBook, begin_research, finish_research
from star.orchestration import Task, TaskPlan


def preview(**overrides):
    plan = TaskPlan([Task("a", "research", "Inspect source")])
    params = dict(
        demands={"a": TaskDemand("a", 1, 1, frozenset({"read"}))},
        pools=(ResourcePool("p", 64, 2),),
        workers=(ModelWorker("w", "p", frozenset({"read"})),),
    )
    params.update(overrides)
    return preview_assignments(plan, **params)


@pytest.mark.parametrize("call,field", [
    (lambda: ResourcePool("", 64, 2), "id"),
    (lambda: ResourcePool("p", 0, 2), "memory_mib"),
    (lambda: ResourcePool("p", 64, 0), "cpu_threads"),
    (lambda: ResourcePool("p", 64, 2, max_jobs=0), "max_jobs"),
    (lambda: ResourcePool("p", 64, 2, boundary="x"), "boundary"),
    (lambda: ModelWorker("", "p", frozenset({"read"})), "id"),
    (lambda: ModelWorker("w", "p", frozenset({"read"}), slots=0), "slots"),
    (lambda: ModelWorker("w", "p", frozenset({0})), "capabilities"),
    (lambda: TaskDemand("", 1, 1, frozenset({"read"})), "task_id"),
    (lambda: TaskDemand("a", 0, 1, frozenset({"read"})), "memory_mib"),
    (lambda: TaskDemand("a", 1, 0, frozenset({"read"})), "cpu_threads"),
    (lambda: TaskDemand("a", 1, 1, frozenset({0})), "capabilities"),
    (lambda: TaskDemand("a", 1, 1, frozenset({"read"}), priority=101), "priority"),
    (lambda: TaskDemand("a", 1, 1, frozenset({"read"}), allow_cloud="yes"), "allow_cloud"),
    (lambda: preview(enable_cloud="yes"), "enable_cloud"),
    (lambda: preview(demands={}), "demands"),
    (lambda: preview(pools=(ResourcePool("p",64,2),)*2), "ResourcePool.id"),
    (lambda: preview(workers=(ModelWorker("w","p",frozenset({"read"})),)*2), "ModelWorker.id"),
    (lambda: preview(workers=(ModelWorker("w","missing",frozenset({"read"})),)), "worker.pool_id"),
    (lambda: preview(completed=frozenset({"unknown"})), "plan.tasks"),
    (lambda: preview(completed=frozenset({"a"}), finished=frozenset({"a"})), "task"),
    (lambda: preview(running={"a":"unknown"}), "ModelWorker.id"),
    (lambda: plan_building(style="other"), "style"),
    (lambda: terrain_height(0, 0, biome="other"), "biome"),
])
def test_real_validation_failures_name_fields_and_next_step(call, field):
    with pytest.raises((ValueError, PermissionError)) as exc:
        call()
    msg = str(exc.value)
    assert field in msg and len(msg) <= 200
    assert any(word in msg for word in (
        "Choose", "Correct", "Set", "Reduce", "Fix", "Supply", "Remove",
        "Select", "Resolve", "Use", "Rename", "Match"))


def test_skill_errors_are_repairable(tmp_path):
    lib = SkillLibrary(workspace=None, home=tmp_path)
    with pytest.raises(ValueError, match="Invalid skill name"):
        lib.load("Wrong")
    with pytest.raises(ValueError, match="SKILL.md needs YAML frontmatter"):
        _frontmatter("plain")
    with pytest.raises(ValueError, match="SKILL.md frontmatter is invalid or too long"):
        _frontmatter("---\nname: incomplete\n")
    folder = tmp_path / "skills" / "sample-skill"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Test skill\n---\nBody\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid reference path"):
        lib.read_reference("sample-skill", "bad\\name")
    with pytest.raises(PermissionError, match="Only skill references"):
        lib.read_reference("sample-skill", "../outside.txt")
    with pytest.raises(PermissionError, match="Reference is unavailable"):
        lib.read_reference("sample-skill", "references/absent.txt")


def test_research_fields_are_actionable(tmp_path):
    with pytest.raises(ValueError, match="Invalid research project"):
        begin_research(tmp_path, "", "Valid objective")
    with pytest.raises(ValueError, match="Invalid research objective"):
        begin_research(tmp_path, "ok", "")
    rid = begin_research(tmp_path, "ok", "Valid objective")
    with pytest.raises(ValueError, match="Invalid research completion status"):
        finish_research(tmp_path, rid, status="pending", book=EvidenceBook(),
                        elapsed_ms=0, peak_concurrency=1)
    with pytest.raises(ValueError, match="Invalid research metric"):
        finish_research(tmp_path, rid, status="failed", book=EvidenceBook(),
                        elapsed_ms=-1, peak_concurrency=1)


@pytest.mark.parametrize("hostile", [
    "sensitive-like-text-" + "z" * 100,
    "z" * 5000,
    "Bearer " + "z" * 100,
])
def test_hostile_input_never_reappears_in_messages(tmp_path, hostile):
    for callback in (
        lambda: ResourcePool(hostile, 64, 2),
        lambda: TaskDemand(hostile, 1, 1, frozenset({"read"})),
        lambda: SkillLibrary(workspace=None, home=tmp_path).load(hostile),
        lambda: plan_building(style=hostile),
        lambda: begin_research(tmp_path, hostile, "Valid objective"),
    ):
        with pytest.raises(ValueError) as exc:
            callback()
        msg = str(exc.value)
        assert len(msg) <= 200 and hostile not in msg and hostile[:12] not in msg


def test_correct_inputs_preserved(tmp_path):
    assert ResourcePool("pool", 64, 2).cpu_threads == 2
    assert plan_building(style="classic-studs")["stage"] == "plan_only"
    assert begin_research(tmp_path, "ok", "Valid objective")
