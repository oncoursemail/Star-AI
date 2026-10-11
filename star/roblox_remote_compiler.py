"""Deterministic, standalone JSON-to-Luau Roblox remote compiler.

Handlers are supplied by trusted game code after compilation, never by the schema.
"""
from __future__ import annotations

import json
import re
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TYPES = {"string", "number", "boolean"}
_DIRECTIONS = {"client_to_server", "server_to_client"}
_RESERVED = {"and", "break", "do", "else", "elseif", "end", "false", "for", "function",
             "if", "in", "local", "nil", "not", "or", "repeat", "return", "then",
             "true", "until", "while", "continue", "type", "export"}


def _name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) or value in _RESERVED:
        raise ValueError(f"{where} must be a safe Luau identifier")
    return value


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    raise ValueError("unsupported literal")


def validate_schema(schema: Any) -> list[dict[str, Any]]:
    """Validate and normalize a JSON list without modifying caller data."""
    if isinstance(schema, str):
        schema = json.loads(schema)
    if not isinstance(schema, list):
        raise ValueError("schema must be a JSON list")
    seen: set[str] = set()
    output = []
    for index, raw in enumerate(schema):
        if not isinstance(raw, dict) or set(raw) - {"name", "direction", "reliable", "arguments", "rate_limit", "reply"}:
            raise ValueError(f"message {index}: invalid fields")
        name = _name(raw.get("name"), "message name")
        if name in seen:
            raise ValueError(f"duplicate message: {name}")
        seen.add(name)
        direction = raw.get("direction")
        if direction not in _DIRECTIONS:
            raise ValueError(f"{name}: invalid direction")
        reliable = raw.get("reliable")
        reply = raw.get("reply", False)
        if type(reliable) is not bool or type(reply) is not bool:
            raise ValueError(f"{name}: reliable and reply must be booleans")
        if reply and (direction != "client_to_server" or not reliable):
            raise ValueError(f"{name}: replies require reliable client_to_server messages")
        arguments = raw.get("arguments", [])
        if not isinstance(arguments, list):
            raise ValueError(f"{name}: arguments must be a list")
        arg_names: set[str] = set()
        normalized = []
        for arg in arguments:
            if not isinstance(arg, dict) or set(arg) - {"name", "type", "min", "max", "enum"}:
                raise ValueError(f"{name}: invalid argument fields")
            arg_name = _name(arg.get("name"), "argument name")
            if arg_name in arg_names or arg_name == "player":
                raise ValueError(f"{name}: duplicate or reserved argument")
            arg_names.add(arg_name)
            kind = arg.get("type")
            if kind not in _TYPES:
                raise ValueError(f"{name}: unsupported argument type")
            lo, hi = arg.get("min"), arg.get("max")
            if lo is not None or hi is not None:
                if kind not in {"number", "string"}:
                    raise ValueError(f"{name}: range only supports number or string")
                if any(type(x) not in (int, float) or x != x or abs(x) == float("inf")
                       for x in (lo, hi) if x is not None):
                    raise ValueError(f"{name}: invalid range")
                if kind == "string" and any(x is not None and (type(x) is not int or x < 0)
                                            for x in (lo, hi)):
                    raise ValueError(f"{name}: string lengths must be nonnegative integers")
                if lo is not None and hi is not None and lo > hi:
                    raise ValueError(f"{name}: inverted range")
            enum = arg.get("enum")
            if enum is not None:
                if not isinstance(enum, list) or not enum or any(
                    (type(v) is not (str if kind == "string" else bool if kind == "boolean" else float)
                     and not (kind == "number" and type(v) is int))
                    for v in enum
                ) or len({(type(v), v) for v in enum}) != len(enum):
                    raise ValueError(f"{name}: invalid enum")
                if any(lo is not None and (len(v) if kind == "string" else v) < lo or
                       hi is not None and (len(v) if kind == "string" else v) > hi for v in enum):
                    raise ValueError(f"{name}: enum outside range")
            normalized.append(dict(arg))
        rate = raw.get("rate_limit", 10)
        if type(rate) is not int or not 1 <= rate <= 10000:
            raise ValueError(f"{name}: rate_limit must be an integer 1..10000")
        output.append({"name": name, "direction": direction, "reliable": reliable,
                       "reply": reply, "arguments": normalized, "rate_limit": rate})
    return output


