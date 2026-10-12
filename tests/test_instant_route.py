"""Offline instant-route decisions, resident-model probes and real chat paths."""
import asyncio
import json
import threading
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

import httpx
import pytest

import star.desktop_core as core
import star.react_shell as shell
from star.desktop_core import Conversations, Settings, run_task
from star.instant_route import (
    InstantAnswer, complete_instant, decide_instant_route,
    loaded_local_model, loaded_model_from_listing,
)
from star.lessons import LessonStore
from star.react_shell import sanitize_event


BASE = dict(prompt="What is a palindrome?", mode="fast", provider="lan",
            enabled=True, installed=True, loaded_model="small")
PERSONAL_PROMPTS = [
    "Am I correct?", "Tell me a fact.", "What is my name?",
    "Which answer is mine?", "Are we ready?", "What is our plan?",
    "Who are you?", "What is your name?", "What is STAR?",
    "Remember the answer?", "Recall the answer?", "What happened last time?",
    "WHO ARE YOU?", "What happened last   time?",
    "What do you remember about me?",
]


@pytest.mark.parametrize(("changes", "expected"), [
    ({}, True),
    ({"mode": "auto"}, True),
    ({"mode": "agent"}, False),
    ({"provider": "local"}, False),
    ({"provider": "cloud"}, False),
    ({"enabled": False}, False),
    ({"installed": False}, False),
    ({"loaded_model": ""}, False),
    ({"attachments": 1}, False),
    ({"tools": True}, False),
    ({"research": True}, False),
    ({"documentation": True}, False),
    ({"deep": True}, False),
    ({"followup": True}, False),
    ({"prompt": ""}, False),
    ({"prompt": "word " * 50}, False),
    ({"prompt": "How do I script an R6 character in Roblox?"}, False),
    ({"prompt": "Write a Python function to reverse a list."}, False),
    ({"prompt": "Look up the latest documentation."}, False),
    ({"prompt": "/deep What is a palindrome?"}, False),
    ({"prompt": "What is\na palindrome?"}, False),
    ({"prompt": "And what about that?"}, False),
    ({"prompt": "What does TweenService do?"}, False),
    ({"prompt": "Why is the sky blue?"}, True),
    ({"prompt": "What is a mineral?"}, True),
    ({"prompt": "What is a meadow?"}, True),
    ({"prompt": "What is starch?"}, True),
])
def test_decision_table(changes, expected):
    inputs = BASE | changes
    assert decide_instant_route(**inputs).use_local is expected
    assert decide_instant_route(**inputs) == decide_instant_route(**inputs)


@pytest.mark.parametrize("prompt", PERSONAL_PROMPTS)
@pytest.mark.parametrize("mode", ["fast", "auto"])
def test_personal_and_memory_words_are_excluded(prompt, mode):
    assert not decide_instant_route(**(BASE | {"prompt": prompt, "mode": mode})).use_local


@pytest.mark.parametrize(("listed", "expected"), [
    ([{"id": "small", "status": {"value": "loaded"}},
      {"id": "huge", "status": {"value": "unloaded"}}], "small"),
    ([{"id": "small", "status": {"value": "unloaded"}}], ""),
    ([{"id": "small", "status": {"value": "loading"}}], ""),
    ([{"id": "small", "status": {"value": "loaded", "failed": True}}], ""),
    ([{"id": "small", "status": {"value": "loaded"}},
      {"id": "other", "status": {"value": "loaded"}}], ""),
    ([{"id": "single"}], "single"),
    ([{"id": "single"}, {"id": "other"}], ""),
    ([{"id": "voice", "status": {"value": "loaded"},
      "architecture": {"input_modalities": ["audio"]}}], ""),
    ([{"id": "not valid id", "status": {"value": "loaded"}}], ""),
    ([], ""),
    (None, ""),
])
def test_loaded_model_table(listed, expected):
    assert loaded_model_from_listing(listed) == expected


def test_loopback_probe_never_loads_or_follows_redirects():
    requested = []

    def handler(request):
        requested.append((request.method, str(request.url)))
        return httpx.Response(200, json={"data": [
            {"id": "small", "status": {"value": "loaded"}},
            {"id": "huge", "status": {"value": "unloaded"}},
        ]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
            assert await loaded_local_model("http://127.0.0.1:8080/v1", client=client) == "small"
            assert await loaded_local_model("https://example.org/v1", client=client) == ""
    asyncio.run(run())
    assert requested == [("GET", "http://127.0.0.1:8080/v1/models")]


class FakeStream:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.chunks)
        except StopIteration:
            raise StopAsyncIteration

    async def aclose(self):
        self.closed = True


def chunk(text="", tokens=None):
    choice = [SimpleNamespace(delta=SimpleNamespace(content=text))] if text else []
    usage = SimpleNamespace(completion_tokens=tokens) if tokens is not None else None
    return SimpleNamespace(choices=choice, usage=usage)


class Completions:
    def __init__(self, response):
        self.response = response
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class Client:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def server_response(text="Server answer."):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=text, tool_calls=None))])


def test_instant_records_actual_first_token_and_throughput_with_fake_clock():
    clock = iter([0.0, 0.08, 0.08, 0.18])
    stream = FakeStream([chunk("Hello"), chunk(" there"), chunk(tokens=3)])
    completions = Completions(stream)
    result = asyncio.run(complete_instant(Client(completions), "small", "Say hello",
                                          clock=lambda: next(clock)))
    assert result == InstantAnswer("Hello there", "small", 80, 20.0, False)
    assert stream.closed
    assert len(completions.requests) == 1
    assert completions.requests[0]["stream"] is True
    assert completions.requests[0]["messages"][-1] == {"role": "user", "content": "Say hello"}
    assert len(completions.requests[0]["messages"]) == 2


def test_local_model_is_cancelled_on_first_token_timeout():
    class NeverResponds:
        async def create(self, **kwargs):
            await asyncio.Future()

    with pytest.raises(TimeoutError):
        asyncio.run(complete_instant(Client(NeverResponds()), "small", "Hello",
                                      first_token_deadline=0.01, total_deadline=0.1))


def test_partial_local_stream_failure_does_not_produce_an_answer():
    class BrokenStream(FakeStream):
        async def __anext__(self):
            result = await super().__anext__()
            if result is None:
                raise RuntimeError("local stream failed")
            return result

    stream = BrokenStream([chunk("incomplete"), None])
    with pytest.raises(RuntimeError, match="stream failed"):
        asyncio.run(complete_instant(Client(Completions(stream)), "small", "Hello"))
    assert stream.closed


@pytest.fixture
 def_placeholder():
    pass
