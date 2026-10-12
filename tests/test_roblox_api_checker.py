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
local d = \`Instance.new("Bogus")\`
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