def _predicate(arg: dict[str, Any], variable: str) -> str:
    kind = arg["type"]
    checks = [f'typeof({variable}) == "{kind}"']
    lo, hi = arg.get("min"), arg.get("max")
    if kind == "number":
        checks.append(f"{variable} == {variable}")
        checks.append(f"{variable} > -math.huge and {variable} < math.huge")
    for op, bound in ((">=", lo), ("<=", hi)):
        if bound is not None:
            term = f"#{variable}" if kind == "string" else variable
            checks.append(f"{term} {op} {_literal(bound)}")
    if "enum" in arg:
        checks.append("(" + " or ".join(f"{variable} == {_literal(v)}" for v in arg["enum"]) + ")")
    return " and ".join(checks)


def _signature(args: list[dict[str, Any]]) -> str:
    return ", ".join(f'{arg["name"]}: {arg["type"]}' for arg in args)


def _validators(messages: list[dict[str, Any]]) -> str:
    lines = ["-- Generated validators; no dependencies or yield points.", "local Validators = {}"]
    for msg in messages:
        names = [a["name"] for a in msg["arguments"]]
        lines.extend([f'function Validators.{msg["name"]}({", ".join(names)}): boolean',
                      "    return " + (" and ".join(
                          f"({_predicate(arg, arg['name'])})" for arg in msg["arguments"]
                      ) if names else "true"), "end"])
    lines.extend(["return Validators", ""])
    return "\n".join(lines)


def _limiter() -> str:
    return """-- Pure-Luau per-player fixed-window rate limiter.
local RateLimiter = {}
RateLimiter.__index = RateLimiter
function RateLimiter.new()
    return setmetatable({ buckets = {} }, RateLimiter)
end
function RateLimiter:allow(player: Player, name: string, limit: number, now: number): boolean
    local bucket = self.buckets[player]
    if not bucket then
        bucket = {}
        self.buckets[player] = bucket
    end
    local state = bucket[name]
    if not state or now - state.started >= 1 then
        bucket[name] = { started = now, count = 1 }
        return true
    end
    if state.count >= limit then return false end
    state.count += 1
    return true
end
function RateLimiter:remove(player: Player)
    self.buckets[player] = nil
end
return RateLimiter
"""


