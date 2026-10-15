"""The standalone analyzer knows no Roblox engine names (proposal #325 item 14).

Without these, every script using Vector2, NumberRange, Random, task-era globals, or a Roblox class
in a `--!strict` annotation got an "Unknown global/type" finding that was not a real mistake.
"""
import pytest

from star import luau_analyze


def diagnostic(kind, message, line=1):
    return f"star-check.luau({line},1): {kind}: {message}\n"


@pytest.mark.parametrize("name", [
    # data types
    "Vector2", "Vector2int16", "Vector3int16", "NumberRange", "NumberSequenceKeypoint",
    "ColorSequenceKeypoint", "Random", "Ray", "RaycastResult", "DateTime", "Rect",
    "PhysicalProperties", "Font", "Faces", "Axes", "PathWaypoint", "SharedTable",
    # Roblox-only globals
    "tick", "wait", "spawn", "delay", "time", "elapsedTime", "warn", "settings", "UserSettings",
])
def test_roblox_data_types_and_globals_are_not_reported(name):
    assert luau_analyze.parse_diagnostics(diagnostic("TypeError", f"Unknown global '{name}'")) == []


@pytest.mark.parametrize("name", [
    "Part", "MeshPart", "BasePart", "Folder", "ModuleScript", "RemoteEvent", "RemoteFunction",
    "UnreliableRemoteEvent", "BindableEvent", "Tool", "Attachment", "Motor6D", "Sound",
    "ParticleEmitter", "Camera", "Workspace", "ScreenGui", "Frame", "TextLabel", "TextButton",
    "ImageLabel", "ScrollingFrame", "GuiObject", "ProximityPrompt", "Animator", "AnimationTrack",
    "InputObject", "Highlight", "ObjectValue", "IntValue", "ReplicatedStorage", "ServerStorage",
    "RunService", "UserInputService", "TweenService", "DataStoreService", "GlobalDataStore",
    "HttpService", "CollectionService", "PathfindingService", "MarketplaceService",
    "TeleportService", "Lighting", "PlayerGui", "Backpack", "Tween", "EnumItem",
])
def test_roblox_classes_in_strict_annotations_are_not_reported(name):
    assert luau_analyze.parse_diagnostics(diagnostic("TypeError", f"Unknown type '{name}'")) == []


@pytest.mark.parametrize("message", [
    "Unknown global 'pointss'",          # a real typo stays a finding
    "Unknown type 'PlayerDatta'",        # a misspelt user type stays a finding
    "Unknown global 'vector2'",          # case matters: Luau names are case-sensitive
])
def test_typos_and_user_types_are_still_reported(message):
    findings = luau_analyze.parse_diagnostics(diagnostic("TypeError", message))
    assert [f.rule_id for f in findings] == ["luau-analyze-typeerror"]


def test_only_unknown_name_errors_are_ignored_for_engine_names():
    findings = luau_analyze.parse_diagnostics(
        diagnostic("TypeError", "Type 'Vector2' could not be converted into 'number'"))
    assert len(findings) == 1


@pytest.mark.parametrize("name", ["RunService", "Part", "TweenService"])
def test_a_class_name_used_as_a_global_is_still_a_mistake(name):
    # `RunService.Heartbeat` without game:GetService, or `Part.new()`, is a real bug.
    findings = luau_analyze.parse_diagnostics(diagnostic("TypeError", f"Unknown global '{name}'"))
    assert [f.rule_id for f in findings] == ["luau-analyze-typeerror"]


def test_a_strict_script_typed_with_roblox_classes_analyzes_clean_without_a_notice(monkeypatch, recwarn):
    from tests.test_luau_analyze import fake_analyzer
    monkeypatch.setattr(luau_analyze, "_notified", set())
    fake_analyzer(monkeypatch, status=1, stderr=(
        "star-check.luau(2,15): TypeError: Unknown type 'Part'\n"
        "star-check.luau(3,20): TypeError: Unknown global 'Vector2'\n"))
    source = "--!strict\nlocal p: Part = nil :: any\nlocal size = Vector2.new(1, 2)\nreturn p, size\n"
    assert luau_analyze.analyze(source) == []
    assert not [w for w in recwarn if "not understood" in str(w.message)]
