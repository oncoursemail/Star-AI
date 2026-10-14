"""Roblox access as the model and the interface see it: tools through the trusted hub, bridge actions, settings."""
import asyncio
import json
from pathlib import Path
import shutil

import pytest

from star import roblox_cloud as rc, studio_loop
from star.desktop_core import Settings
from star.intelligence import ALL_TOOLS, ROBLOX_CLOUD_TOOLS, LocalIntelligence
from star.react_shell import ALLOWED_ACTIONS, PERMITTED_SETTINGS, apply_setting_changes, roblox_state
from star.roblox_cloud import RobloxCloud
from tests.roblox_fakes import ACCOUNT, KEY, PLACE, UNIVERSE, FakeRoblox
from tests.studio_fake import TOOLS, FakeStudio

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "roblox-test-place"
READ = {"star_roblox_cloud_universe", "star_roblox_cloud_status", "star_roblox_cloud_place",
        "star_roblox_cloud_data_stores", "star_roblox_cloud_action"}
REQUEST = {"star_roblox_cloud_request_publish", "star_roblox_cloud_request_test"}
ASK = "Use Open Cloud to publish my Roblox test place and run the tests"


@pytest.fixture(autouse=True)
def no_keyring(monkeypatch):
    monkeypatch.setattr(rc, "_keyring_get", lambda: None)


@pytest.fixture
def hub(tmp_path):
    fake = FakeRoblox()
    workspace = tmp_path / "workspace"
    shutil.copytree(EXAMPLE, workspace / "game")
    cloud = RobloxCloud(home=tmp_path / "home", key=KEY, source="keyring", client=fake.client(),
                        sleep=lambda _seconds: None)
    intelligence = LocalIntelligence(home=tmp_path / "home", workspace=workspace, skills_enabled=False,
                                     graphify_enabled=False, cloud=cloud)
    return intelligence, cloud, fake


def call(intelligence, name, **arguments):
    return intelligence.call(name, arguments, enabled={tool["name"] for tool in ROBLOX_CLOUD_TOOLS})


def test_the_tools_are_read_tools_and_request_tools_only():
    names = {tool["name"] for tool in ROBLOX_CLOUD_TOOLS}
    assert names == READ | REQUEST and names <= set(ALL_TOOLS)
    assert not [name for name in ALL_TOOLS if "approve" in name or "decide" in name or "set_test" in name]
    for tool in ROBLOX_CLOUD_TOOLS:
        assert tool["inputSchema"]["additionalProperties"] is False
        assert "key" not in tool["inputSchema"]["properties"]            # a model never handles the key


def test_tools_are_offered_only_with_a_key_and_a_matching_request(hub, tmp_path):
    intelligence, _cloud, _fake = hub
    offered = {tool["name"] for tool in intelligence.definitions(ASK)}
    assert READ | REQUEST <= offered
    assert not READ & {tool["name"] for tool in intelligence.definitions("Explain Roblox tweens to me")}
    keyless = LocalIntelligence(home=tmp_path / "other", skills_enabled=False, graphify_enabled=False,
                                cloud=RobloxCloud(home=tmp_path / "other"))
    assert not (READ | REQUEST) & {tool["name"] for tool in keyless.definitions(ASK)}
    with pytest.raises(PermissionError):
        call(keyless, "star_roblox_cloud_status")
    off = LocalIntelligence(home=tmp_path / "off", skills_enabled=False, graphify_enabled=False,
                            roblox_research_enabled=False, cloud=RobloxCloud(home=tmp_path / "off", key=KEY))
    assert off.definitions(ASK) == []


def test_read_tools_answer_without_any_write(hub):
    intelligence, cloud, fake = hub
    status = call(intelligence, "star_roblox_cloud_status")
    assert status["key_present"] and status["state"] == "unchecked" and KEY not in json.dumps(status)
    assert call(intelligence, "star_roblox_cloud_place", universe_id=UNIVERSE, place_id=PLACE)["metadata"]["serverSize"] == 10
    with pytest.raises(ValueError, match="No test experience"):
        call(intelligence, "star_roblox_cloud_data_stores")
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    assert call(intelligence, "star_roblox_cloud_data_stores")["data_stores"] == ["Coins"]
    assert fake.writes() == []


def test_a_publish_request_builds_from_the_workspace_and_waits_for_the_owner(hub):
    intelligence, cloud, fake = hub
    with pytest.raises(ValueError, match="No test experience"):
        call(intelligence, "star_roblox_cloud_request_publish", source_dir="game", summary="Publish the shop")
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    for outside in ("..", "../home", "game/../../home"):
        with pytest.raises(ValueError, match="inside the workspace|existing folder"):
            call(intelligence, "star_roblox_cloud_request_publish", source_dir=outside, summary="escape")
    asked = call(intelligence, "star_roblox_cloud_request_publish", source_dir="game", summary="Publish the shop")
    assert asked["status"] == "pending" and "Nothing was sent to Roblox" in asked["note"]
    assert asked["detail"]["files"] == ["ReplicatedStorage/Shared/Catalog.luau", "ServerScriptService/Shop.luau",
                                        "ServerScriptService/Tests/Shop.spec.luau"]
    assert fake.writes() == [] and fake.published == []
    waiting = call(intelligence, "star_roblox_cloud_action", action_id=asked["id"])
    assert waiting["status"] == "pending" and "result" not in waiting

    done = cloud.decide(asked["id"], approved=True, human_approved=True)        # the owner's click
    assert done["status"] == "done" and len(fake.published) == 1
    seen = call(intelligence, "star_roblox_cloud_action", action_id=asked["id"])
    assert seen["result"]["version"] == 4 and seen["untrusted"] is True


