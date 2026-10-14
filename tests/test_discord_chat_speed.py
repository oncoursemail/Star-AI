"""Discord chat speed (docs/agents/chat-speed-20261013.md): routing, fast path, streaming. Offline fakes only."""
import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from star import providers, server_roles
from star.discord_bot import brain as brain_module
from star.discord_bot.brain import QUEUED_NOTE, DiscordBrain, can_downgrade, plan_route
from star.discord_bot.core import AccessPolicy, RateLimiter
from star.discord_bot.service import DiscordService
from star.discord_bot.streaming import CURSOR, LiveReply, preview

ENDPOINT = "http://brain.lan:8080/v1"   # never contacted: discovery, probe and client are fakes
FLEET = [
    {"id": "star-fast", "aliases": ["star-code", "star-vision"], "status": {"value": "loaded"},
     "architecture": {"input_modalities": ["text", "image"]}},
    {"id": "star-voice", "aliases": ["star-quick"], "status": {"value": "loaded"}},
    {"id": "star-deep", "status": {"value": "unloaded"}},
]


def server_settings(**extra):
    values = dict(provider="star_server", server_endpoint=ENDPOINT, model="star-fast", fast_model="",
                  reasoning_model="", roblox_model="", vision_model="", validate=lambda: None)
    values.update(extra)
    return SimpleNamespace(**values)


@pytest.fixture
def fleet(monkeypatch):
    """A STAR Server fleet as discovery would record it: star-voice = quick, star-fast = code (2 slots)."""
    server_roles.forget()
    discovered = []

    def discover(endpoint, key):
        discovered.append(endpoint)
        server_roles.remember_models(endpoint, FLEET)
        providers.remember_server_limits(endpoint, "star-fast", 65536, 2)
        providers.remember_server_limits(endpoint, "star-voice", 32768, 2)
        return {}

    monkeypatch.setattr(providers, "connection_for", lambda settings: (ENDPOINT, "test-key"))
    fake_desktop = ModuleType("star.desktop_core")
    fake_desktop.Settings = object
    fake_desktop.app_data = lambda: None
    monkeypatch.setitem(sys.modules, "star.desktop_core", fake_desktop)
    yield SimpleNamespace(discover=discover, discovered=discovered)
    server_roles.forget()


class Chunk(SimpleNamespace):
    pass


def chunk(text=None, tool_calls=None):
    return Chunk(choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=tool_calls,
                                                                  reasoning_content=None))])


class Stream:
    def __init__(self, parts):
        self.parts, self.closed = list(parts), False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for part in self.parts:
            yield part

    async def close(self):
        self.closed = True


def client_factory(calls, *, parts=("Hi", " there", "!"), fail_models=()):
    class Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def create(self, **kwargs):
            calls.append(kwargs)
            if kwargs["model"] in fail_models:
                error = RuntimeError("model not found")
                error.status_code = 404
                raise error
            if kwargs.get("stream"):
                return Stream([chunk(None)] + [chunk(p) for p in parts])
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="".join(parts), tool_calls=None))])
    return lambda settings, **kwargs: Client()


# ------------------------------------------------------------------ routing (pure)

def test_plain_chat_goes_to_the_quick_model_and_roblox_or_code_to_the_main_model(fleet):
    fleet.discover(ENDPOINT, "k")
    settings = server_settings()
    quick = plan_route(settings, "hey, how are you today?")
    assert quick.model == "star-voice" and quick.quick and quick.fallback == "star-fast"
    for prompt in ("Write a Luau script for a sliding door", "fix this python bug please",
                   "How do RemoteEvents work in Roblox?"):
        route = plan_route(settings, prompt)
        assert route.model == "star-fast" and not route.quick, prompt
    assert not plan_route(settings, "what is new in Roblox", research=True).quick
    # Before the server was asked (or for one model only) everything stays on the primary model.
    server_roles.forget()
    assert plan_route(settings, "hey").model == "star-fast"


def test_only_general_reasoning_chat_may_move_to_the_quick_model():
    route = SimpleNamespace(reason="reasoning")
    assert can_downgrade("compare cats and dogs as pets", route)
    assert not can_downgrade("compare two python sorting algorithms", route)
    assert not can_downgrade("plan a Roblox obby with checkpoints", route)
    assert not can_downgrade("hello", SimpleNamespace(reason="roblox"))


# ------------------------------------------------------------------ fast path request

