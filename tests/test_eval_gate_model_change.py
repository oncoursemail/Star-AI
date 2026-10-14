"""Paired gate across two model names (`--allow-model-change`), for model-scout candidates (PR #378).

Owner-approved change to a protected evaluation file. Default behaviour is unchanged: a different model is
UNUSABLE. With the flag, the two ARMS may name different models, each arm must be one model, everything else
(suite, identity, grader, mode, one session) is checked as before, and the statistics are the same function.
"""
import json

import pytest

from star import eval_gate as gate, eval_stats

from tests.test_eval_stats import BASE, BETTER, at, result


def named(statuses, model, hour):
    run = result(statuses, **at(hour))
    run["run"]["model"] = model
    return run


def test_default_is_unchanged_a_different_model_is_unusable():
    v = gate.compare_paired([named(BASE, "star-fast", 1)], [named(BETTER, "star-fast-cand1", 2)])
    assert v.code == gate.UNUSABLE and any("model differs" in n for n in v.notes)


def test_with_the_flag_two_model_names_are_compared_with_the_same_statistics():
    base = [named(BASE, "star-fast", 1), named(BASE, "star-fast", 4)]
    cand = [named(BETTER, "star-fast-cand1", 2), named(BETTER, "star-fast-cand1", 3)]
    v = gate.compare_paired(base, cand, allow_model_change=True)
    same = gate.compare_paired([result(BASE, **at(1)), result(BASE, **at(4))],
                               [result(BETTER, **at(2)), result(BETTER, **at(3))])
    assert v.code == same.code == gate.ALLOWED
    assert v.paired == same.paired and v.paired_text == same.paired_text        # identical statistics
    expected = eval_stats.paired_decision({t: [s == "pass"] * 2 for t, s in BASE.items()},
                                          {t: [s == "pass"] * 2 for t, s in BETTER.items()})
    assert v.paired == expected.to_dict()
    assert any("star-fast" in n and "star-fast-cand1" in n and "allow-model-change" in n for n in v.notes)


def test_each_arm_must_still_be_one_model():
    mixed = [named(BASE, "star-fast", 1), named(BASE, "other", 4)]
    v = gate.compare_paired(mixed, [named(BETTER, "star-fast-cand1", 2), named(BETTER, "star-fast-cand1", 3)],
                            allow_model_change=True)
    assert v.code == gate.UNUSABLE and any("baseline run 2: model differs" in n for n in v.notes)
    v = gate.compare_paired([named(BASE, "star-fast", 1)],
                            [named(BETTER, "cand1", 2), named(BETTER, "cand2", 3)], allow_model_change=True)
    assert v.code == gate.UNUSABLE and any("candidate run 2: model differs" in n for n in v.notes)


@pytest.mark.parametrize("key, value", [("mode", "fast"), ("grader_sha256", "other")])
def test_mode_grader_and_session_rules_still_apply_with_the_flag(key, value):
    cand = named(BETTER, "star-fast-cand1", 2)
    cand["run"][key] = value
    assert gate.compare_paired([named(BASE, "star-fast", 1)], [cand], allow_model_change=True).code == gate.UNUSABLE
    far = named(BETTER, "star-fast-cand1", 2)
    far["run"]["started_at"], far["run"]["finished_at"] = "2026-10-15T01:00:00+00:00", "2026-10-15T02:00:00+00:00"
    assert gate.compare_paired([named(BASE, "star-fast", 1)], [far], allow_model_change=True).code == gate.UNUSABLE


def test_command_line_flag(tmp_path, capsys):
    files = {}
    for name, statuses, model, hour in (("b1", BASE, "star-fast", 1), ("c1", BETTER, "star-fast-cand1", 2),
                                        ("c2", BETTER, "star-fast-cand1", 3), ("b2", BASE, "star-fast", 4)):
        files[name] = tmp_path / f"{name}.json"
        files[name].write_text(json.dumps(named(statuses, model, hour)), encoding="utf-8")
    args = ["--paired-session", "--baseline", str(files["b1"]), str(files["b2"]),
            "--candidate", str(files["c1"]), str(files["c2"]), "--json"]
    assert gate.main(args) == gate.UNUSABLE
    capsys.readouterr()
    assert gate.main(args + ["--allow-model-change"]) == gate.ALLOWED
    assert json.loads(capsys.readouterr().out)["paired"]["decision"] == "PROMOTE"
    with pytest.raises(SystemExit):                                  # the legacy single-run gate has no such option
        gate.main(["--baseline", str(files["b1"]), "--candidate", str(files["c1"]), "--allow-model-change"])
