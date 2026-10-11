"""The gate: compares a candidate run with the stored baseline (star/eval_gate.py)."""
import json
from pathlib import Path

import pytest

from star import eval_gate as gate


def result(statuses: dict, *, sha="s1", model="star-fast", mode="auto") -> dict:
    return {"schema": 1, "suite": {"sha256": sha, "file": "suite.json", "tasks_total": 4,
            "automated": 3, "selected": ["A", "B", "C"], "identity_sha256": "identity"},
            "run": {"model": model, "mode": mode, "app_commit": "commit", "grader_sha256": "grader"},
            "tasks": {tid: {"status": s, **({"passed": s == "pass"} if s in ("pass", "fail") else {})}
                      for tid, s in statuses.items()}}


BASE = result({"A": "pass", "B": "pass", "C": "fail", "D": "skipped"})


def test_identical_runs_are_allowed():
    v = gate.compare(BASE, BASE)
    assert v.allowed and v.code == gate.ALLOWED and v.compared == 3 and v.baseline_pass == v.candidate_pass == 2


def test_improvement_is_allowed_and_listed():
    v = gate.compare(BASE, result({"A": "pass", "B": "pass", "C": "pass"}))
    assert v.allowed and v.improvements == ["C"] and v.candidate_pass == 3


def test_a_previously_passing_task_that_fails_blocks_even_if_the_count_is_equal():
    v = gate.compare(BASE, result({"A": "pass", "B": "fail", "C": "pass"}))
    assert v.code == gate.BLOCKED and v.regressions == ["B"] and v.improvements == ["C"]
    assert v.candidate_pass == v.baseline_pass == 2 and not v.allowed


def test_pass_count_drop_blocks():
    v = gate.compare(BASE, result({"A": "fail", "B": "fail", "C": "fail"}))
    assert v.code == gate.BLOCKED and "the pass count dropped" in v.notes


def test_errors_never_count_as_passes_or_failures():
    v = gate.compare(BASE, result({"A": "pass", "B": "error", "C": "fail"}))
    assert v.code == gate.INCOMPLETE and v.incomplete == ["B"] and not v.regressions


def test_missing_tasks_are_incomplete_unless_a_targeted_run_is_allowed():
    partial = result({"A": "pass", "B": "pass"})
    assert gate.compare(BASE, partial).code == gate.INCOMPLETE
    v = gate.compare(BASE, partial, allow_partial=True)
    assert v.allowed and v.not_covered == ["C"] and v.compared == 2
    # a partial run cannot hide an error or a regression
    assert gate.compare(BASE, result({"A": "error", "B": "pass"}), allow_partial=True).code == gate.INCOMPLETE
    assert gate.compare(BASE, result({"A": "fail", "B": "pass"}), allow_partial=True).code == gate.BLOCKED


def test_a_different_suite_or_nothing_to_compare_is_unusable():
    assert gate.compare(BASE, result({"A": "pass"}, sha="other")).code == gate.UNUSABLE
    assert gate.compare(BASE, result({"X": "pass"})).code == gate.UNUSABLE
    assert gate.compare(result({"A": "skipped"}), result({"A": "pass"})).code == gate.UNUSABLE


def test_different_model_is_unusable():
    v = gate.compare(BASE, result({"A": "pass", "B": "pass", "C": "fail"}, model="other"))
    assert v.code == gate.UNUSABLE and any("model differs" in n for n in v.notes)


def test_gate_change_confirms_regressions_with_a_rerun():
    candidate = result({"A": "pass", "B": "fail", "C": "fail"})
    asked = []

    def rerun(ids):
        asked.append(ids)
        return result({"B": "pass"})

    v = gate.gate_change(BASE, lambda: candidate, rerun=rerun)
    assert asked == [["B"]] and v.allowed and v.flaky == ["B"] and not v.regressions
    still = gate.gate_change(BASE, lambda: candidate, rerun=lambda ids: result({"B": "fail"}))
    assert still.code == gate.BLOCKED and still.regressions == ["B"] and not still.flaky
    assert gate.gate_change(BASE, lambda: candidate).code == gate.BLOCKED


