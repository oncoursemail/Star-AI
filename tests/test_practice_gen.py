"""W4: per-cause practice tasks (star/practice_gen.py) and the failure ledger's targeted generator.

CI has no Luau VM. The real run (reference passes, bad answer fails *for its named cause*, through the knowledge
service's Luau checker and the server's sandboxed VM) is `python -m star.evals ledger verify`; its result is recorded in
docs/FAILURE_LEDGER.md. These tests pin everything that can be checked offline, including the label rules on the exact
checker messages that real run produced.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

from star import practice_gen as pg
from star.eval_checks import extract_luau_blocks, looks_truncated, pattern_checks, score_answer
from star.failure_ledger import (
    CAUSES, PRELUDE, Failure, check_record, generate_practice, label_failure, load_selftest, practice_for,
    read_failures, verify, write_practice,
)

ROOT = Path(__file__).resolve().parents[1]
SUITES = ROOT / "evals" / "roblox"
sys.path.insert(0, str(ROOT / "server" / "night_school"))
from nightschool.pool import is_validation, load_pool  # noqa: E402

ALL = pg.build_all()


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", text.lower()))


def test_catalogue_has_300_distinct_tasks_evenly_over_the_five_causes():
    assert len(ALL) == 300
    assert len({g.task["id"] for g in ALL}) == 300
    assert len({g.task["prompt"] for g in ALL}) == 300
    assert Counter(g.task["targets_cause"] for g in ALL) == {c: 60 for c in CAUSES}
    assert set(pg.CAUSE_CODES) == set(CAUSES)
    specs = Counter(s.cause for s in pg.SPECS)
    assert specs[pg.WL] == specs[pg.RF] == specs[pg.SC] == specs[pg.IA] == 6 and specs[pg.CO] == 4


def test_every_task_has_a_runtime_unit_test_with_the_declared_assertion_count():
    for g in ALL:
        unit = g.task["auto"]["unit_test"]
        assert unit["file"] == f"tests/{g.task['id']}.luau"
        assert unit["checks"] == pg.count_checks(g.test_body) >= 3, g.task["id"]
        assert "load_answer(" in g.test_body
        assert g.task["auto"]["compile_mode"] == "exact"


def test_reference_answers_pass_every_static_pattern_and_bad_answers_differ():
    for g in ALL:
        blocks = extract_luau_blocks(g.reference_answer)
        assert len(blocks) == 1, g.task["id"]
        assert all(c.ok for c in pattern_checks(g.task["auto"], blocks, g.reference_answer)), g.task["id"]
        assert g.bad_answer != g.reference_answer


def test_bad_answers_have_the_shape_of_their_cause():
    for g in ALL:
        cause, ref = g.task["targets_cause"], extract_luau_blocks(g.reference_answer)[0]
        if cause == pg.CO:
            assert looks_truncated(g.bad_answer) and extract_luau_blocks(g.bad_answer) == [], g.task["id"]
            continue
        bad = extract_luau_blocks(g.bad_answer)
        assert len(bad) == 1 and not looks_truncated(g.bad_answer), g.task["id"]
        if cause == pg.RF:
            defined = lambda code: set(re.findall(r"function \w+[:.](\w+)\(", code))
            assert len(defined(ref) - defined(bad[0])) == 1 and defined(bad[0]) < defined(ref), g.task["id"]
        elif cause == pg.IA:
            assert pg._INVENTED.search(bad[0]) and not pg._INVENTED.search(ref)
            assert any(not c.ok and c.id == "forbid:no_invented_helper"
                       for c in pattern_checks(g.task["auto"], bad, g.bad_answer))
            assert g.static_error.startswith("Unknown global '")
        elif cause == pg.SC:
            assert g.task["auto"]["strict"] is True and ref.startswith("--!strict") and g.static_error
        elif cause == pg.WL:
            assert all(c.ok for c in pattern_checks(g.task["auto"], bad, g.bad_answer)), g.task["id"]


def test_real_loader_accepts_the_whole_pool_with_nothing_dropped(tmp_path):
    out = tmp_path / "pool" / "ledger-practice-v2.json"
    write_practice(ALL, out, selftest_dir=tmp_path / "selftest")
    pool = load_pool(out.parent)                 # night school's own loader, not a reimplementation
    assert pool.dropped == {} and len(pool.tasks) == 300
    assert pool.prelude == PRELUDE == (SUITES / "prelude.luau").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert all(t["_test_body"] for t in pool.tasks)
    # Reference and bad answers exist only in the separate self-test folder.
    assert not list(out.parent.rglob("*.md"))
    assert len(list((tmp_path / "selftest" / "reference").glob("*.md"))) == 600
    assert [i.task for i in load_selftest(tmp_path / "selftest")] == [g.task for g in ALL]
    # About a fifth of the new tasks join night school's validation slice (a dev slice, never the blind holdout).
    share = sum(is_validation(g.task["id"], 20) for g in ALL) / len(ALL)
    assert 0.1 < share < 0.3


def test_never_written_into_the_evaluation_corpus_or_the_holdout(tmp_path):
    for target in (tmp_path / "evals" / "x.json", tmp_path / "holdout-v2.json", tmp_path / "golden-extra.json"):
        with pytest.raises(ValueError, match="evaluation corpus"):
            write_practice(ALL[:2], target)
    with pytest.raises(ValueError, match="evaluation corpus"):
        write_practice(ALL[:2], tmp_path / "p" / "a.json", selftest_dir=tmp_path / "evals" / "st")
    with pytest.raises(ValueError, match="must not be the practice pool"):
        write_practice(ALL[:2], tmp_path / "p" / "a.json", selftest_dir=tmp_path / "p")
    assert not (tmp_path / "evals").exists() and not (tmp_path / "p").exists()
    assert not any(g.task["id"].upper().startswith("HO-") for g in ALL)


def test_not_a_copy_or_near_copy_of_any_evaluation_or_practice_suite():
    old = [t for path in sorted(SUITES.glob("*.json")) for t in json.loads(path.read_text(encoding="utf-8"))]
    assert any(p.name.startswith("holdout") for p in SUITES.glob("*.json"))   # the test compares against it too
    ids = {t["id"] for t in old}
    for g in ALL:
        assert g.task["id"] not in ids
        mine = words(g.task["prompt"])
        for other in old:
            theirs = words(other["prompt"])
            assert len(mine & theirs) / max(1, len(mine | theirs)) < 0.45, (g.task["id"], other["id"])


def test_variants_of_one_spec_differ_in_numbers_or_context():
    by_spec: dict[str, list[str]] = {}
    for g in ALL:
        by_spec.setdefault(g.spec, []).append(g.test_body)
    for spec, bodies in by_spec.items():
        assert len(set(bodies)) >= len(bodies) * 0.5, spec      # tests change with the parameters


# --- the label rules on the exact messages of the real run (2026-10-13, server 1 Luau checker + VM) ------------

REAL_BAD_RECORDS = [
    (pg.WL, "unit_tests: 5/6 passed; failed: exactly duration seconds later is ready"),
    (pg.RF, "unit_tests: 10/13 passed; failed: required feature: Inventory:remove; removing more than held fails "
            "and changes nothing; removing the last one frees the kind"),
    (pg.SC, "luau_check[1]: line 19: Expected this to be 'Vec', but got 'nil'"),
    (pg.SC, "luau_check[1]: line 13: Value of type 'Entry?' could be nil"),
    (pg.SC, "luau_check[1]: line 7: Argument count mismatch. Function expects 2 arguments, but only 1 is specified"),
    (pg.SC, "luau_check[1]: line 13: Expected 'end' (to close 'function' at line 4), got <eof>"),
    (pg.IA, "luau_check[1]: line 8: Unknown global 'StringUtil'"),
    (pg.CO, "luau_block: 0 fenced Luau block(s) in the answer"),
]


@pytest.mark.parametrize(("cause", "signal"), REAL_BAD_RECORDS)
def test_ledger_labels_each_real_bad_answer_with_its_cause(cause, signal):
    check_id, detail = signal.split(": ", 1)
    record = {"status": "fail", "checks": [{"id": check_id, "ok": False, "detail": detail},
                                           {"id": "unit_tests", "ok": False, "detail": "1/5 passed; failed: x"}]}
    assert label_failure(record)[0] == cause


def test_a_required_feature_assertion_outranks_wrong_logic_but_not_a_load_error():
    feature = {"status": "fail", "checks": [{"id": "unit_tests", "ok": False,
                                             "detail": "3/9 passed; failed: required feature: Shop:buy; a b"}]}
    assert label_failure(feature)[0] == pg.RF
    logic = {"status": "fail", "checks": [{"id": "unit_tests", "ok": False, "detail": "3/9 passed; failed: x"}]}
    assert label_failure(logic)[0] == pg.WL
    load = {"status": "fail", "checks": [{"id": "unit_tests", "ok": False,
                                          "detail": "the answer did not load: required feature: x"}]}
    assert label_failure(load)[0] != pg.RF


# --- offline end-to-end through the production scorer ------------------------------------------------------------

class Sandbox:
    """Stands in for the server VM: reports every assertion of the test as passing or as failing."""

    def __init__(self, passing: bool):
        self.passing = passing

    def run(self, script):
        names = re.findall(r'(?m)^\s*check\("([^"]+)"', script.split("-- ===== test body =====", 1)[1])
        mark = "pass" if self.passing else "fail"
        return SimpleNamespace(stdout="\n".join([f"@@T\t{mark}\t{n}" for n in names] + ["@@DONE", ""]),
                               error="", timed_out=False)


def _checker(errors):
    return lambda code, strict=False: {"errors": [{"message": m} for m in errors(code)]}


def test_verify_drives_reference_bad_and_empty_answers_through_the_real_scorer():
    sample = [pg.build(s, 0) for s in pg.SPECS]

    def scorer(task, answer):
        good = answer in {g.reference_answer for g in sample}
        static = []
        if task["targets_cause"] in (pg.SC, pg.IA) and not good:
            static = ["line 3: Unknown global 'StringUtil'" if task["targets_cause"] == pg.IA
                      else "line 3: Value of type 'Entry?' could be nil"]
        return score_answer(task, answer, luau_check=_checker(lambda code: static), sandbox=Sandbox(good),
                            prelude=PRELUDE, test_body=next(g.test_body for g in sample if g.task is task))

    lines: list[str] = []
    assert verify(sample, scorer, log=lines.append) == 0, lines
    assert len(lines) == len(pg.SPECS)


def test_verify_reports_a_bad_answer_that_fails_for_another_reason():
    item = pg.build(pg.SPECS[0], 0)                 # wrong logic
    lines: list[str] = []
    scorer = lambda task, answer: score_answer(task, answer, luau_check=_checker(lambda c: ["line 1: Unknown global 'X'"]),
                                               sandbox=Sandbox(False), prelude=PRELUDE, test_body=item.test_body)
    assert verify([item], scorer, log=lines.append) == 1
    assert "FAIL" in lines[0] and "label=invented API name" in lines[0]


def test_check_record_marks_truncation_like_the_runner():
    co = next(g for g in ALL if g.task["targets_cause"] == pg.CO)
    score = score_answer(co.task, co.bad_answer, luau_check=_checker(lambda c: []), sandbox=Sandbox(True),
                         prelude=PRELUDE, test_body=co.test_body)
    record = check_record(co.task, co.bad_answer, score)
    assert record["truncated"] is True and record["status"] == "fail"
    assert label_failure(record)[0] == pg.CO


# --- the ledger's targeted generator ------------------------------------------------------------------------------

def test_targeted_practice_comes_from_each_failures_own_cause():
    failures = read_failures()
    by_cause, items = generate_practice(failures, per_failure=2)
    distinct = {(f.task_id, f.cause) for f in failures}
    assert sum(by_cause.values()) == len(items) <= 2 * len(distinct)
    assert len({i.task["id"] for i in items}) == len(items)
    sources = {f"{f.result_file}:{f.task_id}": f.cause for f in failures}
    for item in items:
        assert sources[item.task["targets_failure"]] == item.task["targets_cause"]
    assert set(by_cause) == set(CAUSES)            # all five causes occur in the stored results


def test_targeted_choice_is_stable_and_skips_taken_tasks():
    source = Failure("r.json", "UI-12", "ui-scale", pg.RF, "require:uiscale")
    first = practice_for(source)
    assert practice_for(source).task == first.task
    other = practice_for(source, 0, {first.task["id"]})
    assert other.task["id"] != first.task["id"] and other.task["targets_cause"] == pg.RF
    with pytest.raises(ValueError, match="unsupported"):
        practice_for(Failure("r.json", "X", "t", "made up", "e"))


def test_a_family_is_never_repeated_once_used_up():
    many = [Failure("r.json", f"T{i}", "t", pg.IA, "e") for i in range(70)]
    by_cause, items = generate_practice(many)
    assert by_cause == {pg.IA: 60} and len({i.task["id"] for i in items}) == 60
