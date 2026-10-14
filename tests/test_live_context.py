"""Live per-turn context for tool-less chat (Discord, desktop plain chat): web results + the time, last."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from star import clock, live_context


@pytest.mark.parametrize("prompt", ["what's the latest news about Roblox", "any Roblox news today?",
                                    "weather in Chicago", "who won the game last night",
                                    "search the web for Luau type functions", "price of bitcoin",
                                    "what's new in Roblox Studio", "summarize https://example.com/a"])
def test_fresh_questions_search(prompt):
    assert live_context.wants_fresh_web(prompt)


@pytest.mark.parametrize("prompt", ["update the script so the door opens", "write a leaderboard",
                                    "what time is it", "explain RemoteEvents", "hi", "make the latest frame red"])
def test_ordinary_questions_do_not(prompt):
    assert not live_context.wants_fresh_web(prompt)


def test_auto_search_returns_cited_untrusted_results():
    async def searcher(query, limit):
        assert query == "latest Roblox news" and limit == 5
        return [{"title": "Roblox update", "url": "https://news.example/roblox", "snippet": "New editor"}]
    text, sources = asyncio.run(live_context.auto_search("latest Roblox news", searcher=searcher))
    assert "untrusted" in text and "https://news.example/roblox" in text and len(sources) == 1


def test_auto_search_failure_is_one_honest_line():
    async def broken(query, limit):
        raise RuntimeError("down")
    text, sources = asyncio.run(live_context.auto_search("latest Roblox news", searcher=broken))
    assert "failed" in text and "no internet access" in text and sources == []
    assert asyncio.run(live_context.auto_search("write a leaderboard", searcher=broken)) == ("", [])


def test_not_configured_says_so(monkeypatch):
    monkeypatch.setattr("star.web_search.web_search_available", lambda settings=None: False)
    text, _ = asyncio.run(live_context.auto_search("latest Roblox news"))
    assert "not set up" in text


def test_discord_block_ends_with_the_time():
    async def searcher(query, limit):
        return [{"title": "T", "url": "https://news.example/x", "snippet": "S"}]
    block = asyncio.run(live_context.discord_live("roblox news", searcher=searcher))
    assert block.index("https://news.example/x") < block.index("Now: ")
    assert block.splitlines()[-1].startswith("Now: ")
    plain = asyncio.run(live_context.discord_live("hello", searcher=searcher))
    assert plain.startswith("Now: ") and "news.example" not in plain


def test_server_clock_probe_reads_the_date_header_once_per_half_hour():
    clock.forget_server_clock()
    live_context.forget()
    calls = []

    async def get(url):
        calls.append(url)
        return "Tue, 13 Oct 2026 18:16:18 GMT"
    settings = SimpleNamespace(provider="star_server", server_endpoint="http://192.168.1.20:8080/v1")  # star:allow
    asyncio.run(live_context.refresh_server_clock(settings, get=get, monotonic=lambda: 10_000.0))
    asyncio.run(live_context.refresh_server_clock(settings, get=get, monotonic=lambda: 10_100.0))
    assert calls == ["http://192.168.1.20:8080/health"]  # documentation address (star:allow)
    assert clock.server_offset() is not None
    clock.forget_server_clock()
    live_context.forget()
    cloud = SimpleNamespace(provider="groq", server_endpoint="")
    asyncio.run(live_context.refresh_server_clock(cloud, get=get, monotonic=lambda: 50_000.0))
    assert len(calls) == 1
    live_context.forget()
