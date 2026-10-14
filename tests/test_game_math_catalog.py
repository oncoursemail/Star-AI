"""Validate and execute only the harness-owned, offline game-math fixtures."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("game_math_fixtures", ROOT / "evals/math/check_fixtures.py")
math_fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(math_fixtures)
CATALOG = math_fixtures.load_catalog()
TASKS = CATALOG["tasks"]


def test_catalog_has_twenty_independent_harness_owned_tasks():
    math_fixtures.validate_catalog(CATALOG)
    assert CATALOG["harness_owned"] is True
    assert len({task["id"] for task in TASKS}) == 20
    assert len({task["unit_test"]["body"] for task in TASKS}) == 20
    assert sum(task["unit_test"]["checks"] for task in TASKS) == 187


@pytest.mark.parametrize("defect", (
    "missing-task", "duplicate-id", "missing-topic", "false-ownership", "nan-tolerance",
    "bool-tolerance", "wrong-tolerance", "wrong-count", "duplicate-check", "unknown-failure",
    "identical-answers", "global-rng", "harness-override", "missing-contract",
))
def test_validator_rejects_catalog_regressions(defect):
    data = deepcopy(CATALOG)
    task = data["tasks"][0]
    if defect == "missing-task":
        data["tasks"].pop()
    elif defect == "duplicate-id":
        data["tasks"][1]["id"] = task["id"]
    elif defect == "missing-topic":
        task["topic"] = "other"
    elif defect == "false-ownership":
        data["harness_owned"] = False
    elif defect == "nan-tolerance":
        task["tolerance"]["absolute"] = float("nan")
    elif defect == "bool-tolerance":
        task["tolerance"]["relative"] = False
    elif defect == "wrong-tolerance":
        task["tolerance"]["absolute"] = 1
    elif defect == "wrong-count":
        task["unit_test"]["checks"] += 1
    elif defect == "duplicate-check":
        task["unit_test"]["body"] += 'check("returns a function", true)\n'
        task["unit_test"]["checks"] += 1
    elif defect == "unknown-failure":
        task["bad_answer_fails"] = ["not a harness assertion"]
    elif defect == "identical-answers":
        task["bad_answer"] = task["reference_answer"]
    elif defect == "global-rng":
        task["reference_answer"] = "local n = math.random()\n" + task["reference_answer"]
    elif defect == "harness-override":
        task["unit_test"]["body"] += "local function check() end\n"
    elif defect == "missing-contract":
        task["prompt"] = "Write something."
    with pytest.raises(ValueError):
        math_fixtures.validate_catalog(data)


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        math_fixtures._unique_object([("id", 1), ("id", 2)])


def test_fixture_runner_does_not_accept_arbitrary_answers():
    with pytest.raises(ValueError, match="only checked-in"):
        math_fixtures.fixture("MATH-01", "candidate")
    with pytest.raises(ValueError, match="unknown fixture"):
        math_fixtures.fixture("MATH-99", "reference_answer")


@pytest.fixture(scope="module")
def math_runtime():
    selected = math_fixtures.runtime()
    if os.environ.get("STAR_MATH_REQUIRE_LUAU") == "1":
        assert selected and selected[0] == "luau", "native Luau required but not installed"
    if selected is None:
        pytest.skip("no installed Luau or Lua 5.4 runtime; catalog validation still ran")
    return selected


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task["id"])
def test_reference_answer_passes_every_harness_assertion(task, math_runtime):
    outcome = math_fixtures.run_fixture(task["id"], "reference_answer", math_runtime)
    assert not outcome["errors"], outcome
    assert len(outcome["results"]) == task["unit_test"]["checks"]
    assert all(passed for _, passed in outcome["results"]), outcome


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task["id"])
def test_bad_answer_runs_but_fails_its_named_math_assertion(task, math_runtime):
    outcome = math_fixtures.run_fixture(task["id"], "bad_answer", math_runtime)
    # Syntax errors, aborted bodies, omitted checks or missing runtimes are not evidence
    # that the intentional mathematical error was caught.
    assert not outcome["errors"], outcome
    assert len(outcome["results"]) == task["unit_test"]["checks"]
    failed = {name for name, passed in outcome["results"] if not passed}
    assert set(task["bad_answer_fails"]) <= failed, outcome
    assert any(passed for _, passed in outcome["results"]), outcome
