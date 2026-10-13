"""Corpus evidence, clean examples, real scan path, line and token isolation."""
import json
import re

import pytest

from star import roblox_api_confusions as api


def test_eighty_unique_official_source_backed_entries():
    raw = json.loads(api.DATA.read_text(encoding="utf-8"))
    assert len(raw) == len(api.load_confusions()) == 80
    assert {entry["kind"] for entry in raw} == {"method"}
    assert len({row["wrong"] for row in raw}) == 80
    assert len({row["right"] for row in raw}) == 20
    assert {row["source_url"].rsplit("/", 1)[-1] for row in raw} == {
        "Instance", "Players", "Humanoid", "RemoteEvent", "GlobalDataStore", "WorldRoot"
    }
    assert all(row["source_url"].startswith("https://create.roblox.com/docs/reference/engine/classes/")
               for row in raw)
    assert all(re.fullmatch(r":[A-Za-z][A-Za-z0-9]*\\(", row["wrong"]) for row in raw)


@pytest.mark.parametrize("entry", api.load_confusions(), ids=lambda row: row["wrong"][1:-1])
def test_each_wrong_method_hits_but_its_official_replacement_does_not(entry):
    wrong = "local obj = target\\nobj" + entry["wrong"] + "123)\\n"
    right = "local obj = target\\nobj" + entry["right"] + "123)\\n"
    result = api.scan_luau(wrong)
    assert result == [{"line": 2, "column": 4, **entry}]
    assert api.scan_luau(right) == []


def test_multiline_realistic_code_and_ignored_text():
    source = """-- :GetAllChildren(1) is only in a comment
local target = workspace:FindFirstChild("Npc")
if target then
    target:GetAllChildren()
    target:GetDescendants()
end
local quoted = ":FireClients()"
--[[
workspace:RayCast(origin, direction)
]]
local long_comment = 'remote:SendServer()'
workspace:RayCast(origin, direction)
remote:FireAllClients()
remote:FireClients()
"""
    hits = api.scan_luau(source)
    assert [(h["line"], h["wrong"], h["right"]) for h in hits] == [
        (4, ":GetAllChildren(", ":GetChildren("),
        (12, ":RayCast(", ":Raycast("),
        (14, ":FireClients(", ":FireAllClients("),
    ]
    assert all(h["source_url"].startswith("https://create.roblox.com/") for h in hits)


def test_clean_valid_calls_have_no_hits():
    source = """local Players = game:GetService("Players")
local player = Players:GetPlayerFromCharacter(model)
local humanoid = model:FindFirstChildOfClass("Humanoid")
local children = model:GetChildren()
workspace:Raycast(origin, direction)
if humanoid then humanoid:MoveTo(destination) end
dataStore:UpdateAsync("level", function(value) return value end)
remote:FireServer("hello")
"""
    assert api.scan_luau(source) == []
    assert api.scan_luau("") == []
    with pytest.raises(TypeError):
        api.scan_luau(None)


def test_corpus_cannot_be_silently_changed_to_invalid_or_external_sources(monkeypatch, tmp_path):
    original = api.DATA
    bad = [{"wrong": ":GetAllChildren(", "right": ":GetChildren(",
            "kind": "method", "source_url": "https://untrusted.invalid/api"}]
    file = tmp_path / "bad.json"
    file.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(api, "DATA", file)
    api.load_confusions.cache_clear()
    try:
        with pytest.raises(ValueError, match="official class page"):
            api.load_confusions()
    finally:
        monkeypatch.setattr(api, "DATA", original)
        api.load_confusions.cache_clear()
