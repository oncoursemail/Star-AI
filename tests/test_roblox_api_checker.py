"""Offline real-path regression tests for Roblox API dump name checking."""
import json
from pathlib import Path

import pytest

from star.roblox_api_checker import ApiFinding, check_luau_api, load_api_dump


DUMP_PATH = Path(__file__).parent / "fixtures" / "roblox_api_small.json"


@pytest.fixture(scope="module")
def dump():
    return load_api_dump(DUMP_PATH)


def test_loads_full_api_schema_and_inherited_members(dump):
    assert len(dump.classes) == 15
    assert {"Destroy", "PivotTo", "Color", "Shape"} <= dump.inherited_members["Part"]
    assert "Players" in dump.services
    assert "Part" not in dump.services


@pytest.mark.parametrize("source", [
    'local p = Instance.new("Part")\np.Anchored = true\np.Color = Color3.new(1, 0, 0)\np:Destroy()',
    'local players = game:GetService("Players")\nplayers.PlayerAdded:Connect(function(player) end)\nplayers:GetPlayers()',
    'local part = Instance.new("Part")\npart:PivotTo(CFrame.new())\npart.Shape = Enum.PartType.Block',
    'local ws = game:GetService("Workspace")\nws.Gravity = 196.2\nlocal humanoid = Instance.new("Humanoid")\nhumanoid:MoveTo(Vector3.new())',
])
def test_valid_code_has_no_findings(dump, source):
    assert check_luau_api(source, dump) == []


@pytest.mark.parametrize(("source", "rule", "name", "suggestion", "line"), [
    ('Instance.new("Prat")', "unknown-class", "Prat", "Part", 1),
    ('local p = game:GetService("TweenServce")', "unknown-service", "TweenServce", "TweenService", 1),
    ('local p = Instance.new("Part")\np:Destry()', "unknown-member", "Destry", "Destroy", 2),
    ('local p = Instance.new("Part")\np.Colour = Color3.new(1, 0, 0)', "unknown-member", "Colour", "Color", 2),
    ('local p = Instance.new("Part")\np.Transparncy += 0.2', "unknown-member", "Transparncy", "Transparency", 2),
])
def test_wrong_names_produce_exact_diagnostics(dump, source, rule, name, suggestion, line):
    findings = check_luau_api(source, dump)
    assert len(findings) == 1
    assert findings[0].rule_id == rule
    assert findings[0].line == line
    assert findings[0].name == name
    assert findings[0].suggestion == suggestion
    assert findings[0].class_name == ("Part" if rule == "unknown-member" else None)


def test_ignores_comments_and_all_string_forms(dump):
    source = """
-- Instance.new("FakePart")
--[=[ game:GetService("FakeService")
local bogus = Instance.new("Bad")
]=]
local a = "Instance.new('Bogus') p:NotReal()"
local b = 'game:GetService("NoSuch")'
local c = [==[ Instance.new("Fake") ]==]
local d = `Instance.new("Bogus")`
local e = "backslash \\" Instance.new('FalsePositive')"
local p = Instance.new("Part")
-- p:Unreal()
p:Destroy()
"""
    assert check_luau_api(source, dump) == []


def test_unknown_types_dynamic_inputs_and_read_access_are_not_guessed(dump):
    source = """
local name = "Imaginary"
local x = Instance.new(name)
x:MadeUp()
y.Unknown = 1
local p = Instance.new("Part")
local read = p.ChildNamedByUser
p = getDynamicObject()
p:MadeUp()
"""
    assert check_luau_api(source, dump) == []


@pytest.mark.parametrize("source", [
    'local p = Instance.new("Part")\nlocal function inspect(p)\n    p:MadeUp()\nend',
    'local p = Instance.new("Part")\nlocal p\np:MadeUp()',
    'local p = Instance.new("Part")\np = getDynamicObject()\np:MadeUp()',
])
def test_shadowing_and_reassignment_stop_type_inference(dump, source):
    assert check_luau_api(source, dump) == []


