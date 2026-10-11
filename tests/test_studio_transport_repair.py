"""Offline transport checks: no subprocess, server, provider or real profile."""
import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace

import pytest
from mcp.types import Tool

from star import studio


def run(coro):
    return asyncio.run(coro)


def tool(name="list_roblox_studios", **changes):
    value = {"name": name, "description": "Fixture tool", "inputSchema": {"type": "object"}}
    value.update(changes)
    return SimpleNamespace(model_dump=lambda **_: value)


class Pages:
    def __init__(self, pages, delay=0):
        self.pages, self.delay, self.calls = pages, delay, []

    async def list_tools(self, cursor=None):
        self.calls.append(cursor)
        await asyncio.sleep(self.delay)
        tools, next_cursor = self.pages[len(self.calls) - 1]
        return SimpleNamespace(tools=tools, nextCursor=next_cursor)


def install_sdk(monkeypatch, tmp_path, *, custom=False, mode=None):
    import mcp
    import mcp.client.stdio

    captured = {"closed": [], "initialized": 0}
    local = tmp_path / "local"
    parent = local / "Roblox"
    parent.mkdir(parents=True)
    (parent / "mcp.bat").write_text("fixture only")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(studio.sys, "platform", "win32")
    if custom:
        monkeypatch.setenv(studio.COMMAND_ENV, json.dumps(["fixture-program", "private-launcher-argument"]))
    else:
        monkeypatch.delenv(studio.COMMAND_ENV, raising=False)

    @asynccontextmanager
    async def fake_stdio(params, errlog):
        captured["params"], captured["errlog"] = params, errlog
        captured["owner_task"] = asyncio.current_task()
        if mode == "startup_failure":
            raise OSError("private-launcher-argument private-address fixture-secret")
        try:
            yield "reader", "writer"
        finally:
            assert asyncio.current_task() is captured["owner_task"]
            captured["closed"].append("transport")
            if mode == "shutdown_failure":
                raise OSError("private-launcher-argument fixture-secret")

    class FakeSession:
        def __init__(self, reader, writer, read_timeout_seconds):
            assert (reader, writer) == ("reader", "writer")
            captured["read_timeout"] = read_timeout_seconds.total_seconds()

        async def __aenter__(self):
            assert asyncio.current_task() is captured["owner_task"]
            return self

        async def __aexit__(self, *_):
            assert asyncio.current_task() is captured["owner_task"]
            captured["closed"].append("session")

        async def initialize(self):
            captured["initialized"] += 1
            if mode == "initialize_failure":
                raise RuntimeError("fixture-secret private-launcher-argument")
            if mode == "initialize_wait":
                try:
                    await asyncio.Event().wait()
                finally:
                    captured["request_cancelled"] = True
            monkeypatch.setenv(studio.COMMAND_ENV, '["changed-after-start"]')
            return SimpleNamespace(capabilities=SimpleNamespace(tools=None if mode == "no_capability" else {}))

    monkeypatch.setattr(mcp, "ClientSession", FakeSession)
    monkeypatch.setattr(mcp.client.stdio, "stdio_client", fake_stdio)
    return captured, parent


def test_local_batch_parent_cwd_and_initialize_is_not_a_health_probe(monkeypatch, tmp_path):
    captured, parent = install_sdk(monkeypatch, tmp_path)

    async def use():
        async with studio.connect() as session:
            assert session is not None

    run(use())
    params = captured["params"]
    assert params.command == "cmd.exe"
    assert params.args == ["/d", "/c", str(parent / "mcp.bat")]
    assert params.cwd == parent
    assert captured["initialized"] == 1
    assert captured["read_timeout"] == 120
    assert captured["closed"] == ["session", "transport"]
    assert captured["errlog"].closed


