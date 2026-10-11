"""Offline contract tests for Roblox scene craft, recipes and STAR tool gating."""
from __future__ import annotations

import json

import pytest

from star.intelligence import CRAFT_TOOLS, LocalIntelligence
from star.roblox_craft import MAX_FINDINGS, audit, recipe


def node(path, kind, properties=None, *, complete=False):
    return {"path": path, "class": kind, "properties": properties or {}, "complete": complete}


def rules(report):
    return {item["rule"] for item in report["findings"]}


def test_audit_detects_grounded_ui_vfx_animation_and_code_risks():
    snapshot = [
        node("StarterGui.HUD", "ScreenGui", {"ScreenInsets": "None"}),
        node("StarterGui.HUD.Panel", "Frame",
             {"Size": {"xScale": 0, "xOffset": 720, "yScale": 0, "yOffset": 100}}),
        node("StarterGui.HUD.Panel.Label", "TextLabel",
             {"TextScaled": True, "Text": "A", "TextWrapped": False}, complete=True),
        node("Workspace.Effects", "Folder"),
        node("Workspace.Effects.Sparks", "ParticleEmitter", {"Rate": 240, "Lifetime": {"Min": 1, "Max": 2}}),
        node("Workspace.Effects.Beam", "Beam", {"Attachment0": None, "Attachment1": None}),
        node("ReplicatedStorage.Slash", "Animation", {"AnimationId": "rbxassetid://0"}),
        node("Workspace.NPC", "Model"),
        node("Workspace.NPC.Animator", "Animator"),
    ]
    scripts = [
        {"path": "StarterPlayer.StarterPlayerScripts.HUD", "class": "LocalScript",
         "source": 'local ds = game:GetService("DataStoreService")\nwait(1)'},
        {"path": "ServerScriptService.Main", "class": "Script",
         "source": "Remote.OnServerEvent:Connect(function(player, value) print(value) end)"},
    ]
    report = audit(snapshot, scripts)
    found = rules(report)
    assert {"ui-unsafe-insets", "ui-fixed-size", "ui-text-constraint",
            "vfx-parent", "vfx-rate", "vfx-occupancy", "vfx-missing-attachment",
            "animation-missing-id", "animation-animator-owner", "luau-datastore-client",
            "luau-legacy-task", "luau-remote-review", "luau-strict"} <= found
    assert report["domains"]["ui"] == 3 and report["domains"]["vfx"] == 2
    assert report["domains"]["animation"] == 2 and report["domains"]["code"] == 2
    assert report["read_only"] and not report["executed"] and report["snapshot_incomplete"]
    assert report["complete_property_sets"] == 1
    assert all(issue["documentation"].startswith("https://create.roblox.com/docs/") for issue in report["findings"])
    assert all(issue["path"] and issue["recommendation"] and issue["certainty"] for issue in report["findings"])


def test_audit_does_not_assume_missing_properties_are_invalid():
    report = audit([node("Workspace.Anchor", "Attachment"),
                    node("Workspace.Anchor.Arc", "Beam"),
                    node("StarterGui.Example", "ScreenGui"),
                    node("StarterGui.Example.Label", "TextLabel", {"TextScaled": True})])
    assert report["findings"] == []
    assert report["complete_property_sets"] == 0
    assert "No screenshot" in report["limitations"][2]


def test_complete_properties_or_explicit_null_support_attachment_findings():
    report = audit([node("Workspace.Arc", "Beam", complete=True),
                    node("Workspace.Other", "Trail", {"Attachment0": "", "Lifetime": 5})])
    findings = [(f["rule"], f["path"]) for f in report["findings"]]
    assert findings.count(("vfx-missing-attachment", "Workspace.Arc")) == 2
    assert ("vfx-missing-attachment", "Workspace.Other") in findings
    assert "vfx-long-trail" in rules(report)


def test_device_context_changes_review_threshold_not_real_engine_claims():
    instance = node("Workspace.Blast.Sparks", "ParticleEmitter", {"Rate": 140})
    desktop = audit([instance], target="desktop")
    mobile = audit([instance], target="mobile")
    assert "vfx-rate" in rules(mobile) and "vfx-rate" not in rules(desktop)
    assert "not an engine cap" in next(f["recommendation"] for f in mobile["findings"]
                                       if f["rule"] == "vfx-rate")
    with pytest.raises(ValueError):
        audit([], target="all")


