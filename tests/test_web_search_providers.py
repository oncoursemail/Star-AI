"""The provider chain of star/web_search.py: Brave, then Tavily, then the self-hosted STAR search.

One fake handler plays all three services; no network. test_web_search_searxng.py covers the
SearXNG-only set-up; these cover the order, the fall-through and what a failure reports.
"""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from star import web_search

LAN = SimpleNamespace(server_endpoint="http://192.168.1.20:8080/v1", search_endpoint="")  # documentation address (star:allow)
SERVER_KEY = "test-server-key-0123456789"   # synthetic (star:allow)
BRAVE_KEY = "test-brave-key"                # synthetic (star:allow)
TAVILY_KEY = "test-tavily-key"              # synthetic (star:allow)


def hit(n, host="example.com"):
    return {"url": f"https://{host}/{n}", "title": f"Result {n}"}


@pytest.fixture
def services(monkeypatch):
    """Answers for each provider: JSON, raw bytes, an int HTTP status, or a callable giving one of those."""
    state = {"brave": {"web": {"results": [dict(hit(1), description="from brave")]}},
             "tavily": {"results": [dict(hit(2), content="from tavily")]},
             "searx": {"results": [dict(hit(3), snippet="from searx")]},
             "seen": []}

    def handler(request):
        state["seen"].append(request)
        host = request.url.host
        name = "brave" if host == "api.search.brave.com" else "tavily" if host == "api.tavily.com" else "searx"
        answer = state[name]
        if callable(answer):
            answer = answer()
        if isinstance(answer, int):
            return httpx.Response(answer)
        if isinstance(answer, bytes):
            return httpx.Response(200, content=answer, headers={"content-type": "application/json"})
        return httpx.Response(200, json=answer)

    real = httpx.AsyncClient
    monkeypatch.setattr(web_search.httpx, "AsyncClient",
                        lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    return state


def keys(monkeypatch, *names):
    present = {"brave": BRAVE_KEY, "tavily": TAVILY_KEY, "star_server": SERVER_KEY}
    monkeypatch.setattr("star.providers.get_api_key", lambda name: present.get(name) if name in names else None)


def hosts(state):
    return [request.url.host for request in state["seen"]]


def test_brave_answers_first_with_the_owners_key_and_safe_search(monkeypatch, services):
    keys(monkeypatch, "brave", "tavily", "star_server")
    results = asyncio.run(web_search.search_web("  lua tables  ", limit=3, settings=LAN))
    assert results == [{"title": "Result 1", "url": "https://example.com/1", "snippet": "from brave"}]
    [request] = services["seen"]
    assert request.headers["x-subscription-token"] == BRAVE_KEY
    assert request.url.params["q"] == "lua tables" and request.url.params["count"] == "3"
    assert request.url.params["safesearch"] == "moderate"


@pytest.mark.parametrize("brave_reply", [
    ["not", "an", "object"],            # regression: list JSON raised AttributeError and ended the search
    {"web": None},                      # regression: same for a null "web"
    {"web": {"results": []}},
    500,
    b"not json",
])
def test_a_brave_reply_that_is_unusable_falls_through_to_tavily(monkeypatch, services, brave_reply):
    keys(monkeypatch, "brave", "tavily")
    services["brave"] = brave_reply
    results = asyncio.run(web_search.search_web("lua tables", settings=LAN))
    assert [r["snippet"] for r in results] == ["from tavily"]
    assert hosts(services) == ["api.search.brave.com", "api.tavily.com"]
    tavily = services["seen"][1]
    assert tavily.headers["authorization"] == f"Bearer {TAVILY_KEY}"


def test_the_self_hosted_search_answers_when_the_keyed_providers_fail(monkeypatch, services):
    keys(monkeypatch, "brave", "tavily", "star_server")
    services["brave"], services["tavily"] = 429, {"results": "nope"}
    results = asyncio.run(web_search.search_web("lua tables", settings=LAN))
    assert [r["snippet"] for r in results] == ["from searx"]
    assert hosts(services)[-1] == "192.168.1.20"   # documentation address (star:allow)


def test_when_everything_fails_each_provider_says_why_and_no_key_is_shown(monkeypatch, services):
    keys(monkeypatch, "brave", "tavily", "star_server")
    services["brave"], services["tavily"], services["searx"] = 401, {"results": []}, 503
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(web_search.search_web("lua tables", settings=LAN))
    message = str(caught.value)
    assert message.startswith("Web research unavailable: ")
    assert "Brave: HTTPStatusError" in message
    assert "Tavily returned no usable web results" in message
    assert "STAR search: HTTPStatusError 503" in message
    for secret in (BRAVE_KEY, TAVILY_KEY, SERVER_KEY):
        assert secret not in message


def test_an_oversized_self_hosted_reply_is_refused(monkeypatch, services):
    keys(monkeypatch, "star_server")
    services["searx"] = b'{"results": [], "pad": "' + b"x" * (1024 * 1024) + b'"}'
    with pytest.raises(RuntimeError, match="STAR search: ValueError"):
        asyncio.run(web_search.search_web("lua tables", settings=LAN))


def test_a_news_question_retries_without_the_news_filter_when_the_week_is_empty(monkeypatch, services):
    keys(monkeypatch, "star_server")
    answers = iter([{"results": []}, {"results": [dict(hit(9), snippet="older")]}])
    services["searx"] = lambda: next(answers)
    results = asyncio.run(web_search.search_web("latest Roblox update", settings=LAN))
    assert [r["snippet"] for r in results] == ["older"]
    first, second = (request.url.params for request in services["seen"])
    assert first["categories"] == "news" and "categories" not in second


@pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("x" * 601, 5), ("ok", 0), ("ok", 9), (None, 5)])
def test_queries_and_limits_are_bounded_before_any_request(monkeypatch, services, query, limit):
    keys(monkeypatch, "brave")
    with pytest.raises(ValueError, match="1–600 characters"):
        asyncio.run(web_search.search_web(query, limit=limit, settings=LAN))
    assert services["seen"] == []


def test_fresh_questions_are_recognised():
    assert web_search.is_fresh_query("What's the latest Roblox news?")
    assert web_search.is_fresh_query("anything announced this week")
    assert not web_search.is_fresh_query("How do RemoteEvents work?")
    assert not web_search.is_fresh_query(None)