def test_non_service_class_is_rejected_only_from_get_service(dump):
    findings = check_luau_api('game:GetService("Part")', dump)
    assert len(findings) == 1
    assert findings[0].rule_id == "unknown-service"
    assert check_luau_api('Instance.new("Part")', dump) == []


def test_multiple_hits_deterministic_and_line_numbers(dump):
    source = 'local p = Instance.new("Part")\n-- ignore\np:Destry()\np.Colour = nil\n'
    expected = [
        ApiFinding("unknown-member", 3, "Part", "Destry", "Destroy"),
        ApiFinding("unknown-member", 4, "Part", "Colour", "Color"),
    ]
    assert check_luau_api(source, dump) == expected
    assert check_luau_api(source, dump) == expected


@pytest.mark.parametrize("payload", [
    "not-json", "[]", "{}", '{"Classes":[]}',
    '{"Classes":[{"Name":"Part","Superclass":"Instance","Members":[]}]}',
    '{"Classes":[{"Name":"A","Superclass":"A","Members":[]}]}',
    '{"Classes":[{"Name":"A","Superclass":"","Members":[{"Name":3}]}]}',
])
def test_malformed_dump_fails_explicitly(tmp_path, payload):
    path = tmp_path / "dump.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        load_api_dump(path)


def test_invalid_types_are_refused(dump):
    with pytest.raises(TypeError):
        check_luau_api(None, dump)
    with pytest.raises(TypeError):
        check_luau_api("", None)


def test_loading_local_dump_only_and_never_executes_luau(dump):
    assert check_luau_api('require(999)\nloadstring("Instance.new(\\"Bad\\")")', dump) == []
    assert json.loads(DUMP_PATH.read_text(encoding="utf-8"))["Classes"]


# -- "did you mean" is only offered when a real name is close ---------------------------------------------------

@pytest.mark.parametrize("source", [
    'Instance.new("MyCustomHitboxThing")',
    'local s = game:GetService("ZzzQqq")',
    'local p = Instance.new("Part")\np:ExplodeIntoConfetti()',
])
def test_unrelated_unknown_names_get_no_misleading_suggestion(dump, source):
    findings = check_luau_api(source, dump)
    assert len(findings) == 1 and findings[0].suggestion is None


@pytest.mark.parametrize(("source", "suggestion"), [
    ('Instance.new("part")', "Part"),
    ('local p = Instance.new("Part")\np:destroy()', "Destroy"),
    ('local s = game:GetService("players")', "Players"),
])
def test_wrong_case_suggests_the_exact_name(dump, source, suggestion):
    findings = check_luau_api(source, dump)
    assert len(findings) == 1 and findings[0].suggestion == suggestion


def test_preflight_message_omits_review_hint_without_a_close_name(dump):
    from star.roblox_project_preflight import _api_report
    rows = _api_report('Instance.new("MyCustomHitboxThing")', dump)
    assert rows[0]["message"] == "Unknown API name MyCustomHitboxThing."
    rows = _api_report('Instance.new("Prat")', dump)
    assert rows[0]["message"] == "Unknown API name Prat. Review Part."


# -- wrong event/property/method names on services and globals (pre-solve gap 2026-10-16) ---------------------

@pytest.mark.parametrize(("source", "class_name", "name", "suggestion"), [
    ('local Players = game:GetService("Players")\nPlayers.PlayerJoined:Connect(function(p) end)',
     "Players", "PlayerJoined", "PlayerAdded"),
    ('game:GetService("Players").PlayerJoined:Connect(print)', "Players", "PlayerJoined", "PlayerAdded"),
    ('game.Players.PlayerJoined:Connect(print)', "Players", "PlayerJoined", "PlayerAdded"),
    ('local rs = game:GetService("RunService")\nrs.HeartBeat:Wait()', "RunService", "HeartBeat", "Heartbeat"),
    ('local p = Instance.new("Part")\np.Touch:Once(print)', "Part", "Touch", "Touched"),
    ('workspace.gravity = 10', "Workspace", "gravity", "Gravity"),
    ('local g = workspace.currentCamera', "Workspace", "currentCamera", "CurrentCamera"),
    ('game:GetService("TweenService"):Craete(x, i, g)', "TweenService", "Craete", "Create"),
])
def test_wrong_member_on_service_or_global_is_reported(dump, source, class_name, name, suggestion):
    findings = check_luau_api(source, dump)
    assert [(f.rule_id, f.class_name, f.name, f.suggestion) for f in findings] == [
        ("unknown-member", class_name, name, suggestion)]


