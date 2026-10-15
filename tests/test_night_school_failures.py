"""Night school keeps its failing answers (docs/research/multi-model-20261014.md, idea 10).

Passing answers already go to examples.jsonl; failing ones were only hashed in attempts.jsonl, so no pass/fail
pair existed for preference training (DPO) or a router. They now go to data/failures.jsonl: scrubbed, bounded,
joinable to attempts by answer_sha256, and marked when the task is in the validation slice. Nothing else
changes: the engine and the gate do not read this file. No real model: a scripted fake brain.
"""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "night_school"))

from nightschool import fake                                            # noqa: E402
from nightschool.idle import BrainWatch, IdleGate                       # noqa: E402
from nightschool.pool import is_validation                              # noqa: E402

from tests.test_night_school import settings_for                        # noqa: E402


PRIVATE = "192.168." + "50.60"          # built at run time: no address literal in the repository


def leaky(body):
    """The scripted brain, but its failing answer quotes a private address and something key-like."""
    text = fake.scripted(body)
    if "math.clamp" in text or fake.DIAGNOSE_MARK in json.dumps(body.get("messages", [])):
        return text
    return text.replace("Here is the function.", "Tested on " + PRIVATE + " with key sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2")


@pytest.fixture
def model_for(tmp_path, monkeypatch, request):
    pytest.importorskip("openai")
    from nightschool.real import RealModel, bootstrap
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("STAR_NS_APP", str(repo))
    monkeypatch.setenv("STAR_SERVER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("STAR_SKILL_PACKS", raising=False)
    brain = fake.FakeBrain(responder=leaky)
    brain.__enter__()
    request.addfinalizer(lambda: brain.__exit__(None, None, None))
    settings = settings_for(tmp_path, brain_url=brain.url, idle_s=0, poll_s=0.05, watch_s=0.1,
                            key_file=str(tmp_path / "no-key-file"), validation_percent=20)
    bootstrap(settings)
    gate = IdleGate(settings, BrainWatch(brain.url), log=lambda _text: None)
    model = RealModel(settings, gate, knowledge="off", luau_check=fake.luau_ok)
    request.addfinalizer(model.close)
    return settings, model


def rows(settings):
    path = settings.data / "failures.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_a_failing_answer_is_kept_scrubbed_and_joinable_and_a_pass_is_not(model_for):
    settings, model = model_for
    task = dict(fake.practice_task("P-01", "limitHealth"), _test_body="")
    failed = model.solve(task, [])
    assert failed.passed is False
    [row] = rows(settings)
    assert row["task"] == "P-01" and row["category"] == task.get("category", "")
    assert row["prompt"] == task["prompt"] and row["reasons"] == failed.reasons
    assert row["answer_sha256"] == hashlib.sha256(failed.answer.encode("utf-8")).hexdigest()
    assert PRIVATE not in row["answer"] and "sk-A1b2" not in row["answer"] and "<address>" in row["answer"]
    assert row["validation"] is is_validation("P-01", settings.validation_percent)
    assert row["lessons"] == []
    passed = model.solve(task, [{"id": "L1", "text": fake.LESSON}])
    assert passed.passed is True and len(rows(settings)) == 1          # passes go to examples.jsonl, not here


def test_the_file_is_bounded_and_a_write_problem_never_fails_the_answer(model_for, monkeypatch):
    from nightschool import real
    settings, model = model_for
    task = dict(fake.practice_task("P-02", "limitHealth"), _test_body="")
    monkeypatch.setattr(real, "FAILURES_MAX_BYTES", 10)
    (settings.data / "failures.jsonl").write_text("x" * 20, encoding="utf-8")
    assert model.solve(task, []).passed is False
    assert (settings.data / "failures.jsonl").read_text(encoding="utf-8") == "x" * 20   # full: nothing appended
    (settings.data / "failures.jsonl").unlink()
    (settings.data / "failures.jsonl").mkdir()                           # unwritable path
    assert model.solve(task, []).passed is False                         # still a normal failed result