def test_evaluate_change_reads_files_and_survives_garbage(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(BASE), encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert gate.evaluate_change(good, good).allowed
    assert gate.evaluate_change(good, bad).code == gate.UNUSABLE
    assert gate.evaluate_change(good, tmp_path / "missing.json").code == gate.UNUSABLE
    assert gate.evaluate_change(BASE, BASE).allowed          # dicts work too


def test_command_line_exit_codes(tmp_path, capsys):
    base = tmp_path / "base.json"
    base.write_text(json.dumps(BASE), encoding="utf-8")
    worse = tmp_path / "worse.json"
    worse.write_text(json.dumps(result({"A": "fail", "B": "pass", "C": "fail"})), encoding="utf-8")
    assert gate.main(["--baseline", str(base), "--candidate", str(base)]) == 0
    assert gate.main(["--baseline", str(base), "--candidate", str(worse), "--json"]) == 1
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["allowed"] is False and out["regressions"] == ["A"]


def test_python_dash_m_entry_dispatches_to_the_gate(tmp_path):
    from star import evals
    base = tmp_path / "b.json"
    base.write_text(json.dumps(BASE), encoding="utf-8")
    assert evals.main(["gate", "--baseline", str(base), "--candidate", str(base)]) == 0

@pytest.mark.parametrize("field,value", [
    ("row", {"status": "maybe"}), ("row", "pass"),
    ("row", {"status": "pass", "passed": False}),
    ("row", {"status": "pass", "passed": True, "checks": [{"id": "c", "ok": "yes"}]}),
])
def test_invalid_task_rows_fail_closed(field, value):
    broken = result({"A": "pass", "B": "pass", "C": "fail"})
    broken["tasks"]["A"] = value
    assert gate.compare(BASE, broken).code == gate.UNUSABLE


@pytest.mark.parametrize("field", ["file", "identity_sha256", "tasks_total"])
def test_suite_identity_fail_closed(field):
    broken = result({"A": "pass"})
    broken["suite"][field] = "other" if field != "tasks_total" else 5
    assert gate.compare(BASE, broken).code == gate.UNUSABLE


@pytest.mark.parametrize("field", ["model", "mode", "grader_sha256"])
def test_incompatible_grading_configuration_fails_closed(field):
    broken = result({"A": "pass"})
    broken["run"][field] = "different"
    assert gate.compare(BASE, broken).code == gate.UNUSABLE


@pytest.mark.parametrize("field,section", [
    ("model", "run"), ("mode", "run"), ("app_commit", "run"),
    ("grader_sha256", "run"), ("identity_sha256", "suite"),
])
def test_incompatible_rerun_is_unusable(field, section):
    candidate = result({"A": "pass", "B": "fail", "C": "fail"})
    again = result({"B": "pass"})
    again[section][field] = "other"
    assert gate.gate_change(BASE, lambda: candidate, rerun=lambda ids: again).code == gate.UNUSABLE


def test_only_two_named_legacy_baselines_are_exempt(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for filename in ("baseline-v2.json", "baseline-creation-v1.json"):
        original = root / "evals" / "results" / filename
        legacy = gate.load_result(original)
        assert legacy["_legacy"]
        assert not gate._errors(legacy, "baseline")[0]
        assert any("legacy result" in note for note in gate.compare(legacy, legacy).notes)
        copied = tmp_path / filename
        copied.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
        assert not gate.load_result(copied)["_legacy"]
        assert gate.evaluate_change(copied, copied).code == gate.UNUSABLE

def test_in_memory_paired_trial_summaries_do_not_make_untrusted_files_valid(tmp_path):
    summary = {"suite": {"sha256": "paired"}, "tasks": {"A": {"status": "pass"}}}
    assert gate.compare(summary, summary).allowed
    stored = tmp_path / "trial.json"
    stored.write_text(json.dumps(summary), encoding="utf-8")
    assert gate.evaluate_change(stored, stored).code == gate.UNUSABLE
    malformed = {"suite": {"sha256": "paired"}, "tasks": {"A": {"status": ["pass"]}}}
    assert gate.compare(malformed, malformed).code == gate.UNUSABLE
