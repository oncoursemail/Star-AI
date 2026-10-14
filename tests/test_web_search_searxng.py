"""STAR search: the self-hosted SearXNG (behind star-search-gateway) answers when no Brave/Tavily key is set.

The gateway reply is a recorded fixture (tests/fixtures/web/searxng_roblox_news.json); no network.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from star import clock, web_search

RECORDED = json.loads((Path(__file__).parent / "fixtures" / "web" / "searxng_roblox_news.json")
                      .read_text(encoding="utf-8"))
LAN_SETTINGS = SimpleNamespace(server_endpoint="http://192.168.1.20:8080/v1", search_endpoint="")  # star:allow
KEY = "test-server-key-0123456789"   # synthetic (star:allow)


def keys(monkeypatch, **present):
    monkeypatch.setattr("star.providers.get_api_key", lambda name: {"star_server": KEY, **present}.get(name))


def use_transport(monkeypatch, transport):
    real = httpx.AsyncClient
    monkeypatch.setattr(web_search.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))


def gateway(seen):
    def handler(request):
        seen.append(request)
        return httpx.Response(200, headers={"date": "Tue, 13 Oct 2026 18:16:18 GMT"}, json=RECORDED)
    return httpx.MockTransport(handler)


def test_search_endpoint_defaults_to_the_star_server_host():
    assert web_search.search_endpoint_for(LAN_SETTINGS) == "http://192.168.1.20:8093"  # documentation address (star:allow)
    off = SimpleNamespace(server_endpoint=LAN_SETTINGS.server_endpoint, search_endpoint="off")
    assert web_search.search_endpoint_for(off) == ""
    assert web_search.search_endpoint_for(SimpleNamespace(server_endpoint="", search_endpoint="")) == ""
    public = SimpleNamespace(server_endpoint="https://api.example.com:8080/v1", search_endpoint="")
    assert web_search.search_endpoint_for(public) == ""
    assert web_search.search_endpoint_for(None) == ""


def test_no_key_uses_star_search_with_the_server_key(monkeypatch):
    keys(monkeypatch)
    seen = []
    use_transport(monkeypatch, gateway(seen))
    clock.forget_server_clock()
    results = asyncio.run(web_search.search_web("latest Roblox news", limit=4, settings=LAN_SETTINGS))
    assert [r["url"] for r in results] == [r["url"] for r in RECORDED["results"]]
    request = seen[0]
    assert str(request.url).startswith("http://192.168.1.20:8093/search?")  # documentation address (star:allow)
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.url.params["categories"] == "news" and request.url.params["time_range"] == "week"
    assert clock.server_offset() is not None          # the gateway's Date header was observed
    clock.forget_server_clock()
    text = web_search.source_context(results)
    assert "untrusted" in text and RECORDED["results"][0]["url"] in text


def test_general_question_has_no_news_filter(monkeypatch):
    keys(monkeypatch)
    seen = []
    use_transport(monkeypatch, gateway(seen))
    asyncio.run(web_search.search_web("Roblox task.wait documentation", settings=LAN_SETTINGS))
    assert "categories" not in seen[0].url.params


def test_without_any_provider_the_error_says_how_to_fix_it(monkeypatch):
    monkeypatch.setattr("star.providers.get_api_key", lambda name: None)
    with pytest.raises(RuntimeError, match="STAR Server"):
        asyncio.run(web_search.search_web("news", settings=LAN_SETTINGS))
    assert web_search.web_search_available(LAN_SETTINGS) is False
    keys(monkeypatch)
    assert web_search.web_search_available(LAN_SETTINGS) is True


def test_star_search_failure_is_reported_without_the_key(monkeypatch):
    keys(monkeypatch)
    use_transport(monkeypatch, httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": "STAR Server key required"})))
    with pytest.raises(RuntimeError) as failure:
        asyncio.run(web_search.search_web("news", settings=LAN_SETTINGS))
    assert "STAR search" in str(failure.value) and "401" in str(failure.value) and KEY not in str(failure.value)


def test_a_failed_brave_key_falls_back_to_star_search(monkeypatch):
    keys(monkeypatch, brave="brave-test-key-000")
    seen = []

    def handler(request):
        if request.url.host == "api.search.brave.com":
            return httpx.Response(429, json={})
        seen.append(request)
        return httpx.Response(200, json=RECORDED)
    use_transport(monkeypatch, httpx.MockTransport(handler))
    results = asyncio.run(web_search.search_web("latest Roblox news", settings=LAN_SETTINGS))
    assert results and len(seen) == 1