def test_casual_message_streams_from_the_quick_model_without_thinking(fleet):
    calls, seen = [], []

    async def on_delta(text):
        seen.append(text)

    brain = DiscordBrain(settings=server_settings(), client_factory=client_factory(calls),
                         discover=fleet.discover, busy_probe=None)
    answer = asyncio.run(brain.reply("hey star, how's it going?", [], on_delta=on_delta))
    assert answer == "Hi there!"
    assert seen == ["Hi", "Hi there", "Hi there!"]
    assert fleet.discovered == [ENDPOINT]          # the server's model list is read once
    request = calls[0]
    assert request["model"] == "star-voice" and request["stream"] is True
    assert request["max_tokens"] == brain_module.QUICK_MAX_TOKENS
    extra = request["extra_body"]
    assert extra["cache_prompt"] is True and "id_slot" not in extra
    assert extra["chat_template_kwargs"]["enable_thinking"] is False
    assert "tools" not in request
    assert brain.last_stats.quick and brain.last_stats.chunks == 3
    # Second turn: discovery is not repeated, and the system prompt is byte-identical (prompt cache).
    asyncio.run(brain.reply("and you?", [{"role": "user", "content": "hey"},
                                         {"role": "assistant", "content": "Hi there!"}]))
    assert fleet.discovered == [ENDPOINT]
    assert calls[1]["messages"][0] == calls[0]["messages"][0]
    assert "stream" not in calls[1]                # no live view requested: one-piece answer


def test_main_model_busy_moves_general_chat_and_queues_code_with_a_note(fleet):
    calls, notes = [], []

    async def all_busy(settings, model, *, conversation=""):
        return frozenset({0, 1}) if model == "star-fast" else frozenset()

    async def on_status(note):
        notes.append(note)

    async def ignore(text):
        pass

    brain = DiscordBrain(settings=server_settings(), client_factory=client_factory(calls),
                         discover=fleet.discover, busy_probe=all_busy)
    asyncio.run(brain.reply("compare cats and dogs as pets", [], on_delta=ignore, on_status=on_status))
    assert calls[-1]["model"] == "star-voice" and brain.last_stats.reason == "main-busy"
    assert notes == []
    asyncio.run(brain.reply("fix my python code that crashes", [], on_delta=ignore, on_status=on_status))
    assert calls[-1]["model"] == "star-fast" and notes == [QUEUED_NOTE]
    assert calls[-1]["max_tokens"] == brain_module.FULL_MAX_TOKENS
    assert "enable_thinking" not in calls[-1]["extra_body"]["chat_template_kwargs"]


def test_missing_quick_model_falls_back_to_the_main_model(fleet):
    calls = []
    brain = DiscordBrain(settings=server_settings(), client_factory=client_factory(calls, fail_models={"star-voice"}),
                         discover=fleet.discover)
    assert asyncio.run(brain.reply("hello there", [])) == "Hi there!"
    assert [c["model"] for c in calls] == ["star-voice", "star-fast"]
    assert "quick" not in server_roles.discovered_roles(server_settings())


def test_streamed_tool_call_is_refused(fleet):
    calls = []

    class ToolClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def create(self, **kwargs):
            calls.append(kwargs)
            return Stream([chunk(None, tool_calls=[{"id": "x"}])])

    async def ignore(text):
        pass

    brain = DiscordBrain(settings=server_settings(), client_factory=lambda s, **k: ToolClient(),
                         discover=fleet.discover)
    with pytest.raises(RuntimeError, match="plain text"):
        asyncio.run(brain.reply("hello", [], on_delta=ignore))


def test_service_passes_live_callbacks_only_to_streaming_brains():
    class Plain:
        async def reply(self, prompt, history):
            return "plain"

    class Live:
        streams = True

        async def reply(self, prompt, history, *, on_delta=None, on_status=None):
            await on_delta("li")
            await on_delta("live")
            return "live"

    shown = []

    async def on_delta(text):
        shown.append(text)

    policy = AccessPolicy(frozenset({1}), frozenset())

    async def run():
        plain = DiscordService(policy, brain=Plain(), rate_limiter=RateLimiter())
        assert await plain.ask((None, 2, 1), "hi", on_delta=on_delta) == "plain"
        live = DiscordService(policy, brain=Live(), rate_limiter=RateLimiter())
        assert await live.ask((None, 2, 1), "hi", on_delta=on_delta) == "live"
    asyncio.run(run())
    assert shown == ["li", "live"]


# ------------------------------------------------------------------ live message (pure)

def test_live_reply_posts_first_text_at_once_then_rate_limits_edits():
    now = [0.0]
    log = []

    async def post(text):
        log.append(("post", text))
        return "msg"

    async def edit(handle, text):
        log.append(("edit", text))

    live = LiveReply(post, edit, interval=1.0, clock=lambda: now[0])

    async def run():
        await live.status("queued")
        await live.update("Hel")              # first text replaces the note immediately
        now[0] = 0.5
        await live.update("Hello")            # too soon: not shown
        now[0] = 1.6
        await live.update("Hello world")
        assert await live.finish("Hello world, done.")
    asyncio.run(run())
    assert log == [("post", "queued"), ("edit", "Hel" + CURSOR), ("edit", "Hello world" + CURSOR),
                   ("edit", "Hello world, done.")]


