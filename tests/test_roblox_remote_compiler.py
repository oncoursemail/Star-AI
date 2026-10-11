"""Regression tests for the standalone Roblox remote generator."""
import pytest

from star.roblox_remote_compiler import compile_remotes, validate_schema


SCHEMA = [
    {"name": "Buy", "direction": "client_to_server", "reliable": True,
     "reply": True, "rate_limit": 2,
     "arguments": [{"name": "quantity", "type": "number", "min": 1, "max": 5},
                   {"name": "item", "type": "string", "enum": ["A", "B"]}]},
    {"name": "Look", "direction": "client_to_server", "reliable": False,
     "arguments": [{"name": "yaw", "type": "number", "min": -180, "max": 180}]},
    {"name": "Updated", "direction": "server_to_client", "reliable": True,
     "arguments": [{"name": "ready", "type": "boolean"}]},
]


@pytest.mark.parametrize("schema", [
    {}, [{"name": "Bad-Name", "direction": "client_to_server", "reliable": True}],
    [{"name": "for", "direction": "client_to_server", "reliable": True}],
    [{"name": "A", "direction": "wrong", "reliable": True}],
    [{"name": "A", "direction": "client_to_server", "reliable": "yes"}],
    [{"name": "A", "direction": "server_to_client", "reliable": True, "reply": True}],
    [{"name": "A", "direction": "client_to_server", "reliable": False, "reply": True}],
    [{"name": "A", "direction": "client_to_server", "reliable": True, "rate_limit": 0}],
    [{"name": "A", "direction": "client_to_server", "reliable": True,
      "arguments": [{"name": "x", "type": "number", "min": 4, "max": 2}]}],
    [{"name": "A", "direction": "client_to_server", "reliable": True,
      "arguments": [{"name": "x", "type": "boolean", "min": 1}]}],
    [{"name": "A", "direction": "client_to_server", "reliable": True,
      "arguments": [{"name": "x", "type": "string", "enum": []}]}],
    [{"name": "A", "direction": "client_to_server", "reliable": True,
      "arguments": [{"name": "x", "type": "number", "min": float("nan")}]}],
    [{"name": "A", "direction": "client_to_server", "reliable": True},
     {"name": "A", "direction": "client_to_server", "reliable": True}],
])
def test_bad_schemas_fail_closed(schema):
    with pytest.raises(ValueError):
        validate_schema(schema)


def test_json_input_and_no_input_mutation():
    import json
    source = json.dumps(SCHEMA)
    assert compile_remotes(source) == compile_remotes(SCHEMA)
    assert validate_schema(SCHEMA)[0]["name"] == "Buy"


def test_golden_validators():
    got = compile_remotes(SCHEMA)["Validators.luau"]
    assert got == (
        "-- Generated validators; no dependencies or yield points.\n"
        "local Validators = {}\n"
        "function Validators.Buy(quantity, item): boolean\n"
        '    return (typeof(quantity) == "number" and quantity == quantity and quantity > -math.huge and quantity < math.huge and quantity >= 1 and quantity <= 5) and (typeof(item) == "string" and (item == "A" or item == "B"))\n'
        "end\n"
        "function Validators.Look(yaw): boolean\n"
        '    return (typeof(yaw) == "number" and yaw == yaw and yaw > -math.huge and yaw < math.huge and yaw >= -180 and yaw <= 180)\n'
        "end\n"
        "function Validators.Updated(ready): boolean\n"
        '    return (typeof(ready) == "boolean")\n'
        "end\n"
        "return Validators\n"
    )


def test_golden_client_signatures_and_remote_classes():
    output = compile_remotes(SCHEMA)
    assert sorted(output) == ["Client.luau", "RateLimiter.luau", "Server.luau", "Validators.luau"]
    client = output["Client.luau"]
    assert "function API.Buy(quantity: number, item: string): any\n    return remote_Buy:InvokeServer(quantity, item)\nend" in client
    assert "function API.Look(yaw: number)\n    remote_Look:FireServer(yaw)\nend" in client
    assert "function API.on_Updated(callback: (boolean) -> ())" in client
    server = output["Server.luau"]
    for klass in ("RemoteFunction", "RemoteEvent", "UnreliableRemoteEvent"):
        assert f'Instance.new("{klass}")' in server
    assert "InvokeClient" not in "".join(output.values())
    assert server.count('Players.PlayerRemoving:Connect') == 1


def test_handlers_cannot_be_reached_before_validation():
    server = compile_remotes(SCHEMA)["Server.luau"]
    for name in ("Buy", "Look"):
        body = server.split(f"local function dispatch_{name}(", 1)[1].split("\nend", 1)[0]
        assert body.index(f"Validators.{name}(") < body.index("limiter:allow(")
        assert body.index("limiter:allow(") < body.index(f"handlers.{name}")
        assert "return nil end" in body
    assert "task.delay(5," in server
    assert "finished.Event:Wait()" in server
    assert "pcall(handler," in server
    assert "limiter:remove(player)" in server


def test_empty_schema_generates_valid_module_fixtures():
    output = compile_remotes([])
    assert output["Validators.luau"] == (
        "-- Generated validators; no dependencies or yield points.\n"
        "local Validators = {}\nreturn Validators\n"
    )
    assert "return API\n" in output["Client.luau"]
    assert "return API\n" in output["Server.luau"]