@pytest.mark.parametrize("value", [
    [node("a", "Part"), node("a", "Part")],
    [node("b", "Part", {"Rate": float("nan")})],
    [node("c", "Part", {"Rate": object()})],
    [node("d", "Part")] * 161,
    [{"path": "", "class": "Frame"}],
    [{"path": "ok", "class": None}],
    [{"path": "ok", "class": "Frame", "properties": []}],
    [{"path": "ok", "class": "Frame", "complete": "yes"}],
])
def test_invalid_snapshot_rejected(value):
    with pytest.raises(ValueError):
        audit(value)


def test_source_limits_and_types_are_checked():
    with pytest.raises(ValueError):
        audit([], [{"path": "x", "class": "LocalScript", "source": "a" * 20001}])
    with pytest.raises(ValueError):
        audit([], [{"path": "x", "class": "Executable", "source": "hi"}])
    with pytest.raises(ValueError):
        audit([], [{"path": "x", "class": "Script", "source": 123}])
    with pytest.raises(ValueError):
        audit([], [{"path": "x", "class": "Script", "source": "abc"}] * 13)


def test_audit_is_deterministic_and_result_bounded():
    script = {"path": "ServerScriptService.Wait", "class": "Script", "source": "wait(1)\n"}
    first = audit([node("Workspace.A", "Part")], [script])
    second = audit([node("Workspace.A", "Part")], [script])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert len(first["findings"]) <= MAX_FINDINGS
    assert "luau-strict" in rules(first)


@pytest.mark.parametrize("name,source", [
    ("responsive-hud", ["Instance.new(\"ScreenGui\")", "UIListLayout", "UISizeConstraint",
                        "ReducedMotionEnabled", "Activated:Connect"]),
    ("impact-vfx", ["ParticleEmitter", "NumberSequence", "Rate = 0", "Debris:AddItem", ":Emit(18)"]),
    ("animation-marker", ["Animator", "GetMarkerReachedSignal(\"Impact\")",
                          "markerConnection:Disconnect()", "track:Destroy()"]),
])
def test_recipes_are_native_editable_previews(name, source):
    response = recipe(name)
    assert response["preview_only"] and response["installed"] is False and response["executed"] is False
    assert response["source_path"].endswith(".luau") and response["luau"].startswith("--!strict")
    assert all(snippet in response["luau"] for snippet in source)
    assert all(url.startswith("https://create.roblox.com/docs/") for url in response["documentation"])


def test_recipes_require_real_authoring_and_do_not_grant_publication():
    assert "published Animation" in recipe("animation-marker")["luau"]
    assert "cosmetic" in recipe("impact-vfx")["luau"]
    assert "owner-authorized" not in recipe("responsive-hud")["luau"]
    assert not any("publish" in name for name in (tool["name"] for tool in CRAFT_TOOLS))
    with pytest.raises(ValueError):
        recipe("upload-to-every-game")


def test_intelligence_tool_is_prompt_scoped_and_cannot_edit(tmp_path):
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False)
    names = {tool["name"] for tool in hub.definitions("Build Roblox UI and VFX animations")}
    assert {"star_roblox_craft_audit", "star_roblox_craft_recipe"} <= names
    assert not {tool["name"] for tool in CRAFT_TOOLS} & {
        tool["name"] for tool in hub.definitions("Tell me a bedtime story")}
    assert {tool["name"] for tool in CRAFT_TOOLS} <= set(hub.status().get("craft", {"tools": []}).get("tools", [
        "star_roblox_craft_audit", "star_roblox_craft_recipe"]))
    result = hub.call("star_roblox_craft_audit", {"instances": []}, enabled=names)
    assert result["read_only"] and result["findings"] == []
    sample = hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud"}, enabled=names)
    assert sample["preview_only"] and sample["script_class"] == "LocalScript"
    with pytest.raises(PermissionError):
        hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud"}, enabled=set())
    with pytest.raises(Exception):
        hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud", "execute": True}, enabled=names)
    with pytest.raises(Exception):
        hub.call("star_roblox_craft_audit", {"instances": [{"path": "x", "class": "Part", "code": "print(1)"}]},
                 enabled=names)


def test_disable_roblox_research_removes_craft_tools(tmp_path):
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False,
                            roblox_research_enabled=False)
    assert not {tool["name"] for tool in CRAFT_TOOLS} & {
        tool["name"] for tool in hub.definitions("Build Roblox UI and animation")}
    with pytest.raises(PermissionError):
        hub.call("star_roblox_craft_audit", {"instances": []}, enabled={"star_roblox_craft_audit"})
