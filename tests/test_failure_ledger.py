"""Offline regressions for the stored-result failure ledger and practice-task output."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from star.eval_checks import score_answer
from star.failure_ledger import (
    CAUSES, DEFAULT_RESULTS, DEFAULT_SUITES, PRELUDE, Failure, _golden_prompts,
    counts, generate_practice, label_failure, leading_cause, main, overlaps_golden,
    practice_for, read_failures, report_table, write_practice,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "night_school"))
from nightschool.pool import load_pool  # noqa: E402


@pytest.fixture(scope="module")
def stored_failures() -> list[Failure]:
    return read_failures()


@pytest.mark.parametrize(
    ("file", "task_id", "cause", "signal"),
    [
        ("baseline-v2.json", "SYS-01", "wrong logic", "unit_tests:"),
        ("baseline-v2.json", "UI-12", "required feature missing", "require:uiscale"),
        ("baseline-v2.json", "NET-07", "self-check error left unrepaired", "luau_check[1]"),
        ("baseline-creation-v1.json", "ANI-07", "answer cut off", "product_failure:"),
        ("baseline-v2.json", "NET-05", "invented API name", "Unknown type"),
    ],
)
def test_each_cause_uses_an_actual_stored_failure(file, task_id, cause, signal):
    results = json.loads((DEFAULT_RESULTS / file).read_text(encoding="utf-8"))
    labeled = label_failure(results["tasks"][task_id])
    assert labeled is not None
    assert labeled[0] == cause
    assert signal in labeled[1]
    assert labeled[1] in (
        [f"{c['id']}: {c.get('detail') or ''}" for c in results["tasks"][task_id].get("checks", [])
         if c.get("ok") is False]
        + ["product_failure: " + str(results["tasks"][task_id].get("product_failure", ""))]
    )


def test_real_result_corpus_counts_and_retries(stored_failures):
    assert len(stored_failures) == 65
    assert len({f.task_id for f in stored_failures}) == 34
    expected = {
        "wrong logic": 15,
        "required feature missing": 25,
        "self-check error left unrepaired": 13,
        "answer cut off": 11,
        "invented API name": 1,
    }
    assert {cause: counts(stored_failures)[cause][0] for cause in CAUSES} == expected
    assert leading_cause(stored_failures) == "required feature missing"
    table = report_table(stored_failures)
    assert "65" in table and "UI-12" in table and "require:uiscale" in table


def test_non_failure_statuses_are_not_learned():
    assert label_failure({"status": "pass", "checks": [{"id": "unit_tests", "ok": False}]}) is None
    assert label_failure({"status": "error", "reasons": ["sandbox unavailable"]}) is None
    assert label_failure({"status": "skipped"}) is None


def test_rule_precedence_uses_recorded_signals():
    rec = {"status": "fail", "checks": [
        {"id": "unit_tests", "ok": False, "detail": "failed: boundary"},
        {"id": "require:field", "ok": False, "detail": "missing"},
    ]}
    assert label_failure(rec) == ("wrong logic", "unit_tests: failed: boundary")
    rec["truncated"] = True
    assert label_failure(rec) == ("answer cut off", "truncated=True")
    rec.pop("truncated")
    rec["checks"].insert(0, {"id": "luau_check[1]", "ok": False,
                             "detail": "line 4: Unknown type 'Game.FakeWidget'"})
    assert label_failure(rec)[0] == "invented API name"
    assert label_failure({"status": "fail", "reasons": ["legacy failed check"]}) == (
        "wrong logic", "legacy failed check")


def test_loader_accepts_all_generated_exercises_with_sidecars(stored_failures, tmp_path):
    cause, items = generate_practice(stored_failures)
    assert cause == "required feature missing"
    assert len(items) == 16  # retries of the same failed task do not multiply exercises
    assert len({x.task["id"] for x in items}) == len(items)
    assert len({x.task["prompt"] for x in items}) == len(items)
    out = tmp_path / "pool" / "targeted.json"
    assert not out.exists()
    write_practice(items, out)
    assert out.is_file() and (out.parent / "prelude.luau").read_text(encoding="utf-8") == PRELUDE
    pool = load_pool(out.parent)  # Real night-school loader, not a reimplemented shape check.
    assert pool.dropped == {}
    assert len(pool.tasks) == len(items)
    assert pool.prelude == PRELUDE
    assert all(task["_test_body"].count('check("') == 4 for task in pool.tasks)
    assert all((out.parent / task["auto"]["unit_test"]["file"]).is_file() for task in pool.tasks)
    with pytest.raises(FileExistsError, match="replace"):
        write_practice(items, out)


def test_practice_templates_are_not_copies_of_any_golden_task(stored_failures):
    golden = _golden_prompts(DEFAULT_SUITES)  # Never the holdout file.
    _, items = generate_practice(stored_failures)
    for item in items:
        assert not any(overlaps_golden(item.task["prompt"], prompt) for prompt in golden)
    assert overlaps_golden(golden[0], golden[0])
    assert all("source_task" not in item.task and "reference_answer" not in item.task for item in items)


class ScriptedSandbox:
    """CI has no Luau VM; exercise the production grader with deterministic check output."""

    def __init__(self, checks_pass: bool):
        self.checks_pass = checks_pass
        self.calls = 0

    def run(self, script):
        self.calls += 1
        assert "local __SRC =" in script and "load_answer()" in script
        mark = "pass" if self.checks_pass else "fail"
        lines = [f"@@T\t{mark}\tcase {i}" for i in range(4)]
        return SimpleNamespace(stdout="\n".join([*lines, "@@DONE", ""]), error="", timed_out=False)


def test_reference_answers_pass_real_grader_and_bad_answers_fail():
    for index, cause in enumerate(CAUSES):
        source = Failure("sample.json", f"task-{index}", "remote-security", cause, "recorded")
        example = practice_for(source, index)
        good_sandbox = ScriptedSandbox(True)
        good = score_answer(example.task, example.reference_answer,
                            luau_check=lambda code, strict=False: {"errors": []},
                            sandbox=good_sandbox, prelude=PRELUDE, test_body=example.test_body)
        assert good.passed and good_sandbox.calls == 1
        assert len([c for c in good.checks if c.id == "unit_tests" and c.ok]) == 1
        bad_sandbox = ScriptedSandbox(False)
        fence = chr(96) * 3
        bad_answer = fence + "luau\nreturn math.constrain(7, 0, 10)\n" + fence
        bad = score_answer(example.task, bad_answer,
                           luau_check=lambda code, strict=False: {"errors": []},
                           sandbox=bad_sandbox, prelude=PRELUDE, test_body=example.test_body)
        assert not bad.passed and bad_sandbox.calls == 1
        assert {"unit_tests", "require:round_down", "require:limit_output",
                "forbid:no_imaginary_helper"} <= {c.id for c in bad.checks if not c.ok}


def test_holdout_suite_is_never_opened(tmp_path):
    results = tmp_path / "results"
    suites = tmp_path / "suites"
    results.mkdir()
    suites.mkdir()
    (suites / "holdout-v1.json").write_text("invalid JSON that must never be read", encoding="utf-8")
    (results / "blind.json").write_text(json.dumps({
        "suite": {"file": "holdout-v1.json"},
        "tasks": {"HO-01": {"status": "fail", "reasons": ["wrong"]}},
    }), encoding="utf-8")
    assert read_failures(results, suites) == []


def test_bad_result_is_a_hard_error_and_does_not_write_practice(tmp_path, capsys):
    results = tmp_path / "results"
    results.mkdir()
    (results / "corrupt.json").write_text('{"tasks": []}', encoding="utf-8")
    target = tmp_path / "pool" / "new.json"
    assert main(["practice", "--results", str(results), "--out", str(target)]) == 2
    assert not target.exists()
    assert "invalid result file" in capsys.readouterr().err


def test_explicit_output_only_and_reject_eval_tree(stored_failures, tmp_path):
    _, items = generate_practice(stored_failures, count=2)
    assert not (tmp_path / "pool").exists()
    with pytest.raises(ValueError, match="evaluation corpus"):
        write_practice(items, tmp_path / "evals" / "bad.json")
    assert not (tmp_path / "evals").exists()
    with pytest.raises(ValueError, match="count"):
        generate_practice(stored_failures, count=1000)
    with pytest.raises(ValueError, match="count"):
        generate_practice(stored_failures, count=0)
    with pytest.raises(ValueError, match="no failed"):
        generate_practice([])
    assert not (tmp_path / "pool").exists()


def test_copy_guard_fails_closed_on_golden_overlap(stored_failures, tmp_path):
    _, items = generate_practice(stored_failures, count=1)
    prompt = _golden_prompts(DEFAULT_SUITES)[0]
    copied = replace(items[0], task={**items[0].task, "prompt": prompt})
    with pytest.raises(ValueError, match="overlaps"):
        write_practice([copied], tmp_path / "pool" / "targeted.json")
    assert not (tmp_path / "pool").exists()


def test_cli_read_only_by_default(stored_failures, tmp_path, capsys):
    output = tmp_path / "uncreated"
    assert main(["--results", str(DEFAULT_RESULTS), "--suites", str(DEFAULT_SUITES)]) == 0
    out = capsys.readouterr().out
    assert "required feature missing" in out and "Recorded check evidence" in out
    assert not output.exists()
