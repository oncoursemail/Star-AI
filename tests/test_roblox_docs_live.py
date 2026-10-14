"""Roblox docs retrieval, fully offline: recorded responses through httpx.MockTransport."""
from pathlib import Path

import httpx
import pytest

from star import roblox_docs_live as live
from star.roblox_docs_live import DocsUnavailable, RobloxDocsLive, normalize_page_path

FIXTURES = Path(__file__).parent / "fixtures" / "roblox_docs"
INDEX = (FIXTURES / "llms_excerpt.txt").read_text(encoding="utf-8")
SEARCH = (FIXTURES / "search_remote_events.json").read_text(encoding="utf-8")
PAGE = (FIXTURES / "bindable.md").read_text(encoding="utf-8")


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def recorded(requests: list, *, fail=False):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if fail:
            raise httpx.ConnectError("offline", request=request)
        assert request.url.host == "create.roblox.com"
        path = request.url.raw_path.decode()
        if path == "/docs/llms.txt":
            return httpx.Response(200, text=INDEX, headers={"content-type": "text/plain; charset=utf-8"})
        if path.startswith("/docs/api/search/"):
            return httpx.Response(200, text=SEARCH, headers={"content-type": "application/json; charset=utf-8"})
        if path == "/docs/en-us/scripting/events/bindable.md":
            return httpx.Response(200, text=PAGE, headers={"content-type": "text/markdown; charset=utf-8"})
        if path == "/docs/en-us/redirect/me.md":
            return httpx.Response(302, headers={"location": "https://evil.example/"})
        if path == "/docs/en-us/html/page.md":
            return httpx.Response(200, text="<html>", headers={"content-type": "text/html"})
        return httpx.Response(404, text="<html>not found</html>", headers={"content-type": "text/html"})
    return httpx.Client(transport=httpx.MockTransport(handler))


def make(tmp_path, *, fail=False, clock=None):
    requests = []
    docs = RobloxDocsLive(cache_dir=tmp_path / "cache", client=recorded(requests, fail=fail), now=clock or Clock())
    return docs, requests


def test_search_uses_fixed_host_encodes_query_and_drops_foreign_links(tmp_path):
    docs, requests = make(tmp_path)
    found = docs.search("How do RemoteEvent.OnServerEvent events work?", 10)
    path = requests[0].url.raw_path.decode()
    assert path.startswith("/docs/api/search/") and "." not in path.removeprefix("/docs/api/search/")
    assert "%20" in path and "?" not in path
    urls = [item["url"] for item in found["results"]]
    assert urls and all(url.startswith("https://create.roblox.com/docs/") for url in urls)
    assert not any("evil.example" in url for url in urls)
    assert found["untrusted"] is True and "CC BY 4.0" in found["attribution"]
    assert found["results"][0]["title"] == "RemoteEvent"


def test_search_is_cached_in_memory_and_on_disk(tmp_path):
    clock = Clock()
    docs, requests = make(tmp_path, clock=clock)
    docs.search("remote events", 3)
    docs.search("remote events", 3)
    assert len(requests) == 1
    # a new instance (new app session) reads the disk cache, still without the network
    fresh, more = make(tmp_path, fail=True, clock=clock)
    again = fresh.search("remote events", 3)
    assert not more and again["from_cache"] is True and again["stale"] is False


def test_offline_returns_stale_cache_then_index_then_curated_links(tmp_path):
    clock = Clock()
    docs, _ = make(tmp_path, clock=clock)
    docs.search("remote events", 3)
    docs.index_entries()
    clock.t += live.TTL["search"] + 10   # search cache expired, index cache (7 days) still fresh
    offline, requests = make(tmp_path, fail=True, clock=clock)
    stale = offline.search("remote events", 3)
    assert requests and stale["stale"] is True and stale["results"]
    via_index = offline.search("bindable events", 3)   # never searched before: falls back to llms.txt
    assert via_index["source"].startswith("llms.txt index")
    assert via_index["results"][0]["url"].endswith("/scripting/events/bindable.md")
    empty, _ = make(tmp_path / "nothing", fail=True)
    curated = empty.search("remote events", 3)
    assert curated["offline"] is True and curated["source"].startswith("STAR curated")
    assert all(item["url"].startswith("https://create.roblox.com/docs/") for item in curated["results"])


