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
    assert "releaseLock(userId)" in module.split("migration failed")[1]
    assert "retry(function()" in module.split("local function releaseLock", 1)[1].split("local function mirror", 1)[0]


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


@pytest.mark.parametrize(("field_type", "description"), [
    ([], "list"), ({}, "object"), (42, "integer"), (None, "null"),
])
def test_unhashable_or_nonstr_field_types_fail_as_valueerror(field_type, description):
    schema = {"version": 1, "fields": {"Coins": {"type": field_type, "default": 0}}}
    with pytest.raises(ValueError, match="unsupported field type"):
        validate_schema(schema)


@pytest.mark.parametrize("operation", [[], {}, 17, None])
def test_unhashable_or_nonstr_migration_ops_fail_as_valueerror(operation):
    schema = {
        "version": 2,
        "fields": {"Coins": {"type": "number", "default": 0}},
        "migrations": [{"from": 1, "to": 2,
                        "operations": [{"op": operation, "field": "Coins"}]}],
    }
    with pytest.raises(ValueError, match="unsupported migration operation"):
        validate_schema(schema)


@pytest.mark.parametrize(("autosave", "timeout", "accepted"), [
    (60, 180, True), (60, 149, False), (60, 120, False),
    (10, 50, True), (10, 49, False), (3600, 10, False),
    (3600, 7230, True), (3600, 7200, False), (10, True, False),
    (10, 86401, False),
])
def test_session_lock_refresh_margin(autosave, timeout, accepted):
    schema = {
        "version": 1,
        "fields": {"Coins": {"type": "number", "default": 0}},
        "autosave_seconds": autosave,
        "lock_timeout_seconds": timeout,
    }
    if not accepted:
        with pytest.raises(ValueError):
            compile_schema(schema)
        return
    module, _ = compile_schema(schema)
    assert f"local AUTOSAVE = {autosave}" in module
    assert f"local LOCK_TIMEOUT = {timeout}" in module


def test_default_lock_timeout_is_safe_for_default_autosave():
    module, _ = compile_schema(SCHEMAS[0])
    assert "local AUTOSAVE = 60" in module
    assert "local LOCK_TIMEOUT = 180" in module


def test_utf8_control_quotes_and_digits_emit_valid_luau_byte_literals():
    example = 'Joueur é 😀\x01"\\9'
    expected = r'"Joueur \195\169 \240\159\152\128\001\"\\9"'
    schema = {
        "version": 2,
        "fields": {"Name": {"type": "string", "default": example,
                            "max": len(example.encode("utf-8"))}},
        "migrations": [{"from": 1, "to": 2,
                        "operations": [{"op": "set", "field": "Name", "value": example}]}],
    }
    module, spec = compile_schema(schema)
    assert f"default = {expected}" in module
    assert f"value = {expected}" in module
    assert f"assert(valid.Name == {expected})" in spec
    assert "\\u00e9" not in module and "\\u00e9" not in spec
    assert "\\ud83d" not in module and "\\ud83d" not in spec


def test_utf8_byte_bounds_and_invalid_unicode_raise_valueerror():
    short = {"version": 1, "fields": {"Name": {"type": "string", "default": "é", "max": 1}}}
    with pytest.raises(ValueError, match="outside bounds"):
        validate_schema(short)
    short["fields"]["Name"]["max"] = 2
    assert validate_schema(short) == short
    short["fields"]["Name"]["default"] = "\ud800"
    with pytest.raises(ValueError, match="invalid Unicode"):
        validate_schema(short)
    migration = {
        "version": 2, "fields": {"Name": {"type": "string", "default": ""}},
        "migrations": [{"from": 1, "to": 2, "operations":
                        [{"op": "set", "field": "Name", "value": "\ud800"}]}],
    }
    with pytest.raises(ValueError, match="valid Unicode"):
        validate_schema(migration)


def test_departed_player_release_is_guarded_before_activation():
    module, _ = compile_schema(SCHEMAS[0])
    release = module.split("local function releaseLock(userId: number)", 1)[1].split(
        "local function mirror", 1)[0]
    assert "retry(function()" in release
    assert "store:UpdateAsync(keyFor(userId)" in release
    assert "old.lock.token ~= token then return nil end" in release
    assert "nextRecord.lock = nil" in release

    acquire = module.split("local function acquire(player: Player)", 1)[1].split(
        "local function save(", 1)[0]
    assert acquire.count("releaseLock(userId)") == 2  # failed migration or departed player
    assert acquire.index("local data, issues = validate(migrated)") < acquire.index(
        "if player.Parent ~= Players then") < acquire.index("active[userId] =")
    departed = acquire.split("if player.Parent ~= Players then", 1)[1].split(
        "active[userId] =", 1)[0]
    assert "releaseLock(userId)" in departed
    assert "return" in departed
    assert departed.index("releaseLock(userId)") < departed.index("return")


def test_autosave_snapshots_ids_before_yielding_save():
    module, _ = compile_schema(SCHEMAS[0])
    loop = module.split("task.wait(AUTOSAVE)", 1)[1].split("game:BindToClose", 1)[0]
    expected_order = (
        "local ids = {}", "for userId in pairs(active) do",
        "table.insert(ids, userId)", "for _, userId in ipairs(ids) do",
        "save(userId, false)",
    )
    positions = [loop.index(part) for part in expected_order]
    assert positions == sorted(positions)
    assert not re.search(r"for userId in pairs\(active\) do\s+save\(userId, false\)", loop)


def test_missing_fields_use_defaults_without_warning_and_invalid_fields_are_reported():
    module, spec = compile_schema(SCHEMAS[0])
    validation = module.split("local function validate(", 1)[1].split(
        "local function migrate(", 1)[0]
    assert "elseif value ~= nil then" in validation
    assert validation.index("elseif value ~= nil then") < validation.index(
        'table.insert(issues, "invalid field: " .. key)')
    assert "and #issues_Coins == 0" in spec
    assert "and #reported_Coins > 0" in spec
    assert "wrong_Coins.Coins = " in spec


def test_spec_requires_studio_services_and_makes_no_cli_claim():
    _, spec = compile_schema(SCHEMAS[1])
    assert "Roblox Studio-only smoke test" in spec
    assert "Requiring PlayerData initializes DataStore" in spec
    assert "Not executable by a standalone Luau CLI" in spec
    assert "Standalone pure-Luau test" not in spec
    assert "PlayerData Studio spec passed" in spec


@pytest.mark.parametrize("word", ["and", "break", "do", "elseif", "for", "in", "not", "or", "return", "while"])
def test_every_luau_keyword_is_refused_as_a_field_or_migration_name(word):
    with pytest.raises(ValueError):
        validate_schema({"version": 1, "fields": {word: {"type": "number", "default": 0}}})
    with pytest.raises(ValueError):
        validate_schema({"version": 2, "fields": {"A": {"type": "number", "default": 0}},
                         "migrations": [{"from": 1, "to": 2,
                                         "operations": [{"op": "rename", "field": "A", "to": word}]}]})
