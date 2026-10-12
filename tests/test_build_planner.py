"""Exercise the real planner against the shipped templates and catalogs."""
from pathlib import Path

import pytest

from star.build_planner import build_plan, next_step
from star.studio_milestones import load_milestones


@pytest.mark.parametrize("template", ("obby", "tycoon", "simulator", "rounds"))
def test_each_template_has_ordered_steps_and_real_source_paths(template):
    plan = build_plan("A fun starter game", template)
    assert len(plan.milestones) == 4
    assert plan.milestones[0].depends_on == ()
    assert all(step.depends_on == (plan.milestones[i - 1].id,)
               for i, step in enumerate(plan.milestones) if i)
    assert all(step.token_budget > 0 and step.template_module for step in plan.milestones)
    assert all(Path(filename).is_absolute() and Path(filename).is_file()
               for step in plan.milestones for filename in step.create)
    known = {m.id for m in load_milestones(template)} if template != "simulator" else set()
    assert all(set(step.check_ids) <= known for step in plan.milestones)
    checks = [check for step in plan.milestones for check in step.check_ids]
    assert len(checks) == len(set(checks))
    assert next_step(plan).milestone == plan.milestones[0]


@pytest.mark.parametrize("template", ("obby", "tycoon", "simulator", "rounds"))
def test_source_paths_are_independent_of_working_directory(template, monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples" / "roblox-templates" / template
    original = build_plan("A fun starter game", template)
    monkeypatch.chdir(tmp_path)
    plan = build_plan("A fun starter game", template)
    assert plan == original
    for step in plan.milestones:
        assert Path(step.create[0]) == root / step.template_module
        for filename in step.create:
            path = Path(filename)
            assert path.is_absolute()
            assert path.is_relative_to(root)
            assert path.is_file()


@pytest.mark.parametrize("completed", ({"course"}, {"course", "checkpoints"}))
def test_failed_check_returns_repair_target_and_stops_at_limit(completed):
    plan = build_plan("Jump between checkpoints", "obby", max_failed_repairs=2)
    check = plan.milestones[1].check_ids[0]
    outcome = next_step(plan, {check: False}, failed_repairs={check: 1},
                        completed_steps=completed)
    assert (outcome.kind, outcome.failed_check, outcome.milestone.id) == (
        "repair", check, "checkpoints")
    stopped = next_step(plan, {check: False}, failed_repairs={check: 2},
                        completed_steps=completed)
    assert (stopped.kind, stopped.failed_check, stopped.milestone.id) == (
        "stopped", check, "checkpoints")


def test_obby_course_and_checkpoints_are_scheduled_separately():
    plan = build_plan("An obby", "obby")
    course, checkpoints = plan.milestones[:2]
    assert course.check_ids == ()
    assert checkpoints.check_ids == ("obby.checkpoints",)
    first = next_step(plan)
    assert (first.kind, first.milestone.id) == ("build", "course")
    second = next_step(plan, completed_steps={"course"})
    assert (second.kind, second.milestone.id) == ("build", "checkpoints")
    third = next_step(plan, {"obby.checkpoints": True}, completed_steps={"course"})
    assert (third.kind, third.milestone.id) == ("build", "hazards")


def test_passed_checks_advance_but_missing_check_never_passes():
    plan = build_plan("An obby", "obby")
    # A checkpoint pass alone cannot account for an unbuilt course.
    assert next_step(plan, {"obby.checkpoints": True}).milestone.id == "course"
    results = {"obby.checkpoints": True, "obby.kill_handlers": True, "obby.finish": True}
    assert next_step(plan, results).milestone.id == "course"
    assert next_step(plan, results, completed_steps={"course"}).kind == "complete"
    results.pop("obby.finish")
    pending = next_step(plan, results, completed_steps={"course"})
    assert (pending.kind, pending.milestone.id) == ("build", "finish")


@pytest.mark.parametrize("result,kind", [(None, "build"), (False, "repair"), (1, "build")])
def test_completed_steps_do_not_bypass_missing_or_failed_checks(result, kind):
    plan = build_plan("An obby", "obby")
    results = {} if result is None else {"obby.checkpoints": result}
    outcome = next_step(plan, results, completed_steps={step.id for step in plan.milestones})
    assert (outcome.kind, outcome.milestone.id) == (kind, "checkpoints")


def test_zero_repair_limit_stops_on_first_failed_check():
    plan = build_plan("An obby", "obby", max_failed_repairs=0)
    outcome = next_step(plan, {"obby.checkpoints": False}, completed_steps={"course"})
    assert (outcome.kind, outcome.failed_check) == ("stopped", "obby.checkpoints")


def test_unverified_simulator_does_not_claim_completion():
    plan = build_plan("Clicker with pets", "simulator")
    assert plan.unsupported == ()
    assert all(not step.check_ids for step in plan.milestones)
    assert next_step(plan, {}).kind == "build"


def test_simulator_completed_steps_advance_in_order_and_finish():
    plan = build_plan("Clicker with pets", "simulator")
    completed = set()
    for step in plan.milestones:
        outcome = next_step(plan, completed_steps=frozenset(completed))
        assert (outcome.kind, outcome.milestone) == ("build", step)
        completed.add(step.id)
    outcome = next_step(plan, completed_steps=completed)
    assert outcome.kind == "complete"
    assert outcome.milestone is None
    assert outcome.failed_check is None
    assert "no Studio checks are available" in outcome.reason


def test_checkless_steps_require_their_own_completed_ids():
    plan = build_plan("A simulator", "simulator")
    # Later/unknown IDs and booleans in the check-result map cannot finish economy.
    completed = {"service", "saving", "hud", "unknown"}
    outcome = next_step(plan, {"economy": True}, completed_steps=completed)
    assert (outcome.kind, outcome.milestone.id) == ("build", "economy")


def test_next_step_does_not_mutate_caller_progress():
    plan = build_plan("An obby", "obby")
    results = {"obby.checkpoints": False}
    failures = {"obby.checkpoints": 1}
    completed = {"course"}
    first = next_step(plan, results, failed_repairs=failures, completed_steps=completed)
    assert first == next_step(plan, results, failed_repairs=failures, completed_steps=completed)
    assert results == {"obby.checkpoints": False}
    assert failures == {"obby.checkpoints": 1}
    assert completed == {"course"}


@pytest.mark.parametrize("brief,template", [
    ("A competitive obby with lava", "obby"),
    ("A tycoon with a carpet factory", "tycoon"),
    ("Rounds game with trumpet sounds", "rounds"),
    ("Obby with a trademark logo", "obby"),
    ("An obby that has begun", "obby"),
])
def test_ordinary_briefs_do_not_match_capability_substrings(brief, template):
    plan = build_plan(brief, template)
    assert plan.unsupported == ()
    outcome = next_step(plan)
    assert (outcome.kind, outcome.milestone) == ("build", plan.milestones[0])


@pytest.mark.parametrize("keyword,capability", [
    ("pet", "pet system"),
    ("pets", "pet system"),
    ("gun", "combat weapons"),
    ("guns", "combat weapons"),
    ("weapon", "combat weapons"),
    ("weapons", "combat weapons"),
    ("FPS", "combat weapons"),
    ("shooter", "combat weapons"),
    ("shooters", "combat weapons"),
    ("trade", "multiplayer trading"),
    ("trades", "multiplayer trading"),
    ("trading", "multiplayer trading"),
    ("procedural", "procedural world generation"),
    ("random terrain", "procedural world generation"),
    ("world generation", "procedural world generation"),
    ("vehicle", "vehicle physics"),
    ("vehicles", "vehicle physics"),
    ("driving", "vehicle physics"),
    ("car racing", "vehicle physics"),
])
def test_whole_capability_words_and_phrases_remain_unsupported(keyword, capability):
    # Uppercase and punctuation must not bypass the word-boundary filter.
    plan = build_plan(f"An obby with ({keyword.upper()}).", "obby")
    assert plan.unsupported == (capability,)
    outcome = next_step(plan)
    assert outcome.kind == "unsupported"
    assert outcome.milestone is None


@pytest.mark.parametrize("brief", [
    "An obby with random rewards and terrain",
    "An obby with a world map and generation counter",
    "An obby with a car display and racing stripes",
])
def test_multiword_capabilities_are_not_matched_as_separate_words(brief):
    plan = build_plan(brief, "obby")
    assert plan.unsupported == ()
    assert next_step(plan).kind == "build"


def test_simulator_pet_exception_does_not_hide_other_capabilities():
    plan = build_plan("A simulator with pets and guns", "simulator")
    assert plan.unsupported == ("combat weapons",)
    assert next_step(plan).kind == "unsupported"


@pytest.mark.parametrize("template", ("obby", "tycoon", "simulator", "rounds"))
def test_out_of_scope_brief_reports_missing_capability(template):
    plan = build_plan("Build an FPS with guns and multiplayer trading", template)
    assert "combat weapons" in plan.unsupported
    assert "multiplayer trading" in plan.unsupported
    assert next_step(plan).kind == "unsupported"


@pytest.mark.parametrize("brief,template,limit", [
    ("", "obby", 1), ("Hi", "unknown", 1), ("Hi", "obby", -1), ("Hi", "obby", True),
])
def test_rejects_invalid_inputs(brief, template, limit):
    with pytest.raises(ValueError):
        build_plan(brief, template, max_failed_repairs=limit)
