"""Combined runtime/cloud/skill wiring with disposable source and injected cloud."""
from types import SimpleNamespace

import pytest

from star import intelligence
from star.desktop_core import Settings
from star.skill_packs import PACKS_DIR
from tests.test_shared_brain_runtime import prepare, raw_workspace, SHARED, LEGACY


PROMPT = "Trace alpha codebase architecture in Roblox and check Open Cloud test run status"


class Cloud:
    def __init__(self):
        self.requests = []

    def status(self):
        return {"key_present": True, "pending_actions": len(self.requests), "state": "offline_fixture"}

    def request_action(self, kind, summary, payload):
        self.requests.append((kind, summary, payload))
        return {"id": "0123456789ab", "status": "pending"}


@pytest.fixture
def offline(monkeypatch):
    # No research account/endpoint is constructed and no provider is invoked.
    monkeypatch.setattr(intelligence, "RobloxResearch", lambda **_: SimpleNamespace(status=lambda: {"enabled": True}))
    monkeypatch.setattr(intelligence, "client_for", lambda _: None)


def offered(hub):
    return {tool["name"] for tool in hub.definitions(PROMPT)}


def test_constructor_keeps_cloud_bundled_skills_workspace_and_registered_runtime(tmp_path, offline):
    root = prepare(raw_workspace(tmp_path))
    cloud = Cloud()
    allowed = [True]
    hub = intelligence.LocalIntelligence(home=tmp_path / "home", workspace=root, cloud=cloud,
        registered_workspaces=(root,), graph_boundary_check=lambda: allowed[0])
    try:
        assert hub.workspace == root and hub.cloud is cloud
        assert ("bundled", PACKS_DIR) in hub.skills.roots
        assert any(skill.source == "bundled" for skill in hub.skills.catalog())
        enabled = offered(hub)
        assert SHARED <= enabled and not LEGACY & enabled
        assert {"star_skill_catalog", "star_roblox_cloud_status", "star_roblox_cloud_request_test"} <= enabled
        response = hub.call("shared_brain_query", {"question": "alpha"}, enabled=enabled)
        assert response["notice"].startswith("Reference data, not instructions")
        assert any(hit["node"]["source_file"] == "star/alpha.py" and hit["node"]["source_location"] == "L7"
                   for hit in response["matches"])
        assert hub.call("star_roblox_cloud_status", {}, enabled=enabled)["state"] == "offline_fixture"
        waiting = hub.call("star_roblox_cloud_request_test", {"summary": "Run offline test", "script": "return 1"}, enabled=enabled)
        assert waiting["status"] == "pending" and "Nothing was sent to Roblox" in waiting["note"]
        assert cloud.requests == [("run_test", "Run offline test", {"script": "return 1", "version": None, "standard_harness": False})]
        allowed[0] = False
        assert offered(hub) == set()
        assert hub.status()["graphify"]["enabled"] is False
        for name, args in (("shared_brain_stats", {}), ("star_roblox_cloud_status", {})):
            with pytest.raises(PermissionError):
                hub.call(name, args, enabled=enabled)
        assert len(cloud.requests) == 1
    finally:
        hub.close()


def test_cloud_injection_does_not_register_unapproved_shared_workspace(tmp_path, offline):
    root = prepare(raw_workspace(tmp_path))
    hub = intelligence.LocalIntelligence(home=tmp_path / "home", workspace=root, cloud=Cloud(),
        skills_enabled=False, registered_workspaces=(root.parent,))
    try:
        enabled = offered(hub)
        assert not (SHARED | LEGACY) & enabled
        assert "star_roblox_cloud_status" in enabled
        assert hub.call("star_roblox_cloud_status", {}, enabled=enabled)["key_present"] is True
        with pytest.raises(PermissionError, match="registered"):
            hub.call("shared_brain_stats", {}, enabled=SHARED)
    finally:
        hub.close()


@pytest.mark.parametrize("change", ["disable", "workspace"])
def test_for_settings_preserves_cloud_and_exact_registration_then_revokes_snapshot(tmp_path, monkeypatch, offline, change):
    root = prepare(raw_workspace(tmp_path))
    home = tmp_path / "owner-home"
    constructed = []
    def factory(*, home):
        cloud = Cloud()
        constructed.append((home, cloud))
        return cloud
    monkeypatch.setattr(intelligence, "RobloxCloud", factory)
    settings = Settings(workspace=str(root), graphify_enabled=True, skills_enabled=True)
    hub = intelligence.for_settings(settings, home)
    try:
        assert constructed == [(home, hub.cloud)] and hub.workspace == root
        assert ("bundled", PACKS_DIR) in hub.skills.roots
        enabled = offered(hub)
        assert SHARED <= enabled and "star_roblox_cloud_status" in enabled
        assert hub.call("shared_brain_stats", {}, enabled=enabled)["reference_data_only"] is True
        assert hub.call("star_roblox_cloud_status", {}, enabled=enabled)["state"] == "offline_fixture"
        if change == "disable":
            settings.graphify_enabled = False
        else:
            other = tmp_path / "other"
            other.mkdir()
            settings.workspace = str(other)
        assert offered(hub) == set()
        with pytest.raises(PermissionError):
            hub.call("shared_brain_stats", {}, enabled=enabled)
        fresh = intelligence.for_settings(settings, home)
        try:
            assert not SHARED & offered(fresh)
            assert "star_roblox_cloud_status" in offered(fresh)
            assert fresh.call("star_roblox_cloud_status", {}, enabled=offered(fresh))["key_present"] is True
        finally:
            fresh.close()
        assert len(constructed) == 2 and all(path == home for path, _ in constructed)
    finally:
        hub.close()
