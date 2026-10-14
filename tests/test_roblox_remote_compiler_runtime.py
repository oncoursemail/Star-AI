"""Execute unchanged generated Lua-subset modules with service/scheduler doubles.

This optional compatibility run uses a locally installed Lua 5.4 shared library,
not Roblox or a native Luau typechecker. It needs no downloads or Python packages.
The mandatory compiler/schema/golden/guard checks live in the companion test file.
"""
import ctypes
import ctypes.util
import json
from pathlib import Path

import pytest

from star.roblox_remote_compiler import compile_remotes


FIXTURES = Path(__file__).parent / "fixtures" / "remote_compiler"
SCHEMA = json.loads((FIXTURES / "protocol.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lua():
    name = ctypes.util.find_library("lua5.4")
    if not name:
        pytest.skip("optional Lua 5.4 compatibility runtime is not installed")
    library = ctypes.CDLL(name)
    pointer = ctypes.c_void_p
    library.luaL_newstate.restype = pointer
    library.luaL_openlibs.argtypes = [pointer]
    library.luaL_loadbufferx.argtypes = [pointer, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
    library.luaL_loadbufferx.restype = ctypes.c_int
    library.lua_pcallk.argtypes = [pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, pointer]
    library.lua_pcallk.restype = ctypes.c_int
    library.lua_tolstring.argtypes = [pointer, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    library.lua_tolstring.restype = pointer
    library.lua_close.argtypes = [pointer]

    def execute(source):
        state = library.luaL_newstate()
        assert state, "could not create compatibility Lua state"
        try:
            library.luaL_openlibs(state)
            data = source.encode("utf-8")
            status = library.luaL_loadbufferx(state, data, len(data), b"generated-remotes", b"t")
            if status == 0:
                status = library.lua_pcallk(state, 0, 0, 0, 0, None)
            if status:
                length = ctypes.c_size_t()
                error = library.lua_tolstring(state, -1, ctypes.byref(length))
                pytest.fail(ctypes.string_at(error, length.value).decode("utf-8", errors="replace"))
        finally:
            library.lua_close(state)
    return execute


def module(name, content):
    # Wrap, but do not strip annotations, rewrite expressions or translate code.
    return f"\nlocal {name} = (function()\n{content}\nend)()\n"


def core(schema):
    output = compile_remotes(schema)
    return ("local typeof = type\n" + module("Validators", output["Validators.luau"])
            + module("RateLimiter", output["RateLimiter.luau"])
            + module("spec", output["Remote.spec.luau"])
            + "assert(spec(Validators, RateLimiter))\n")


def server(body, before="", immediate=False, source=None):
    output = compile_remotes(SCHEMA)
    harness = (FIXTURES / "runtime.luau").read_text(encoding="utf-8")
    return (harness + ("\nimmediateSignals = true\n" if immediate else "\n")
            + module("Validators", output["Validators.luau"])
            + module("RateLimiter", output["RateLimiter.luau"])
            + "local originalNew, lastLimiter = RateLimiter.new, nil\n"
              "RateLimiter.new = function() lastLimiter = originalNew(); return lastLimiter end\n"
              "local script = { Parent = { Validators = Validators, RateLimiter = RateLimiter } }\n"
              "local function require(value) return value end\n"
            + before + "\nlocal function loadServer()\n"
            + (source or output["Server.luau"]) + "\nend\n" + body)


@pytest.mark.parametrize("schema", [
    [], SCHEMA,
    [{"name": "Probe", "direction": "client_to_server", "reliable": True,
      "arguments": [{"name": "typeof", "type": "string", "enum": ['é\x007\\"\n', '"); error(1); --']},
                    {"name": "math", "type": "number", "min": -2.5, "max": 2.5, "enum": [0, -2.5, 2.5]},
                    {"name": "handlers", "type": "boolean", "enum": [False]}]}],
    [{"name": "Limits", "direction": "client_to_server", "reliable": True,
      "arguments": [{"name": "text", "type": "string", "min": 0, "max": 3},
                    {"name": "positive", "type": "number", "min": 0.25},
                    {"name": "negative", "type": "number", "max": -0.25}]}],
    [{"name": "Wide", "direction": "server_to_client", "reliable": True,
      "arguments": [{"name": "value", "type": "number", "min": -1.7976931348623157e308,
                     "max": 1.7976931348623157e308}]}],
])
def test_emitted_pure_specs_execute_unchanged(lua, schema):
    lua(core(schema))


def test_validators_short_circuit_before_any_metatable_operation(lua):
    output = compile_remotes(SCHEMA)
    lua("local typeof = type\n" + module("Validators", output["Validators.luau"]) + '''
local poison = setmetatable({}, { __len = function() error("length before typeof") end })
assert(not Validators.Buy(1, poison))
assert(not Validators.Look(poison))
assert(not Validators.Buy(1, "A", nil))
assert(not Validators.Ping(nil))
''')


@pytest.mark.parametrize("immediate", [False, True])
def test_actual_dispatch_rejects_bad_packets_and_preserves_reply_tuples(lua, immediate):
    lua(server('''
local API = loadServer()
local folder = ReplicatedStorage:FindFirstChild("StarRemotes")
local remote = folder:FindFirstChild("Buy")
local first, calls = player(), 0
API.on("Buy", function(who, quantity, item)
    assert(who == first and quantity >= 1 and item == "A")
    calls = calls + 1
    return false, nil, quantity
end)
local invalid = {
    table.pack(), table.pack(1), table.pack(nil, "A"), table.pack(1, nil),
    table.pack(true, "A"), table.pack(0, "A"), table.pack(6, "A"),
    table.pack(0 / 0, "A"), table.pack(math.huge, "A"), table.pack(1, "C"),
    table.pack(1, "A", nil), table.pack({}, "A"), table.pack(1, {}),
}
for _, arguments in ipairs(invalid) do
    local result = invoke(remote, first, table.unpack(arguments, 1, arguments.n)).values
    assert(result[1] == nil and result[2] == "invalid_arguments")
end
assert(calls == 0 and lastLimiter.buckets[first] == nil)
for _ = 1, 2 do
    local result = invoke(remote, first, 1, "A").values
    assert(result.n == 3 and result[1] == false and result[2] == nil and result[3] == 1)
end
assert(invoke(remote, first, 1, "A").values[2] == "rate_limited")
assert(calls == 2 and alive() == 0 and next(timers) == nil and bindableAlive == 0)
assert(created.RemoteFunction == 1 and created.RemoteEvent == 2 and created.UnreliableRemoteEvent == 2)
''', immediate=immediate))


def test_event_dispatch_and_outgoing_paths_validate_and_rate_limit(lua):
    lua(server('''
local API = loadServer()
local folder = ReplicatedStorage:FindFirstChild("StarRemotes")
local first, second, seen = player(), player(), 0
local look, ping = folder:FindFirstChild("Look"), folder:FindFirstChild("Ping")
API.on("Look", function() seen = seen + 1 end)
API.on("Ping", function() seen = seen + 10 end)
look.OnServerEvent:Fire(first, 181)
look.OnServerEvent:Fire(first, 0, nil)
ping.OnServerEvent:Fire(first, nil)
tick()
assert(seen == 0)
look.OnServerEvent:Fire(first, 0)
look.OnServerEvent:Fire(first, 1)
look.OnServerEvent:Fire(second, 1)
ping.OnServerEvent:Fire(first)
ping.OnServerEvent:Fire(first)
tick()
assert(seen == 12)
tick(1)
look.OnServerEvent:Fire(first, 0)
tick()
assert(seen == 13)
local updated, pulse = folder:FindFirstChild("Updated"), folder:FindFirstChild("Pulse")
assert(API.Updated(first, "bad") == nil and #updated.sent == 0)
assert(API.Updated(first, true, nil) == nil and #updated.sent == 0)
assert(API.Updated(first, true) and API.Updated(first, false))
assert(API.Updated(first, true) == nil and #updated.sent == 2)
assert(API.Updated(second, true) and #updated.sent == 3)
assert(API.Pulse(first, 2) == nil and #pulse.sent == 0)
assert(API.Pulse(first, 0.5) and #pulse.sent == 1)
assert(API.Pulse(first, 0.5) == nil)
assert(alive() == 0 and bindableAlive == 0)
'''))


@pytest.mark.parametrize("immediate", [False, True])
@pytest.mark.parametrize("yield_body", ['task.wait(100)', 'coroutine.yield()'])
def test_timeout_cancels_yielding_handler_and_destroys_wait_resources(lua, immediate, yield_body):
    lua(server('''
local API = loadServer()
local remote = ReplicatedStorage:FindFirstChild("StarRemotes"):FindFirstChild("Buy")
local first, completed = player(), 0
API.on("Buy", function()
    YIELD_BODY
    completed = completed + 1
    return "late"
end)
local result = invoke(remote, first, 1, "A")
assert(result.values == nil and bindableAlive == 1)
tick(4.999)
assert(result.values == nil)
tick(5)
assert(result.values[1] == nil and result.values[2] == "timeout")
assert(alive() == 0 and bindableAlive == 0 and next(timers) == nil)
tick(100)
assert(completed == 0)
'''.replace('YIELD_BODY', yield_body), immediate=immediate))


@pytest.mark.parametrize("immediate", [False, True])
def test_departure_cancels_all_pending_calls_and_cannot_recreate_buckets(lua, immediate):
    lua(server('''
local API = loadServer()
local remote = ReplicatedStorage:FindFirstChild("StarRemotes"):FindFirstChild("Buy")
local first, second, completed = player(), player(), 0
API.on("Buy", function() task.wait(100); completed = completed + 1 end)
local one = invoke(remote, first, 1, "A")
local two = invoke(remote, first, 1, "A")
local other = invoke(remote, second, 1, "A")
Players.PlayerRemoving:Fire(first)
tick()
assert(one.values[2] == "player_left" and two.values[2] == "player_left")
assert(lastLimiter.buckets[first] == nil and lastLimiter.buckets[second] ~= nil)
assert(other.values == nil)
-- PlayerRemoving can run while Parent still points at Players.
assert(first.Parent == Players)
assert(invoke(remote, first, 1, "A").values[2] == "player_left")
assert(API.Updated(first, true) == nil and lastLimiter.buckets[first] == nil)
Players.PlayerRemoving:Fire(second)
tick()
assert(other.values[2] == "player_left")
assert(next(lastLimiter.buckets) == nil and alive() == 0 and bindableAlive == 0)
tick(100)
assert(completed == 0)
''', immediate=immediate))


@pytest.mark.parametrize("immediate", [False, True])
def test_success_before_deadline_and_handler_error_are_clean(lua, immediate):
    lua(server('''
local API = loadServer()
local remote = ReplicatedStorage:FindFirstChild("StarRemotes"):FindFirstChild("Buy")
local first, calls = player(), 0
API.on("Buy", function()
    calls = calls + 1
    if calls == 2 then error("internal failure details must not cross the remote") end
    task.wait(4.999)
    return nil, "done", nil
end)
local result = invoke(remote, first, 1, "A")
tick(4.999)
assert(result.values.n == 3 and result.values[1] == nil and result.values[2] == "done" and result.values[3] == nil)
tick(5)
local failure = invoke(remote, first, 1, "A").values
assert(failure.n == 2 and failure[1] == nil and failure[2] == "handler_error")
assert(alive() == 0 and bindableAlive == 0 and next(timers) == nil)
''', immediate=immediate))


def test_registration_direction_missing_handler_and_existing_remote_reuse(lua):
    lua(server('''
local API = loadServer()
local folder = ReplicatedStorage:FindFirstChild("StarRemotes")
assert(folder:FindFirstChild("Buy") == existing)
assert(created.RemoteFunction == 1)
local first = player()
assert(invoke(existing, first, 1, "A").values[2] == "no_handler")
assert(not pcall(API.on, "Missing", function() end))
assert(not pcall(API.on, "Updated", function() end))
assert(not pcall(API.on, "Buy", false))
API.on("Buy", function() return true end)
assert(not pcall(API.on, "Buy", function() end))
assert(invoke(existing, first, 1, "A").values[1] == true)
assert(created.RemoteFunction == 1 and bindableAlive == 0)
''', before='''
local folder = Instance.new("Folder")
folder.Name, folder.Parent = "StarRemotes", ReplicatedStorage
local existing = Instance.new("RemoteFunction")
existing.Name, existing.Parent = "Buy", folder
'''))


@pytest.mark.parametrize("before", [
    'local folder = Instance.new("RemoteEvent"); folder.Name, folder.Parent = "StarRemotes", ReplicatedStorage',
    'local folder = Instance.new("Folder"); folder.Name, folder.Parent = "StarRemotes", ReplicatedStorage\n'
    'local wrong = Instance.new("RemoteEvent"); wrong.Name, wrong.Parent = "Buy", folder',
])
def test_wrong_instance_classes_fail_closed(lua, before):
    lua(server('assert(not pcall(loadServer))\nassert(bindableAlive == 0)', before=before))


def test_runtime_suite_detects_removed_validation_guard(lua):
    generated = compile_remotes(SCHEMA)["Server.luau"]
    unsafe = generated.replace('    if not Validators.Buy(...) then return nil, "invalid_arguments" end\n', '')
    body = '''
local API = loadServer()
local first, reached = player(), false
API.on("Buy", function() reached = true end)
invoke(ReplicatedStorage:FindFirstChild("StarRemotes"):FindFirstChild("Buy"), first, "bad", {})
assert(not reached, "validation bypass reached the handler")
'''
    lua(server(body))
    with pytest.raises(pytest.fail.Exception, match="validation bypass reached the handler"):
        lua(server(body, source=unsafe))


@pytest.mark.parametrize("immediate", [False, True])
def test_exact_deadline_race_has_one_settlement(lua, immediate):
    lua(server('''
local API = loadServer()
local remote = ReplicatedStorage:FindFirstChild("StarRemotes"):FindFirstChild("Buy")
local first, completed = player(), 0
API.on("Buy", function() task.wait(5); completed = completed + 1; return true end)
local result = invoke(remote, first, 1, "A")
tick(5)
assert(result.values[2] == "timeout" and completed == 0)
assert(alive() == 0 and bindableAlive == 0 and next(timers) == nil)
''', immediate=immediate))


def test_empty_reply_tuple_and_detached_player(lua):
    lua(server('''
local API = loadServer()
local remote = ReplicatedStorage:FindFirstChild("StarRemotes"):FindFirstChild("Buy")
local first, calls = player(), 0
API.on("Buy", function() calls = calls + 1 end)
assert(invoke(remote, first, 1, "A").values.n == 0)
assert(calls == 1 and bindableAlive == 0)
local detached = player()
detached.Parent = nil
assert(invoke(remote, detached, 1, "A").values[2] == "player_left")
assert(lastLimiter.buckets[detached] == nil and calls == 1)
'''))
