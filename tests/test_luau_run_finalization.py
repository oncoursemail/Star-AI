"""The reviewed answer belongs in Fast and agent transcripts without mutating input."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from star import doc_grounding, doc_knowledge
from star.luau_run_review import MARKER

ANSWER = "```luau\nreturn 42\n```"


@pytest.mark.parametrize("messages", [
    [],
    [{"role": "user", "content": "Show an arithmetic example."}],
    [{"role": "user", "content": "Show an arithmetic example."},
     {"role": "assistant", "content": ANSWER, "extra": "retained"}],
])
def test_finalization_persists_one_reviewed_answer_and_preserves_originals(monkeypatch, messages):
    # An unavailable client still produces an honest, persisted execution note.
    monkeypatch.setattr(doc_knowledge, "client_for", lambda settings: None)
    before = deepcopy(messages)
    archive = [{"earlier": "record"}]
    result = asyncio.run(doc_grounding.finalize(
        doc_grounding.Grounding(), SimpleNamespace(task_timeout=600),
        (ANSWER, messages, archive), settings=SimpleNamespace(luau_run_before_answer=True)))
    answer, saved, records = result
    assert MARKER in answer and "not configured" in answer
    assert saved[-1]["role"] == "assistant" and saved[-1]["content"] == answer
    assert sum(message["role"] == "assistant" for message in saved) == 1
    assert [message for message in saved if message["role"] == "user"] == [
        message for message in before if message["role"] == "user"]
    if before and before[-1]["role"] == "assistant":
        assert saved[-1]["extra"] == "retained"
    assert messages == before and archive == [{"earlier": "record"}]
    assert records[0] == archive[0] and records[-1]["star_luau_run"]["blocks"][0]["ran"] is False


def test_default_off_keeps_fast_request_transcript_unchanged(monkeypatch):
    def no_client(settings):
        pytest.fail("default-off finalization must not resolve a sandbox client")
    monkeypatch.setattr(doc_knowledge, "client_for", no_client)
    messages = [{"role": "user", "content": "Show an arithmetic example."}]
    result = (ANSWER, messages, [])
    assert asyncio.run(doc_grounding.finalize(
        doc_grounding.Grounding(), SimpleNamespace(task_timeout=600), result,
        settings=SimpleNamespace(luau_run_before_answer=False))) == result