@pytest.mark.parametrize("source", [
    # Plain reads can be children: never guessed.
    'local base = workspace.Baseplate\nworkspace.Map.Spawn.Touched:Connect(print)',
    'local remotes = game.ReplicatedStorage.Remotes\nlocal p1 = game.Players.Player1',
    # A chained call result is a child, not the service.
    'local remote = game:GetService("ReplicatedStorage"):WaitForChild("Ping")\nremote.OnServerEvent:Connect(print)',
    'local folder = Instance.new("Folder", workspace):Clone()\nfolder:Whatever()',
    # Locals and parameters named like the globals.
    'local workspace = {}\nworkspace.Anything:Connect(print)',
    'local function f(game) game.Players.Nope:Connect(print) end',
    'local Players = game:GetService("Players")\nPlayers.PlayerAdded:Connect(print)\nPlayers.PlayerRemoving:Wait()',
])
def test_child_reads_chains_and_shadowed_globals_are_not_flagged(dump, source):
    assert check_luau_api(source, dump) == []


REAL_GOOD = """
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local remote = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("Hit")
Players.PlayerAdded:Connect(function(player)
    local stats = Instance.new("Folder")
    stats.Name = "leaderstats"
    stats.Parent = player
    player.CharacterAdded:Connect(function(character) end)
end)
Players.PlayerRemoving:Connect(function(player) end)
game.Players.PlayerAdded:Wait()
game:GetService("Players").PlayerAdded:Once(print)
game:BindToClose(function() end)
game.Loaded:Wait()
RunService.Heartbeat:Connect(function(dt) end)
RunService.Stepped:Wait()
workspace.ChildAdded:Connect(print)
workspace.Gravity = 196.2
local cam = workspace.CurrentCamera
local hit = workspace:Raycast(Vector3.zero, Vector3.yAxis)
local part = Instance.new("Part")
part.Touched:Connect(print)
part:GetPropertyChangedSignal("Color"):Connect(print)
part.Size = Vector3.new(4, 1, 4)
TweenService:Create(part, TweenInfo.new(1), {Transparency = 1}):Play()
remote.OnServerEvent:Connect(print)
local hum = Instance.new("Humanoid")
hum.Died:Connect(print)
hum.HealthChanged:Connect(print)
"""


def test_real_dump_correct_code_has_no_findings_and_catches_player_joined():
    from star.roblox_api_dataset import api_dump
    real = api_dump()
    assert check_luau_api(REAL_GOOD, real) == []
    bad = check_luau_api('local Players = game:GetService("Players")\nPlayers.PlayerJoined:Connect(print)', real)
    assert [(f.class_name, f.name, f.suggestion) for f in bad] == [("Players", "PlayerJoined", "PlayerAdded")]


def test_real_dump_repo_luau_examples_have_no_api_findings():
    """Every hand-written example in the repo is intended-correct Luau: the full dump must find nothing."""
    from star.roblox_api_dataset import api_dump
    real = api_dump()
    root = Path(__file__).resolve().parents[1]
    files = [p for parent in ("examples/roblox", "examples/roblox-templates")
             for p in sorted((root / parent).rglob("*.luau")) if not p.name.endswith(".spec.luau")]
    assert len(files) >= 30
    hits = [(p.name, f.line, f.name) for p in files
            for f in check_luau_api(p.read_text(encoding="utf-8"), real)]
    assert hits == []
