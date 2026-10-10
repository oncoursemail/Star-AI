"""Offline contract tests for STAR's read-only Roblox research integration."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from star.agent import execute
from star.desktop_core import Settings
from star.intelligence import LocalIntelligence
from star.roblox_research import RobloxResearch, infer_game_type


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)


def _game_handler(request):
    assert request.method == "GET"
    host, path = request.url.host, request.url.path
    if host == "games.roblox.com" and path == "/v1/games":
        assert request.url.params.get("universeIds") == "999"
        return httpx.Response(200, json={"data": [{
            "id": 999, "rootPlaceId": 321, "name": "Space Survival Obby",
            "description": "Survive spooky obstacles in this challenging obby; run and jump across the map",
            "creator": {"id": 7, "name": "Dev", "type": "User"},
            "playing": 42, "visits": 10001, "favoritedCount": 90,
            "maxPlayers": 18, "created": "2026-01-01T00:00:00Z",
            "updated": "2026-10-09T00:00:00Z", "genre_l1": "Adventure"
        }]})
    if host == "games.roblox.com" and path == "/v1/games/votes":
        return httpx.Response(200, json={"data": [{"id": 999, "upVotes": 21, "downVotes": 2}]})
    if host == "thumbnails.roblox.com" and path == "/v1/games/icons":
        return httpx.Response(200, json={"data": [
            {"imageUrl": "https://tr.rbxcdn.com/test/512/512/Image/Png/noFilter"},
            {"imageUrl": "https://evil.example.com/steal"},
        ]})
    if host == "thumbnails.roblox.com" and path == "/v1/games/multiget/thumbnails":
        return httpx.Response(200, json={"data": [{"thumbnails": [
            {"imageUrl": "https://tr.rbxcdn.com/test2/768/432/Image/Png/noFilter"}
        ]}]})
    raise AssertionError(f"Unexpected request: {request.url}")


def test_public_game_report_and_snapshots(tmp_path):
    time_now = [1_780_000_000]
    research = RobloxResearch(home=tmp_path, client=_client(_game_handler), now=lambda: time_now[0])
    first = research.game_report(999)
    assert first["universe_id"] == 999
    assert first["root_place_id"] == 321
    assert first["url"] == "https://www.roblox.com/games/321"
    assert first["metrics"]["playing_now_snapshot"] == 42
    assert first["metrics"]["cumulative_visits"] == 10001
    assert first["metrics"]["votes_up"] == 21
    assert first["genre"]["confidence"] == "medium"
    assert first["genre"]["platform_label"] == "Adventure"
    assert any(item["type"] == "obby / platformer" for item in first["genre"]["inferred_types"])
    assert len(first["images"]) == 2
    assert all(item["url"].startswith("https://tr.rbxcdn.com") for item in first["images"])
    assert first["history"]["samples"] == 1
    assert first["history"]["playing_change"] is None
    time_now[0] += 3600
    second = research.game_report(999)
    assert second["history"]["samples"] == 2
    assert second["history"]["playing_change"] == 0
    assert second["history"]["visits_change"] == 0
    assert (tmp_path / "roblox_public_snapshots.sqlite3").exists()


def test_unknown_genre_is_not_fabricated():
    result = infer_game_type("The Place", "Cool stuff", "")
    assert result["inferred_types"] == []
    assert result["confidence"] == "insufficient evidence"
    assert result["platform_label"] is None


@pytest.mark.parametrize("invalid", [0, -1, False, "1/../etc/passwd", "99?auth=secret", None, 1.5])
def test_reject_invalid_ids_without_network(invalid, tmp_path):
    research = RobloxResearch(home=tmp_path, client=_client(lambda r: (_ for _ in ()).throw(AssertionError("network"))))
    with pytest.raises(ValueError):
        research.game_report(invalid)


def test_partial_auxiliary_failure_is_a_warning(tmp_path):
    def handler(request):
        if request.url.path == "/v1/games":
            return _game_handler(request)
        return httpx.Response(429, json={"message": "rate limited"})
    research = RobloxResearch(home=tmp_path, client=_client(handler))
    report = research.game_report(999)
    assert report["metrics"]["cumulative_visits"] == 10001
    assert report["metrics"]["votes_up"] is None
    assert report["warnings"]
    assert not report["images"]


def test_search_discovers_nested_universe_ids_without_arbitrary_urls(tmp_path):
    requested = []
    def handler(request):
        requested.append(str(request.url))
        if request.url.path == "/search-api/omni-search":
            assert request.url.params["searchQuery"] == "type=FPS & copy"
            return httpx.Response(200, json={"searchResults": [
                {"contents": [{"universeId": 999}, {"universeId": 999}]},
                {"contents": [{"universeId": -1}, {"universeId": "x"}]},
            ]})
        return _game_handler(request)
    research = RobloxResearch(home=tmp_path, client=_client(handler))
    response = research.search_games("type=FPS & copy")
    assert len(response["results"]) == 1
    assert response["results"][0]["universe_id"] == 999
    assert response["results"][0]["root_place_id"] == 321
    assert len(requested) == 2
    assert all(url.startswith(("https://apis.roblox.com/", "https://games.roblox.com/")) for url in requested)


def test_search_api_schema_change_is_not_guessed(tmp_path):
    research = RobloxResearch(home=tmp_path, client=_client(
        lambda _: httpx.Response(200, json={"searchResults": [{"name": "No known ID field"}]})
    ))
    result = research.search_games("roblox")
    assert result["results"] == []
    assert "changeable" in result["note"]


def test_forum_search_latest_and_docs(tmp_path):
    def handler(request):
        if request.url.path == "/search.json":
            assert request.url.params["q"] == "UI scaling"
            return httpx.Response(200, json={"topics": [
                {"id": 55, "title": "ScreenGui scaling", "created_at": "2026-10-08", "posts_count": 4}
            ]})
        if request.url.path == "/latest.json":
            return httpx.Response(200, json={"topic_list": {"topics": [
                {"id": 56, "title": "New feature", "created_at": "2026-10-09"}
            ]}})
        raise AssertionError(str(request.url))
    research = RobloxResearch(home=tmp_path, client=_client(handler))
    forum = research.search_forum("UI scaling")
    assert forum["topics"][0]["url"] == "https://devforum.roblox.com/t/55"
    assert "Community" in forum["note"]
    latest = research.forum_latest()
    assert latest["topics"][0]["url"] == "https://devforum.roblox.com/t/56"
    docs = research.docs("Luau type checking", limit=3)
    assert docs["results"][0]["url"].startswith("https://create.roblox.com/docs/")
    assert docs["results"]


def test_non_json_challenge_page_and_429_have_explicit_errors(tmp_path):
    for response, expected in [
        (httpx.Response(200, text="verify captcha", headers={"content-type": "text/html"}), "non-JSON"),
        (httpx.Response(429, json={}), "rate limiting"),
        (httpx.Response(403, json={}), "HTTP 403"),
    ]:
        hub = RobloxResearch(home=tmp_path, client=_client(lambda r, v=response: v))
        with pytest.raises(ValueError, match=expected):
            hub.search_forum("lag")


def test_youtube_no_key_does_not_invent_results(monkeypatch, tmp_path):
    monkeypatch.delenv("STAR_YOUTUBE_API_KEY", raising=False)
    hub = RobloxResearch(home=tmp_path, client=_client(lambda r: (_ for _ in ()).throw(AssertionError("Unexpected request"))))
    result = hub.youtube_search("Roblox UI tutorial")
    assert result["configured"] is False
    assert result["results"] == []
    assert "search_query=Roblox+UI+tutorial" in result["search_url"]


def test_youtube_api_is_metadata_not_watched(monkeypatch, tmp_path):
    monkeypatch.setenv("STAR_YOUTUBE_API_KEY", "fake-key-never-show")
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "www.googleapis.com"
        assert request.url.params["key"] == "fake-key-never-show"
        if request.url.path == "/youtube/v3/search":
            return httpx.Response(200, json={"items": [{
                "id": {"videoId": "ABcdefg1234"},
                "snippet": {"title": "Watch me play", "channelTitle": "Builder",
                            "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/ABcdefg1234/mqdefault.jpg"}}},
            }]})
        return httpx.Response(200, json={"items": [{
            "id": "ABcdefg1234",
            "snippet": {"title": "Watch me play", "description": "Some text", "channelTitle": "Builder"},
            "statistics": {"viewCount": "1000", "likeCount": "20"},
            "contentDetails": {"caption": "true", "duration": "PT2M30S"},
        }]})
    hub = RobloxResearch(home=tmp_path, client=_client(handler))
    search = hub.youtube_search("roblox")
    assert search["results"][0]["video_id"] == "ABcdefg1234"
    video = hub.youtube_video("ABcdefg1234")
    assert video["view_count"] == 1000
    assert video["captions_flag"] is True
    assert video["video_watched"] is False
    assert video["transcript_available"] is False
    assert "fake-key-never-show" not in json.dumps(search) + json.dumps(video)
    assert len(calls) == 2


def test_youtube_oembed_fallback_and_video_id_validation(monkeypatch, tmp_path):
    monkeypatch.delenv("STAR_YOUTUBE_API_KEY", raising=False)
    hub = RobloxResearch(home=tmp_path, client=_client(
        lambda r: httpx.Response(200, json={"title": "Roblox demo", "author_name": "Creator",
                                           "thumbnail_url": "https://i.ytimg.com/vi/ABcdefg1234/hqdefault.jpg"})
    ))
    result = hub.youtube_video("ABcdefg1234")
    assert result["video_watched"] is False
    assert result["title"] == "Roblox demo"
    with pytest.raises(ValueError):
        hub.youtube_video("https://evil.test/123")


def test_authorized_cloud_read_only_key_stays_private(monkeypatch, tmp_path):
    monkeypatch.setenv("STAR_ROBLOX_READ_API_KEY", "private-test-key")
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/cloud/v2/universes/999"
        assert request.headers["x-api-key"] == "private-test-key"
        return httpx.Response(200, json={"name": "games/999", "displayName": "Our Studio Game", "visibility": "PRIVATE"})
    research = RobloxResearch(home=tmp_path, client=_client(handler))
    result = research.open_cloud_universe(999)
    assert result["metadata"]["displayName"] == "Our Studio Game"
    assert "private-test-key" not in repr(result)


def test_intelligence_uses_task_scoping_and_schema_validation(tmp_path):
    hub = LocalIntelligence(home=tmp_path)
    assert hub.definitions("Hello, can you tell me a joke?") == []
    game_tools = {x["name"] for x in hub.definitions("Find Roblox game stats and compare experiences")}
    assert "star_roblox_game_report" in game_tools
    assert "star_roblox_compare_games" in game_tools
    assert "star_roblox_youtube_search" not in game_tools
    video_tools = {x["name"] for x in hub.definitions("Search a Roblox YouTube gameplay video")}
    assert "star_roblox_youtube_search" in video_tools
    assert "star_roblox_docs" in video_tools
    assert hub.owns("star_roblox_game_report")
    with pytest.raises(PermissionError):
        hub.call("star_roblox_game_report", {"universe_id": 999}, enabled=set())
    with pytest.raises(Exception):
        hub.call("star_roblox_game_report", {"universe_id": "999"}, enabled={"star_roblox_game_report"})
    result = hub.call("star_roblox_docs", {"query": "server remote events"}, enabled={"star_roblox_docs"})
    assert result["results"]
    assert hub.status()["roblox_research"]["read_only"] is True


def test_settings_persist_and_user_can_disable_research(tmp_path):
    settings = Settings()
    assert settings.roblox_research_enabled is True
    settings.validate()
    settings.roblox_research_enabled = False
    settings.save(tmp_path / "settings.json")
    fresh = Settings.load(tmp_path / "settings.json")
    assert fresh.roblox_research_enabled is False
    hub = LocalIntelligence(home=tmp_path, roblox_research_enabled=False)
    assert hub.definitions("Research Roblox game stats") != []  # Local skills still load.
    assert all(not x["name"].startswith("star_roblox_") for x in hub.definitions("Research Roblox game stats"))


def test_model_tool_call_dispatch_and_source_evidence(tmp_path):
    class FakeCompletion:
        def __init__(self):
            self.calls = []
        async def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                msg = SimpleNamespace(content="", tool_calls=[
                    SimpleNamespace(id="call", function=SimpleNamespace(
                        name="star_roblox_docs", arguments=json.dumps({"query": "Luau types"})))])
            else:
                msg = SimpleNamespace(content="These are sourced official links.", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    fake = FakeCompletion()
    model = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    hub = LocalIntelligence(home=tmp_path)
    async def task():
        return await execute(client=model, model="local", prompt="Research Roblox Luau type checking",
                             image_paths=[], intelligence=hub)
    answer, messages, _ = asyncio.run(task())
    assert "sourced" in answer
    assert any(m["role"] == "tool" and "create.roblox.com/docs" in m["content"] for m in messages)
    assert [m["role"] for m in messages].count("system") == 1
