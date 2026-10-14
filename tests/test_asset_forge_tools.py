"""Real Asset Forge discovery, permissions, schema validation and offline dispatch."""
import httpx
import pytest
from jsonschema import ValidationError

from star import asset_forge, intelligence
from star.desktop_core import Settings
from star.react_shell import apply_setting_changes


def names(hub, prompt):
    return [tool["name"] for tool in hub.definitions(prompt)]


def hub(home, *, enabled=False, research=True):
    return intelligence.LocalIntelligence(
        home=home, skills_enabled=False, graphify_enabled=False,
        asset_forge_enabled=enabled, roblox_research_enabled=research)


def test_new_tools_are_off_until_the_owner_enables_asset_forge(tmp_path):
    default = hub(tmp_path)
    assert not default.status()["asset_forge"]["enabled"]
    assert all(tool["name"] not in names(default, "Plan a modular Roblox building")
               for tool in intelligence.ASSET_TOOLS)
    with pytest.raises(PermissionError, match="Enable Asset Forge"):
        default.call("star_building_plan", {"floors": 2}, enabled={"star_building_plan"})
    settings = Settings()
    assert settings.asset_forge_enabled is False
    settings = apply_setting_changes(settings, {"asset_forge_enabled": True})
    settings.save(tmp_path / "settings.json")
    reopened = Settings.load(tmp_path / "settings.json")
    assert reopened.asset_forge_enabled is True
    assert intelligence.for_settings(reopened, tmp_path).status()["asset_forge"]["enabled"]
    reopened.asset_forge_enabled = "true"
    with pytest.raises(ValueError):
        reopened.validate()


def test_offered_only_for_relevant_roblox_asset_prompts_and_network_permission(tmp_path):
    online = hub(tmp_path, enabled=True)
    assert names(online, "Plan a modular Roblox building")[:3] == [
        "star_asset_search", "star_building_plan", "star_terrain_preview"]
    for prompt in ("How are you?", "Fix my Roblox DataStore script",
                   "hello world script in Roblox", "explain the architecture of my Roblox game"):
        assert not set(names(online, prompt)).intersection({
            "star_asset_search", "star_building_plan", "star_terrain_preview"})
    offline = hub(tmp_path, enabled=True, research=False)
    names_without_research = names(offline, "Roblox terrain texture")
    assert "star_asset_search" not in names_without_research
    assert names_without_research == ["star_building_plan", "star_terrain_preview"]
    with pytest.raises(PermissionError, match="Asset search is disabled"):
        offline.call("star_asset_search", {"query": "stone"}, enabled={"star_asset_search"})


def test_real_call_validates_schema_entitlements_and_dispatches_offline_plans(tmp_path):
    instance = hub(tmp_path, enabled=True, research=False)
    result = instance.call("star_building_plan", {"floors": 2}, enabled={"star_building_plan"})
    assert result["stage"] == "plan_only"
    terrain = instance.call("star_terrain_preview", {"size": 4, "seed": 5}, enabled={"star_terrain_preview"})
    assert terrain["stage"] == "heightmap_preview"
    with pytest.raises(PermissionError):
        instance.call("star_building_plan", {"floors": 2}, enabled=set())
    with pytest.raises(ValidationError):
        instance.call("star_building_plan", {"floors": 9}, enabled={"star_building_plan"})
    with pytest.raises(ValidationError):
        instance.call("star_terrain_preview", {"step": False}, enabled={"star_terrain_preview"})


def test_search_dispatch_creates_default_identified_client_and_no_real_network(tmp_path, monkeypatch):
    real_client = asset_forge.httpx.Client
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert request.url.host == "api.polyhaven.com"
        assert request.method == "GET"
        assert request.headers["User-Agent"] == "STAR-Intelligence-Assets/1.0"
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"slug": "sample_rock"}]})
        return httpx.Response(200, json={"type": 2, "name": "Sample Rock", "date_published": 1600000000})

    def client_factory(*args, **kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(asset_forge.httpx, "Client", client_factory)
    instance = hub(tmp_path, enabled=True)
    result = instance.call("star_asset_search", {"query": "rock"}, enabled={"star_asset_search"})
    assert result["provider"] == "Poly Haven"
    assert result["credit"] == "Powered by Poly Haven"
    assert result["assets"][0]["source_url"] == "https://polyhaven.com/a/sample_rock"
    assert paths == ["/search", "/info/sample_rock"]