def test_a_test_request_uses_the_standard_harness_and_the_model_reads_the_result_later(hub):
    intelligence, cloud, fake = hub
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    asked = call(intelligence, "star_roblox_cloud_request_test", summary="Run the shop tests", version=4)
    assert asked["status"] == "pending" and asked["detail"]["standard_harness"] is True and fake.tasks == {}
    own = call(intelligence, "star_roblox_cloud_request_test", summary="One check", script="return 1 + 1")
    assert own["detail"]["script_preview"] == "return 1 + 1" and own["detail"]["standard_harness"] is False
    cloud.decide(asked["id"], approved=True, human_approved=True)
    seen = call(intelligence, "star_roblox_cloud_action", action_id=asked["id"])
    assert seen["status"] == "done" and seen["result"]["state"] == "COMPLETE" and seen["result"]["version"] == 4
    assert len(fake.tasks) == 1                                           # the other request is still waiting
    with pytest.raises(Exception):
        call(intelligence, "star_roblox_cloud_action", action_id="not-an-id")


def test_no_tool_lets_the_model_approve_or_choose_the_experience(hub):
    intelligence, cloud, fake = hub
    for name in ("star_roblox_cloud_decide", "star_roblox_cloud_approve", "star_roblox_cloud_set_test_experience",
                 "robloxDecideAction"):
        with pytest.raises(PermissionError):
            intelligence.call(name, {"id": "x", "approved": True}, enabled={name})
    with pytest.raises(Exception):                                         # extra fields are rejected by the schema
        call(intelligence, "star_roblox_cloud_request_test", summary="x", approved=True)
    assert fake.writes() == [] and cloud.status()["test_experience"] is None


# ------------------------------------------------------------------ interface and settings

def test_the_interface_has_the_owner_actions_and_no_direct_publish():
    assert rc.ROBLOX_ACTIONS <= ALLOWED_ACTIONS
    assert rc.ROBLOX_NETWORK_ACTIONS == {"robloxTestKey", "robloxSetTestExperience", "robloxDecideAction"}
    assert not {"publishRobloxGame", "robloxPublish", "robloxRunLuau"} & ALLOWED_ACTIONS
    assert {"studio_own_places", "studio_luau"} <= PERMITTED_SETTINGS
    assert not [name for name in PERMITTED_SETTINGS if "roblox_key" in name or "api_key" in name]


def test_the_start_up_summary_never_calls_roblox_and_never_holds_the_key(tmp_path, monkeypatch):
    assert roblox_state(tmp_path) == {
        "key_present": False, "source": "", "state": "no_key", "message": "No Roblox API key is connected.",
        "last_check": None, "test_experience": None, "pending_actions": 0,
        "denied_place_ids": sorted(rc.DENIED_PLACE_IDS), "denied_universe_ids": sorted(rc.DENIED_UNIVERSE_IDS)}
    monkeypatch.setenv("ROBLOX_OPEN_CLOUD_API_KEY", KEY)
    shown = roblox_state(tmp_path)                                         # no client was given: a call would fail
    assert shown["key_present"] and shown["source"] == "environment" and KEY not in json.dumps(shown)


def test_the_studio_switches_are_settings_and_off_by_default():
    settings = Settings()
    assert settings.studio_edit is False and settings.studio_own_places is False and settings.studio_luau is False
    changed = apply_setting_changes(Settings(), {"studio_own_places": True, "studio_luau": True, "roblox_key": "x"})
    assert changed.studio_own_places and changed.studio_luau and not hasattr(changed, "roblox_key")
    changed.studio_luau = "yes"
    with pytest.raises(ValueError):
        changed.validate()


def test_stars_own_account_comes_from_the_last_key_test(tmp_path, monkeypatch):
    assert studio_loop.own_account_id(tmp_path) is None                   # no key, no account
    fake = FakeRoblox()
    cloud = RobloxCloud(home=tmp_path, key=KEY, source="environment", client=fake.client())
    monkeypatch.setenv("ROBLOX_OPEN_CLOUD_API_KEY", KEY)
    assert studio_loop.own_account_id(tmp_path) is None                   # a key that was never tested
    cloud.check_key()
    assert studio_loop.own_account_id(tmp_path) == ACCOUNT
    monkeypatch.setenv("ROBLOX_OPEN_CLOUD_API_KEY", "Z" * 60)             # another key: its account is unknown
    assert studio_loop.own_account_id(tmp_path) is None


def test_a_turn_reports_studio_changes_after_the_answer():
    fake = FakeStudio()
    studio = asyncio.run(studio_loop.open_guarded(fake, TOOLS, studio_id=fake.studio_id, opted_in=True))
    untouched = ("Nothing changed.", ["messages"], [])
    assert studio_loop.with_report(untouched, studio) == untouched
    asyncio.run(studio.call_tool("multi_edit", {
        "studio_id": fake.studio_id, "datamodel_type": "Edit", "file_path": "ServerScriptService.Main",
        "className": "Script", "edits": [{"old_string": "", "new_string": "print('hi')"}]}))
    answer, messages, archive = studio_loop.with_report(("I added the script.", ["messages"], []), studio)
    assert answer.startswith("I added the script.\n\nStudio changes in this turn (1):")
    assert "created script ServerScriptService.Main" in answer and "Undo:" in answer and messages == ["messages"]
