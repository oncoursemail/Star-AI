"""Exercise the real planner against the shipped templates and catalogs."""
import pytest

from star.build_planner import build_plan, next_step
from star.studio_milestones import load_milestones


@pytest.mark.parametrize("template", ("obby", "tycoon", "simulator", "rounds"))
def test_each_template_has_ordered_steps_and_real_source_paths(template):
    from pathlib import Path

    plan = build_plan("A fun starter game", template)
    assert len(plan.milestones) == 4
    assert plan.milestones[0].depends_on == ()
    assert all(step.depends_on == (plan.milestones[i - 1].id,)
               for i, step in enumerate(plan.milestones) if i)
    assert all(step.token_budget > 0 and step.template_module for step in plan.milestones)
    assert all(Path(filename).is_file() for step in plan.milestones for filename in step.create)
    known = {m.id for m in load_milestones(template)} if template != "simulator" else set()
    assert all(set(step.check_ids) <= known for step in plan.milestones)
    assert next_step(plan).milestone == plan.milestones[0]


def test_failed_check_returns_repair_target_and_stops_at_limit():
    plan = build_plan("Jump between checkpoints", "obby", max_failed_repairs=2)
    check = plan.milestones[0].check_ids[0]
    outcome = next_step(plan, {check: False}, failed_repairs={check: 1})
    assert (outcome.kind, outcome.failed_check, outcome.milestone.id) == (
        "repair", check, "course")
    stopped = next_step(plan, {check: False}, failed_repairs={check: 2})
    assert (stopped.kind, stopped.failed_check) == ("stopped", check)


def test_passed_checks_advance_but_missing_check_never_passes():
    plan = build_plan("An obby", "obby")
    assert next_step(plan, {"obby.checkpoints": True}).milestone.id == "hazards"
    assert next_step(plan, {"obby.checkpoints": True, "obby.kill_handlers": True,
                            "obby.finish": True}).kind == "complete"


def test_unverified_simulator_does_not_claim_completion():
    plan = build_plan("Clicker with pets", "simulator")
    assert plan.unsupported == ()
    assert all(not step.check_ids for step in plan.milestones)
    assert next_step(plan, {}).kind == "build"


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