def test_search_error_field_is_reported_not_treated_as_empty(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"error": "bad request", "usage": "/docs/api/search/<question>", "results": []})
    docs = RobloxDocsLive(cache_dir=None, client=httpx.Client(transport=httpx.MockTransport(handler)))
    found = docs.search("anything", 3)
    assert found["error"] == "bad request" and "malformed" in found["note"]


def test_index_search_ranks_titles(tmp_path):
    docs, _ = make(tmp_path)
    found = docs.index_search("remote events and callbacks", 3)
    assert found["results"][0]["title"] == "Remote events and callbacks"
    assert found["pages_indexed"] == len(live.parse_index(INDEX)) > 30


def test_page_read_strips_front_matter_and_caps_size(tmp_path):
    docs, _ = make(tmp_path)
    page = docs.page("https://create.roblox.com/docs/en-us/scripting/events/bindable.md#bindable-events", 1000)
    assert page["title"] == "Bindable events and callbacks"
    assert page["url"] == "https://create.roblox.com/docs/en-us/scripting/events/bindable.md"
    assert page["content"].startswith("# Bindable events") and len(page["content"]) == 1000 and page["truncated"]
    assert page["untrusted"] is True
    same = docs.page("scripting/events/bindable")
    assert same["from_cache"] is True


def test_page_errors_redirects_and_wrong_types_are_refused(tmp_path):
    docs, _ = make(tmp_path)
    with pytest.raises(FileNotFoundError):
        docs.page("nope/missing")
    with pytest.raises(DocsUnavailable):
        docs.page("redirect/me")   # redirects are never followed
    with pytest.raises(DocsUnavailable):
        docs.page("html/page")
    offline, _ = make(tmp_path / "other", fail=True)
    with pytest.raises(DocsUnavailable):
        offline.page("scripting/events/bindable")


@pytest.mark.parametrize("bad", [
    "https://evil.example/docs/x.md", "http://create.roblox.com/docs/x.md", "https://create.roblox.com:8443/docs/x",
    "../../etc/passwd", "scripting/../../secret", "", "a" * 301, "file:///c:/x", "scripting/ev ents",
])
def test_page_path_allowlist(bad):
    with pytest.raises((PermissionError, ValueError)):
        normalize_page_path(bad)


def test_page_path_normalisation():
    expected = "/docs/en-us/scripting/events/remote.md"
    for value in ("scripting/events/remote", "/docs/scripting/events/remote.md", "docs/en-us/scripting/events/remote",
                  "https://create.roblox.com/docs/en-us/scripting/events/remote.md?x=1#y"):
        assert normalize_page_path(value) == expected


def test_offline_mode_never_touches_the_network(tmp_path):
    requests = []
    docs = RobloxDocsLive(cache_dir=tmp_path, client=recorded(requests), online=False)
    found = docs.search("remote events", 3)
    assert not requests and found["offline"] is True


def test_live_switch_is_off_by_default(monkeypatch):
    monkeypatch.delenv("STAR_ROBLOX_DOCS_LIVE", raising=False)
    assert live.live_enabled(None) is False
    monkeypatch.setenv("STAR_ROBLOX_DOCS_LIVE", "1")
    assert live.live_enabled(None) is True
    monkeypatch.setenv("STAR_ROBLOX_DOCS_LIVE", "0")

    class Settings:
        roblox_docs_live_enabled = True
    assert live.live_enabled(Settings()) is True


def test_live_setting_is_a_real_persisted_setting(monkeypatch, tmp_path):
    from star import desktop_core as core
    monkeypatch.delenv("STAR_ROBLOX_DOCS_LIVE", raising=False)
    file = tmp_path / "settings.json"
    assert core.Settings().roblox_docs_live_enabled is False
    assert live.live_enabled(core.Settings()) is False
    core.Settings(roblox_docs_live_enabled=True).save(file)
    loaded = core.Settings.load(file)
    assert loaded.roblox_docs_live_enabled is True
    assert live.live_enabled(loaded) is True
    for bad in ("yes", 1, None):
        with pytest.raises(ValueError):
            core.Settings(roblox_docs_live_enabled=bad).save(tmp_path / "bad.json")
    # the environment variable still enables it when the setting is off
    monkeypatch.setenv("STAR_ROBLOX_DOCS_LIVE", "1")
    assert live.live_enabled(core.Settings()) is True
