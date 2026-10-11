"""Offline schema, full-file goldens and fail-closed dispatch structure checks."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from star.roblox_remote_compiler import compile_remotes, validate_schema


FIXTURES = Path(__file__).parent / "fixtures" / "remote_compiler"
SCHEMA = json.loads((FIXTURES / "protocol.json").read_text(encoding="utf-8"))
MESSAGE = {"name": "Probe", "direction": "client_to_server", "reliable": True}


def message(**changes):
    return [{**MESSAGE, **changes}]


def argument(**changes):
    return message(arguments=[{"name": "value", "type": "number", **changes}])


BAD_SCHEMAS = [
    None, {}, 1, True, (), b"[]", [None], [[]], [{}], message(extra=True),
    message(name=None), message(name=""), message(name="a" * 65), message(name="Bad-Name"),
    message(name="end"), message(name="on"), message(name="9Probe"), message(name="a\nb"),
    message(name="x); error() --"), message(direction="wrong"), message(direction=[]),
    message(direction=None), message(reliable=1), message(reliable=None), message(reply="yes"),
    message(reply=None), message(reply=True, reliable=False),
    message(reply=True, direction="server_to_client"), message(rate_limit=True),
    message(rate_limit=0), message(rate_limit=10001), message(rate_limit=1.5),
    message(rate_limit="10"), message(arguments=None), message(arguments={}),
    message(arguments=[None]), message(arguments=[{"name": "x"}]),
    argument(type=[]), argument(type=None), argument(type="table"), argument(extra=True),
    argument(name=""), argument(name="return"), argument(min=None), argument(max=None),
    argument(min=True), argument(max="1"), argument(min=5, max=4),
    argument(min=float("nan")), argument(max=float("inf")), argument(min=-float("inf")),
    argument(min=2**53), argument(max=10**1000), argument(type="boolean", min=0),
    argument(type="string", min=-1), argument(type="string", min=1.5),
    argument(type="string", max=1000001), argument(enum=None), argument(enum=[]),
    argument(enum={}), argument(enum=[True]), argument(enum=["1"]),
    argument(enum=[1, 1.0]), argument(enum=[float("nan")]), argument(enum=[float("inf")]),
    argument(enum=[2**53]), argument(enum=[{}]), argument(enum=[1] * 65),
    argument(enum=[1, 6], min=1, max=5), argument(type="string", enum=[1]),
    argument(type="boolean", enum=[0]), argument(type="boolean", enum=[True, True]),
    argument(type="string", enum=["a", "a"]), argument(type="string", enum=["é"], max=1),
    argument(type="string", enum=["\ud800"]), argument(type="string", enum=["a" * 4097]),
    message(arguments=[{"name": "x", "type": "number"}, {"name": "x", "type": "string"}]),
    message(arguments=[{"name": f"a{i}", "type": "boolean"} for i in range(33)]),
    [MESSAGE, MESSAGE],
    [{**MESSAGE, "name": f"Msg{i}"} for i in range(65)],
    [{**MESSAGE, "name": "on_Probe"}, {**MESSAGE, "direction": "server_to_client"}],
    [{**MESSAGE, "direction": "server_to_client"}, {**MESSAGE, "name": "on_Probe"}],
]


@pytest.mark.parametrize("schema", BAD_SCHEMAS)
def test_invalid_schema_fails_with_value_error(schema):
    with pytest.raises(ValueError):
        validate_schema(schema)
    with pytest.raises(ValueError):
        compile_remotes(schema)


@pytest.mark.parametrize("source", [
    "not json", "[", "[" * 2000 + "]" * 2000, '[{"name":"A","name":"B"}]',
    '[{"name":"A","direction":"client_to_server","reliable":true,"reply":false,"reply":true}]',
    '[{"name":"A","direction":"client_to_server","reliable":true,"arguments":[{"name":"x","type":"number","min":0,"min":1}]}]',
    '[NaN]', '[Infinity]', '[-Infinity]',
])
def test_json_rejects_syntax_duplicate_fields_and_nonfinite_values(source):
    with pytest.raises(ValueError):
        compile_remotes(source)


def test_defaults_and_deep_copy():
    assert validate_schema(message())[0] == {**MESSAGE, "arguments": [], "reply": False, "rate_limit": 10}
    before = copy.deepcopy(SCHEMA)
    normalized = validate_schema(SCHEMA)
    normalized[0]["arguments"][1]["enum"].append("C")
    assert SCHEMA == before


def test_json_python_and_key_order_are_equivalent():
    original = copy.deepcopy(SCHEMA)
    expected = compile_remotes(SCHEMA)
    assert compile_remotes(json.dumps(SCHEMA)) == expected
    reordered = [{key: value for key, value in reversed(list(msg.items()))} for msg in SCHEMA]
    assert compile_remotes(reordered) == expected
    assert SCHEMA == original
    assert compile_remotes(SCHEMA) == expected


@pytest.mark.parametrize("filename", ["Server.luau", "Client.luau", "Validators.luau", "RateLimiter.luau", "Remote.spec.luau"])
def test_full_file_goldens(filename):
    assert compile_remotes(SCHEMA)[filename] == (FIXTURES / filename).read_text(encoding="utf-8")


def test_empty_protocol_and_output_contract():
    output = compile_remotes([])
    assert set(output) == {"Server.luau", "Client.luau", "Validators.luau", "RateLimiter.luau", "Remote.spec.luau"}
    assert output["Validators.luau"] == (
        "-- Generated pure-Luau validators. No Roblox objects or yield points.\n"
        "local Validators = {}\nreturn Validators\n"
    )
    assert all(text.endswith("\n") and "\r" not in text for text in output.values())


def test_safe_labels_never_shadow_generated_locals():
    names = ["player", "typeof", "math", "select", "handlers", "Validators", "remote_Probe", "callback"]
    output = compile_remotes(message(arguments=[{"name": name, "type": "number"} for name in names]))
    validators = output["Validators.luau"]
    assert "function Validators.Probe(...)" in validators
    assert "local arg8 = select(8, ...)" in validators
    for name in names:
        assert f"local {name} = select(" not in validators
    assert "arg1: number, arg2: number" in output["Client.luau"]
    assert "Probe: (player: number, typeof: number" in output["Client.luau"]


def test_unicode_and_control_literals_are_luau_not_json_escapes():
    source = argument(type="string", enum=['é\x007\\"\n', '"); error(1); --'])
    validators = compile_remotes(source)["Validators.luau"]
    assert r'\195\169\0007' in validators
    assert r'\u00' not in validators
    assert r'\"' in validators and r'\010' in validators
    assert validate_schema(argument(type="string", enum=["é"], min=2, max=2))


def test_typed_client_has_enum_types_concrete_remotes_and_bounded_lookup():
    client = compile_remotes(SCHEMA)["Client.luau"]
    assert client.startswith("--!strict\n")
    assert 'item: "A" | "B"' in client
    assert '-> ...any' in client
    assert ':: RemoteFunction' in client and ':: UnreliableRemoteEvent' in client
    assert ':: RemoteEvent' in client
    assert 'WaitForChild("StarRemotes", 10)' in client
    assert 'WaitForChild(name, 10)' in client
    assert 'if not Validators.Updated(...) then return end\n        callback(...)' in client
    assert 'assert(Validators.Buy(arg1, arg2, ...)' in client
    boolean_client = compile_remotes(argument(type="boolean", enum=[True]))["Client.luau"]
    assert 'value: true' in boolean_client


def assert_guarded_dispatch(server, schema):
    """Fail closed on *any* new statement before a dispatch's dominating guards.

    This intentionally checks a small exact grammar, not substring positions.
    A guard hidden in a comment, inverted branch, extra handler call or alternate
    registration must fail. The shared runner is the only handler-call sink.
    """
    schema = validate_schema(schema)
    expected_names = {msg["name"] for msg in schema if msg["direction"] == "client_to_server"}
    bodies = dict(re.findall(r"^local function dispatch_(\w+)\(player, \.\.\.\)\n(.*?)\nend$",
                             server, re.MULTILINE | re.DOTALL))
    assert set(bodies) == expected_names
    for msg in schema:
        if msg["direction"] != "client_to_server":
            continue
        name = msg["name"]
        assert bodies[name].splitlines() == [
            f'    if not Validators.{name}(...) then return nil, "invalid_arguments" end',
            '    if departing[player] or player.Parent ~= Players then return nil, "player_left" end',
            f'    if not limiter:allow(player, "{name}", {msg["rate_limit"]}, os.clock()) then return nil, "rate_limited" end',
            f'    local handler = handlers.{name}',
            '    if not handler then return nil, "no_handler" end',
            '    return invokeBounded(handler, player, ...)',
        ]
        binding = (f'remotes.{name}.OnServerInvoke = dispatch_{name}' if msg["reply"] else
                   f'remotes.{name}.OnServerEvent:Connect(dispatch_{name})')
        assert server.count(binding) == 1
    assert server.count('return invokeBounded(handler, player, ...)') == len(expected_names)
    assert server.count('pcall(handler, player,') == 1
    assert len(re.findall(r"(?<![\w])handler\s*\(", server)) == 0
    assert len(re.findall(r"(?<![\w])invokeBounded\s*\(", server)) == len(expected_names) + 1
    assert server.count('.OnServerInvoke = ') + server.count('.OnServerEvent:Connect(') == len(expected_names)


def test_every_handler_path_is_dominated_by_validation():
    assert_guarded_dispatch(compile_remotes(SCHEMA)["Server.luau"], SCHEMA)
    empty = message(arguments=[])
    assert_guarded_dispatch(compile_remotes(empty)["Server.luau"], validate_schema(empty))


@pytest.mark.parametrize("mutation", [
    lambda s: s.replace('if not Validators.Buy', 'if Validators.Buy', 1),
    lambda s: s.replace('    if not Validators.Buy', '    -- if not Validators.Buy', 1),
    lambda s: s.replace('local function dispatch_Buy(player, ...)\n',
                        'local function dispatch_Buy(player, ...)\n    handler(player, ...)\n', 1),
    lambda s: s.replace('then return nil, "invalid_arguments" end', 'then print("invalid") end', 1),
    lambda s: s.replace('remotes.Buy.OnServerInvoke = dispatch_Buy', 'remotes.Buy.OnServerInvoke = handlers.Buy'),
    lambda s: s + '\ninvokeBounded(handlers.Buy, player)\n',
])
def test_guard_checker_detects_unsafe_mutations(mutation):
    with pytest.raises(AssertionError):
        assert_guarded_dispatch(mutation(compile_remotes(SCHEMA)["Server.luau"]), SCHEMA)


def test_server_lifecycle_timeout_and_direction_contracts():
    output = compile_remotes(SCHEMA)
    server = output["Server.luau"]
    assert 'InvokeClient' not in ''.join(output.values())
    assert 'OnClientInvoke' not in ''.join(output.values())
    assert server.index('timer = task.delay(5,') < server.index('worker = task.defer(') < server.index('finished.Event:Wait()')
    assert 'pcall(task.cancel, worker)' in server and 'pcall(task.cancel, timer)' in server
    assert 'table.unpack(result, 2, result.n)' in server
    assert 'limiter:remove(player)' in server and 'request.abort("player_left")' in server
    assert 'assert(incoming[name] == true' in server
    assert 'incoming.Updated' not in server and 'incoming.Pulse' not in server
    for name in ('Updated', 'Pulse'):
        body = server.split(f'function API.{name}(player, ...)\n')[1].split('\nend', 1)[0]
        assert body.index(f'Validators.{name}') < body.index('limiter:allow') < body.index(':FireClient')


def test_generated_spec_has_no_roblox_dependency_and_covers_each_argument():
    spec = compile_remotes(SCHEMA)["Remote.spec.luau"]
    assert 'return function(Validators, RateLimiter)' in spec
    assert 'script.' not in spec and 'game:' not in spec and ': Player' not in spec
    assert 'Validators.Buy(nil, "A")' in spec and 'Validators.Buy(1, nil)' in spec
    assert 'Validators.Ping(nil)' in spec
    assert '0 / 0' in spec and '-math.huge' in spec
    assert 'limiter:allow(second' in spec and 'limiter.buckets[first] == nil' in spec


def test_generated_spec_in_native_luau_when_available(tmp_path):
    executable = shutil.which("luau")
    if executable is None:
        pytest.skip("native Luau CLI is not installed; Python checks still execute the compiler")
    for name, content in compile_remotes(SCHEMA).items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    runner = tmp_path / 'run.luau'
    runner.write_text('local run = require("./Remote.spec")\n'
                      'assert(run(require("./Validators"), require("./RateLimiter")))\n', encoding="utf-8")
    result = subprocess.run([executable, str(runner)], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
