"""Regression tests for generated Roblox player-data code."""
import re

import pytest

from star.roblox_data_compiler import compile_schema, validate_schema


SCHEMAS = [
    {"version": 1, "fields": {"Coins": {"type": "number", "default": 0, "min": 0, "leaderstats": True}}},
    {"version": 2, "fields": {"Name": {"type": "string", "default": "New", "max": 24}},
     "migrations": [{"from": 1, "to": 2, "operations": [{"op": "rename", "field": "OldName", "to": "Name"}]}]},
    {"version": 3, "fields": {"Wins": {"type": "number", "default": 1, "min": 0, "max": 999},
                               "Verified": {"type": "boolean", "default": False}},
     "migrations": [{"from": 1, "to": 2, "operations": [{"op": "set", "field": "Wins", "value": 1}]},
                    {"from": 2, "to": 3, "operations": [{"op": "delete", "field": "Legacy"}]}]},
]

# Stable golden fragments exercised for three independent schema layouts.
GOLDENS = [
    ('local VERSION = 1', 'Coins = { type = "number", default = 0, min = 0 }', 'Coins: number,'),
    ('local VERSION = 2', 'Name = { type = "string", default = "New", max = 24 }',
     '{ op = "rename", field = "OldName", to = "Name" }'),
    ('local VERSION = 3', 'Verified = { type = "boolean", default = false }',
     '{ op = "delete", field = "Legacy" }'),
]


@pytest.mark.parametrize(("schema", "golden"), zip(SCHEMAS, GOLDENS))
def test_three_schema_goldens(schema, golden):
    module, spec = compile_schema(schema)
    for fragment in golden:
        assert fragment in module
    assert module.startswith("--!strict")
    assert spec.startswith("--!strict")
    assert "module.migrate({}, 1)" in spec
    for name in schema["fields"]:
        assert f"invalid_{name}" in spec
    assert compile_schema(schema) == (module, spec)


@pytest.mark.parametrize("schema", [
    {"version": 0, "fields": {"A": {"type": "number", "default": 1}}},
    {"version": 1, "fields": {"end": {"type": "string", "default": ""}}},
    {"version": 1, "fields": {"A": {"type": "number", "default": True}}},
    {"version": 1, "fields": {"A": {"type": "number", "default": 5, "max": 3}}},
    {"version": 1, "fields": {"A": {"type": "boolean", "default": False, "min": 0}}},
    {"version": 2, "fields": {"A": {"type": "number", "default": 0}}},
    {"version": 2, "fields": {"A": {"type": "number", "default": 0}},
     "migrations": [{"from": 1, "to": 3, "operations": []}]},
    {"version": 1, "fields": {"A": {"type": "string", "default": "a", "min": 2}}},
])
def test_schema_rejection(schema):
    with pytest.raises(ValueError):
        validate_schema(schema)


def test_every_datastore_access_wrapped_by_pcall():
    module, _ = compile_schema(SCHEMAS[2])
    assert "SetAsync" not in module
    assert "GetAsync" not in module
    assert module.count("store:UpdateAsync(") == 3
    # All generated DataStore calls are inside retry callbacks; retry runs action in pcall.
    assert "local ok, value = pcall(action)" in module
    assert not re.search(r"store:(?:UpdateAsync|GetAsync|SetAsync)\(", module.split("local function retry")[0])
    assert "local ok, record = retry(function()" in module
    assert "local succeeded, result = retry(function()" in module
    assert "retry(function()" in module.split("migration failed")[1]


def test_retry_lock_and_lifecycle():
    module, _ = compile_schema(SCHEMAS[0])
    for fragment in ("2 ^ (attempt - 1)", "old.lock.expires > os.time()",
                     "old.lock.token ~= token", "Players.PlayerRemoving:Connect",
                     "game:BindToClose", "task.wait(AUTOSAVE)", "warn(\"PlayerData validation\""):
        assert fragment in module


def test_compile_file(tmp_path):
    import json
    from star.roblox_data_compiler import compile_file

    source = tmp_path / "schema.json"
    source.write_text(json.dumps(SCHEMAS[0]))
    module, spec = compile_file(source, tmp_path / "out")
    assert module.read_text().startswith("--!strict")
    assert spec.read_text().startswith("--!strict")