def test_host_command_and_safe_environment_are_snapshotted(monkeypatch, tmp_path):
    captured, _ = install_sdk(monkeypatch, tmp_path, custom=True)
    monkeypatch.setenv("PROVIDER_API_KEY", "fixture-secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "fixture-agent")
    monkeypatch.setenv("HOME", "fixture-home")
    monkeypatch.setenv("TMP", "() shell-function")

    async def use():
        async with studio.connect():
            monkeypatch.setenv("SSH_AUTH_SOCK", "changed-after-start")

    run(use())
    params = captured["params"]
    assert params.command == "fixture-program"
    assert params.args == ["private-launcher-argument"]
    assert params.cwd is None
    assert params.env["HOME"] == "fixture-home"
    assert params.env["SSH_AUTH_SOCK"] == "fixture-agent"
    assert "PROVIDER_API_KEY" not in params.env
    assert studio.COMMAND_ENV not in params.env
    assert "TMP" not in params.env


def test_explicit_local_target_bypasses_even_invalid_custom_environment(monkeypatch, tmp_path):
    captured, parent = install_sdk(monkeypatch, tmp_path)
    monkeypatch.setenv(studio.COMMAND_ENV, "invalid fixture-secret")
    assert studio.launcher("local_pc") == ("cmd.exe", ["/d", "/c", str(parent / "mcp.bat")], parent / "mcp.bat")
    async def use():
        async with studio.connect(target="local_pc"):
            pass
    run(use())
    assert captured["params"].command == "cmd.exe"


def test_explicit_host_target_requires_valid_configuration_without_local_fallback(monkeypatch, tmp_path):
    install_sdk(monkeypatch, tmp_path)
    with pytest.raises(studio.StudioTransportError, match="no local fallback"):
        studio.launcher("host_launcher")
    monkeypatch.setenv(studio.COMMAND_ENV, json.dumps(["fixture-program", "fixed-argument"]))
    assert studio.launcher("host_launcher") == ("fixture-program", ["fixed-argument"], None)
    with pytest.raises(studio.StudioTransportError, match="Unknown Studio"):
        studio.launcher("fixture-secret")


@pytest.mark.parametrize("mode", ["startup_failure", "initialize_failure", "shutdown_failure"])
@pytest.mark.parametrize("custom", [False, True])
def test_transport_errors_are_route_specific_and_do_not_echo_private_args(monkeypatch, tmp_path, mode, custom):
    install_sdk(monkeypatch, tmp_path, custom=custom, mode=mode)

    async def use():
        async with studio.connect():
            pass

    with pytest.raises(studio.StudioTransportError) as error:
        run(use())
    message = str(error.value)
    assert ("host-defined custom launcher" if custom else "local Windows launcher") in message
    assert "private-launcher-argument" not in message
    assert "fixture-secret" not in message
    assert error.value.__suppress_context__


def test_initialize_requires_declared_tools_capability(monkeypatch, tmp_path):
    captured, _ = install_sdk(monkeypatch, tmp_path, mode="no_capability")

    async def use():
        async with studio.connect():
            pytest.fail("must not expose an initialized but unsupported session")

    with pytest.raises(studio.StudioTransportError, match="without a tools capability"):
        run(use())
    assert captured["closed"] == ["session", "transport"]


def test_initialize_timeout_closes_owned_contexts(monkeypatch, tmp_path):
    captured, _ = install_sdk(monkeypatch, tmp_path, mode="initialize_wait")
    monkeypatch.setattr(studio, "INITIALIZE_SECONDS", 0.01)

    async def use():
        async with studio.connect():
            pytest.fail("unresponsive initialize must not yield")

    with pytest.raises(studio.StudioTransportError, match="initialization timed out"):
        run(use())
    assert captured["request_cancelled"]
    assert captured["closed"] == ["session", "transport"]


def test_connect_cancellation_is_not_converted_to_failure(monkeypatch, tmp_path):
    captured, _ = install_sdk(monkeypatch, tmp_path, mode="initialize_wait")

    async def use():
        async def pending():
            async with studio.connect():
                pass
        task = asyncio.create_task(pending())
        while not captured["initialized"]:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(use())
    assert captured["closed"] == ["session", "transport"]


def test_caller_failure_is_not_misreported_as_a_transport_failure(monkeypatch, tmp_path):
    install_sdk(monkeypatch, tmp_path)
    original = ValueError("caller-owned failure")

    async def use():
        async with studio.connect():
            raise original

    with pytest.raises(ValueError) as error:
        run(use())
    assert error.value is original


@pytest.mark.parametrize("bad", ["\n", "\t", "\x01", "\x7f"])
def test_custom_command_rejects_control_characters_without_echo(monkeypatch, bad):
    monkeypatch.setenv(studio.COMMAND_ENV, json.dumps(["fixture-program", "fixture-secret" + bad]))
    with pytest.raises(RuntimeError, match="JSON list") as error:
        studio.custom_launcher()
    assert "fixture-secret" not in str(error.value)


def test_tool_discovery_accepts_real_sdk_tools_and_complete_pagination():
    client = Pages([([Tool(name="first", inputSchema={"type": "object"})], "next"),
                    ([Tool(name="second", inputSchema={"type": "object"})], None)])
    assert [x["name"] for x in run(studio.list_tools(client))] == ["first", "second"]
    assert client.calls == [None, "next"]


def test_actual_studio_fixture_schemas_remain_compatible():
    from tests.studio_fake import FakeStudio
    assert len(run(studio.list_tools(FakeStudio()))) == 30


@pytest.mark.parametrize("pages,match", [
    ([([], None)], "zero tools"),
    ([([tool(), tool()], None)], "duplicate tool"),
    ([([tool()], "next"), ([tool()], None)], "duplicate tool"),
    ([([tool(name="")], None)], "invalid tool"),
    ([([tool(name="bad\nname")], None)], "invalid tool"),
    ([([tool(inputSchema=None)], None)], "invalid tool schema"),
    ([([tool(inputSchema={"type": "invented"})], None)], "invalid tool schema"),
    ([([tool(outputSchema={"required": "invalid"})], None)], "invalid tool schema"),
    ([([tool()], False)], "invalid tool-list cursor"),
    ([([tool(name="a")], "next"), ([tool(name="b")], "next")], "Repeated MCP"),
])
def test_invalid_discovery_never_returns_a_healthy_catalog(pages, match):
    with pytest.raises(studio.StudioTransportError, match=match):
        run(studio.list_tools(Pages(pages)))


def test_discovery_has_an_aggregate_deadline(monkeypatch):
    monkeypatch.setattr(studio, "DISCOVERY_SECONDS", 0.025)
    client = Pages([([tool(name=str(i))], str(i)) for i in range(20)], delay=0.01)
    with pytest.raises(studio.StudioTransportError, match="timed out"):
        run(studio.list_tools(client))
    assert 1 <= len(client.calls) <= 3


def test_discovery_count_and_aggregate_bytes_are_bounded(monkeypatch):
    monkeypatch.setattr(studio, "MAX_TOOLS", 2)
    with pytest.raises(studio.StudioTransportError, match="count exceeds"):
        run(studio.list_tools(Pages([([tool(name="a"), tool(name="b"), tool(name="c")], None)])))
    monkeypatch.setattr(studio, "MAX_DISCOVERY_BYTES", 200)
    with pytest.raises(studio.StudioTransportError, match="size bound"):
        run(studio.list_tools(Pages([([tool(name="a", description="x" * 100)], "next"),
                                    ([tool(name="b", description="x" * 100)], None)])))


@pytest.mark.parametrize("ref", ["$ref", "$dynamicRef", "$recursiveRef"])
@pytest.mark.parametrize("uri", ["https://fixture.invalid/private-schema", "file:///private-schema", "#/$defs/local"])
def test_schema_references_never_reach_validator_or_resource_resolution(monkeypatch, ref, uri):
    import jsonschema.validators
    monkeypatch.setattr(jsonschema.validators, "validator_for", lambda *_args, **_kwargs: pytest.fail("reference reached validator"))
    schema = {"type": "object", "properties": {"argument": {ref: uri}}}
    with pytest.raises(studio.StudioTransportError, match="no resource lookup"):
        run(studio.list_tools(Pages([([tool(inputSchema=schema)], None)])))


def test_schema_depth_and_node_count_are_bounded_before_validation(monkeypatch):
    deep = {"type": "string"}
    for _ in range(studio.MAX_SCHEMA_DEPTH + 1):
        deep = {"type": "object", "properties": {"child": deep}}
    with pytest.raises(studio.StudioTransportError, match="complexity bound"):
        run(studio.list_tools(Pages([([tool(inputSchema=deep)], None)])))
    wide = {"type": "object", "properties": {str(i): {"type": "string"} for i in range(studio.MAX_SCHEMA_NODES)}}
    with pytest.raises(studio.StudioTransportError, match="complexity bound"):
        run(studio.list_tools(Pages([([tool(inputSchema=wide)], None)])))


@pytest.mark.parametrize("ref", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_public_schema_validator_blocks_all_refs_before_jsonschema(monkeypatch, ref):
    import jsonschema.validators
    monkeypatch.setattr(jsonschema.validators, "validator_for", lambda *_args, **_kwargs: pytest.fail("reference reached validator"))
    for uri in ("https://fixture.invalid/schema", "file:///private-schema", "#/$defs/local"):
        with pytest.raises(studio.StudioTransportError, match="no resource lookup"):
            studio.validate_tool_schema({"type": "object", "properties": {"value": {ref: uri}}})


def test_public_schema_validator_bounds_depth_nodes_and_bytes(monkeypatch):
    import jsonschema.validators
    monkeypatch.setattr(jsonschema.validators, "validator_for", lambda *_args, **_kwargs: pytest.fail("oversized schema reached validator"))
    deep = {"type": "string"}
    for _ in range(studio.MAX_SCHEMA_DEPTH + 1):
        deep = {"properties": {"child": deep}}
    wide = {"properties": {str(i): {"type": "string"} for i in range(studio.MAX_SCHEMA_NODES)}}
    for schema in (deep, wide):
        with pytest.raises(studio.StudioTransportError, match="complexity bound"):
            studio.validate_tool_schema(schema)
    with pytest.raises(studio.StudioTransportError, match="size bound"):
        studio.validate_tool_schema({"description": "x" * studio.MAX_TOOL_BYTES})


def test_public_schema_validator_accepts_actual_input_and_output_contracts():
    studio.validate_tool_schema({"type": "object", "properties": {"studio_id": {"type": "string"}},
                                 "required": ["studio_id"], "additionalProperties": False})
    studio.validate_tool_schema({"type": "array", "items": {"type": "string"}}, input_schema=False)
    with pytest.raises(studio.StudioTransportError, match="argument object"):
        studio.validate_tool_schema({"type": "array"})
    with pytest.raises(studio.StudioTransportError, match="invalid tool schema"):
        studio.validate_tool_schema({"required": "invalid"})


def test_tool_input_schema_must_accept_object_arguments():
    with pytest.raises(studio.StudioTransportError, match="argument object"):
        run(studio.list_tools(Pages([([tool(inputSchema={"type": "array"})], None)])))


def test_discovery_cancellation_propagates():
    async def use():
        started = asyncio.Event()
        class Waiting:
            async def list_tools(self, cursor=None):
                started.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(studio.list_tools(Waiting()))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    run(use())


def test_discovery_error_details_are_private():
    class Broken:
        async def list_tools(self, cursor=None):
            raise RuntimeError("fixture-secret private-launcher-argument")
    with pytest.raises(studio.StudioTransportError) as error:
        run(studio.list_tools(Broken()))
    assert "fixture-secret" not in str(error.value)
    assert error.value.__suppress_context__


def instances(items, **changes):
    data = {"content": [{"type": "text", "text": json.dumps({"studios": items})}], "isError": False}
    data.update(changes)
    return data


@pytest.mark.parametrize("items", [[], [{"id": 7, "name": "Studio"}], [{"id": "", "name": "Studio"}],
                                  [{"id": "a\n", "name": "Studio"}], [{"id": "a", "name": 7}],
                                  [{"id": "a", "name": "one"}, {"id": "a", "name": "two"}]])
def test_invalid_instances_do_not_become_connection_success(items):
    with pytest.raises(studio.StudioTransportError):
        studio.parse_studios(instances(items))


def test_instance_error_size_and_representation_disagreement_are_visible():
    values = [{"id": "a", "name": "Studio"}]
    for bad in (instances(values, isError=True), instances(values, private="x" * 16_000),
                instances(values, structuredContent={"studios": [{"id": "b", "name": "other"}]})):
        with pytest.raises(studio.StudioTransportError):
            studio.parse_studios(bad)


def test_instance_selection_never_falls_back_to_first():
    values = [{"id": "a", "name": "one"}, {"id": "b", "name": "two"}]
    with pytest.raises(studio.StudioTransportError, match="explicitly"):
        studio.select_studio(values, "")
    with pytest.raises(studio.StudioTransportError, match="no other instance"):
        studio.select_studio(values, "missing")
    assert studio.select_studio(values, "b") == values[1]


def test_probe_only_discovers_and_never_auto_selects():
    class Client(Pages):
        async def call_tool(self, name, arguments):
            assert name == "list_roblox_studios" and arguments == {}
            return instances([{"id": "a", "name": "Studio"}])
    client = Client([([tool()], None)])
    result = run(studio.probe(client))
    assert result["status"] == "tools_and_instances_discovered"
    assert result["selected"] is None
    assert result["tool_count"] == 1
    assert "editable" not in result and "healthy" not in result


def test_probe_rejects_missing_instance_tool_and_zero_instances():
    with pytest.raises(studio.StudioTransportError, match="does not expose"):
        run(studio.probe(Pages([([tool(name="other")], None)])))
    class Empty(Pages):
        async def call_tool(self, name, arguments):
            return instances([])
    with pytest.raises(studio.StudioTransportError, match="no connected Studios"):
        run(studio.probe(Empty([([tool()], None)])))


def test_probe_host_target_is_forwarded_once_and_no_second_connection_is_opened(monkeypatch):
    class Client(Pages):
        async def call_tool(self, name, arguments):
            return instances([{"id": "a", "name": "Studio"}])
    client = Client([([tool()], None)])
    calls = []
    @asynccontextmanager
    async def fake_connect(*, target=None):
        calls.append(target)
        yield client
    monkeypatch.setattr(studio, "connect", fake_connect)
    result = run(studio.probe(target="host_launcher", studio_id="a"))
    assert calls == ["host_launcher"]
    assert result["selected"] == {"id": "a", "name": "Studio"}


def test_probe_instance_request_timeout_is_bounded(monkeypatch):
    monkeypatch.setattr(studio, "INSTANCE_SECONDS", 0.01)
    class Waiting(Pages):
        async def call_tool(self, name, arguments):
            await asyncio.Event().wait()
    with pytest.raises(studio.StudioTransportError, match="instance discovery timed out"):
        run(studio.probe(Waiting([([tool()], None)])))


@pytest.mark.parametrize("mode", ["success", "silent", "caller_failure", "sdk_failure"])
def test_actual_sdk_session_context_and_initialize_protocol_without_a_process(monkeypatch, tmp_path, mode):
    """Real ClientSession/AnyIO scopes, but injected in-memory transport only."""
    import anyio
    import mcp.client.stdio
    from mcp import types
    from mcp.shared.message import SessionMessage
    from mcp.shared.exceptions import McpError

    parent = tmp_path / "Roblox"
    parent.mkdir()
    (parent / "mcp.bat").write_text("not executed")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    monkeypatch.setattr(studio.sys, "platform", "win32")
    observed = []

    @asynccontextmanager
    async def memory_transport(params, errlog):
        server_send, client_read = anyio.create_memory_object_stream(1)
        client_send, server_read = anyio.create_memory_object_stream(1)

        async def server():
            async with server_read, server_send:
                async for message in server_read:
                    request = message.message.root
                    observed.append(request.method)
                    if mode == "silent":
                        continue
                    if request.method == "initialize":
                        result = {"protocolVersion": types.LATEST_PROTOCOL_VERSION,
                                  "capabilities": {"tools": {}}, "serverInfo": {"name": "fixture", "version": "1"}}
                    elif request.method == "tools/list":
                        result = {"tools": [{"name": "list_roblox_studios", "inputSchema": {"type": "object"}}]}
                    else:
                        continue
                    await server_send.send(SessionMessage(types.JSONRPCMessage(
                        types.JSONRPCResponse(jsonrpc="2.0", id=request.id, result=result))))

        async with anyio.create_task_group() as group:
            group.start_soon(server)
            try:
                yield client_read, client_send
            finally:
                group.cancel_scope.cancel()

    monkeypatch.setattr(mcp.client.stdio, "stdio_client", memory_transport)
    monkeypatch.setattr(studio, "INITIALIZE_SECONDS", 0.03 if mode == "silent" else 1)
    caller_failure = ValueError("caller-owned failure")

    async def use():
        async with studio.connect() as client:
            assert len(await studio.list_tools(client)) == 1
            if mode == "caller_failure":
                raise caller_failure
            if mode == "sdk_failure":
                raise McpError(types.ErrorData(code=-32000, message="fixture-secret private-launcher-argument"))
    if mode == "silent":
        with pytest.raises(studio.StudioTransportError, match="initialization timed out"):
            run(use())
    elif mode == "caller_failure":
        with pytest.raises(ValueError) as error:
            run(use())
        assert error.value is caller_failure
    elif mode == "sdk_failure":
        import traceback
        with pytest.raises(studio.StudioTransportError, match="MCP request failed") as error:
            run(use())
        public = "".join(traceback.format_exception(error.value))
        assert "fixture-secret" not in public and "private-launcher-argument" not in public
    else:
        run(use())
        assert observed[:3] == ["initialize", "notifications/initialized", "tools/list"]
