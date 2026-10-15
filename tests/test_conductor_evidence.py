"""STAR Conductor evidence is a candidate review gate, not a training pipeline."""
from dataclasses import replace

import pytest

from star.conductor_evidence import (
    CheckEvidence, TaskEvidence, assess_learning_readiness,
)

SOURCE = "a" * 40
ARTIFACT = "b" * 64
REPORT = "c" * 64


def check(**changes):
    fields = dict(
        name="tests", status="passed", provenance="host_tool",
        verifier_id="pytest-runner", project_id="roblox-project",
        source_sha=SOURCE, artifact_sha256=ARTIFACT, report_sha256=REPORT,
    )
    fields.update(changes)
    return CheckEvidence(**fields)


def task(**changes):
    fields = dict(
        mission_id="mission-1", project_id="roblox-project", task_id="task-1",
        worker_id="claude-agent", provider_id="anthropic", transport="coding_agent",
        model_id="sonnet", status="completed", source_sha=SOURCE,
        artifact_sha256=ARTIFACT, checks=(check(),),
    )
    fields.update(changes)
    return TaskEvidence(**fields)


def decide(candidate, required_checks=("tests",)):
    return assess_learning_readiness(
        candidate, expected_project="roblox-project", required_checks=required_checks,
    )


def test_real_host_check_makes_only_a_review_candidate_not_learned():
    result = decide(task())
    assert result.eligible_for_review
    assert "review still required" in result.reason
    assert result.verified_checks == ("tests",)


@pytest.mark.parametrize("status", ["failed", "cancelled", "incomplete"])
def test_failed_or_interrupted_worker_is_never_eligible(status):
    assert not decide(task(status=status)).eligible_for_review


def test_no_checks_or_only_agent_self_claim_is_not_evidence():
    assert not decide(task(checks=())).eligible_for_review
    assert not decide(task(checks=(check(provenance="model_claim"),))).eligible_for_review
    # An arbitrary model can *claim* it has a different verifier identity. Its
    # provenance still cannot be upgraded by this module.
    assert not decide(task(checks=(
        check(provenance="model_claim", verifier_id="independent-judge"),
    ))).eligible_for_review


@pytest.mark.parametrize("status", ["failed", "error"])
def test_host_observed_failure_blocks_even_if_another_check_passed(status):
    outcome = decide(task(checks=(
        check(), check(name="security", status=status, report_sha256="d" * 64),
    )))
    assert not outcome.eligible_for_review
    assert outcome.reason == "Independent check failed"


def test_self_check_even_from_host_tool_cannot_count():
    result = decide(task(checks=(check(verifier_id="claude-agent"),)))
    assert not result.eligible_for_review
    assert result.reason == "Worker cannot independently verify itself"


@pytest.mark.parametrize("change", [
    {"project_id": "other-project"},
    {"source_sha": "d" * 40},
    {"artifact_sha256": "e" * 64},
])
def test_check_bound_to_exact_project_source_and_artifact(change):
    assert decide(task(checks=(check(**change),))).reason == "Check source, artifact, or project mismatch"


def test_request_must_match_authorized_project():
    assert not assess_learning_readiness(task(), expected_project="different").eligible_for_review


def test_scoped_required_verification_classes():
    candidate = task(checks=(check(), check(name="native_studio", report_sha256="d" * 64)))
    result = decide(candidate, ("tests", "native_studio"))
    assert result.eligible_for_review
    assert result.verified_checks == ("native_studio", "tests")
    assert not decide(task(), ("tests", "native_studio")).eligible_for_review


def test_skipped_or_model_claim_does_not_satisfy_required_check():
    assert not decide(task(checks=(check(status="skipped"),))).eligible_for_review
    both = task(checks=(check(name="visual", provenance="model_claim"), check()))
    assert not decide(both, ("tests", "visual")).eligible_for_review


@pytest.mark.parametrize("required", [(), ("all",), ("tests", "tests"), ["tests"]])
def test_required_check_policy_is_strict(required):
    with pytest.raises(ValueError):
        decide(task(), required)


@pytest.mark.parametrize("bad", [
    {"project_id": "../other"},
    {"mission_id": "bad/id"},
    {"task_id": "x" * 81},
    {"source_sha": "a" * 39},
    {"artifact_sha256": "0" * 63},
    {"model_id": "claude; rm -rf /"},
    {"transport": "not-a-provider"},
    {"status": "passed"},  # task status vs independent check status
    {"checks": [check()]},
    {"checks": (check(),) * 25},
    {"checks": ({"name": "tests"},)},
])
def test_task_contract_rejects_unsafe_or_invalid_metadata(bad):
    with pytest.raises(ValueError):
        task(**bad)


@pytest.mark.parametrize("bad", [
    {"report_sha256": "c" * 63},
    {"source_sha": "d" * 39},
    {"artifact_sha256": "e" * 63},
    {"verifier_id": "../escape"},
    {"name": "arbitrary"},
    {"status": "pretend-passed"},
    {"provenance": "signed-by-model"},
])
def test_individual_check_contract_rejects_bogus_metadata(bad):
    with pytest.raises(ValueError):
        check(**bad)


def test_no_automatic_model_weight_or_lesson_mutation():
    original = task()
    changed = replace(original, checks=())
    assert not decide(changed).eligible_for_review
    assert original.checks == (check(),)
    assert decide(original).eligible_for_review
