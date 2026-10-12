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
def desk(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(core, "connection_for", lambda *_: ("http://127.0.0.1:8080/v1", "local-only"))
    home = core.app_data()
    chats = Conversations(home / "conversations.sqlite3")
    chat_id = chats.new_chat("STAR")
    settings = Settings(provider="star_server", server_endpoint="http://127.0.0.1:8080/v1",
                        model="server-model", gguf_model="configured.gguf", knowledge_endpoint="off",
                        instant_route_enabled=True)
    events = []
    yield SimpleNamespace(home=home, chats=chats, chat_id=chat_id, settings=settings, events=events)
    chats.close()


def run_saved_turn(desk, question, *, mode="fast", **flags):
    desk.chats.add("STAR", "user", question, chat_id=desk.chat_id)
    answer = run_task(desk.settings, question, chat_id=desk.chat_id, mode=mode,
                      on_event=desk.events.append, **flags)
    desk.chats.add("STAR", "assistant", answer, chat_id=desk.chat_id)
    rows = desk.chats.recent_records("STAR", chat_id=desk.chat_id)
    record = json.loads(next((desk.home / "runs").glob("*/transcript.json")).read_text(encoding="utf-8"))
    return answer, rows, record


def test_loaded_local_answer_is_saved_once_and_its_brain_recorded(monkeypatch, desk):
    probes = []

    async def probe(*_):
        probes.append("loaded")
        return "pc-small"

    async def answer(*_):
        return InstantAnswer("A word that reads the same backwards.", "pc-small", 96, 33.2, False)

    monkeypatch.setattr(core, "loaded_local_model", probe)
    monkeypatch.setattr(core, "answer_on_pc", answer)
    monkeypatch.setattr(core, "open_client", lambda *_: pytest.fail("server must not be called"))
    response, rows, artifact = run_saved_turn(desk, "What is a palindrome?")
    assert response.startswith("A word")
    assert probes == ["loaded"]
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[-1]["body"] == response
    assert artifact["answer_stats"] == {
        "brain": "pc", "model": "pc-small", "first_token_ms": 96,
        "tokens_per_second": 33.2, "estimated_tokens": False}
    assert [e["event"] for e in desk.events].count("assistant_delta") == 1
    assert [e["event"] for e in desk.events].count("model_answered") == 1


def test_failed_instant_tries_server_once_with_no_duplicate_row(monkeypatch, desk):
    async def loaded(*_):
        return "pc-small"

    async def failed(*_):
        raise TimeoutError("first token slow")

    monkeypatch.setattr(core, "loaded_local_model", loaded)
    monkeypatch.setattr(core, "answer_on_pc", failed)
    server = Completions(server_response())
    monkeypatch.setattr(core, "open_client", lambda *_: Client(server))
    answer, rows, artifact = run_saved_turn(desk, "What is a palindrome?")
    assert answer == "Server answer."
    assert len(server.requests) == 1
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert artifact["answer_stats"]["brain"] == "server"
    assert artifact["answer_stats"]["model"] == "server-model"
    assert [e["event"] for e in desk.events].count("instant_fallback") == 1
    assert [e["event"] for e in desk.events].count("model_answered") == 1


@pytest.mark.parametrize("flag", [False, None])
def test_instant_disabled_never_probes(monkeypatch, desk, flag):
    desk.settings.instant_route_enabled = flag
    monkeypatch.setattr(core, "loaded_local_model", lambda *_: pytest.fail("must not probe"))
    server = Completions(server_response("Server as selected."))
    monkeypatch.setattr(core, "open_client", lambda *_: Client(server))
    answer, rows, _ = run_saved_turn(desk, "What is a palindrome?")
    assert answer == "Server as selected."
    assert len(server.requests) == 1 and len(rows) == 2


@pytest.mark.parametrize("case", ["attachment", "probe_error", "uninstalled"])
def test_attachment_and_failed_probe_keep_the_single_server_request(monkeypatch, desk, case):
    probed = []

    async def probe(*_):
        probed.append("called")
        if case == "probe_error":
            raise RuntimeError("PC model endpoint unavailable")
        return "pc-small"

    if case == "uninstalled":
        desk.settings.gguf_model = ""
        desk.settings.router_models_dir = ""
    monkeypatch.setattr(core, "loaded_local_model", probe)
    monkeypatch.setattr(core, "answer_on_pc", lambda *_: pytest.fail("no local answer"))
    server = Completions(server_response("Server answered once."))
    monkeypatch.setattr(core, "open_client", lambda *_: Client(server))
    kwargs = {"attachment_count": 1} if case == "attachment" else {}
    answer, rows, artifact = run_saved_turn(desk, "What is a palindrome?", **kwargs)
    assert answer == "Server answered once."
    assert [row["role"] for row in rows] == ["user", "assistant"]
    assert len(server.requests) == 1
    assert probed == (["called"] if case == "probe_error" else [])
    assert artifact["answer_stats"]["brain"] == "server"


@pytest.mark.parametrize("question", PERSONAL_PROMPTS)
def test_personal_questions_keep_real_server_context_without_local_probe(monkeypatch, desk, question):
    earlier = "The chosen symbol is an acorn."
    preference = "Prefer short paragraphs."
    checkpoint = "The checkpoint marker is amber."
    desk.chats.add("STAR", "user", earlier, chat_id=desk.chat_id)
    desk.chats.add("STAR", "assistant", "The acorn is selected.", chat_id=desk.chat_id)
    memory = core.Memory(desk.home / "checkpoints.sqlite3")
    try:
        memory.put(core.memory_scope_for(desk.settings, desk.chat_id), checkpoint)
    finally:
        memory.close()
    lessons = LessonStore(desk.home)
    try:
        captured = lessons.capture_owner(project="STAR", kind="preference", text=preference,
                                         message=preference, source="fixture:owner")
        assert captured.status == "accepted"
    finally:
        lessons.close()
    monkeypatch.setattr(core, "loaded_local_model", lambda *_: pytest.fail("personal question must not probe"))
    monkeypatch.setattr(core, "answer_on_pc", lambda *_: pytest.fail("personal question must not use bare prompt"))
    server = Completions(server_response("Context-aware server answer."))
    monkeypatch.setattr(core, "open_client", lambda *_: Client(server))

    answer, rows, artifact = run_saved_turn(desk, question)
    assert answer == "Context-aware server answer."
    assert len(server.requests) == 1
    messages = server.requests[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "You are STAR Genesis" in messages[0]["content"]
    assert checkpoint in messages[0]["content"]
    assert any(message["role"] == "user" and message["content"] == earlier for message in messages)
    current = json.dumps(messages[-1]["content"])
    assert question in current
    assert preference in current
    assert [row["role"] for row in rows] == ["user", "assistant", "user", "assistant"]
    assert artifact["answer_stats"]["brain"] == "server"
    assert not any(event["event"] in {"instant_selected", "instant_fallback"} for event in desk.events)


@pytest.mark.parametrize("value", ["yes", "automatic", 0, 1, [], {}])
def test_instant_setting_validation_has_no_automatic_mode(value):
    with pytest.raises(ValueError, match="^Instant answers setting must be true or false$"):
        Settings(instant_route_enabled=value).validate()


def test_settings_and_sanitized_activity_are_nonsecret(tmp_path):
    for value in (True, False, None):
        settings = shell.apply_setting_changes(Settings(), {"instant_route_enabled": value})
        settings.save(tmp_path / "settings.json")
        assert Settings.load(tmp_path / "settings.json").instant_route_enabled is value
    payload = sanitize_event({"event": "answer_stats", "brain": "pc",
                              "model": "pc-small", "first_token_ms": 96,
                              "tokens_per_second": 33.2, "estimated_tokens": False,
                              "prompt": "must never leak", "secret": "must never leak"})
    assert payload["activity"] == {
        "type": "answer_stats", "brain": "pc", "model": "pc-small",
        "first_token_ms": 96, "tokens_per_second": 33.2, "estimated_tokens": False}
    assert "must never leak" not in str(payload)


def test_default_off_runs_original_server_and_still_emits_stats(monkeypatch, desk):
    assert Settings().instant_route_enabled is False
    desk.settings.instant_route_enabled = False
    monkeypatch.setattr(core, "loaded_local_model", lambda *_: pytest.fail("must not probe"))
    server = Completions(server_response())
    monkeypatch.setattr(core, "open_client", lambda *_: Client(server))
    answer, rows, artifact = run_saved_turn(desk, "What is a palindrome?")
    assert answer == "Server answer." and len(server.requests) == 1
    assert [row["role"] for row in rows] == ["user", "assistant"]
    assert artifact["answer_stats"]["brain"] == "server"
    stats = [event for event in desk.events if event["event"] == "answer_stats"]
    assert len(stats) == 1 and stats[0]["brain"] == "server"


@pytest.mark.parametrize("case", ["instant", "fallback", "off", "attachment"])
def test_real_chat_bridge_persists_origin_and_defers_only_instant_warmup(monkeypatch, desk, case):
    # Bridge is nested inside launch(). Use its actual compiled production
    # method, without copying its source or starting Qt/WebEngine/GPU widgets.
    bridge_code = next(code for code in shell.launch.__code__.co_consts
                       if isinstance(code, CodeType) and code.co_name == "Bridge")
    method_code = next(code for code in bridge_code.co_consts
                       if isinstance(code, CodeType) and code.co_name == "_run_chat")
    assert method_code.co_freevars == ()
    run_chat = FunctionType(method_code, vars(shell))
    desk.settings.instant_route_enabled = case != "off"
    settings_file = desk.home / "settings.json"
    desk.settings.save(settings_file)
    progress, warms, health, probed = [], [], [], []
    digest = lambda report=None: None
    bridge = SimpleNamespace(settings_file=settings_file, cancel_chat=threading.Event(), turn=None,
                             _emit=lambda rid, kind, data: progress.append((rid, kind, data)),
                             _warm=lambda **kwargs: warms.append(kwargs), _digest_when_idle=digest)
    monkeypatch.setattr(shell, "note_server_result", lambda *args: health.append(args))
    monkeypatch.setattr(shell, "prepare_turn", lambda *args, **kwargs: SimpleNamespace(
        pictures=[], documents=[], prompt=lambda text: text, footer=""))
    switched = []

    def switch_view():
        second = desk.chats.new_chat("STAR")
        desk.chats.switch_chat("STAR", second)
        switched.append(second)

    async def probe(*_):
        probed.append("loaded")
        return "pc-small"

    async def instant(*_):
        if case == "fallback":
            raise TimeoutError("first token slow")
        assert case == "instant"
        switch_view()
        return InstantAnswer("Instant reply.", "pc-small", 80, 20.0, False)

    class Server(Completions):
        async def create(self, **kwargs):
            switch_view()
            return await super().create(**kwargs)

    server = Server(server_response())
    monkeypatch.setattr(core, "loaded_local_model", probe)
    monkeypatch.setattr(core, "answer_on_pc", instant)
    monkeypatch.setattr(core, "open_client", lambda *_: Client(server))
    selected = [desk.home / "reference.wav"] if case == "attachment" else []
    result = run_chat(bridge, "request-1", "What is a palindrome?", selected,
                      "fast", False, False, None)
    expected = "Instant reply." if case == "instant" else "Server answer."
    assert result["answer"] == expected
    assert len(server.requests) == (0 if case == "instant" else 1)
    assert probed == (["loaded"] if case in {"instant", "fallback"} else [])
    rows = desk.chats.recent_records("STAR", chat_id=desk.chat_id)
    assert [row["role"] for row in rows] == ["user", "assistant"]
    assert rows[-1]["body"] == expected
    assert bridge.turn.chat_id == desk.chat_id
    assert len(switched) == 1 and desk.chats.active_chat("STAR") == switched[0]
    assert desk.chats.recent_records("STAR", chat_id=switched[0]) == []
    activities = [data["activity"] for _, _, data in progress if "activity" in data]
    stats = [activity for activity in activities if activity["type"] == "answer_stats"]
    assert len(stats) == 1
    assert stats[0]["brain"] == ("pc" if case == "instant" else "server")
    assert sum(activity["type"] == "instant_fallback" for activity in activities) == (case == "fallback")
    if case == "instant":
        assert warms == [] and health == []
    else:
        assert warms == [{"check": False, "then": digest}]
        assert len(health) == 1 and health[0][1:] == (True, "ok")


def test_documentation_discloses_missing_instant_context():
    document = Path(__file__).resolve().parents[1] / "docs" / "STAR_MODEL_ROUTER_WINDOWS.md"
    assert "Instant answers do not use the conversation, lessons or memory." in document.read_text(encoding="utf-8")


def test_decision_overhead_benchmark():
    import time
    count = 20000
    start = time.perf_counter_ns()
    for _ in range(count):
        decide_instant_route(**BASE)
    microseconds = (time.perf_counter_ns() - start) / (count * 1000)
    import warnings
    warnings.warn(f"Instant routing decision overhead: {microseconds:.3f} microseconds/call over {count} calls", stacklevel=1)
    assert microseconds >= 0