def test_live_reply_stops_quietly_when_discord_refuses_an_edit():
    async def post(text):
        return "msg"

    async def edit(handle, text):
        raise RuntimeError("429")

    live = LiveReply(post, edit, interval=0)

    async def run():
        await live.update("a")
        await live.update("ab")
        assert live.broken and not live.live
        assert await live.finish("done") is False
    asyncio.run(run())


def test_preview_fits_and_closes_an_open_code_block():
    text = "Here:\n```lua\nlocal x = 1\n" + "x = x + 1\n" * 500
    shown = preview(text, 1900)
    assert len(shown) <= 1900 and shown.count("```") % 2 == 0 and shown.endswith(CURSOR)


# ------------------------------------------------------------------ gateway fakes (real discord.py objects)

class StreamingBrain:
    streams = True

    def __init__(self, parts):
        self.parts = parts

    async def reply(self, prompt, history, *, evidence="", on_delta=None, on_status=None):
        text = ""
        for part in self.parts:
            text += part
            if on_delta:
                await on_delta(text)
        return text


def test_dm_answer_appears_early_and_is_finished_in_the_same_message():
    from tests.test_discord_gateway_fake import DMChannel, dm, make_bot

    class Sent:
        def __init__(self, channel, content):
            self.channel, self.content = channel, content

        async def edit(self, content=None, **kwargs):
            self.channel.edits.append(content)

    class LiveChannel(DMChannel):
        def __init__(self, discord):
            super().__init__(discord)
            self.edits = []

        async def send(self, content=None, **kwargs):
            self.sent.append((content, kwargs))
            return Sent(self, content)

    discord, bot, service, _ = make_bot(brain=StreamingBrain(["Hello", " from", " STAR."]))

    async def run():
        try:
            channel = LiveChannel(discord)
            await bot.on_message(dm(discord, channel, "hi"))
            assert [c for c, _ in channel.sent] == ["Hello" + CURSOR]     # one message, posted early
            assert channel.edits[-1] == "Hello from STAR."                 # finished in place
        finally:
            await bot.close()
    asyncio.run(run())


def test_slash_ask_streams_into_the_deferred_response():
    from tests.test_discord_gateway_fake import embeds_text, interaction, make_bot
    discord, bot, service, _ = make_bot(brain=StreamingBrain(["Remote", "Events ", "explained."]))
    ask = bot.tree.get_command("ask")

    async def run():
        try:
            owner = interaction()

            async def edit_original_response(**kwargs):
                owner.log.append(("edit_original", kwargs))
            owner.edit_original_response = edit_original_response
            await ask.callback(owner, prompt="What is a RemoteEvent?", private=True)
            kinds = [kind for kind, _ in owner.log]
            assert kinds[0] == "defer" and "followup" not in kinds
            final = owner.log[-1][1]
            assert final["embed"].description == "RemoteEvents explained." and final.get("view") is not None
        finally:
            await bot.close()
    asyncio.run(run())


def test_live_text_goes_at_the_end_of_the_user_turn_only(fleet):
    calls = []
    brain = DiscordBrain(settings=server_settings(), client_factory=client_factory(calls), discover=fleet.discover)
    asyncio.run(brain.reply("hello", [], live="Now: Tuesday 13 October 2026, 18:30"))
    asyncio.run(brain.reply("hello", [], live="Now: Tuesday 13 October 2026, 18:31"))
    first, second = calls
    assert first["messages"][-1]["content"].endswith("18:30") and first["messages"][-1]["content"].startswith("hello")
    assert first["messages"][:-1] == second["messages"][:-1]      # system prefix unchanged by the clock


def test_brain_chat_templates_named_in_models_ini_are_shipped():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "server" / "brain"
    names = [line.split("=", 1)[1].strip() for line in (root / "models.ini").read_text(encoding="utf-8").splitlines()
             if line.startswith("chat-template-file")]
    assert names, "star-voice should use the cache-friendly template"
    for name in names:
        assert name.startswith("/opt/star/config/templates/")
        template = root / "templates" / name.rsplit("/", 1)[1]
        text = template.read_text(encoding="utf-8")
        # Earlier answers carry the same empty think block the generation prompt ends with.
        assert "empty_think + content" in text and "enable_thinking is false" in text
    assert "templates/*.jinja" in (root / "apply.sh").read_text(encoding="utf-8")
