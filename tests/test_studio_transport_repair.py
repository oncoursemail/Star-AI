"""Offline transport checks: no subprocess, server, provider or real profile."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, TextContent, Tool

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


def write_host_config(home, command, **extra):
    path = home / "studio" / "remote.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"target": "server", "command": command, **extra}), encoding="utf-8")
    return path


def test_profile_commands_are_isolated_immutable_and_do_not_change_environment(monkeypatch, tmp_path):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    first, second = tmp_path / "first", tmp_path / "second"
    write_host_config(first, ["first-launcher", "first-argument"])
    write_host_config(second, ["second-launcher", "second-argument"])
    frozen = studio.configured_command(first)
    assert frozen == ("first-launcher", "first-argument")
    assert studio.configured_command(second) == ("second-launcher", "second-argument")
    write_host_config(first, ["changed-launcher"])
    assert frozen == ("first-launcher", "first-argument")
    assert studio.COMMAND_ENV not in os.environ
    assert studio.configured_command(tmp_path / "missing") is None
    write_host_config(first, [])
    assert studio.configured_command(first) is None


def test_host_environment_precedence_and_invalid_environment_never_falls_back(monkeypatch, tmp_path):
    path = write_host_config(tmp_path, ["file-launcher"])
    monkeypatch.setenv(studio.COMMAND_ENV, '["environment-launcher", "argument"]')
    assert studio.configured_command(tmp_path) == ("environment-launcher", "argument")
    path.write_bytes(b"invalid file that an explicit valid environment overrides")
    assert studio.configured_command(tmp_path) == ("environment-launcher", "argument")
    write_host_config(tmp_path, ["file-launcher"])
    monkeypatch.setenv(studio.COMMAND_ENV, "fixture-secret invalid environment")
    with pytest.raises(studio.StudioTransportError) as failure:
        studio.configured_command(tmp_path)
    assert "fixture-secret" not in str(failure.value)


@pytest.mark.parametrize("raw", [
    b"", b"not JSON fixture-secret", b"[]", b"{}", b'{"command":null}',
    b'{"command":"fixture-secret"}', b'{"command":[] ,"command":["other"]}',
    b'{"command":["program","bad\\nargument"]}', b'{"command":[" "]}',
    b'{"command":["program",false]}', b'{"command":["program","bad\\u007fargument"]}',
    b'\xff', b" " * (studio.MAX_COMMAND_BYTES + 1),
])
def test_malformed_or_oversize_host_file_fails_closed_without_private_diagnostics(monkeypatch, tmp_path, raw):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    path = write_host_config(tmp_path, [])
    path.write_bytes(raw)
    with pytest.raises(studio.StudioTransportError) as failure:
        studio.configured_command(tmp_path)
    assert "fixture-secret" not in str(failure.value) and str(path) not in str(failure.value)


@pytest.mark.parametrize("command", [["x"] * 41, ["x" * 501], ["program", "x" * 501], [""]])
def test_host_argv_limits_apply_to_file_and_explicit_transport(monkeypatch, tmp_path, command):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    write_host_config(tmp_path, command)
    with pytest.raises(studio.StudioTransportError):
        studio.configured_command(tmp_path)
    with pytest.raises(studio.StudioTransportError):
        studio.launcher("host_launcher", command=command)


def test_nonregular_linked_and_unreadable_config_are_refused(monkeypatch, tmp_path):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    path = write_host_config(tmp_path, ["program"])
    other = tmp_path / "hardlink.json"
    os.link(path, other)
    with pytest.raises(studio.StudioTransportError):
        studio.configured_command(tmp_path)
    other.unlink()
    path.unlink()
    path.mkdir()
    with pytest.raises(studio.StudioTransportError):
        studio.configured_command(tmp_path)
    path.rmdir()
    write_host_config(tmp_path, ["program"])
    monkeypatch.setattr(studio.os, "open", lambda *_: (_ for _ in ()).throw(PermissionError("fixture-secret")))
    with pytest.raises(studio.StudioTransportError) as failure:
        studio.configured_command(tmp_path)
    assert "fixture-secret" not in str(failure.value)


@pytest.mark.parametrize("directory", [False, True])
def test_symlink_host_file_or_folder_is_refused(monkeypatch, tmp_path, directory):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    source = write_host_config(tmp_path / "source", ["program"])
    home = tmp_path / "linked"
    home.mkdir()
    if not directory:
        (home / "studio").mkdir()
    link = home / "studio" if directory else home / "studio" / "remote.json"
    try:
        link.symlink_to(source.parent if directory else source, target_is_directory=directory)
    except OSError:
        pytest.skip("Host cannot create a synthetic symlink")
    with pytest.raises(studio.StudioTransportError):
        studio.configured_command(home)


@pytest.mark.parametrize('home', ['relative', '.', '..'])
def test_relative_profile_root_is_refused_even_with_valid_environment(monkeypatch, home):
    monkeypatch.setenv(studio.COMMAND_ENV, '["fixture-launcher"]')
    with pytest.raises(studio.StudioTransportError):
        studio.configured_command(home)


@pytest.mark.parametrize('ancestor', [False, True])
def test_linked_profile_root_or_ancestor_is_refused(monkeypatch, tmp_path, ancestor):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    real = tmp_path / 'real'
    write_host_config(real / 'profile' if ancestor else real, ['fixture-launcher'])
    link = tmp_path / 'linked'
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(real), str(link))
    else:
        link.symlink_to(real, target_is_directory=True)
    try:
        with pytest.raises(studio.StudioTransportError):
            studio.configured_command(link / 'profile' if ancestor else link)
    finally:
        link.rmdir() if os.name == 'nt' else link.unlink()


def test_parent_replacement_during_read_is_refused(monkeypatch, tmp_path):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    profile = tmp_path / 'profile'
    write_host_config(profile, ['original-launcher'])
    original_stamp = studio._directory_stamp
    calls = 0
    def replaced(path):
        nonlocal calls
        if path == profile:
            calls += 1
            if calls == 2:
                profile.rename(tmp_path / 'old-profile')
                write_host_config(profile, ['replacement-launcher'])
        return original_stamp(path)
    monkeypatch.setattr(studio, '_directory_stamp', replaced)
    with pytest.raises(studio.StudioTransportError):
        studio.configured_command(profile)
    assert calls == 2 and (tmp_path / 'old-profile' / 'studio' / 'remote.json').exists()


def test_host_file_read_has_a_hard_byte_bound(monkeypatch, tmp_path):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)
    write_host_config(tmp_path, ['fixture-launcher'])
    original_fdopen = studio.os.fdopen
    reads = []
    class Reader:
        def __init__(self, fd, mode):self.stream = original_fdopen(fd, mode)
        def __enter__(self):self.stream.__enter__();return self
        def __exit__(self, *args):return self.stream.__exit__(*args)
        def fileno(self):return self.stream.fileno()
        def read(self, size):reads.append(size);return self.stream.read(size)
    monkeypatch.setattr(studio.os, 'fdopen', Reader)
    assert studio.configured_command(tmp_path) == ('fixture-launcher',)
    assert reads == [studio.MAX_COMMAND_BYTES + 1]


def test_explicit_host_argv_is_a_connection_snapshot_without_environment_mutation(monkeypatch, tmp_path):
    captured, _ = install_sdk(monkeypatch, tmp_path)
    write_host_config(tmp_path, ["profile-launcher", "private-fixture-argument"])
    command = studio.configured_command(tmp_path)
    write_host_config(tmp_path, ["changed-file-launcher"])
    monkeypatch.setenv(studio.COMMAND_ENV, '["later-environment-launcher"]')

    async def scenario():
        async with studio.connect(target="host_launcher", command=command):
            assert captured["params"].command == "profile-launcher"
            assert captured["params"].args == ["private-fixture-argument"]
            assert captured["params"].cwd is None
            assert studio.COMMAND_ENV not in captured["params"].env
    run(scenario())
    assert captured["initialized"] == 1 and captured["closed"] == ["session", "transport"]


def test_this_pc_ignores_host_argv_and_environment_even_when_invalid(monkeypatch, tmp_path):
    captured, parent = install_sdk(monkeypatch, tmp_path)
    monkeypatch.setenv(studio.COMMAND_ENV, "invalid fixture-secret")
    async def scenario():
        async with studio.connect(target="local_pc", command=object()):
            assert captured["params"].command == "cmd.exe"
            assert captured["params"].args == ["/d", "/c", str(parent / "mcp.bat")]
    run(scenario())


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


@pytest.mark.parametrize("item", [{"id": "exact-id", "name": None}, {"id": "exact-id"}])
def test_unnamed_studio_keeps_exact_identity_and_only_normalizes_display(item):
    assert studio.parse_studios(instances([item])) == [{"id": "exact-id", "name": "Unnamed Studio"}]


@pytest.mark.parametrize("name", [False, 7, {}, [], "bad\nname", "bad\x7f", "x" * 201])
def test_optional_display_name_does_not_relax_other_name_validation(name):
    with pytest.raises(studio.StudioTransportError, match="invalid Studio instance"):
        studio.parse_studios(instances([{"id": "exact-id", "name": name}]))


@pytest.mark.parametrize("textual,structured", [
    ([{"id": "a", "name": None}], [{"id": "a"}]),
    ([{"id": "a", "name": None}], [{"id": "a", "name": "Unnamed Studio"}]),
    ([{"id": "a"}], [{"id": "a", "name": "Unnamed Studio"}]),
    ([], [{"id": "a", "name": None}]),
    ([{"id": "a", "name": None}], []),
])
def test_raw_name_or_empty_representation_disagreement_is_not_normalized_away(textual, structured):
    reply = CallToolResult(content=[TextContent(type="text", text=json.dumps({"studios": textual}))],
                           structuredContent={"studios": structured})
    with pytest.raises(studio.StudioTransportError, match="representations disagree"):
        studio.parse_studios(reply)


def test_real_sdk_null_name_agrees_before_display_normalization():
    items = [{"id": "exact-id", "name": None}]
    reply = CallToolResult(content=[TextContent(type="text", text=json.dumps({"studios": items}))],
                           structuredContent={"studios": items})
    assert studio.parse_studios(reply) == [{"id": "exact-id", "name": "Unnamed Studio"}]


def test_textual_json_null_is_malformed_even_with_valid_structured_instances():
    reply = CallToolResult(content=[TextContent(type="text", text="null")],
                           structuredContent={"studios": [{"id": "a", "name": None}]})
    with pytest.raises(studio.StudioTransportError, match="representations disagree"):
        studio.parse_studios(reply)


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


def test_probe_rejects_missing_instance_tool_and_zero_instances(monkeypatch):
    monkeypatch.setattr(studio, "INSTANCE_SECONDS", 0.02)
    with pytest.raises(studio.StudioTransportError, match="does not expose"):
        run(studio.probe(Pages([([tool(name="other")], None)])))
    class Empty(Pages):
        async def call_tool(self, name, arguments):
            return instances([])
    with pytest.raises(studio.StudioTransportError, match="no connected Studios"):
        run(studio.probe(Empty([([tool()], None)])))


def test_delayed_attach_is_polled_on_the_same_client_and_exact_selection(monkeypatch):
    monkeypatch.setattr(studio, "INSTANCE_SECONDS", 0.2)
    monkeypatch.setattr(studio, "INSTANCE_POLL_SECONDS", 0.005)
    class Delayed(Pages):
        instance_calls = 0
        async def call_tool(self, name, arguments):
            assert name == "list_roblox_studios" and arguments == {}
            self.instance_calls += 1
            return instances([] if self.instance_calls < 3 else [{"id": "b", "name": None}])
    client = Delayed([([tool()], None)])
    selected = run(studio.probe(client, studio_id="b"))
    assert selected["selected"] == {"id": "b", "name": "Unnamed Studio"}
    assert selected["tool_count"] == 1 and client.instance_calls == 3 and client.calls == [None]
    client = Delayed([([tool()], None)])
    with pytest.raises(studio.StudioTransportError, match="no other instance"):
        run(studio.probe(client, studio_id="missing"))
    assert client.instance_calls == 3 and client.calls == [None]


def test_permanent_validated_empty_is_bounded_across_requests_and_sleeps(monkeypatch):
    monkeypatch.setattr(studio, "INSTANCE_SECONDS", 0.15)
    monkeypatch.setattr(studio, "INSTANCE_POLL_SECONDS", 0.08)
    class Empty:
        calls = 0
        async def call_tool(self, name, arguments):
            assert name == "list_roblox_studios" and arguments == {}
            self.calls += 1
            await asyncio.sleep(0.005)
            return instances([])
    async def scenario():
        client = Empty()
        before = asyncio.get_running_loop().time()
        with pytest.raises(studio.StudioNoInstancesError) as caught:
            await studio.list_studios(client, tool_count=30)
        assert 0.1 <= asyncio.get_running_loop().time() - before < 0.5
        assert caught.value.tool_count == 30 and 2 <= client.calls <= 6
    run(scenario())


@pytest.mark.parametrize("failure", [RuntimeError("private-launcher-secret"), TimeoutError("private-launcher-secret"),
    instances([], isError=True), instances([{"id": 7}]),
    instances([], structuredContent={"studios": [{"id": "a", "name": None}]})])
def test_instance_poll_never_retries_error_or_malformed_reply(failure):
    class Failed:
        calls = 0
        async def call_tool(self, name, arguments):
            self.calls += 1
            if isinstance(failure, Exception):
                raise failure
            return failure
    client = Failed()
    with pytest.raises(studio.StudioTransportError) as caught:
        run(studio.list_studios(client))
    assert client.calls == 1 and not isinstance(caught.value, studio.StudioNoInstancesError)
    assert "private-launcher-secret" not in str(caught.value)


def test_timeout_after_an_empty_reply_is_not_reported_as_no_instances(monkeypatch):
    monkeypatch.setattr(studio, "INSTANCE_SECONDS", 0.15)
    monkeypatch.setattr(studio, "INSTANCE_POLL_SECONDS", 0.005)
    class Waiting:
        calls = 0
        async def call_tool(self, name, arguments):
            self.calls += 1
            if self.calls == 1:
                return instances([])
            await asyncio.Event().wait()
    client = Waiting()
    with pytest.raises(studio.StudioTransportError, match="timed out") as caught:
        run(studio.list_studios(client))
    assert client.calls == 2 and not isinstance(caught.value, studio.StudioNoInstancesError)


@pytest.mark.parametrize("during", ["request", "empty_poll"])
def test_instance_poll_cancellation_propagates_without_another_request(monkeypatch, during):
    monkeypatch.setattr(studio, "INSTANCE_POLL_SECONDS", 1)
    async def scenario():
        entered = asyncio.Event()
        class Waiting:
            calls = 0
            async def call_tool(self, name, arguments):
                self.calls += 1
                entered.set()
                if during == "request":
                    await asyncio.Event().wait()
                return instances([])
        client = Waiting()
        task = asyncio.create_task(studio.list_studios(client))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.calls == 1
    run(scenario())


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