def _server(messages: list[dict[str, Any]]) -> str:
    lines = [
        "-- Generated server module. Put the four modules together in ServerScriptService.",
        'local Players = game:GetService("Players")',
        'local ReplicatedStorage = game:GetService("ReplicatedStorage")',
        'local Validators = require(script.Parent.Validators)',
        'local RateLimiter = require(script.Parent.RateLimiter)',
        'local limiter = RateLimiter.new()',
        'local folder = ReplicatedStorage:FindFirstChild("StarRemotes")',
        'if not folder then',
        '    folder = Instance.new("Folder")',
        '    folder.Name = "StarRemotes"',
        '    folder.Parent = ReplicatedStorage',
        'end',
        'local remotes = {}',
        'local handlers = {}',
    ]
    for msg in messages:
        name = msg["name"]
        cls = "RemoteFunction" if msg["reply"] else "RemoteEvent" if msg["reliable"] else "UnreliableRemoteEvent"
        lines.extend([
            f'local remote_{name} = folder:FindFirstChild("{name}")',
            f'if remote_{name} then',
            f'    assert(remote_{name}:IsA("{cls}"), "Remote class mismatch: {name}")',
            "else",
            f'    remote_{name} = Instance.new("{cls}")',
            f'    remote_{name}.Name = "{name}"',
            f'    remote_{name}.Parent = folder',
            "end",
            f'remotes.{name} = remote_{name}',
        ])
    lines.append('Players.PlayerRemoving:Connect(function(player) limiter:remove(player) end)')
    for msg in messages:
        if msg["direction"] != "client_to_server":
            continue
        name = msg["name"]
        argnames = [arg["name"] for arg in msg["arguments"]]
        params = ", ".join(["player"] + argnames)
        args = ", ".join(argnames)
        lines.extend([
            f'local function dispatch_{name}({params})',
            f'    if not Validators.{name}({args}) then return nil end',
            f'    if not limiter:allow(player, "{name}", {msg["rate_limit"]}, os.clock()) then return nil end',
            f'    local handler = handlers.{name}',
            '    if not handler then return nil end',
        ])
        if msg["reply"]:
            # A detached task and timer bound the invocation even if a handler yields.
            lines.extend([
                '    local finished = Instance.new("BindableEvent")',
                '    local settled = false',
                '    local result = nil',
                '    task.spawn(function()',
                f'        local ok, value = pcall(handler, player{", " if args else ""}{args})',
                '        if not settled then',
                '            settled = true',
                '            if ok then result = value end',
                '            finished:Fire()',
                '        end',
                '    end)',
                '    task.delay(5, function()',
                '        if not settled then',
                '            settled = true',
                '            finished:Fire()',
                '        end',
                '    end)',
                '    if not settled then finished.Event:Wait() end',
                '    finished:Destroy()',
                '    return result',
            ])
        else:
            lines.append(f'    handler(player{", " if args else ""}{args})')
        lines.extend(["end"])
        event = "OnServerInvoke" if msg["reply"] else "OnServerEvent"
        connector = f'remote_{name}.{event} = dispatch_{name}' if msg["reply"] else f'remote_{name}.{event}:Connect(dispatch_{name})'
        lines.append(connector)
    lines.extend([
        'local API = {}',
        'function API.on(name: string, callback: (...any) -> ...any)',
        '    assert(type(callback) == "function", "callback must be a function")',
        '    assert(handlers[name] == nil, "handler already registered")',
        '    assert(remotes[name] ~= nil, "unknown remote")',
        '    handlers[name] = callback',
        'end',
    ])
    for msg in messages:
        if msg["direction"] == "server_to_client":
            name = msg["name"]
            params = _signature(msg["arguments"])
            args = ", ".join(arg["name"] for arg in msg["arguments"])
            lines.extend([
                f'function API.{name}(player: Player{", " if params else ""}{params})',
                f'    assert(Validators.{name}({args}), "invalid outgoing arguments")',
                f'    remotes.{name}:FireClient(player{", " if args else ""}{args})',
                'end',
            ])
    lines.extend(["return API", ""])
    return "\n".join(lines)


def _client(messages: list[dict[str, Any]]) -> str:
    lines = [
        "--!strict",
        "-- Generated typed client wrapper.",
        'local ReplicatedStorage = game:GetService("ReplicatedStorage")',
        'local folder = ReplicatedStorage:WaitForChild("StarRemotes")',
        'local API = {}',
    ]
    for msg in messages:
        name = msg["name"]
        lines.append(f'local remote_{name} = folder:WaitForChild("{name}")')
        params = _signature(msg["arguments"])
        args = ", ".join(a["name"] for a in msg["arguments"])
        if msg["direction"] == "client_to_server":
            lines.extend([
                f'function API.{name}({params}){": any" if msg["reply"] else ""}',
                (f'    return remote_{name}:InvokeServer({args})' if msg["reply"]
                 else f'    remote_{name}:FireServer({args})'),
                'end',
            ])
        else:
            lines.extend([
                f'function API.on_{name}(callback: ({", ".join(a["type"] for a in msg["arguments"])}) -> ())',
                f'    return remote_{name}.OnClientEvent:Connect(callback)',
                'end',
            ])
    lines.extend(["return API", ""])
    return "\n".join(lines)


def compile_remotes(schema: Any) -> dict[str, str]:
    """Return four deterministic Luau files: Server, Client, Validators, RateLimiter."""
    messages = validate_schema(schema)
    return {"Server.luau": _server(messages), "Client.luau": _client(messages),
            "Validators.luau": _validators(messages), "RateLimiter.luau": _limiter()}
