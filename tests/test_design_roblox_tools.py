"""The design, DESIGN.md, map plan and live Roblox docs tools as STAR's agent sees them."""
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from jsonschema import ValidationError

from star import intelligence
from star.intelligence import LocalIntelligence, for_settings
from star.roblox_docs_live import RobloxDocsLive

FIXTURES = Path(__file__).parent / "fixtures" / "roblox_docs"
NEW_TOOLS = {"star_design_search", "star_design_md", "star_roblox_map_plan",
             "star_roblox_docs_live_search", "star_roblox_docs_live_page"}


def hub(tmp_path, **kwargs):
    return LocalIntelligence(home=tmp_path / "home", workspace=kwargs.pop("workspace", None), skills_enabled=False,
                             graphify_enabled=False, **kwargs)


def names(tools):
    return {tool["name"] for tool in tools}


def docs_client():
    def handler(request):
        path = request.url.raw_path.decode()
        if path.startswith("/docs/api/search/"):
            return httpx.Response(200, text=(FIXTURES / "search_remote_events.json").read_text(encoding="utf-8"),
                                  headers={"content-type": "application/json"})
        if path == "/docs/en-us/scripting/events/bindable.md":
            return httpx.Response(200, text=(FIXTURES / "bindable.md").read_text(encoding="utf-8"),
                                  headers={"content-type": "text/markdown"})
        if path == "/docs/llms.txt":
            return httpx.Response(200, text=(FIXTURES / "llms_excerpt.txt").read_text(encoding="utf-8"),
                                  headers={"content-type": "text/plain"})
        return httpx.Response(404, headers={"content-type": "text/html"})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_tools_are_registered_with_valid_schemas():
    assert NEW_TOOLS <= set(intelligence.ALL_TOOLS)
    for name in NEW_TOOLS:
        schema = intelligence.ALL_TOOLS[name]["inputSchema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False


def test_prompt_gating(tmp_path):
    h = hub(tmp_path)
    assert names(h.definitions("How are you?")) == set()
    assert names(h.definitions("Build a Roblox UI")).isdisjoint(NEW_TOOLS)   # plain UI prompts unchanged
    assert {"star_design_search", "star_design_md"} <= names(h.definitions("Pick a colour palette and font pairing"))
    assert "star_design_md" in names(h.definitions("Lint my DESIGN.md for WCAG contrast"))
    assert "star_roblox_map_plan" in names(h.definitions("Plan a Roblox obby map blockout"))
    assert "star_roblox_map_plan" not in names(h.definitions("Show me a map of Paris"))   # needs a Roblox prompt
    # live docs stay off unless enabled
    assert names(h.definitions("Roblox docs for RemoteEvent")).isdisjoint(
        {"star_roblox_docs_live_search", "star_roblox_docs_live_page"})
    live = hub(tmp_path, docs_live=RobloxDocsLive(cache_dir=None, client=docs_client()))
    assert {"star_roblox_docs_live_search", "star_roblox_docs_live_page"} <= names(
        live.definitions("Roblox docs for RemoteEvent"))
    off = hub(tmp_path, design_enabled=False, map_plans_enabled=False)
    assert names(off.definitions("Plan a Roblox map with a colour palette")).isdisjoint(NEW_TOOLS)


def test_design_calls(tmp_path):
    h = hub(tmp_path, workspace=tmp_path)
    enabled = NEW_TOOLS
    rec = h.call("star_design_search", {"domain": "recommend", "query": "kids learning game"}, enabled=enabled)
    assert rec["tokens"]["colors"] and rec["typography"]["heading_font"]
    found = h.call("star_design_search", {"domain": "typography", "query": "elegant", "limit": 2}, enabled=enabled)
    assert len(found["results"]) == 2
    assert h.call("star_design_md", {"action": "read"}, enabled=enabled)["exists"] is False
    drafted = h.call("star_design_md", {"action": "draft", "query": "pet adoption app", "name": "Paws"},
                     enabled=enabled)
    assert drafted["saved"] is False and drafted["lint"]["ok"] and not (tmp_path / "DESIGN.md").exists()
    (tmp_path / "DESIGN.md").write_text(drafted["text"], encoding="utf-8")
    read = h.call("star_design_md", {"action": "read"}, enabled=enabled)
    assert read["text"] == drafted["text"] and read["lint"]["ok"] and read["untrusted"]
    linted = h.call("star_design_md", {"action": "lint", "text": "---\nname: x\ncolors:\n  accent: '#fff'\n---\n"},
                    enabled=enabled)
    assert "missing-primary" in {f["rule"] for f in linted["lint"]["findings"]}
    with pytest.raises(ValueError):
        h.call("star_design_md", {"action": "draft"}, enabled=enabled)
    with pytest.raises(ValidationError):
        h.call("star_design_search", {"domain": "colours", "query": "x"}, enabled=enabled)
    with pytest.raises(PermissionError):
        h.call("star_design_search", {"domain": "style", "query": "x"}, enabled=set())
    no_workspace = hub(tmp_path)
    with pytest.raises(ValueError):
        no_workspace.call("star_design_md", {"action": "read"}, enabled=enabled)


def test_map_plan_call_returns_operations_and_optional_luau(tmp_path):
    h = hub(tmp_path)
    plan = {"mapName": "Yard", "bounds": {"size": [100, 40, 100]},
            "parts": [{"name": "Floor", "position": [0, -0.5, 0], "size": [40, 1, 40]}],
            "spawns": [{"name": "Spawn", "position": [0, 0.5, 0]}]}
    report = h.call("star_roblox_map_plan", {"plan": plan, "include_luau": True}, enabled=NEW_TOOLS)
    assert report["ok"] and report["operations"] and "Instance.new" in report["luau"]
    assert json.dumps(report)   # serialisable for the tool payload
    bad = h.call("star_roblox_map_plan", {"plan": {"mapName": "x"}}, enabled=NEW_TOOLS)
    assert not bad["ok"] and "luau" not in bad


def test_live_docs_calls_use_fixtures_only(tmp_path):
    h = hub(tmp_path, docs_live=RobloxDocsLive(cache_dir=tmp_path / "c", client=docs_client()))
    found = h.call("star_roblox_docs_live_search", {"query": "remote events"}, enabled=NEW_TOOLS)
    assert found["results"] and found["untrusted"]
    index = h.call("star_roblox_docs_live_search", {"query": "bindable", "source": "index"}, enabled=NEW_TOOLS)
    assert index["source"] == "llms.txt index"
    page = h.call("star_roblox_docs_live_page", {"path": "scripting/events/bindable"}, enabled=NEW_TOOLS)
    assert page["title"] == "Bindable events and callbacks"
    with pytest.raises(PermissionError):
        h.call("star_roblox_docs_live_page", {"path": "https://evil.example/x"}, enabled=NEW_TOOLS)
    with pytest.raises(PermissionError):
        hub(tmp_path).call("star_roblox_docs_live_search", {"query": "x"}, enabled=NEW_TOOLS)


def test_for_settings_switches(tmp_path, monkeypatch):
    settings = SimpleNamespace(workspace="", obsidian_vault="", obsidian_enabled=False, skills_enabled=False,
                               graphify_enabled=False, roblox_research_enabled=True)
    monkeypatch.setattr(intelligence, "client_for", lambda s: None)
    monkeypatch.delenv("STAR_ROBLOX_DOCS_LIVE", raising=False)
    monkeypatch.delenv("STAR_DESIGN_TOOLS", raising=False)
    monkeypatch.delenv("STAR_MAP_PLAN_TOOLS", raising=False)
    default = for_settings(settings, tmp_path)
    assert default.design_enabled and default.map_plans_enabled and default.docs_live is None
    status = default.status()
    assert status["roblox_docs_live"]["enabled"] is False and status["design"]["enabled"] is True
    monkeypatch.setenv("STAR_DESIGN_TOOLS", "off")
    monkeypatch.setenv("STAR_MAP_PLAN_TOOLS", "0")
    monkeypatch.setenv("STAR_ROBLOX_DOCS_LIVE", "1")
    switched = for_settings(settings, tmp_path)
    assert not switched.design_enabled and not switched.map_plans_enabled
    assert switched.docs_live is not None and switched.docs_live.cache_dir == tmp_path / "cache" / "roblox-docs"
