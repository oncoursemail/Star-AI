"""Studio milestone manifests are inert data until Studio executes a check."""
import json

import pytest

from star.studio_milestones import (
    GAMES, MAX_CHECK_CHARS, STUDIO_DIR, load_all_milestones, load_milestones, validate_check,
)


READ_ONLY_CHECK = '''
local count = 0
for _, item in ipairs(workspace:GetChildren()) do
    if item:IsA("SpawnLocation") then
        count = count + 1
    end
end
if count == 0 then
    return false, "Missing spawn"
end
return true, "Found " .. tostring(count) .. " spawns"
'''


def manifest(game, rows=None):
    return {"game": game, "milestones": rows if rows is not None else [
        {"id": game + ".test", "description": "Inspect the model", "check": READ_ONLY_CHECK},
    ]}


def write_manifest(folder, game, rows=None):
    (folder / f"{game}.json").write_text(json.dumps(manifest(game, rows)), encoding="utf-8")


def test_shipped_catalog_is_ordered_and_statically_read_only():
    milestones = load_all_milestones()
    assert len(milestones) == 11
    assert [m.id.split(".")[0] for m in milestones] == ["obby"] * 3 + ["tycoon"] * 4 + ["rounds"] * 4
    assert len({m.id for m in milestones}) == len(milestones)
    assert all(m.description and m.check and len(m.check) <= MAX_CHECK_CHARS for m in milestones)
    assert all("return true," in m.check and "return false," in m.check for m in milestones)
    for game in GAMES:
        raw = json.loads((STUDIO_DIR / f"{game}.json").read_text(encoding="utf-8"))
        assert [m.id for m in load_milestones(game)] == [row["id"] for row in raw["milestones"]]


def test_read_only_inspection_with_local_counters_is_allowed():
    validate_check(READ_ONLY_CHECK)
    validate_check('''
local state = game:GetService("ReplicatedStorage"):FindFirstChild("RoundState")
if not state or not state:IsA("StringValue") then
    return false, "No RoundState"
end
return true, "RoundState " .. state.Value
''')


@pytest.mark.parametrize("attack", [
    'workspace.Part:Destroy()',
    'workspace.Part.Parent = nil',
    'local part = workspace.Part\npart.Transparency = 0.5',
    'local part = workspace.Part\npart["Anchored"] = true',
    'local web = game:GetService("HttpService")',
    'loadstring("return true")()',
    'local env = getfenv()',
    'local part = Instance.new("Part")',
    'workspace.Part.Touched:Connect(function() end)',
    'workspace.Part:SetAttribute("Owner", 1)',
    'workspace:ClearAllChildren()',
    'local copy = workspace.Part:Clone()',
    'local p = workspace.Part\np . Parent = workspace',
    'local f = workspace.Part.Destroy\nf(workspace.Part)',
    'local service = game:GetService("Http" .. "Service")',
    'local p = workspace.Part\np.Value += 10',
    'local _ = game:GetService("Players"):FindFirstChild("Thing")',
    'local _ = game["GetService"](game, "HttpService")',
    'workspace.Part:PivotTo(CFrame.new())',
    'local count = 0\nwhile true do count = count + 1 end',
    'local p = workspace.Part\nrawset(p, "Parent", workspace)',
    'local localOnly = 1\nglobalValue = localOnly',
    'local x = 1\nworkspace.Name, x = "bad", 2',
    'local x = 1\nworkspace.Name,\n x = "bad", 2',
    'local name = "Http" .. "Service"\nlocal spoof = \':GetService("ReplicatedStorage")\'\nlocal service = game:GetService(name)',
])
def test_malicious_or_unapproved_luau_is_rejected(attack):
    with pytest.raises(ValueError):
        validate_check(attack + '\nreturn false, "fail"\nreturn true, "pass"')


@pytest.mark.parametrize("invalid", [None, 2, "", " ", "return true", "x" * (MAX_CHECK_CHARS + 1)])
def test_invalid_or_unbounded_snippets_are_rejected(invalid):
    with pytest.raises(ValueError):
        validate_check(invalid)


def test_size_limit_is_in_bytes_not_only_unicode_codepoints():
    source = 'local hint = "' + '✦' * 1500 + '"\nreturn false, "fail"\nreturn true, hint'
    assert len(source) < MAX_CHECK_CHARS
    with pytest.raises(ValueError, match="bounded"):
        validate_check(source)


@pytest.mark.parametrize("bad", [
    [], None, {},
    {"game": "obby", "milestones": []},
    {"game": "tycoon", "milestones": [
        {"id": "obby.test", "description": "Inspect the model", "check": READ_ONLY_CHECK},
    ]},
    {"game": "obby", "milestones": [{"id": "Bad ID", "description": "valid", "check": READ_ONLY_CHECK}]},
    {"game": "obby", "milestones": [{"id": "obby.test", "description": "", "check": READ_ONLY_CHECK}]},
    {"game": "obby", "milestones": [{"id": "obby.test", "description": 9, "check": READ_ONLY_CHECK}]},
    {"game": "obby", "milestones": [{"id": "obby.test", "description": "desc", "check": 9}]},
    {"game": "obby", "milestones": [{"id": "obby.test", "description": "desc", "check": READ_ONLY_CHECK, "extra": 1}]},
    {"game": "obby", "milestones": [
        {"id": "obby.test", "description": "desc", "check": READ_ONLY_CHECK},
        {"id": "obby.test", "description": "desc", "check": READ_ONLY_CHECK},
    ]},
])
def test_manifest_schema_and_duplicate_ids_are_rejected(tmp_path, bad):
    (tmp_path / "obby.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_milestones("obby", directory=tmp_path)


def test_rejects_unknown_game_and_missing_file(tmp_path):
    with pytest.raises(ValueError):
        load_milestones("../other", directory=tmp_path)
    with pytest.raises(FileNotFoundError):
        load_milestones("obby", directory=tmp_path)


def test_detects_duplicate_ids_across_game_files(tmp_path):
    for game in GAMES:
        write_manifest(tmp_path, game, [
            {"id": "shared.id", "description": "Inspect", "check": READ_ONLY_CHECK},
        ])
    with pytest.raises(ValueError, match="Duplicate"):
        load_all_milestones(directory=tmp_path)


def test_manifest_is_loaded_as_inert_data_without_studio_or_execution(tmp_path):
    rows = [
        {"id": "obby.alpha", "description": "First", "check": READ_ONLY_CHECK},
        {"id": "obby.beta", "description": "Second", "check": READ_ONLY_CHECK},
    ]
    write_manifest(tmp_path, "obby", rows)
    checks = load_milestones("obby", directory=tmp_path)
    assert [m.id for m in checks] == ["obby.alpha", "obby.beta"]
    assert [m.check for m in checks] == [READ_ONLY_CHECK, READ_ONLY_CHECK]


def test_get_service_matches_literal_arguments_not_text_inside_quoted_strings():
    validate_check('''
local hint = ':GetService("ReplicatedStorage")'
local storage = game:GetService("ReplicatedStorage")
if storage == nil then
    return false, "missing"
end
return true, hint
''')
