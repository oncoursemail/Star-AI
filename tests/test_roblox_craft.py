"""Offline contract tests for Roblox scene craft, recipes and STAR tool gating."""
from __future__ import annotations

import json
from types import SimpleNamespace

from jsonschema import ValidationError
import pytest

import star.roblox_craft as craft
from star.intelligence import CRAFT_TOOLS, LocalIntelligence
from star.roblox_craft import MAX_FINDINGS, MAX_SCRIPT_CHARS, audit, recipe


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
    assert hub.status()["craft"] == {
        "enabled": True, "read_only": True, "tools": [tool["name"] for tool in CRAFT_TOOLS]}
    result = hub.call("star_roblox_craft_audit", {"instances": []}, enabled=names)
    assert result["read_only"] and result["findings"] == []
    sample = hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud"}, enabled=names)
    assert sample["preview_only"] and sample["script_class"] == "LocalScript"
    with pytest.raises(PermissionError):
        hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud"}, enabled=set())
    with pytest.raises(ValidationError):
        hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud", "execute": True}, enabled=names)
    with pytest.raises(ValidationError):
        hub.call("star_roblox_craft_audit", {"instances": [{"path": "x", "class": "Part", "code": "print(1)"}]},
                 enabled=names)


def test_disable_roblox_research_removes_craft_tools(tmp_path):
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False,
                            roblox_research_enabled=False)
    assert not {tool["name"] for tool in CRAFT_TOOLS} & {
        tool["name"] for tool in hub.definitions("Build Roblox UI and animation")}
    assert hub.status()["craft"] == {"enabled": False, "read_only": True, "tools": []}
    with pytest.raises(PermissionError):
        hub.call("star_roblox_craft_audit", {"instances": []}, enabled={"star_roblox_craft_audit"})
    with pytest.raises(PermissionError):
        hub.call("star_roblox_craft_recipe", {"kind": "impact-vfx"}, enabled={"star_roblox_craft_recipe"})


@pytest.mark.parametrize("source", [
    "task.wait(1)",
    "task.spawn(function() end)",
    "task.delay(1, function() end)",
    "worker.wait(1)",
    "worker:spawn(function() end)",
    "worker:delay(1, function() end)",
    "await(1)",
    "respawn()",
    "custom_delay(1)",
])
def test_task_library_and_member_calls_are_not_legacy(source):
    report = audit([], [{"path": "ServerScriptService.Timer", "class": "Script", "source": source}])
    assert report["reviewed_scripts"] == 1
    assert "luau-legacy-task" not in rules(report)


@pytest.mark.parametrize("source", [
    "wait(1)",
    "spawn(function() end)",
    "delay(1, function() end)",
    "local elapsed = wait \t(1)",
])
def test_bare_scheduling_calls_are_legacy(source):
    report = audit([], [{"path": "ServerScriptService.Timer", "class": "Script", "source": source}])
    assert "luau-legacy-task" in rules(report)


@pytest.mark.parametrize("source", ["--!strict\ntask.wait(1)", " \t--!strict\n", "\n \t--!strict\n"])
def test_strict_directive_accepts_horizontal_indentation(source):
    report = audit([], [{"path": "ServerScriptService.Timer", "class": "Script", "source": source}])
    assert "luau-strict" not in rules(report)


@pytest.mark.parametrize("source", ["\v--!strict", "\f--!strict", "--!strictly"])
def test_strict_directive_rejects_nonhorizontal_prefixes_and_longer_words(source):
    report = audit([], [{"path": "ServerScriptService.Timer", "class": "Script", "source": source}])
    assert "luau-strict" in rules(report)


def test_whitespace_heavy_audit_uses_line_bounded_strict_scan(monkeypatch):
    """Exercise the largest script and verify the live pattern cannot rescan later lines.

    This checks the source of the quadratic regression without a flaky clock threshold.
    The spy delegates every search to the real regex engine.
    """
    patterns = []
    original_search = craft.re.search

    def observe_search(pattern, source, *args, **kwargs):
        if "--!strict" in pattern:
            patterns.append(pattern)
        return original_search(pattern, source, *args, **kwargs)

    monkeypatch.setattr(craft.re, "search", observe_search)
    report = audit([], [{"path": "ServerScriptService.Blank", "class": "Script",
                         "source": "\n" * MAX_SCRIPT_CHARS}])
    assert report["reviewed_scripts"] == 1
    assert "luau-strict" in rules(report)
    assert len(patterns) == 1
    pattern = craft.re.compile(patterns[0])
    assert pattern.match("\n--!strict") is None
    assert pattern.match(" \t--!strict") is not None


