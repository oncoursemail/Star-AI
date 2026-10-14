"""Real MCP protocol over memory; guarded backends here are stand-ins, not Studio."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session

from star import local_mcp


def run(coro):
    return asyncio.run(coro)


def tool(name, properties=None, required=None):
    return {"name": name, "description": "offline contract fixture", "inputSchema": {
        "type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}


CATALOG = [tool("list_roblox_studios"),
           tool("script_read", {"studio_id": {"type": "string"}, "target_file": {"type": "string"}}, ["studio_id", "target_file"]),
           tool("execute_luau", {"studio_id": {"type": "string"}, "code": {"type": "string"}, "datamodel_type": {"type": "string"}}, ["studio_id", "code", "datamodel_type"]),
           tool("insert_asset"), tool("unknown_power_tool")]


class Guard:
    studio_id = "selected-studio"

    def __init__(self, editable=False):
        self.verdict = SimpleNamespace(editable=editable)
        self.journal = SimpleNamespace(entries=[])
        self.calls = []
        self.failure = False

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        if self.failure:
            raise RuntimeError("private-launcher-argument-provider-key")
        return types.CallToolResult(content=[types.TextContent(type="text", text="offline response")])

    async def undo(self):
        return ["host recovery invoked"]


@asynccontextmanager
async def session(guard=None, *, allow_luau=False):
    server, catalog = local_mcp.make_server(guarded=guard, discovered=CATALOG if guard else (),
        allow_luau=allow_luau, status={"target": "local_pc", "local_mcp": "memory"})
    async with create_connected_server_and_client_session(server, read_timeout_seconds=timedelta(seconds=2)) as client:
        yield client, catalog


def test_local_protocol_lists_curated_tools_and_status():
    async def scenario():
        guard = Guard()
        async with session(guard) as (client, catalog):
            listed = await client.list_tools()
            assert {t.name for t in listed.tools} == {"script_read", "list_roblox_studios", local_mcp.STATUS_TOOL}
            assert {t["name"] for t in catalog} == {"script_read", "list_roblox_studios"}
            result = await client.call_tool(local_mcp.STATUS_TOOL, {})
            assert result.structuredContent == {"target": "local_pc", "local_mcp": "memory"}
            assert not result.isError and guard.calls == []
    run(scenario())


@pytest.mark.parametrize("name", ["character_navigation", "user_keyboard_input", "user_mouse_input"])
def test_unbound_native_input_is_neither_offered_nor_dispatched(name):
    async def scenario():
        guard = Guard(editable=True)
        discovered = [*CATALOG, tool(name, {"studio_id": {"type": "string"}}, ["studio_id"])]
        server, catalog = local_mcp.make_server(guarded=guard, discovered=discovered,
            allow_luau=True, status={"target": "local_pc", "local_mcp": "memory"})
        async with create_connected_server_and_client_session(server, read_timeout_seconds=timedelta(seconds=2)) as client:
            assert name not in {entry["name"] for entry in catalog}
            assert name not in {entry.name for entry in (await client.list_tools()).tools}
            result = await client.call_tool(name, {"studio_id": guard.studio_id})
            assert result.isError and guard.calls == []
    run(scenario())


@pytest.mark.parametrize("name,args", [
    ("insert_asset", {}), ("unknown_power_tool", {}),
    ("execute_luau", {"studio_id": "selected-studio", "code": "return 1", "datamodel_type": "Edit"}),
    ("script_read", {"studio_id": "other-studio", "target_file": "Main"}),
    ("script_read", {"studio_id": "selected-studio"}),
    ("script_read", {"studio_id": "selected-studio", "target_file": "Main", "secret": "private"}),
    (local_mcp.STATUS_TOOL, {"command": "private"}),
])
def test_protocol_refuses_unknown_target_schema_and_unauthorized_writes(name, args):
    async def scenario():
        guard = Guard()
        async with session(guard) as (client, _):
            result = await client.call_tool(name, args)
            assert result.isError and guard.calls == []
            assert "private" not in str(result.model_dump())
    run(scenario())


def test_valid_read_crosses_protocol_and_preserves_result():
    async def scenario():
        guard = Guard()
        async with session(guard) as (client, _):
            args = {"studio_id": "selected-studio", "target_file": "Main"}
            result = await client.call_tool("script_read", args)
            assert not result.isError and result.content[0].text == "offline response"
            assert guard.calls == [("script_read", args)]
    run(scenario())


@pytest.mark.parametrize("enabled", [False, True])
def test_luau_requires_host_opt_in_and_edit_datamodel(enabled):
    async def scenario():
        guard = Guard(editable=True)
        async with session(guard, allow_luau=enabled) as (client, catalog):
            assert ("execute_luau" in {x["name"] for x in catalog}) is enabled
            bad = await client.call_tool("execute_luau", {"studio_id": guard.studio_id, "code": "return 1", "datamodel_type": "Client"})
            assert bad.isError and guard.calls == []
            good = await client.call_tool("execute_luau", {"studio_id": guard.studio_id, "code": "return 1", "datamodel_type": "Edit"})
            assert good.isError is not enabled
            assert len(guard.calls) == int(enabled)
    run(scenario())


def test_lost_reply_does_not_retry_or_expose_backend_exception():
    async def scenario():
        guard = Guard()
        guard.failure = True
        async with session(guard) as (client, _):
            result = await client.call_tool("script_read", {"studio_id": guard.studio_id, "target_file": "Main"})
            assert result.isError and len(guard.calls) == 1
            assert "private-launcher" not in str(result.model_dump())
            assert "no automatic retry" in result.content[0].text
    run(scenario())


def test_status_only_discovery_server_grants_no_studio_access():
    async def scenario():
        async with session() as (client, catalog):
            assert catalog == []
            assert (await client.call_tool("list_roblox_studios", {})).isError
    run(scenario())


def test_mcp_calls_are_serialized():
    class ConcurrentGuard(Guard):
        active = peak = 0

        async def call_tool(self, name, arguments=None):
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return await super().call_tool(name, arguments)

    async def scenario():
        guard = ConcurrentGuard()
        async with session(guard) as (client, _):
            args = {"studio_id": guard.studio_id, "target_file": "Main"}
            replies = await asyncio.gather(*(client.call_tool("script_read", args) for _ in range(3)))
            assert all(not result.isError for result in replies)
            assert guard.peak == 1 and len(guard.calls) == 3
    run(scenario())


def test_discovery_uses_exact_route_and_actual_local_status_protocol(monkeypatch):
    seen = []
    remote = object()
    monkeypatch.setenv(local_mcp.studio.COMMAND_ENV, '["fixture-launcher"]')

    @asynccontextmanager
    async def connect(*, target, command=None):
        seen.append((target, command))
        yield remote

    async def probe(client, *, studio_id=None):
        assert client is remote and studio_id == "s1"
        return {"status": "tools_and_instances_discovered", "tool_count": 30,
                "studios": [{"id": "s1", "name": "Baseplate"}], "selected": {"id": "s1", "name": "Baseplate"}}

    monkeypatch.setattr(local_mcp.studio, "connect", connect)
    monkeypatch.setattr(local_mcp.studio, "probe", probe)
    result = run(local_mcp.discover(target="host_launcher", studio_id="s1"))
    assert seen == [("host_launcher", ("fixture-launcher",))] and result["local_mcp"] == "memory"
    assert result["server_name"] == "STAR local MCP" and result["selected"]["id"] == "s1"


def test_discovery_failure_does_not_become_connected(monkeypatch):
    @asynccontextmanager
    async def connect(*, target):
        yield object()

    async def probe(*_, **__):
        raise local_mcp.studio.StudioTransportError("offline failure")

    monkeypatch.setattr(local_mcp.studio, "connect", connect)
    monkeypatch.setattr(local_mcp.studio, "probe", probe)
    with pytest.raises(local_mcp.studio.StudioTransportError):
        run(local_mcp.discover())


@pytest.mark.parametrize('mode', ['discover', 'factory'])
def test_per_home_command_routes_through_real_local_mcp_without_global_env_or_auto_grants(monkeypatch, tmp_path, mode):
    import json
    import os
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio
    seen, closed = [], []
    monkeypatch.delenv(local_mcp.studio.COMMAND_ENV, raising=False)

    @asynccontextmanager
    async def connect(*, target, command=None):
        assert target == 'host_launcher' and type(command) is tuple
        assert local_mcp.studio.COMMAND_ENV not in os.environ
        seen.append(command)
        fake = FakeStudio()
        try:
            yield fake
        finally:
            closed.append(command)
            assert fake.scripts == {} and not fake.history
            assert local_mcp.studio.COMMAND_ENV not in os.environ

    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio_loop, 'own_account_id', lambda *_: pytest.fail('No account read without own-place opt-in'))
    async def scenario():
        for index in range(2):
            home = tmp_path / str(index)
            path = home / 'studio' / 'remote.json'
            path.parent.mkdir(parents=True)
            # The stored target cannot override the explicit host route or grant edits.
            path.write_text(json.dumps({'target':'pc', 'command':['fixture-launcher', f'private-argument-{index}']}))
            fake_id = FakeStudio().studio_id
            if mode == 'discover':
                result = await local_mcp.discover(target='host_launcher', studio_id=fake_id, home=home)
            else:
                current = Settings(studio_target='host_launcher', studio_id=fake_id)
                async with local_mcp.connect_studio(current, home) as connection:
                    assert not connection.verdict.editable
                    assert not current.studio_edit and not current.studio_luau
                    response = await connection.client.call_tool(local_mcp.STATUS_TOOL, {})
                    assert not response.isError
                    result = response.structuredContent
            assert result['target'] == 'host_launcher' and result['selected']['id'] == fake_id
            assert result['local_mcp'] == 'memory'
            assert f'private-argument-{index}' not in json.dumps(result)
    run(scenario())
    assert seen == [('fixture-launcher', 'private-argument-0'), ('fixture-launcher', 'private-argument-1')]
    assert closed == seen


@pytest.mark.parametrize('mode', ['discover', 'factory'])
def test_local_pc_never_reads_host_file_or_environment_in_local_mcp(monkeypatch, tmp_path, mode):
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio
    fake, routes = FakeStudio(), []
    path = tmp_path / 'studio' / 'remote.json'
    path.parent.mkdir()
    path.write_text('invalid fixture-secret')
    monkeypatch.setenv(local_mcp.studio.COMMAND_ENV, 'invalid fixture-secret')
    monkeypatch.setattr(local_mcp.studio, 'configured_command', lambda *_: pytest.fail('This PC must ignore host configuration'))
    @asynccontextmanager
    async def connect(*, target, command=None):
        assert command is None
        routes.append(target)
        yield fake
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    async def scenario():
        if mode == 'discover':
            result = await local_mcp.discover(home=tmp_path)
        else:
            async with local_mcp.connect_studio(Settings(studio_id=fake.studio_id), tmp_path) as connection:
                result = connection.status
        assert result['target'] == 'local_pc' and result['local_mcp'] == 'memory'
    run(scenario())
    assert routes == ['local_pc'] and fake.scripts == {} and not fake.history


def test_configuration_home_never_moves_native_account_or_durable_ledger_home(monkeypatch, tmp_path):
    import json
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio
    persistence, configuration = tmp_path / 'persistence', tmp_path / 'configuration'
    persistence.mkdir()
    configuration.mkdir()
    for home, name in [(persistence, 'wrong-launcher'), (configuration, 'selected-launcher')]:
        path = home / 'studio' / 'remote.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'command':[name]}))
    monkeypatch.delenv(local_mcp.studio.COMMAND_ENV, raising=False)
    accounts, routes = [], []
    def account(home):accounts.append(home);return 0
    fake = FakeStudio()
    @asynccontextmanager
    async def connect(*, target, command=None):
        routes.append((target, command))
        yield fake
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio_loop, 'own_account_id', account)
    async def scenario():
        current = Settings(studio_target='host_launcher', studio_id=fake.studio_id, studio_own_places=True)
        async with local_mcp.connect_studio(current, persistence, studio_configuration_home=configuration) as connection:
            assert connection.guarded._uncertainty_store.path == persistence / 'studio-uncertainty.sqlite3'
            response = await connection.client.call_tool(local_mcp.STATUS_TOOL, {})
            assert not response.isError and response.structuredContent['selected']['id'] == fake.studio_id
        assert routes == [('host_launcher', ('selected-launcher',))] and accounts == [persistence]
        assert not (configuration / 'studio-uncertainty.sqlite3').exists()
    run(scenario())


@pytest.mark.parametrize('mode', ['discover', 'factory'])
@pytest.mark.parametrize('raw', [None, '[]', '{"command":[]}', 'invalid fixture-secret'])
def test_bad_or_absent_host_configuration_never_connects_or_falls_back(monkeypatch, tmp_path, mode, raw):
    from star.desktop_core import Settings
    monkeypatch.delenv(local_mcp.studio.COMMAND_ENV, raising=False)
    if raw is not None:
        path = tmp_path / 'studio' / 'remote.json'
        path.parent.mkdir()
        path.write_text(raw)
    @asynccontextmanager
    async def connect(**_):
        pytest.fail('Invalid host configuration cannot launch a connector')
        yield
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    async def scenario():
        with pytest.raises(local_mcp.studio.StudioTransportError) as error:
            if mode == 'discover':
                await local_mcp.discover(target='host_launcher', home=tmp_path)
            else:
                async with local_mcp.connect_studio(Settings(studio_target='host_launcher'), tmp_path):
                    pytest.fail('Invalid configuration must refuse before opening a task')
        assert 'fixture-secret' not in str(error.value)
        assert not (tmp_path / 'studio-uncertainty.sqlite3').exists()
    run(scenario())


def test_empty_remote_instances_are_explicit_and_never_selected(monkeypatch):
    monkeypatch.setattr(local_mcp.studio, "INSTANCE_SECONDS", .05)
    @asynccontextmanager
    async def connect(*, target):
        yield object()

    async def probe(*_, **__):
        error = local_mcp.studio.StudioNoInstancesError("no open Studio")
        error.tool_count = 30
        raise error

    monkeypatch.setattr(local_mcp.studio, "connect", connect)
    monkeypatch.setattr(local_mcp.studio, "probe", probe)
    result = run(local_mcp.discover())
    assert result["status"] == "tools_discovered_no_instances" and result["studios"] == []
    assert result["local_mcp"] == "memory" and result["tool_count"] == 30 and result["selected"] is None
    with pytest.raises(local_mcp.studio.StudioNoInstancesError):
        run(local_mcp.discover(studio_id="missing"))


@pytest.mark.parametrize('target', ['local_pc', 'host_launcher'])
@pytest.mark.parametrize('mode', ['discover', 'factory'])
@pytest.mark.parametrize('name_present', [False, True])
def test_real_local_protocol_accepts_delayed_unnamed_studio_without_reconnecting(monkeypatch, tmp_path, target, mode, name_present):
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio, text
    fake = FakeStudio()
    monkeypatch.setenv(local_mcp.studio.COMMAND_ENV, '["fixture-launcher"]')
    original = fake.call_tool
    attempts, routes = [], []
    async def delayed(name, arguments=None):
        if name == 'list_roblox_studios':
            assert arguments == {}
            attempts.append(name)
            item = {'id': fake.studio_id, **({'name': None} if name_present else {})}
            return text({'studios': [] if len(attempts) < 3 else [item]})
        return await original(name, arguments)
    @asynccontextmanager
    async def connect(*, target, command=None):
        routes.append(target)
        assert command == (("fixture-launcher",) if target == 'host_launcher' else None)
        yield fake
    fake.call_tool = delayed
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio, 'INSTANCE_POLL_SECONDS', .005)
    async def scenario():
        if mode == 'discover':
            result = await local_mcp.discover(target=target, studio_id=fake.studio_id)
        else:
            settings = Settings(studio_target=target, studio_id=fake.studio_id)
            async with local_mcp.connect_studio(settings, tmp_path) as connection:
                reply = await connection.client.call_tool(local_mcp.STATUS_TOOL, arguments={})
                assert not reply.isError
                result = reply.structuredContent
                assert not connection.verdict.editable and not connection.journal.entries
        assert routes == [target] and len(attempts) >= 3
        assert result['local_mcp'] == 'memory' and result['status'] == 'tools_and_instances_discovered'
        assert result['selected'] == {'id': fake.studio_id, 'name': 'Unnamed Studio'}
        assert result['tool_count'] == 30 and result['label'] == local_mcp.route_label(target)
        assert fake.scripts == {} and not fake.history
    run(scenario())


def test_factory_empty_discovery_never_opens_guard_or_selects_other_instance(monkeypatch, tmp_path):
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio, text
    fake = FakeStudio()
    calls = []
    async def empty(name, arguments=None):
        assert name == 'list_roblox_studios' and arguments == {}
        calls.append(name)
        return text({'studios': []})
    @asynccontextmanager
    async def connect(*, target):
        yield fake
    async def guard(*args, **kwargs):
        pytest.fail('Empty discovery must not open a guarded tool session')
    fake.call_tool = empty
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio, 'INSTANCE_SECONDS', .1)
    monkeypatch.setattr(local_mcp.studio, 'INSTANCE_POLL_SECONDS', .005)
    monkeypatch.setattr(local_mcp.studio_loop, 'open_guarded', guard)
    async def scenario():
        with pytest.raises(local_mcp.studio.StudioNoInstancesError) as caught:
            async with local_mcp.connect_studio(Settings(studio_id='absent'), tmp_path):
                pytest.fail('Empty discovery is not connected')
        assert caught.value.tool_count == 30 and len(calls) >= 2
        assert fake.scripts == {} and not (tmp_path / 'studio-uncertainty.sqlite3').exists()
    run(scenario())


@pytest.mark.parametrize('malformed', [False, True])
def test_factory_error_after_valid_empty_is_not_retried_or_reported_connected(monkeypatch, tmp_path, malformed):
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio, text
    fake = FakeStudio()
    attempts, routes = [], []
    async def failed(name, arguments=None):
        assert name == 'list_roblox_studios' and arguments == {}
        attempts.append(name)
        if len(attempts) == 1:
            return text({'studios': []})
        return text({'studios': [{'id': 7}]} if malformed else 'private-remote-error', not malformed)
    @asynccontextmanager
    async def connect(*, target):
        routes.append(target)
        yield fake
    async def guard(*args, **kwargs):
        pytest.fail('Unverified discovery must not open a guarded tool session')
    fake.call_tool = failed
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio, 'INSTANCE_POLL_SECONDS', .005)
    monkeypatch.setattr(local_mcp.studio_loop, 'open_guarded', guard)
    async def scenario():
        with pytest.raises(local_mcp.studio.StudioTransportError) as caught:
            async with local_mcp.connect_studio(Settings(studio_id=fake.studio_id), tmp_path):
                pytest.fail('Failed discovery is not connected')
        assert not isinstance(caught.value, local_mcp.studio.StudioNoInstancesError)
        assert 'private-remote-error' not in str(caught.value)
        assert routes == ['local_pc'] and attempts == ['list_roblox_studios'] * 2
        assert fake.scripts == {} and not fake.history
    run(scenario())


def test_factory_never_falls_back_when_exact_selected_id_is_absent(monkeypatch, tmp_path):
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio
    fake = FakeStudio()
    routes = []
    @asynccontextmanager
    async def connect(*, target):
        routes.append(target)
        yield fake
    async def guard(*args, **kwargs):
        pytest.fail('Missing selected id must not open a guarded tool session')
    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio_loop, 'open_guarded', guard)
    async def scenario():
        with pytest.raises(local_mcp.studio.StudioTransportError, match='no other instance'):
            async with local_mcp.connect_studio(Settings(studio_id='absent'), tmp_path):
                pytest.fail('Another instance must never be selected')
        assert routes == ['local_pc'] and fake.names() == ['list_roblox_studios']
        assert fake.scripts == {} and not fake.history
    run(scenario())


def test_local_proxy_reports_and_undo_share_same_guard():
    guard = Guard()
    proxy = local_mcp.LocalStudioClient(None, guard, [], {})
    assert proxy.verdict is guard.verdict and proxy.journal is guard.journal
    assert proxy.studio_id == guard.studio_id
    assert run(proxy.undo()) == ["host recovery invoked"]


def test_oversized_arguments_refused_before_backend():
    async def scenario():
        guard = Guard()
        async with session(guard) as (client, _):
            result = await client.call_tool("script_read", {"studio_id": guard.studio_id,
                "target_file": "x" * local_mcp.MAX_ARGUMENT_BYTES})
            assert result.isError and guard.calls == []
    run(scenario())


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_server_construction_rejects_remote_schema_references(reference):
    catalog = [tool("script_read", {"value": {reference: "https://invalid.example/schema"}})]
    with pytest.raises(local_mcp.studio.StudioTransportError):
        local_mcp.make_server(guarded=Guard(), discovered=catalog, status={})


def test_proxy_cancellation_cancels_real_mcp_handler():
    class SlowGuard(Guard):
        def __init__(self):
            super().__init__()
            self.started, self.cancelled = asyncio.Event(), asyncio.Event()

        async def call_tool(self, name, arguments=None):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise
            self.calls.append((name, arguments))

    async def scenario():
        guard = SlowGuard()
        server, catalog = local_mcp.make_server(guarded=guard, discovered=CATALOG, status={})
        async with create_connected_server_and_client_session(server) as client:
            proxy = local_mcp.LocalStudioClient(client, guard, catalog, {}, server._star_control)
            task = asyncio.create_task(proxy.call_tool("script_read", {"studio_id": guard.studio_id, "target_file": "Main"}))
            await asyncio.wait_for(guard.started.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert guard.cancelled.is_set() and guard.calls == []
            assert proxy.control.operations == {}
    run(scenario())


def test_proxy_cancelled_queue_never_dispatches_after_lock_releases():
    async def scenario():
        guard = Guard()
        server, catalog = local_mcp.make_server(guarded=guard, discovered=CATALOG, status={})
        control = server._star_control
        async with create_connected_server_and_client_session(server) as client:
            proxy = local_mcp.LocalStudioClient(client, guard, catalog, {}, control)
            async with control.serial:
                task = asyncio.create_task(proxy.call_tool("script_read", {"studio_id": guard.studio_id, "target_file": "Main"}))
                for _ in range(200):
                    if control.operations and next(iter(control.operations.values())).request_id is not None:
                        break
                    await asyncio.sleep(0.001)
                assert control.operations and next(iter(control.operations.values())).request_id is not None
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            status = await client.call_tool(local_mcp.STATUS_TOOL, {})
            assert not status.isError and guard.calls == [] and control.operations == {}
    run(scenario())


def test_proxy_host_undo_waits_for_active_tool():
    class BusyGuard(Guard):
        def __init__(self):
            super().__init__()
            self.started, self.release = asyncio.Event(), asyncio.Event()
            self.active = False
            self.recovered = False

        async def call_tool(self, name, arguments=None):
            self.active = True
            self.started.set()
            await self.release.wait()
            self.active = False
            return await super().call_tool(name, arguments)

        async def undo(self):
            assert not self.active
            self.recovered = True
            return ["host recovery invoked"]

    async def scenario():
        guard = BusyGuard()
        server, catalog = local_mcp.make_server(guarded=guard, discovered=CATALOG, status={})
        async with create_connected_server_and_client_session(server) as client:
            proxy = local_mcp.LocalStudioClient(client, guard, catalog, {}, server._star_control)
            task = asyncio.create_task(proxy.call_tool("script_read", {"studio_id": guard.studio_id, "target_file": "Main"}))
            await asyncio.wait_for(guard.started.wait(), timeout=2)
            recovery = asyncio.create_task(proxy.undo())
            await asyncio.sleep(0)
            assert not recovery.done() and not guard.recovered
            guard.release.set()
            assert not (await task).isError
            assert await recovery == ["host recovery invoked"]
    run(scenario())


@asynccontextmanager
async def bound_fake(monkeypatch, tmp_path, fake, *, target='local_pc', editable=True):
    """Real desktop bridge + SDK memory transport + actual guard; only Roblox is fake."""
    from star.desktop_core import Settings
    if target == 'host_launcher':
        monkeypatch.setenv(local_mcp.studio.COMMAND_ENV, '["fixture-launcher"]')
    routes=[]
    @asynccontextmanager
    async def connect(*,target,command=None):
        routes.append(target)
        assert command == (("fixture-launcher",) if target == 'host_launcher' else None)
        yield fake
    monkeypatch.setattr(local_mcp.studio,'connect',connect)
    monkeypatch.setattr(local_mcp.studio_loop,'own_account_id',lambda _:None)
    settings=Settings(studio_target=target,studio_id=fake.studio_id,studio_edit=editable,studio_luau=True)
    async with local_mcp.connect_studio(settings,tmp_path) as proxy:
        protocol=[]
        original=proxy.client.call_tool
        async def crossing(name,arguments=None,**kwargs):
            protocol.append((name,arguments))
            return await original(name,arguments=arguments,**kwargs)
        monkeypatch.setattr(proxy.client,'call_tool',crossing)
        yield proxy,protocol,routes


def native_stops(fake):
    return [args for name,args in fake.calls
            if name=='execute_luau' and args.get('code','').startswith('-- STAR:play-stop-bound ')]


@pytest.mark.parametrize('own_places', [False, True])
def test_factory_reads_account_scope_only_after_own_place_opt_in(monkeypatch, tmp_path, own_places):
    from star.desktop_core import Settings
    from tests.studio_fake import FakeStudio
    fake = FakeStudio()
    account_reads = []

    @asynccontextmanager
    async def connect(*, target):
        assert target == 'local_pc'
        yield fake

    def account(home):
        assert own_places, 'Account metadata must not be read without the host grant'
        account_reads.append(home)
        return 42

    monkeypatch.setattr(local_mcp.studio, 'connect', connect)
    monkeypatch.setattr(local_mcp.studio_loop, 'own_account_id', account)
    settings = Settings(studio_target='local_pc', studio_id=fake.studio_id,
                        studio_edit=True, studio_own_places=own_places)

    async def scenario():
        async with local_mcp.connect_studio(settings, tmp_path) as connection:
            assert connection.verdict.editable
        assert account_reads == ([tmp_path] if own_places else [])
    run(scenario())


@pytest.mark.parametrize('target',['local_pc','host_launcher'])
def test_real_mcp_build_loop_reads_writes_repairs_and_stops(monkeypatch,tmp_path,target):
    from tests.studio_fake import FakeStudio
    sl=local_mcp.studio_loop
    path='ServerScriptService.Main'
    fake=FakeStudio()
    def console(current):
        current.console=['Main:1: error injected'] if current.scripts[path]['source']=='broken' else ['STAR ok']
    fake.on_play=console
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake,target=target) as (proxy,protocol,routes):
            assert proxy.session is proxy and proxy.session is not fake
            assert proxy.tools=={tool['name'] for tool in proxy.discovered}
            assert 'insert_asset' not in proxy.tools and local_mcp.STATUS_TOOL not in proxy.tools
            repaired=[]
            def fix(errors):
                repaired.extend(errors)
                return [{'path':path,'source':"print('fixed')"}]
            report=await sl.run_build_loop(proxy,scripts=[{'path':path,'source':'broken'}],fix=fix)
            assert report['ok'] and repaired==['Main:1: error injected']
            assert fake.scripts[path]['source']=="print('fixed')" and not fake.playing and not proxy._play_pending
            assert routes==[target] and proxy.status['target']==target
            names=[name for name,_ in protocol]
            assert {'get_studio_state','search_game_tree','script_grep','screen_capture',
                    'script_read','multi_edit','start_stop_play','get_console_output'}<=set(names)
            assert names.count('multi_edit')==2 and names.count('start_stop_play')==2
            assert all(args['studio_id']==fake.studio_id for _,args in protocol)
            assert len(native_stops(fake))==2
            assert not any(name=='start_stop_play' and args['is_start'] is False for name,args in fake.calls)
            before=len(fake.calls)
            refused=await proxy.call_tool('insert_asset',{'studio_id':fake.studio_id,'assetId':'1'})
            assert refused.isError and len(fake.calls)==before
    run(scenario())


@pytest.mark.parametrize('fault',['read','write_lost_reply','console','stop'])
def test_real_mcp_build_loop_failures_never_become_clean_or_replay(monkeypatch,tmp_path,fault):
    from tests.studio_fake import FakeStudio,text
    sl=local_mcp.studio_loop
    fake=FakeStudio()
    original=fake.call_tool
    failed=[]
    async def broken(name,arguments=None):
        if (fault=='read' and name=='search_game_tree' or fault=='console' and name=='get_console_output'
                or fault=='stop' and name=='execute_luau' and arguments['code'].startswith('-- STAR:play-stop-bound ')):
            failed.append(name)
            return text('offline operation failed',True)
        answer=await original(name,arguments)
        if fault=='write_lost_reply' and name=='execute_luau' and '-- STAR:script-cas' in arguments['code']:
            failed.append(name)
            raise RuntimeError('private endpoint/key/lost payload')
        return answer
    fake.call_tool=broken
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,protocol,_):
            report=await sl.run_build_loop(proxy,scripts=[{'path':'ServerScriptService.Main','source':"print('STAR')"}])
            assert not report['ok'] and report['stopped'] and len(failed)==1
            assert 'private endpoint' not in str(report)
            if fault=='read':
                assert not fake.scripts and not any(name=='multi_edit' for name,_ in protocol)
            elif fault=='write_lost_reply':
                assert fake.scripts and not fake.playing
                assert any(entry['kind']=='script' and not entry['known'] for entry in proxy.journal.entries)
                assert sum(name=='multi_edit' for name,_ in protocol)==1
            elif fault=='console':
                step=next(step for step in report['steps'] if step['step']=='playtest first')
                assert step['errors'] is None and not step['console_ok'] and step['stop_ok']
                assert not fake.playing
            else:
                assert fake.playing and proxy._play_pending and report['cleanup']
                step=next(step for step in report['steps'] if step['step']=='playtest first')
                assert not step['stop_ok']
    run(scenario())


@pytest.mark.parametrize('during',['settle','native_request'])
def test_real_mcp_build_loop_cancellation_stops_once(monkeypatch,tmp_path,during):
    from tests.studio_fake import FakeStudio
    sl=local_mcp.studio_loop
    async def scenario():
        fake=FakeStudio()
        entered=asyncio.Event()
        original=fake.call_tool
        async def blocked(name,arguments=None):
            answer=await original(name,arguments)
            if during=='native_request' and name=='execute_luau' and '-- STAR:play-bound' in arguments['code']:
                entered.set()
                await asyncio.Event().wait()
            if name=='execute_luau' and arguments['code'].startswith('-- STAR:play-stop-bound '):
                await asyncio.sleep(0)  # cleanup must survive the cancelled handler's checkpoint
            return answer
        fake.call_tool=blocked
        async def settle():
            entered.set()
            await asyncio.Event().wait()
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,protocol,_):
            task=asyncio.create_task(sl.run_build_loop(proxy,scripts=[],settle=settle))
            # Wait for the blocking point itself, not for a wall-clock budget: a cold first run on a
            # loaded Windows runner once needed more than the former 2 s. If the loop ends without
            # reaching the blocking point, fail at once instead of waiting; 60 s is only a hang guard.
            reached=asyncio.create_task(entered.wait())
            await asyncio.wait({reached,task},timeout=60,return_when=asyncio.FIRST_COMPLETED)
            if not reached.done():reached.cancel()
            assert entered.is_set() and not task.done()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await asyncio.wait_for(task,60)
            assert not fake.playing and not proxy._play_pending and not proxy.control.operations
            assert len(native_stops(fake))==1
            starts=[entry for entry in proxy.journal.entries if entry['kind']=='playtest' and entry['start']]
            assert starts[0]['confirmed'] is (during=='settle')
            assert sum(name=='start_stop_play' for name,_ in protocol)==1
    run(scenario())


def test_host_stop_cleanup_waits_for_mcp_lock_and_has_a_deadline(monkeypatch):
    class CleanupGuard(Guard):
        _play_pending=True
        cleanup_calls=0
        async def _stop_cleanup(self):
            self.cleanup_calls+=1
            return types.CallToolResult(content=[types.TextContent(type='text',text='stopped')])
    async def scenario():
        guard=CleanupGuard()
        server,catalog=local_mcp.make_server(guarded=guard,discovered=CATALOG,status={})
        async with create_connected_server_and_client_session(server) as client:
            proxy=local_mcp.LocalStudioClient(client,guard,catalog,{},server._star_control)
            monkeypatch.setattr(local_mcp,'CALL_SECONDS',.02)
            async with proxy.control.serial:
                timed=await proxy._stop_cleanup()
                assert timed.isError and guard.cleanup_calls==0 and proxy._play_pending
            stopped=await proxy._stop_cleanup()
            assert not stopped.isError and guard.cleanup_calls==1
            assert (await client.call_tool('_stop_cleanup',{})).isError
    run(scenario())


def test_desktop_factory_keeps_lost_write_blocked_after_new_connector_id(monkeypatch,tmp_path):
    from tests.studio_fake import FakeStudio
    fake=FakeStudio()
    original=fake.call_tool
    async def lost(name,arguments=None):
        answer=await original(name,arguments)
        if name=='execute_luau' and '-- STAR:script-cas' in arguments['code']:
            raise RuntimeError('lost native reply')
        return answer
    fake.call_tool=lost
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            failed=await proxy.call_tool('multi_edit',{'studio_id':fake.studio_id,'datamodel_type':'Edit',
                'file_path':'ServerScriptService.Main','className':'Script',
                'edits':[{'old_string':'','new_string':"print('applied')"}]})
            assert failed.isError and fake.scripts['ServerScriptService.Main']['source']=="print('applied')"
        fake.call_tool=original
        fake.studio_id='new-connector-id-same-native-session'
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            assert not (await proxy.call_tool('get_studio_state',{'studio_id':fake.studio_id})).isError
            before=len(fake.calls)
            refused=await proxy.call_tool('execute_luau',{'studio_id':fake.studio_id,
                'datamodel_type':'Edit','code':"print('must not replay')"})
            assert refused.isError and len(fake.calls)==before
            assert (tmp_path/'studio-uncertainty.sqlite3').is_file()
    run(scenario())


def test_desktop_factory_corrupt_ledger_allows_reads_and_stop_but_refuses_writes(monkeypatch,tmp_path):
    from tests.studio_fake import FakeStudio
    ledger=tmp_path/'studio-uncertainty.sqlite3'
    fake=FakeStudio()
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            started=await proxy.call_tool('start_stop_play',{'studio_id':fake.studio_id,'is_start':True})
            assert not started.isError and fake.playing and proxy._play_pending
            ledger.write_bytes(b'corrupt offline ledger')
            assert not (await proxy.call_tool('get_studio_state',{'studio_id':fake.studio_id})).isError
            failed=await proxy.call_tool('execute_luau',{'studio_id':fake.studio_id,
                'datamodel_type':'Edit','code':"print('refused')"})
            assert failed.isError and fake.scripts=={} and not fake.history
            await proxy.call_tool('start_stop_play',{'studio_id':fake.studio_id,'is_start':False})
            assert not fake.playing and not proxy._play_pending and len(native_stops(fake))==1
            assert not any(name=='start_stop_play' and args['is_start'] is False for name,args in fake.calls)
            assert ledger.read_bytes()==b'corrupt offline ledger'
    run(scenario())


@pytest.mark.parametrize('during',['settle','native_request'])
def test_memory_build_loop_level_triggered_cancellation_preserves_stop(monkeypatch,tmp_path,during):
    import anyio
    from tests.studio_fake import FakeStudio
    async def scenario():
        fake=FakeStudio()
        original=fake.call_tool
        entered=anyio.Event()
        checkpoints=[]
        async def blocked(name,arguments=None):
            answer=await original(name,arguments)
            if name=='execute_luau' and arguments['code'].startswith('-- STAR:play-stop-bound '):
                await anyio.sleep(0)
                checkpoints.append('stopped')
            if during=='native_request' and name=='execute_luau' and '-- STAR:play-bound' in arguments['code']:
                entered.set()
                await anyio.sleep_forever()
            return answer
        fake.call_tool=blocked
        async def settle():
            entered.set()
            await anyio.sleep_forever()
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            async with anyio.create_task_group() as group:
                group.start_soon(lambda:local_mcp.studio_loop.run_build_loop(proxy,scripts=[],settle=settle))
                await entered.wait()
                group.cancel_scope.cancel()
            assert not fake.playing and not proxy._play_pending and not proxy.control.operations
            assert checkpoints==['stopped']
            assert len(native_stops(fake))==1
    anyio.run(scenario,backend='asyncio')


def test_local_mcp_refuses_to_stop_foreign_play_without_star_request(monkeypatch,tmp_path):
    from tests.studio_fake import FakeStudio
    fake=FakeStudio()
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            fake.playing=True  # an external playtest, not a STAR-bound launch
            result=await proxy.call_tool('start_stop_play',{'studio_id':fake.studio_id,'is_start':False})
            assert result.isError and fake.playing
            assert not any(name=='start_stop_play' for name,_ in fake.calls)
            assert not any(entry.get('confirmed') for entry in proxy.journal.entries if entry['kind']=='playtest')
    run(scenario())


def test_local_mcp_cleanup_refuses_another_unsaved_blank_with_same_place_ids(monkeypatch,tmp_path):
    from tests.studio_fake import FakeStudio
    fake=FakeStudio()
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            started=await proxy.call_tool('start_stop_play',{'studio_id':fake.studio_id,'is_start':True})
            assert not started.isError and proxy._play_pending
            fake.playing=False
            fake.identity['session']='another-unsaved-native-game:workspace'
            result=await proxy._stop_cleanup()
            assert local_mcp.studio_loop.result_failed(result) and proxy._play_pending
            assert not any(name=='start_stop_play' for name,_ in fake.calls)
            assert not any(entry.get('confirmed') for entry in proxy.journal.entries
                if entry['kind']=='playtest' and not entry['start'])
    run(scenario())


@pytest.mark.parametrize('when',['before_probe','after_probe'])
def test_local_mcp_cleanup_refuses_a_different_native_play_nonce(monkeypatch,tmp_path,when):
    from tests.studio_fake import FakeStudio
    fake=FakeStudio()
    async def scenario():
        async with bound_fake(monkeypatch,tmp_path,fake) as (proxy,_,__):
            started=await proxy.call_tool('start_stop_play',{'studio_id':fake.studio_id,'is_start':True})
            assert not started.isError and fake.playing and proxy._play_pending
            assert fake.test_args['starRequest'].startswith('StarEdit_')
            if when=='before_probe':
                fake.test_args['starRequest']='foreign-play-request'
            else:
                def drift(current,code):
                    if code.startswith('-- STAR:play-stop-bound '):
                        current.test_args['starRequest']='foreign-play-request'
                fake.before_native=drift
            result=await proxy._stop_cleanup()
            assert local_mcp.studio_loop.result_failed(result) and fake.playing and proxy._play_pending
            assert len(native_stops(fake))==int(when=='after_probe')
            assert all(args['datamodel_type']=='Server' for args in native_stops(fake))
            assert not any(name=='start_stop_play' for name,_ in fake.calls)
            assert not any(entry.get('confirmed') for entry in proxy.journal.entries
                if entry['kind']=='playtest' and not entry['start'])
            again=await proxy._stop_cleanup()
            assert local_mcp.studio_loop.result_failed(again)
            assert len(native_stops(fake))==int(when=='after_probe')  # never replay EndTest
    run(scenario())
