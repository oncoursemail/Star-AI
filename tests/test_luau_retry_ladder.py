"""Opt-in Luau retry ladder (docs/research/multi-model-20261014.md, idea 4).

When the one repair still fails the static check, a second, bounded attempt is fed the real diagnostics of the
repaired code and, on a llama.cpp brain (local or STAR Server), asks with thinking on. Off by default. The model is
scripted: no network, no real brain.
"""
import asyncio
from time import monotonic
from types import SimpleNamespace

import pytest

from star import doc_grounding
from star.desktop_core import Settings
from star.doc_grounding import finalize, review_luau

from tests.test_doc_grounding import ANSWER, FakeKnowledge, failed, grounding, passed


class ScriptedModel:
    """Returns the scripted replies in order and records every request."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


FIRST = '```luau\nlocal x: string = 2\n```'
THOUGHT = '<think>Maybe ```luau\nlocal x = nil\n``` no.</think>\n```luau\nlocal x: string = "1"\n```'


def run(found, model, *, ladder, thinking=True, started=None, events=None):
    route = SimpleNamespace(quick=False, task_timeout=600, model="star-fast", response_tokens=1600)
    messages = [{"role": "system", "content": "s"}, {"role": "assistant", "content": ANSWER}]
    return asyncio.run(finalize(found, route, (ANSWER, messages, []), model_client=model, prompt="Make x a string",
                                started=monotonic() if started is None else started,
                                on_event=events.append if events is not None else None,
                                retry_ladder=ladder, thinking=thinking))


def test_off_by_default_one_repair_only():
    assert Settings().luau_retry_ladder is False
    model = ScriptedModel(FIRST)
    answer, _, _ = run(grounding(FakeKnowledge(reports=[failed(), failed("still wrong", 1)])), model, ladder=False)
    assert len(model.calls) == 1 and "shown unchanged" in answer


def test_a_failed_repair_gets_one_thinking_retry_fed_with_the_repaired_codes_own_errors():
    model, events = ScriptedModel(FIRST, THOUGHT), []
    knowledge = FakeKnowledge(reports=[failed(), failed("Type 'number' could not be converted into 'string'", 1),
                                       passed()])
    answer, _, archive = run(grounding(knowledge), model, ladder=True, events=events)
    assert len(model.calls) == 2
    retry = model.calls[1]
    assert retry["extra_body"] == {"chat_template_kwargs": {"enable_thinking": True}}
    assert "extra_body" not in model.calls[0]
    sent = retry["messages"][1]["content"]
    assert "local x: string = 2" in sent and "could not be converted" in sent    # the repaired code and ITS errors
    assert retry["max_tokens"] > model.calls[0]["max_tokens"]                    # room for the thinking
    assert knowledge.checked[-1] == 'local x: string = "1"\n'                    # the answer, not the thought
    assert '```luau\nlocal x: string = "1"\n```' in answer and "STAR corrected it" in answer
    record = archive[-1]["star_knowledge"]["luau_checks"][0]
    assert record["repaired"] and record["retry_attempted"]
    assert [e["event"] for e in events].count("luau_repair_started") == 2
    assert events[-1] == {"event": "luau_check_finished", "state": "repaired", "blocks": 1, "errors": 0}


def test_the_ladder_is_bounded_two_model_calls_per_block_then_the_note_says_so():
    model = ScriptedModel(FIRST, '```luau\nlocal x: string = 3\n```')
    knowledge = FakeKnowledge(reports=[failed(), failed("still wrong", 1), failed("wrong again", 1)])
    answer, _, _ = run(grounding(knowledge), model, ladder=True)
    assert len(model.calls) == 2 and len(knowledge.checked) == 3
    assert "local x: string = 1\n" in answer                                      # the original stays
    assert "Two automatic fixes were tried and did not pass either" in answer


def test_a_cloud_provider_retries_without_llama_cpp_fields():
    model = ScriptedModel(FIRST, '```luau\nlocal x: string = "1"\n```')
    knowledge = FakeKnowledge(reports=[failed(), failed("still wrong", 1), passed()])
    answer, _, _ = run(grounding(knowledge), model, ladder=True, thinking=False)
    assert len(model.calls) == 2 and "extra_body" not in model.calls[1]
    assert "STAR corrected it" in answer


def test_no_retry_when_the_turn_has_too_little_time_left(monkeypatch):
    # 600 s budget, 350 s used: the repair may run (>= 35% left) but not a retry needing more than is left.
    monkeypatch.setattr(doc_grounding, "RETRY_MIN_SECONDS", 300.0)
    model = ScriptedModel(FIRST, THOUGHT)
    knowledge = FakeKnowledge(reports=[failed(), failed("still wrong", 1), passed()])
    answer, _, _ = run(grounding(knowledge), model, ladder=True, started=monotonic() - 350)
    assert len(model.calls) == 1 and "shown unchanged" in answer


def test_review_luau_retries_only_after_a_repair_that_completed():
    async def raises(code, errors):
        raise RuntimeError("model went away")
    retried = []

    async def retry(code, errors):
        retried.append(code)
        return 'local x: string = "1"'
    answer, records = asyncio.run(review_luau(ANSWER, FakeKnowledge(reports=[failed(), passed()]).luau_check,
                                              repair=raises, retry=retry))
    assert retried == [] and not records[0]["ok"]


@pytest.mark.parametrize("value", [None, "yes", 1])
def test_the_setting_is_a_strict_boolean_and_saved_by_the_desktop(value):
    with pytest.raises(ValueError):
        Settings(model="m", luau_retry_ladder=value).validate()
    from star.react_shell import PERMITTED_SETTINGS
    assert "luau_retry_ladder" in PERMITTED_SETTINGS


@pytest.mark.parametrize(("enabled", "provider", "thinking"), [
    (False, "local", True), (True, "local", True), (True, "groq", False)])
def test_run_task_passes_the_setting_and_thinks_only_on_a_llama_cpp_brain(tmp_path, monkeypatch, enabled,
                                                                         provider, thinking):
    from tests.test_learning_loop import Client, Models, reply
    import star.desktop_core as core
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    models = Models()
    models.responses.append(reply("Done."))
    monkeypatch.setattr(core, "open_client", lambda settings, **_: Client(models))
    monkeypatch.setattr(doc_grounding, "client_for", lambda settings: None)
    seen = {}
    real = doc_grounding.finalize

    async def spy(*args, **kwargs):
        seen.update(retry_ladder=kwargs.get("retry_ladder"), thinking=kwargs.get("thinking"))
        return await real(*args, **kwargs)
    monkeypatch.setattr(doc_grounding, "finalize", spy)
    import star.providers as providers
    monkeypatch.setattr(providers, "get_api_key", lambda _name: "test-key-not-real")   # cloud arm only
    settings = Settings(model="qwen-test", provider=provider, luau_retry_ladder=enabled)
    core.run_task(settings, "Write a Luau function that adds two numbers.", mode="fast")
    assert seen == {"retry_ladder": enabled, "thinking": thinking}
