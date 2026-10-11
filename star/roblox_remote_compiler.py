"""Deterministic, standalone JSON-to-Luau Roblox remote compiler.

Only data is accepted; handlers are registered by trusted server code at runtime.
The compiler performs no IO and has no application or third-party dependencies.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_RESERVED = frozenset("and break do else elseif end false for function if in local nil not "
                      "or repeat return then true until while continue type export const".split())
_TYPES = {"string", "number", "boolean"}
_DIRECTIONS = {"client_to_server", "server_to_client"}
_MESSAGE_FIELDS = {"name", "direction", "reliable", "arguments", "rate_limit", "reply"}
_ARGUMENT_FIELDS = {"name", "type", "min", "max", "enum"}
_MAX_INTEGER = 2**53 - 1


def _name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) or value in _RESERVED:
        raise ValueError(f"{where} must be a safe Luau identifier (1..64 characters)")
    return value


def _number(value: Any, where: str) -> int | float:
    if type(value) not in (int, float):
        raise ValueError(f"{where} must be a finite number, not a boolean")
    if isinstance(value, int) and abs(value) > _MAX_INTEGER:
        raise ValueError(f"{where} integer exceeds Luau's exact integer range")
    if not math.isfinite(value):
        raise ValueError(f"{where} must be finite")
    return value


def _utf8(value: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("strings must contain valid Unicode scalar values") from exc


def _literal(value: str | bool | int | float) -> str:
    # JSON's \\uXXXX is NOT a Luau string escape. Decimal UTF-8 byte escapes
    # preserve control characters, Unicode, quotes and following digits exactly.
    if isinstance(value, str):
        parts = []
        for byte in _utf8(value):
            if byte in (34, 92):
                parts.append("\\" + chr(byte))
            elif 32 <= byte < 127:
                parts.append(chr(byte))
            else:
                parts.append(f"\\{byte:03d}")
        return '"' + "".join(parts) + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def validate_schema(schema: Any) -> list[dict[str, Any]]:
    """Validate a JSON list and return a deep, normalized copy; fail with ValueError."""
    if isinstance(schema, str):
        try:
            schema = json.loads(schema, object_pairs_hook=_object, parse_constant=_reject_constant)
        except RecursionError as exc:
            raise ValueError("schema nesting is too deep") from exc
    if not isinstance(schema, list) or len(schema) > 64:
        raise ValueError("schema must be a JSON list of at most 64 messages")
    names: set[str] = set()
    client_methods: set[str] = set()
    output = []
    for index, raw in enumerate(schema):
        if not isinstance(raw, dict) or set(raw) - _MESSAGE_FIELDS:
            raise ValueError(f"message {index}: invalid fields")
        name = _name(raw.get("name"), "message name")
        if name in names or name == "on":
            raise ValueError(f"duplicate or reserved message name: {name}")
        names.add(name)
        direction = raw.get("direction")
        if not isinstance(direction, str) or direction not in _DIRECTIONS:
            raise ValueError(f"{name}: invalid direction")
        method = name if direction == "client_to_server" else f"on_{name}"
        if method in client_methods:
            raise ValueError(f"{name}: generated client method collision")
        client_methods.add(method)
        reliable, reply = raw.get("reliable"), raw.get("reply", False)
        if type(reliable) is not bool or type(reply) is not bool:
            raise ValueError(f"{name}: reliable and reply must be booleans")
        if reply and (direction != "client_to_server" or not reliable):
            raise ValueError(f"{name}: replies require reliable client_to_server messages")
        rate = raw.get("rate_limit", 10)
        if type(rate) is not int or not 1 <= rate <= 10000:
            raise ValueError(f"{name}: rate_limit must be an integer 1..10000")
        arguments = raw.get("arguments", [])
        if not isinstance(arguments, list) or len(arguments) > 32:
            raise ValueError(f"{name}: arguments must be a list of at most 32 entries")
        arg_names: set[str] = set()
        normalized = []
        for arg in arguments:
            if not isinstance(arg, dict) or set(arg) - _ARGUMENT_FIELDS:
                raise ValueError(f"{name}: invalid argument fields")
            arg_name = _name(arg.get("name"), "argument name")
            if arg_name in arg_names:
                raise ValueError(f"{name}: duplicate argument name")
            arg_names.add(arg_name)
            kind = arg.get("type")
            if not isinstance(kind, str) or kind not in _TYPES:
                raise ValueError(f"{name}: unsupported argument type")
            item = {"name": arg_name, "type": kind}
            for key in ("min", "max"):
                if key not in arg:
                    continue
                if kind == "boolean":
                    raise ValueError(f"{name}: ranges only support number or string")
                bound = _number(arg[key], f"{name}.{arg_name}.{key}")
                if kind == "string" and (type(bound) is not int or not 0 <= bound <= 1000000):
                    raise ValueError(f"{name}: string byte lengths must be integers 0..1000000")
                item[key] = bound
            lo, hi = item.get("min"), item.get("max")
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f"{name}: inverted range")
            if "enum" in arg:
                enum = arg["enum"]
                if not isinstance(enum, list) or not 1 <= len(enum) <= 64:
                    raise ValueError(f"{name}: enum must be a list of 1..64 values")
                values = []
                for value in enum:
                    if kind == "number":
                        _number(value, f"{name}.{arg_name}.enum")
                    elif type(value) is not (str if kind == "string" else bool):
                        raise ValueError(f"{name}: enum value does not match type")
                    measure = len(_utf8(value)) if kind == "string" else value
                    if kind == "string" and measure > 4096:
                        raise ValueError(f"{name}: enum strings exceed 4096 bytes")
                    if value in values:  # 1 and 1.0 are equal in Luau, not distinct enums.
                        raise ValueError(f"{name}: duplicate enum value")
                    if (lo is not None and measure < lo) or (hi is not None and measure > hi):
                        raise ValueError(f"{name}: enum outside range")
                    values.append(value)
                item["enum"] = values
            normalized.append(item)
        output.append({"name": name, "direction": direction, "reliable": reliable,
                       "reply": reply, "arguments": normalized, "rate_limit": rate})
    return output


def _validators(messages: list[dict[str, Any]]) -> str:
    lines = ["-- Generated pure-Luau validators. No Roblox objects or yield points.",
             "local Validators = {}"]
    for msg in messages:
        lines.extend([f'function Validators.{msg["name"]}(...)',
                      f'    if select("#", ...) ~= {len(msg["arguments"])} then return false end'])
        for index, arg in enumerate(msg["arguments"], 1):
            var, kind = f"arg{index}", arg["type"]
            # Schema names are labels only, never implementation-local variables.
            lines.extend([f"    local {var} = select({index}, ...)",
                          f'    if typeof({var}) ~= "{kind}" then return false end'])
            if kind == "number":
                lines.append(f"    if {var} ~= {var} or {var} == math.huge or {var} == -math.huge then return false end")
            for field, op in (("min", "<"), ("max", ">")):
                if field in arg:
                    term = f"#{var}" if kind == "string" else var
                    lines.append(f"    if {term} {op} {_literal(arg[field])} then return false end")
            if "enum" in arg:
                checks = " or ".join(f"{var} == {_literal(value)}" for value in arg["enum"])
                lines.append(f"    if not ({checks}) then return false end")
        lines.extend(["    return true", "end"])
    return "\n".join(lines + ["return Validators", ""])


def _limiter() -> str:
    return '''-- Generated pure-Luau per-player, per-message one-second fixed windows.
local RateLimiter = {}
RateLimiter.__index = RateLimiter
function RateLimiter.new()
    return setmetatable({ buckets = {} }, RateLimiter)
end
function RateLimiter:allow(player, name, limit, now)
    if player == nil or typeof(name) ~= "string" then return false end
    if typeof(limit) ~= "number" or limit ~= limit or limit < 1 or limit > 10000 or limit % 1 ~= 0 then return false end
    if typeof(now) ~= "number" or now ~= now or now == math.huge or now == -math.huge then return false end
    local bucket = self.buckets[player]
    if not bucket then
        bucket = {}
        self.buckets[player] = bucket
    end
    local state = bucket[name]
    if state and now < state.started then return false end
    if not state or now - state.started >= 1 then
        bucket[name] = { started = now, count = 1 }
        return true
    end
    if state.count >= limit then return false end
    state.count = state.count + 1
    return true
end
function RateLimiter:remove(player)
    self.buckets[player] = nil
end
return RateLimiter
'''


_BOUNDED_HANDLER = '''-- Only dispatch functions below can enter this private handler runner.
-- The timer is armed before the worker starts. Cooperative scheduling cannot
-- preempt a CPU-bound handler; handlers must not block the scheduler.
local pending = {}
local function invokeBounded(handler, player, ...)
    local arguments = table.pack(...)
    local finished = Instance.new("BindableEvent")
    local request = { done = false }
    local requests = pending[player]
    if not requests then
        requests = {}
        pending[player] = requests
    end
    requests[request] = true
    local worker, timer
    local function settle(result)
        if request.done then return end
        request.done = true
        request.result = result
        finished:Fire()
    end
    request.abort = function(reason)
        if request.done then return end
        -- Cancel the suspended worker before waking the caller.
        if worker and coroutine.status(worker) == "suspended" then
            pcall(task.cancel, worker)
        end
        settle(table.pack(nil, reason))
    end
    timer = task.delay(5, function()
        timer = nil
        request.abort("timeout")
    end)
    worker = task.defer(function()
        local result = table.pack(pcall(handler, player, table.unpack(arguments, 1, arguments.n)))
        if result[1] then
            settle(table.pack(table.unpack(result, 2, result.n)))
        else
            settle(table.pack(nil, "handler_error"))
        end
    end)
    if not request.done then finished.Event:Wait() end
    if timer then pcall(task.cancel, timer) end
    requests[request] = nil
    if next(requests) == nil and pending[player] == requests then
        pending[player] = nil
    end
    finished:Destroy()
    return table.unpack(request.result, 1, request.result.n)
end
local departing = setmetatable({}, { __mode = "k" })
Players.PlayerRemoving:Connect(function(player)
    departing[player] = true
    limiter:remove(player)
    local requests = pending[player]
    pending[player] = nil
    if requests then
        for request in pairs(requests) do
            request.abort("player_left")
        end
    end
end)
'''


def _class(msg: dict[str, Any]) -> str:
    return "RemoteFunction" if msg["reply"] else "RemoteEvent" if msg["reliable"] else "UnreliableRemoteEvent"


def _server(messages: list[dict[str, Any]]) -> str:
    lines = [
        "-- Generated server ModuleScript; require one copy in server code.",
        'local Players = game:GetService("Players")',
        'local ReplicatedStorage = game:GetService("ReplicatedStorage")',
        'local Validators = require(script.Parent.Validators)',
        'local RateLimiter = require(script.Parent.RateLimiter)',
        'local limiter = RateLimiter.new()',
        'local folder = ReplicatedStorage:FindFirstChild("StarRemotes")',
        'if folder then',
        '    assert(folder.ClassName == "Folder", "StarRemotes must be a Folder")',
        'else',
        '    folder = Instance.new("Folder")',
        '    folder.Name = "StarRemotes"',
        '    folder.Parent = ReplicatedStorage',
        'end',
        'local definitions = {',
    ]
    for msg in messages:
        lines.append(f'    {{ name = "{msg["name"]}", class = "{_class(msg)}" }},')
    lines.extend([
        '}',
        'local remotes, handlers, incoming = {}, {}, {}',
        '-- No yields in remote creation/binding: each instance is created or reused once.',
        'for _, definition in ipairs(definitions) do',
        '    local remote = folder:FindFirstChild(definition.name)',
        '    if remote then',
        '        assert(remote.ClassName == definition.class, "Remote class mismatch: " .. definition.name)',
        '    else',
        '        remote = Instance.new(definition.class)',
        '        remote.Name = definition.name',
        '        remote.Parent = folder',
        '    end',
        '    remotes[definition.name] = remote',
        'end',
        _BOUNDED_HANDLER.rstrip(),
    ])
    for msg in messages:
        if msg["direction"] != "client_to_server":
            continue
        name = msg["name"]
        lines.extend([
            f'incoming.{name} = true',
            f'local function dispatch_{name}(player, ...)',
            f'    if not Validators.{name}(...) then return nil, "invalid_arguments" end',
            '    if departing[player] or player.Parent ~= Players then return nil, "player_left" end',
            f'    if not limiter:allow(player, "{name}", {msg["rate_limit"]}, os.clock()) then return nil, "rate_limited" end',
            f'    local handler = handlers.{name}',
            '    if not handler then return nil, "no_handler" end',
            '    return invokeBounded(handler, player, ...)',
            'end',
        ])
        if msg["reply"]:
            lines.append(f'remotes.{name}.OnServerInvoke = dispatch_{name}')
        else:
            lines.append(f'remotes.{name}.OnServerEvent:Connect(dispatch_{name})')
    lines.extend([
        'local API = {}',
        'function API.on(name, callback)',
        '    assert(incoming[name] == true, "unknown incoming message")',
        '    assert(typeof(callback) == "function", "callback must be a function")',
        '    assert(handlers[name] == nil, "handler already registered")',
        '    handlers[name] = callback',
        'end',
    ])
    for msg in messages:
        if msg["direction"] != "server_to_client":
            continue
        name = msg["name"]
        lines.extend([
            f'function API.{name}(player, ...)',
            f'    if not Validators.{name}(...) then return nil, "invalid_arguments" end',
            '    if departing[player] or player.Parent ~= Players then return nil, "player_left" end',
            f'    if not limiter:allow(player, "{name}", {msg["rate_limit"]}, os.clock()) then return nil, "rate_limited" end',
            f'    remotes.{name}:FireClient(player, ...)',
            '    return true',
            'end',
        ])
    return "\n".join(lines + ["return API", ""])


def _type(arg: dict[str, Any]) -> str:
    if "enum" in arg and arg["type"] in {"string", "boolean"}:
        return " | ".join(_literal(value) for value in arg["enum"])
    return arg["type"]  # Luau does not have numeric singleton types.


def _client(messages: list[dict[str, Any]]) -> str:
    lines = [
        '--!strict',
        '-- Generated typed client wrapper; Validators must be a sibling ModuleScript.',
        'local ReplicatedStorage = game:GetService("ReplicatedStorage")',
        'local Validators = require(script.Parent.Validators)',
        'local candidate = ReplicatedStorage:WaitForChild("StarRemotes", 10)',
        'assert(candidate and candidate.ClassName == "Folder", "StarRemotes missing or wrong class")',
        'local folder = candidate :: Folder',
        'local function getRemote(name: string, className: string): Instance',
        '    local remote = folder:WaitForChild(name, 10)',
        '    assert(remote and remote.ClassName == className, "Remote missing or wrong class: " .. name)',
        '    return remote',
        'end',
        'export type Client = {',
    ]
    for msg in messages:
        name = msg["name"]
        signature = ", ".join(f'{arg["name"]}: {_type(arg)}' for arg in msg["arguments"])
        if msg["direction"] == "client_to_server":
            lines.append(f'    {name}: ({signature}) -> {"...any" if msg["reply"] else "()"},')
        else:
            lines.append(f'    on_{name}: (callback: ({signature}) -> ()) -> RBXScriptConnection,')
    lines.extend(['}', 'local API = {}'])
    for msg in messages:
        name = msg["name"]
        lines.append(f'local remote_{name} = getRemote("{name}", "{_class(msg)}") :: {_class(msg)}')
        if msg["direction"] == "client_to_server":
            parameters = [f'arg{index}: {_type(arg)}' for index, arg in enumerate(msg["arguments"], 1)]
            args = ", ".join([f'arg{index}' for index in range(1, len(parameters) + 1)] + ['...'])
            parameters.append('...: any')
            lines.extend([
                f'function API.{name}({", ".join(parameters)}): {"...any" if msg["reply"] else "()"}',
                f'    assert(Validators.{name}({args}), "invalid outgoing arguments")',
                (f'    return remote_{name}:InvokeServer({args})' if msg["reply"]
                 else f'    remote_{name}:FireServer({args})'),
                'end',
            ])
        else:
            parameters = ", ".join(_type(arg) for arg in msg["arguments"])
            lines.extend([
                f'function API.on_{name}(callback: ({parameters}) -> ()): RBXScriptConnection',
                '    assert(typeof(callback) == "function", "callback must be a function")',
                f'    return remote_{name}.OnClientEvent:Connect(function(...: any)',
                f'        if not Validators.{name}(...) then return end',
                '        callback(...)',
                '    end)',
                'end',
            ])
    return "\n".join(lines + ["return API :: Client", ""])


def _sample(arg: dict[str, Any]) -> str:
    if "enum" in arg:
        return _literal(arg["enum"][0])
    if arg["type"] == "boolean":
        return "true"
    if arg["type"] == "string":
        return f'string.rep("x", {arg.get("min", 0)})'
    return _literal(max(arg.get("min", -math.inf), min(0, arg.get("max", math.inf))))


def _outside(bound: int | float, toward: float) -> str:
    value = math.nextafter(bound, toward)
    return ("math.huge" if value > 0 else "-math.huge") if not math.isfinite(value) else repr(value)


def _spec(messages: list[dict[str, Any]]) -> str:
    # Dependency injection keeps the exact same spec runnable in Roblox and the
    # standalone Luau CLI. No script, game, Player or Roblox test framework here.
    lines = [
        '-- Generated pure-Luau spec: call the returned function with the two modules.',
        'return function(Validators, RateLimiter)',
        '    local limiter = RateLimiter.new()',
        '    local first, second = {}, {}',
        '    assert(limiter:allow(first, "Probe", 2, 0))',
        '    assert(limiter:allow(first, "Probe", 2, 0))',
        '    assert(not limiter:allow(first, "Probe", 2, 0.999))',
        '    assert(limiter:allow(second, "Probe", 2, 0))',
        '    assert(limiter:allow(first, "Other", 1, 0))',
        '    assert(limiter:allow(first, "Probe", 2, 1))',
        '    assert(not limiter:allow(first, "Probe", 2, 0.5))',
        '    limiter:remove(first)',
        '    assert(limiter.buckets[first] == nil)',
        '    assert(limiter.buckets[second] ~= nil)',
        '    assert(limiter:allow(first, "Probe", 2, 1))',
        '    assert(not limiter:allow(first, "Probe", 0, 1))',
        '    assert(not limiter:allow(first, "Probe", 2, 0 / 0))',
        '    assert(not limiter:allow(first, "Probe", 2, math.huge))',
    ]
    for msg in messages:
        name, args = msg["name"], msg["arguments"]
        samples = [_sample(arg) for arg in args]

        def check(values: list[str], valid: bool) -> None:
            lines.append(f'    assert({"" if valid else "not "}Validators.{name}({", ".join(values)}))')

        check(samples, True)
        check(samples + ["nil"], False)  # Including an extra nil must fail arity.
        if samples:
            check(samples[:-1], False)
        for index, arg in enumerate(args):
            bad = ["nil", "{}", '"wrong-type"' if arg["type"] != "string" else "false"]
            if arg["type"] == "number":
                bad.extend(["0 / 0", "math.huge", "-math.huge"])
            for field, toward in (("min", -math.inf), ("max", math.inf)):
                if field not in arg:
                    continue
                bound = arg[field]
                if arg["type"] == "number":
                    bad.append(_outside(bound, toward))
                elif field == "max" or bound > 0:
                    bad.append(f'string.rep("x", {bound + (1 if field == "max" else -1)})')
                if "enum" not in arg:
                    good = f'string.rep("x", {bound})' if arg["type"] == "string" else _literal(bound)
                    check(samples[:index] + [good] + samples[index + 1:], True)
            if "enum" in arg:
                for value in arg["enum"]:
                    check(samples[:index] + [_literal(value)] + samples[index + 1:], True)
                if arg["type"] == "boolean":
                    bad.extend(_literal(value) for value in (False, True) if value not in arg["enum"])
                elif arg["type"] == "string":
                    candidate = "outside_enum"
                    while candidate in arg["enum"]:
                        candidate += "_"
                    bad.append(_literal(candidate))
                else:
                    candidate_number = 0
                    while candidate_number in arg["enum"]:
                        candidate_number += 1
                    bad.append(str(candidate_number))
            for value in bad:
                check(samples[:index] + [value] + samples[index + 1:], False)
    return "\n".join(lines + ["    return true", "end", ""])


def compile_remotes(schema: Any) -> dict[str, str]:
    """Return server/client modules, two pure support modules, and a pure-Luau spec."""
    messages = validate_schema(schema)
    return {"Server.luau": _server(messages), "Client.luau": _client(messages),
            "Validators.luau": _validators(messages), "RateLimiter.luau": _limiter(),
            "Remote.spec.luau": _spec(messages)}