@pytest.mark.parametrize("word", [
    "ui", "gui", "hud", "vfx", "particle", "particles", "animation", "animations",
    "tween", "tweens", "rig", "rigs", "audit",
])
def test_craft_words_offer_tools_with_default_roblox_research(tmp_path, word):
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False)
    names = {tool["name"] for tool in hub.definitions(f"Roblox {word}")}
    assert {tool["name"] for tool in CRAFT_TOOLS} <= names


@pytest.mark.parametrize("word", [
    "code", "build", "create", "review", "script", "scripts", "effect", "effects",
    "scripting", "interface", "interfaces", "inspect", "guidance", "rigging", "auditorium",
    "build create review scripts and effects",
])
def test_generic_roblox_prompts_do_not_offer_or_authorize_craft(tmp_path, word):
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False)
    names = {tool["name"] for tool in hub.definitions(f"Roblox {word}")}
    assert not {tool["name"] for tool in CRAFT_TOOLS} & names
    with pytest.raises(PermissionError):
        hub.call("star_roblox_craft_recipe", {"kind": "responsive-hud"}, enabled=names)


@pytest.mark.parametrize("field", ["instances", "scripts"])
def test_craft_audit_schema_describes_dot_separated_paths(field):
    tool = next(tool for tool in CRAFT_TOOLS if tool["name"] == "star_roblox_craft_audit")
    path = tool["inputSchema"]["properties"][field]["items"]["properties"]["path"]
    assert path["description"] == "dot-separated Studio path, for example Workspace.Part.Emitter"
    assert path["maxLength"] == 220


@pytest.mark.parametrize("kind,parent,rule,expected", [
    ("ParticleEmitter", "Folder", "vfx-parent", True),
    ("ParticleEmitter", "Part", "vfx-parent", False),
    ("ParticleEmitter", "Attachment", "vfx-parent", False),
    ("Animator", "Model", "animation-animator-owner", True),
    ("Animator", "Humanoid", "animation-animator-owner", False),
    ("Animator", "AnimationController", "animation-animator-owner", False),
])
def test_dot_separated_paths_drive_parent_checks(tmp_path, kind, parent, rule, expected):
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False)
    names = {tool["name"] for tool in hub.definitions("Audit Roblox VFX and animation")}
    report = hub.call("star_roblox_craft_audit", {"instances": [
        node("Workspace.Parent", parent), node("Workspace.Parent.Child", kind)]}, enabled=names)
    assert report["reviewed_instances"] == 2
    assert (rule in rules(report)) is expected
    if expected:
        assert next(item["path"] for item in report["findings"] if item["rule"] == rule) == "Workspace.Parent.Child"


def test_craft_and_current_cloud_dispatch_remain_independent(tmp_path):
    cloud = SimpleNamespace(status=lambda: {"key_present": True})
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False, cloud=cloud)
    names = {tool["name"] for tool in hub.definitions("Audit Roblox UI and Open Cloud")}
    assert {"star_roblox_craft_audit", "star_roblox_craft_recipe", "star_roblox_cloud_status"} <= names
    assert hub.call("star_roblox_cloud_status", {}, enabled=names) == {"key_present": True}
    report = hub.call("star_roblox_craft_audit", {"instances": [], "scripts": [
        {"path": "ServerScriptService.Modern", "class": "Script", "source": "--!strict\ntask.wait(1)"},
        {"path": "ServerScriptService.Legacy", "class": "Script", "source": "--!strict\nwait(1)"},
    ]}, enabled=names)
    assert report["read_only"] and not report["executed"]
    assert [(item["rule"], item["path"]) for item in report["findings"]] == [
        ("luau-legacy-task", "ServerScriptService.Legacy")]
