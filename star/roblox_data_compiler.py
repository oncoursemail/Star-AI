"""Compile declarative JSON schemas into server-side Roblox Luau data modules.

No code from a schema is executed: migrations are restricted to declarative
rename, set, and delete operations.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TYPES = {"number", "string", "boolean"}
RESERVED = {"end", "local", "function", "repeat", "until", "if", "then", "else", "true", "false", "nil"}


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value)) and value not in RESERVED


def validate_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Validate and return the original schema; raise ValueError on invalid input."""
    if not isinstance(schema, dict):
        raise ValueError("schema must be an object")
    version = schema.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("version must be a positive integer")
    fields = schema.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("fields must be a nonempty object")
    for name, field in fields.items():
        if not _identifier(name):
            raise ValueError(f"invalid field name: {name!r}")
        if (not isinstance(field, dict) or not isinstance(field.get("type"), str)
                or field["type"] not in TYPES):
            raise ValueError(f"{name}: unsupported field type")
        kind = field["type"]
        if "default" not in field:
            raise ValueError(f"{name}: missing default")
        default = field["default"]
        if kind == "number":
            if type(default) not in (int, float) or not math.isfinite(default):
                raise ValueError(f"{name}: invalid numeric default")
        elif kind == "string":
            if not isinstance(default, str):
                raise ValueError(f"{name}: invalid string default")
            try:
                default.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError(f"{name}: invalid Unicode default") from exc
        elif type(default) is not bool:
            raise ValueError(f"{name}: invalid boolean default")
        if kind == "boolean" and ("min" in field or "max" in field):
            raise ValueError(f"{name}: boolean bounds unsupported")
        for bound in ("min", "max"):
            if bound in field:
                value = field[bound]
                if kind == "number" and (type(value) not in (float, int) or not math.isfinite(value)):
                    raise ValueError(f"{name}: invalid {bound}")
                if kind == "string" and (type(value) is not int or value < 0):
                    raise ValueError(f"{name}: string {bound} must be a nonnegative length")
        if "min" in field and "max" in field and field["min"] > field["max"]:
            raise ValueError(f"{name}: min exceeds max")
        if kind != "boolean":
            size = len(default.encode("utf-8")) if kind == "string" else default
            if ("min" in field and size < field["min"]) or ("max" in field and size > field["max"]):
                raise ValueError(f"{name}: default outside bounds")
        if "leaderstats" in field and (type(field["leaderstats"]) is not bool or kind != "number"):
            raise ValueError(f"{name}: leaderstats requires a number")
    migrations = schema.get("migrations", [])
    if not isinstance(migrations, list):
        raise ValueError("migrations must be a list")
    transitions = {}
    for migration in migrations:
        if not isinstance(migration, dict):
            raise ValueError("migration must be an object")
        source = migration.get("from")
        target = migration.get("to")
        if type(source) is not int or type(target) is not int or target != source + 1 or source < 1 or target > version:
            raise ValueError("migration must advance exactly one version")
        if source in transitions:
            raise ValueError("duplicate migration transition")
        transitions[source] = migration
        operations = migration.get("operations")
        if not isinstance(operations, list):
            raise ValueError("migration operations must be an array")
        for op in operations:
            if (not isinstance(op, dict) or not isinstance(op.get("op"), str)
                    or op["op"] not in {"rename", "set", "delete"}):
                raise ValueError("unsupported migration operation")
            if not _identifier(op.get("field")):
                raise ValueError("invalid migration field")
            if op["op"] == "rename" and not _identifier(op.get("to")):
                raise ValueError("invalid migration rename target")
            if op["op"] == "set" and (
                "value" not in op or
                type(op["value"]) not in (str, bool, int, float) or
                (type(op["value"]) is float and not math.isfinite(op["value"]))
            ):
                raise ValueError("set requires a scalar finite value")
            if op["op"] == "set" and isinstance(op["value"], str):
                try:
                    op["value"].encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise ValueError("set requires valid Unicode") from exc
    if set(transitions) != set(range(1, version)):
        raise ValueError("migrations must cover every version transition")
    autosave = schema.get("autosave_seconds", 60)
    lock_timeout = schema.get("lock_timeout_seconds", 180)
    for key, value, maximum in (("autosave_seconds", autosave, 3600),
                                ("lock_timeout_seconds", lock_timeout, 86400)):
        if type(value) is not int or not 10 <= value <= maximum:
            raise ValueError(f"{key} must be an integer in [10, {maximum}]")
    # Two refresh intervals plus headroom: never accept a lock that can expire
    # during ordinary autosaves on a healthy server.
    if lock_timeout < 2 * autosave + 30:
        raise ValueError("lock_timeout_seconds must be >= 2 * autosave_seconds + 30")
    store = schema.get("store_name", "PlayerData")
    if not isinstance(store, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", store):
        raise ValueError("invalid store_name")
    return schema


def _luau(value: Any) -> str:
    if isinstance(value, str):
        # Luau does not support JSON's \uXXXX escapes. Use decimal UTF-8
        # byte escapes, as in the remote compiler; pad to three digits so
        # escaped bytes cannot absorb a following ASCII digit.
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("strings must contain valid Unicode scalar values") from exc
        chars = []
        for byte in encoded:
            if byte in (34, 92):
                chars.append("\\" + chr(byte))
            elif 32 <= byte < 127:
                chars.append(chr(byte))
            else:
                chars.append(f"\\{byte:03d}")
        return '"' + "".join(chars) + '"'
    if value is True:
        return "true"
    if value is False:
        return "false"
    return json.dumps(value, allow_nan=False)


def _field_rules(schema: dict[str, Any]) -> str:
    lines = []
    for name, field in schema["fields"].items():
        props = [f'type = "{field["type"]}"', f'default = {_luau(field["default"])}']
        for key in ("min", "max"):
            if key in field:
                props.append(f'{key} = {_luau(field[key])}')
        lines.append(f"    {name} = {{ {', '.join(props)} }},")
    return "\n".join(lines)


def _migration_rules(schema: dict[str, Any]) -> str:
    out = []
    for migration in sorted(schema.get("migrations", []), key=lambda m: m["from"]):
        operations = []
        for op in migration["operations"]:
            props = [f'op = "{op["op"]}"', f'field = {_luau(op["field"])}']
            if op["op"] == "rename":
                props.append(f'to = {_luau(op["to"])}')
            if op["op"] == "set":
                props.append(f'value = {_luau(op["value"])}')
            operations.append("            { " + ", ".join(props) + " },")
        out.append(f'    [{migration["from"]}] = {{\n' + "\n".join(operations) + "\n    },")
    return "\n".join(out)


def compile_schema(schema: dict[str, Any]) -> tuple[str, str]:
    """Return (server_module, Roblox-Studio-only smoke spec)."""
    validate_schema(schema)
    kinds = "\n".join(f"    {name}: {field['type']}," for name, field in schema["fields"].items())
    stats = "\n".join(f'    "{name}",' for name, field in schema["fields"].items() if field.get("leaderstats"))
    module = r'''--!strict
-- Generated player data module. Place in ServerScriptService.
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")
local store = DataStoreService:GetDataStore(__STORE__)
local VERSION = __VERSION__
local AUTOSAVE = __AUTOSAVE__
local LOCK_TIMEOUT = __LOCK_TIMEOUT__
local MAX_ATTEMPTS = 5
local token = HttpService:GenerateGUID(false)
local rules = {
__RULES__
}
local migrations = {
__MIGRATIONS__
}
export type PlayerData = {
__TYPES__
}
local leaderFields = {
__STATS__
}
local active: {[number]: {data: PlayerData, dirty: boolean}} = {}
local loading: {[number]: boolean} = {}
local Data = {}

local function defaults(): {[string]: any}
    local result: {[string]: any} = {}
    for key, rule in pairs(rules) do
        result[key] = rule.default
    end
    return result
end

local function validate(raw: any): (PlayerData, {string})
    local result = defaults()
    local issues: {string} = {}
    if type(raw) ~= "table" then
        table.insert(issues, "profile is not a table")
        return result :: any, issues
    end
    for key, rule in pairs(rules) do
        local value = raw[key]
        local valid = type(value) == rule.type
        if valid and rule.type == "number" then
            valid = value == value and value ~= math.huge and value ~= -math.huge
        end
        if valid and rule.min ~= nil then
            local measured = if rule.type == "string" then #value else value
            valid = measured >= rule.min
        end
        if valid and rule.max ~= nil then
            local measured = if rule.type == "string" then #value else value
            valid = measured <= rule.max
        end
        if valid then
            result[key] = value
        elseif value ~= nil then
            -- Missing keys use defaults; only present invalid values warn.
            table.insert(issues, "invalid field: " .. key)
        end
    end
    return result :: any, issues
end

local function migrate(raw: {[string]: any}, fromVersion: number): {[string]: any}
    local current = table.clone(raw)
    if fromVersion > VERSION or fromVersion < 1 then
        error("Unsupported profile version")
    end
    for step = fromVersion, VERSION - 1 do
        local ops = migrations[step]
        if ops == nil then
            error("Missing migration " .. tostring(step))
        end
        for _, op in ipairs(ops) do
            if op.op == "rename" then
                current[op.to] = current[op.field]
                current[op.field] = nil
            elseif op.op == "set" then
                current[op.field] = op.value
            elseif op.op == "delete" then
                current[op.field] = nil
            end
        end
    end
    return current
end

-- Export pure functions for a standalone Luau spec runner.
Data.validate = validate
Data.migrate = migrate

local function retry<T>(action: () -> T): (boolean, T?)
    for attempt = 1, MAX_ATTEMPTS do
        local ok, value = pcall(action)
        if ok then
            return true, value
        end
        warn("PlayerData DataStore attempt failed", attempt, value)
        if attempt < MAX_ATTEMPTS then
            task.wait(math.min(2 ^ (attempt - 1), 8))
        end
    end
    return false, nil
end

local function keyFor(userId: number): string
    return "p_" .. tostring(userId)
end

-- Unlock without saving defaults over data that failed validation or migration.
local function releaseLock(userId: number): boolean
    local succeeded, result = retry(function()
        return store:UpdateAsync(keyFor(userId), function(old)
            if type(old) ~= "table" or type(old.lock) ~= "table"
                or old.lock.token ~= token then return nil end
            local nextRecord = table.clone(old)
            nextRecord.lock = nil
            return nextRecord
        end)
    end)
    return succeeded and result ~= nil
end

local function mirror(player: Player, data: PlayerData)
    local folder = player:FindFirstChild("leaderstats")
    if folder == nil then
        folder = Instance.new("Folder")
        folder.Name = "leaderstats"
        folder.Parent = player
    end
    for _, name in ipairs(leaderFields) do
        local value = folder:FindFirstChild(name)
        if value == nil then
            value = Instance.new("NumberValue")
            value.Name = name
            value.Parent = folder
        end
        (value :: NumberValue).Value = (data :: any)[name]
    end
end

local function acquire(player: Player)
    local userId = player.UserId
    if loading[userId] or active[userId] ~= nil then return end
    loading[userId] = true
    -- A lock may be reclaimed only after expiration. Never overwrite a live lock.
    local ok, record = retry(function()
        return store:UpdateAsync(keyFor(userId), function(old)
            if type(old) == "table" and type(old.lock) == "table" then
                if old.lock.token ~= token and type(old.lock.expires) == "number"
                    and old.lock.expires > os.time() then
                    return nil
                end
            end
            local result = if type(old) == "table" then table.clone(old) else {}
            result.lock = {token = token, expires = os.time() + LOCK_TIMEOUT}
            return result
        end)
    end)
    loading[userId] = nil
    if not ok or type(record) ~= "table" or type(record.lock) ~= "table"
        or record.lock.token ~= token then
        warn("PlayerData lock unavailable", userId)
        player:Kick("Your data is still open in another server. Please rejoin.")
        return
    end
    local source = if type(record.data) == "table" then record.data else {}
    local version = if type(record.version) == "number" then record.version else 1
    local migrationOk, migrated = pcall(migrate, source, version)
    if not migrationOk then
        warn("PlayerData migration failed", userId, migrated)
        if not releaseLock(userId) then
            warn("PlayerData failed to release migration lock", userId)
        end
        player:Kick("Unable to migrate player data.")
        return
    end
    local data, issues = validate(migrated)
    for _, issue in ipairs(issues) do warn("PlayerData validation", userId, issue) end
    -- PlayerRemoving may have fired during the yielding UpdateAsync/retries.
    -- Do not put a departed player's locked profile into the autosave table.
    if player.Parent ~= Players then
        if not releaseLock(userId) then
            warn("PlayerData failed to release departed player's lock", userId)
        end
        return
    end
    active[userId] = {data = data, dirty = #issues > 0 or version ~= VERSION}
    mirror(player, data)
end

local function save(userId: number, release: boolean): boolean
    local profile = active[userId]
    if profile == nil then return true end
    local normalized, issues = validate(profile.data)
    for _, issue in ipairs(issues) do warn("PlayerData save validation", userId, issue) end
    local succeeded, result = retry(function()
        return store:UpdateAsync(keyFor(userId), function(old)
            if type(old) ~= "table" or type(old.lock) ~= "table"
                or old.lock.token ~= token then return nil end
            local updated = table.clone(old)
            updated.data = normalized
            updated.version = VERSION
            updated.lock = if release then nil else {token = token, expires = os.time() + LOCK_TIMEOUT}
            return updated
        end)
    end)
    if not succeeded or result == nil then
        warn("PlayerData save lost lock or failed", userId)
        return false
    end
    if release then active[userId] = nil else profile.dirty = false end
    return true
end

function Data.get(player: Player): PlayerData?
    local profile = active[player.UserId]
    return if profile then profile.data else nil
end

function Data.set(player: Player, field: string, value: any): boolean
    local profile = active[player.UserId]
    if profile == nil or rules[field] == nil then return false end
    local candidate: {[string]: any} = table.clone(profile.data :: any)
    candidate[field] = value
    local checked, issues = validate(candidate)
    if #issues > 0 then return false end
    profile.data = checked
    profile.dirty = true
    mirror(player, checked)
    return true
end

Players.PlayerAdded:Connect(acquire)
Players.PlayerRemoving:Connect(function(player)
    save(player.UserId, true)
end)
for _, player in ipairs(Players:GetPlayers()) do
    task.spawn(acquire, player)
end
task.spawn(function()
    while true do
        task.wait(AUTOSAVE)
        -- Snapshot keys before save yields; acquire/leave may change active.
        local ids = {}
        for userId in pairs(active) do
            table.insert(ids, userId)
        end
        for _, userId in ipairs(ids) do
            save(userId, false)
        end
    end
end)
game:BindToClose(function()
    local deadline = os.clock() + 25
    local pending = 0
    for userId in pairs(active) do
        pending += 1
        task.spawn(function()
            save(userId, true)
            pending -= 1
        end)
    end
    while pending > 0 and os.clock() < deadline do task.wait(0.1) end
end)
return Data
'''
    module = (module.replace("__STORE__", _luau(schema.get("store_name", "PlayerData")))
              .replace("__VERSION__", str(schema["version"]))
              .replace("__AUTOSAVE__", str(schema.get("autosave_seconds", 60)))
              .replace("__LOCK_TIMEOUT__", str(schema.get("lock_timeout_seconds", 180)))
              .replace("__RULES__", _field_rules(schema))
              .replace("__MIGRATIONS__", _migration_rules(schema))
              .replace("__TYPES__", kinds)
              .replace("__STATS__", stats))
    spec = '''--!strict
-- Roblox Studio-only smoke test. Requires a sibling PlayerData ModuleScript.
-- Requiring PlayerData initializes DataStore and player lifecycle listeners.
-- Not executable by a standalone Luau CLI; use a disposable Studio test place.
local module = require(script.Parent.PlayerData)
local sample = module.migrate({}, 1)
local valid, errors = module.validate(sample)
assert(type(valid) == "table")
assert(type(errors) == "table")
'''
    assertions = []
    for name, field in schema["fields"].items():
        assertions.append(f'assert(valid.{name} == {_luau(field["default"])})')
        assertions.append(f'local invalid_{name} = table.clone(valid)')
        assertions.append(f'invalid_{name}.{name} = nil')
        assertions.append(f'local restored_{name}, issues_{name} = module.validate(invalid_{name})')
        assertions.append(f'assert(restored_{name}.{name} == {_luau(field["default"])} and #issues_{name} == 0)')
        assertions.append(f'local wrong_{name} = table.clone(valid)')
        wrong = 0 if field["type"] == "string" else "invalid"
        assertions.append(f'wrong_{name}.{name} = {_luau(wrong)}')
        assertions.append(f'local fixed_{name}, reported_{name} = module.validate(wrong_{name})')
        assertions.append(f'assert(fixed_{name}.{name} == {_luau(field["default"])} and #reported_{name} > 0)')
    spec += "\n".join(assertions) + "\nprint('PlayerData Studio spec passed')\n"
    return module, spec


def compile_file(source: str | Path, output_dir: str | Path) -> tuple[Path, Path]:
    schema = json.loads(Path(source).read_text(encoding="utf-8"))
    module, spec = compile_schema(schema)
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    module_path = dest / "PlayerData.luau"
    spec_path = dest / "PlayerData.spec.luau"
    module_path.write_text(module, encoding="utf-8")
    spec_path.write_text(spec, encoding="utf-8")
    return module_path, spec_path
