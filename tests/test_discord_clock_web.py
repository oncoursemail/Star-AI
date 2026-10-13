"""Discord: every message ends with the time; news/"latest" questions get cited web results first.

Real DiscordBrain with a fake model client (no network): what the model receives, in what order, and
what the session remembers (the time line is kept so the next request starts with cached bytes).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from star.discord_bot import brain as brain_module
from star.discord_bot.brain import DiscordBrain
from star.discord_bot.core import AccessPolicy, SessionMemory
from star.discord_bot.service import DiscordService, _accepts_live

LAN = "http://192.168.1.20:8080/v1"   # documentation address (star:allow)


class Completions:
    def __init__(self):
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="It is 13:05.",
                                                                                tool_calls=None))])


def make_service(monkeypatch, searcher=None):
    completions = Completions()

    class Client:
        chat = SimpleNamespace(completions=completions)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    settings = SimpleNamespace(validate=lambda: None, provider="groq", model="m", fast_model="",
                               server_endpoint="")
    monkeypatch.setattr(brain_module, "plan_route",
                        lambda settings, prompt, research=False: brain_module.ChatRoute("m", False, "test"))
    brain = DiscordBrain(settings=settings, client_factory=lambda s, **_: Client())
    monkeypatch.setattr(brain, "_learn_roles", lambda settings: asyncio.sleep(0))
    monkeypatch.setattr(brain, "_main_model_full", lambda settings, model: asyncio.sleep(0, result=False))
    service = DiscordService(AccessPolicy(owners=frozenset({1}), guilds=frozenset()), brain=brain, memory=SessionMemory(), searcher=searcher)
    return service, completions


def test_the_real_brain_takes_live_text_and_test_doubles_need_not():
    assert _accepts_live(DiscordBrain())

    class Old:
        async def reply(self, prompt, history):
            return "x"
    assert not _accepts_live(Old())


def test_plain_question_ends_with_the_time_and_is_remembered_with_it(monkeypatch):
    service, completions = make_service(monkeypatch)
    key = (None, 5, 1)
    asyncio.run(service.ask(key, "what time is it"))
    sent = completions.requests[0]["messages"][-1]["content"]
    assert sent.startswith("what time is it\n\nNow: ") and "the owner's local time" in sent
    assert "lack real-time data" in " ".join(completions.requests[0]["messages"][0]["content"].split())
    # The next request replays exactly what was sent (the server's cache matches it).
    asyncio.run(service.ask(key, "thanks"))
    replay = completions.requests[1]["messages"][1]
    assert replay == {"role": "user", "content": sent}
    assert completions.requests[1]["messages"][0] == completions.requests[0]["messages"][0]


def test_news_question_gets_cited_results_before_the_time(monkeypatch):
    seen = []

    async def searcher(query, limit):
        seen.append(query)
        return [{"title": "Roblox ships a terrain update", "url": "https://news.example/roblox", "snippet": "S"}]
    service, completions = make_service(monkeypatch, searcher=searcher)
    answer = asyncio.run(service.ask((None, 5, 1), "what's the latest news about Roblox"))
    assert answer == ("It is 13:05.\n\nSources:\n- Roblox ships a terrain update: <https://news.example/roblox>")
    assert service.memory.history((None, 5, 1))[1]["content"] == "It is 13:05."   # as generated (cached)
    sent = completions.requests[0]["messages"][-1]["content"]
    assert seen == ["what's the latest news about Roblox"]
    assert sent.index("https://news.example/roblox") < sent.index("\nNow: ")
    assert sent.rstrip().splitlines()[-1].startswith("Now: ")
    # Web results are never stored in the session.
    remembered = service.memory.history((None, 5, 1))[0]["content"]
    assert remembered == "what's the latest news about Roblox"


def test_failed_search_is_one_honest_line(monkeypatch):
    async def broken(query, limit):
        raise RuntimeError("down")
    service, completions = make_service(monkeypatch, searcher=broken)
    asyncio.run(service.ask((None, 5, 1), "any Roblox news today?"))
    sent = completions.requests[0]["messages"][-1]["content"]
    assert "failed" in sent and "no internet access" in sent and "\nNow: " in sent
