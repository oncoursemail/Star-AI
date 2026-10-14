"""Night school role split (docs/research/multi-model-20261014.md, idea 3).

`STAR_NS_DIAG_MODEL` sends the failure diagnosis and lesson draft to another model (star-quick); the graded
answers stay on `STAR_NS_MODEL`. Unset, nothing changes. The paired gate code is not touched: a drafted lesson is
still only a candidate until the engine's own checks and gate keep it. No real model: a scripted fake brain.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "night_school"))

from nightschool import fake                                            # noqa: E402
from nightschool.idle import BrainWatch, IdleGate                       # noqa: E402

from tests.test_night_school import settings_for                        # noqa: E402


@pytest.fixture
def brain_model(tmp_path, monkeypatch, request):
    pytest.importorskip("openai")
    from nightschool.real import RealModel, bootstrap
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("STAR_NS_APP", str(repo))
    monkeypatch.setenv("STAR_SERVER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("STAR_SKILL_PACKS", raising=False)
    brain = fake.FakeBrain()
    brain.__enter__()
    request.addfinalizer(lambda: brain.__exit__(None, None, None))

    def make():
        settings = settings_for(tmp_path, brain_url=brain.url, idle_s=0, poll_s=0.05, watch_s=0.1,
                                key_file=str(tmp_path / "no-key-file"))
        bootstrap(settings)
        gate = IdleGate(settings, BrainWatch(brain.url), log=lambda _text: None)
        model = RealModel(settings, gate, knowledge="off", luau_check=fake.luau_ok)
        request.addfinalizer(model.close)
        return model
    return brain, make


def failed_result(model):
    task = dict(fake.practice_task("P-01", "limitHealth"), _test_body="")
    return task, model.solve(task, [])


def test_without_the_setting_diagnosis_uses_the_answer_model(brain_model, monkeypatch):
    monkeypatch.delenv("STAR_NS_DIAG_MODEL", raising=False)
    brain, make = brain_model
    model = make()
    task, first = failed_result(model)
    assert first.passed is False
    assert model.diagnose(task, first)["lesson"] == fake.LESSON
    assert [body["model"] for body in brain.completions][-1] == "star-fast"


def test_the_quick_model_drafts_the_diagnosis_while_answers_stay_on_the_main_model(brain_model, monkeypatch):
    monkeypatch.setenv("STAR_NS_DIAG_MODEL", "star-quick")
    brain, make = brain_model
    model = make()
    task, first = failed_result(model)
    answered = {body["model"] for body in brain.completions}
    assert "star-quick" not in answered                       # the graded answer did not use the quick model
    assert model.diagnose(task, first)["lesson"] == fake.LESSON
    last = brain.completions[-1]
    assert last["model"] == "star-quick" and last.get("id_slot") == 1   # its own slot, never slot 0


def test_a_quick_model_with_a_single_slot_falls_back_to_the_answer_model(brain_model, monkeypatch):
    monkeypatch.setenv("STAR_NS_DIAG_MODEL", "star-quick")
    brain, make = brain_model
    model = make()
    task, first = failed_result(model)
    model._slots = {**model._slots, "star-quick": 0}
    model._slots_at = float("inf")                            # keep the scripted slot table
    assert model.diagnose(task, first)["lesson"] == fake.LESSON
    assert brain.completions[-1]["model"] == "star-fast" and brain.completions[-1].get("id_slot") == 1
    assert model._refusal == ""                               # the fallback is not a refusal of the next answer
