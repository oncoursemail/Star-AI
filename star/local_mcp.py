"""STAR's local MCP bridge. The desktop uses real MCP over private memory streams.

The optional source entry point serves stdio, never a public HTTP listener. All
Roblox calls terminate at the same host-selected GuardedStudio used by the app.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4

import anyio

from mcp import types
from mcp.server import Server
from mcp.shared.memory import create_connected_server_and_client_session

from . import studio, studio_loop
from .policy import PLAYTEST_TOOLS, allowed_registry, enforce

STATUS_TOOL = "star_connection_status"
MAX_ARGUMENT_BYTES = 120_000
CALL_SECONDS = 65


@dataclass
class _Operation:
    cancelled: bool = False
    request_id: object = None
    done: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class _Control:
    serial: asyncio.Lock = field(default_factory=asyncio.Lock)
    operations: dict = field(default_factory=dict)


def route_label(target):
    if target == "local_pc":
        return "Roblox Studio on this PC"
    if target == "host_launcher":
        return "Practice Studio (configured host)"
    raise ValueError("Select a supported Studio connection target")


def _result(value):
    if isinstance(value, types.CallToolResult):
        return value
    data = value.model_dump(by_alias=True, exclude_none=True) if hasattr(value, "model_dump") else value
    return types.CallToolResult.model_validate(data)


def _error(message):
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True)


def make_server(*, guarded=None, discovered=(), allow_luau=False, status):
    """Only trusted host code constructs a bridge; catalogs cannot grant access.

    No code/command/endpoint registration tool exists. Unknown tools, mismatched
    instance IDs, writes without host opt-in and Luau without opt-in are refused.
    """
    public_status = deepcopy(status)
    may_edit = bool(guarded is not None and guarded.verdict.editable)
    sid = guarded.studio_id if guarded is not None else ""
    definitions = deepcopy(list(discovered))
    for tool in definitions:
        studio.validate_tool_schema(tool["inputSchema"])
        if tool.get("outputSchema") is not None:
            studio.validate_tool_schema(tool["outputSchema"], input_schema=False)
    # These native input APIs accept only a Studio ID, not this play request's
    # immutable ownership token. A read-before-input check cannot bind dispatch.
    bound_definitions = [tool for tool in definitions if tool["name"] not in PLAYTEST_TOOLS]
    registry = deepcopy(allowed_registry(bound_definitions, may_edit, allow_luau and may_edit))
    catalog = [types.Tool.model_validate(tool) for tool in registry.values()]
    catalog.append(types.Tool(name=STATUS_TOOL, description="Read STAR's current host-selected Studio connection status; this grants no edit access.",
                              inputSchema={"type": "object", "properties": {}, "additionalProperties": False}))
    bridge = Server("STAR local MCP", version="1.0")
    control = _Control()
    bridge._star_control = control

    @bridge.list_tools()
    async def tools():
        return deepcopy(catalog)

    # Validate ourselves so a schema error cannot echo user code/private arguments
    # through the SDK's default validation exception text.
    @bridge.call_tool(validate_input=False)
    async def call(name, arguments):
        operation = None
        try:
            meta = bridge.request_context.meta
            nonce = meta.model_dump().get("starLocalCall") if meta is not None else None
            if nonce is not None:
                operation = control.operations.get(nonce) if isinstance(nonce, str) else None
                if operation is None or operation.cancelled:
                    return _error("STAR local MCP: this local request has been cancelled or expired.")
                operation.request_id = bridge.request_context.request_id
            if type(arguments) is not dict or len(json.dumps(arguments, allow_nan=False).encode("utf-8")) > MAX_ARGUMENT_BYTES:
                return _error("STAR local MCP: invalid or oversized tool arguments.")
            if name == STATUS_TOOL:
                return deepcopy(public_status) if not arguments else _error("STAR local MCP status takes no arguments.")
            if guarded is None:
                return _error("STAR local MCP: select and verify a Studio before using its tools.")
            enforce(name, arguments, registry, sid, may_edit, allow_luau and may_edit)
            async with asyncio.timeout(CALL_SECONDS):
                async with control.serial:
                    if operation is not None and operation.cancelled:
                        return _error("STAR local MCP: request cancelled before dispatch.")
                    response = await guarded.call_tool(name, arguments=arguments)
            return _result(response)
        except Exception:
            # A tool may have changed Studio before its reply was lost. Never retry.
            return _error("STAR local MCP: tool result unavailable or request refused; no automatic retry. Check the change journal before continuing.")
        finally:
            if operation is not None:
                operation.done.set()

    return bridge, [deepcopy(tool) for tool in registry.values()]


@dataclass
class LocalStudioClient:
    """Agent-facing session; each call crosses STAR's real local MCP server."""
    client: object
    guarded: object
    discovered: list[dict]
    status: dict
    control: _Control | None = None

    @property
    def verdict(self):
        return self.guarded.verdict

    @property
    def journal(self):
        return self.guarded.journal

    @property
    def studio_id(self):
        return self.guarded.studio_id

    @property
    def session(self):
        # The build loop's read helper must cross this MCP client, never the raw connector.
        return self

    @property
    def tools(self):
        return {tool["name"] for tool in self.discovered}

    @property
    def _play_pending(self):
        return self.guarded._play_pending

    async def _read(self, path):
        if "script_read" not in self.tools:
            return None
        result = await self.call_tool("script_read", {"studio_id": self.studio_id,
            "target_file": path, "should_read_entire_file": True})
        return (None if studio_loop.result_failed(result)
                else studio_loop._plain_source(studio_loop.result_text(result)))

    async def _stop_cleanup(self):
        # Recovery is host-only and shares the bridge lock with model tool calls.
        # Keep AnyIO's cancelled handler scope out of the guard's shielded stop.
        with anyio.CancelScope(shield=True):
            try:
                async with asyncio.timeout(CALL_SECONDS):
                    if self.control is None:
                        return await self.guarded._stop_cleanup()
                    async with self.control.serial:
                        return await self.guarded._stop_cleanup()
            except TimeoutError:
                return _error("STAR local MCP: playtest cleanup timed out; stop outcome unconfirmed. Inspect Studio before continuing.")

    async def call_tool(self, name, arguments=None):
        if self.control is None:
            return await self.client.call_tool(name, arguments=arguments or {})
        nonce, operation = uuid4().hex, _Operation()
        self.control.operations[nonce] = operation
        try:
            return await self.client.call_tool(name, arguments=arguments or {}, meta={"starLocalCall": nonce})
        except BaseException:
            operation.cancelled = True
            # SDK timeout/caller cancellation alone removes its response waiter;
            # emit the real protocol cancellation as well. The shared nonce closes
            # cancellation-before-server-dispatch without guessing an SDK ID.
            with anyio.move_on_after(12, shield=True):
                if operation.request_id is not None:
                    try:
                        await self.client.send_notification(types.ClientNotification(types.CancelledNotification(
                            params=types.CancelledNotificationParams(requestId=operation.request_id,
                                reason="STAR local task stopped"))))
                        await operation.done.wait()
                    except Exception:
                        pass
            raise
        finally:
            self.control.operations.pop(nonce, None)

    async def undo(self):
        # Recovery is a host operation, not a model-discovered permission tool.
        if self.control is None:
            return await self.guarded.undo()
        async with asyncio.timeout(CALL_SECONDS):
            async with self.control.serial:
                return await self.guarded.undo()


def _transport_options(target, home):
    options = {"target": target}
    if target == "host_launcher":
        command = studio.configured_command(home)
        if command is None:
            raise studio.StudioTransportError("The host-defined Studio launcher is not configured; no local fallback was attempted.")
        options["command"] = command
    return options


async def discover(*, target="local_pc", studio_id=None, home=None):
    """Read-only remote discovery plus an actual STAR local MCP status request."""
    label = route_label(target)
    async with studio.connect(**_transport_options(target, home)) as remote:
        try:
            checked = await studio.probe(remote, studio_id=studio_id)
        except studio.StudioNoInstancesError as error:
            if studio_id is not None:
                raise
            checked = {"status": "tools_discovered_no_instances", "tool_count": error.tool_count,
                       "studios": [], "selected": None}
        status = {**checked, "target": target, "label": label, "local_mcp": "memory",
                  "server_name": "STAR local MCP"}
        server, _ = make_server(status=status)
        async with create_connected_server_and_client_session(server, read_timeout_seconds=timedelta(seconds=CALL_SECONDS)) as client:
            response = await client.call_tool(STATUS_TOOL, arguments={})
            if response.isError or not isinstance(response.structuredContent, dict):
                raise studio.StudioTransportError("STAR local MCP status request failed.")
            return deepcopy(response.structuredContent)


@asynccontextmanager
async def connect_studio(settings, home, *, studio_configuration_home=None):
    """Desktop tool session: host configuration -> STAR MCP -> guarded Roblox MCP."""
    from .studio_uncertainty import StudioUncertaintyStore
    target = settings.studio_target
    label = route_label(target)
    uncertainty = StudioUncertaintyStore(Path(home) / "studio-uncertainty.sqlite3")
    configuration_home = studio_configuration_home if studio_configuration_home is not None else home
    async with studio.connect(**_transport_options(target, configuration_home)) as remote:
        discovered = await studio.list_tools(remote)
        if "list_roblox_studios" not in {tool["name"] for tool in discovered}:
            raise studio.StudioTransportError("Studio MCP does not expose instance discovery.")
        instances = await studio.list_studios(remote, tool_count=len(discovered))
        studio.select_studio(instances, settings.studio_id)
        guarded = await studio_loop.open_guarded(remote, discovered, studio_id=settings.studio_id,
            opted_in=settings.studio_edit, own_places=settings.studio_own_places,
            own_account_id=studio_loop.own_account_id(Path(home)) if settings.studio_own_places else None,
            uncertainty_store=uncertainty, route=target)
        status = {"status": "tools_and_instances_discovered", "target": target, "label": label,
                  "local_mcp": "memory", "server_name": "STAR local MCP", "tool_count": len(discovered),
                  "studios": instances, "selected": studio.select_studio(instances, settings.studio_id)}
        server, catalog = make_server(guarded=guarded, discovered=discovered,
            allow_luau=settings.studio_luau, status=status)
        async with create_connected_server_and_client_session(server, read_timeout_seconds=timedelta(seconds=CALL_SECONDS + 5)) as client:
            # Verify our own catalog through MCP, not only its Python construction.
            listed = await client.list_tools()
            if {item.name for item in listed.tools} != {tool["name"] for tool in catalog} | {STATUS_TOOL}:
                raise studio.StudioTransportError("STAR local MCP tool catalog verification failed.")
            yield LocalStudioClient(client, guarded, catalog, status, server._star_control)


async def _serve(settings_path):
    # Explicit operator-selected configuration; no model-supplied configuration.
    from .desktop_core import Settings
    from mcp.server.stdio import stdio_server
    settings = Settings.load(settings_path)
    settings.validate()
    # The selected configuration's folder owns the isolated credential/account scope.
    home = settings_path.parent
    async with connect_studio(settings, home) as connection:
        server, _ = make_server(guarded=connection.guarded, discovered=connection.discovered,
            allow_luau=settings.studio_luau, status={**connection.status, "local_mcp": "stdio"})
        async with stdio_server() as (incoming, outgoing):
            await server.run(incoming, outgoing, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description="STAR local MCP: operator-configured, guarded Roblox bridge over stdio")
    parser.add_argument("--settings", required=True, type=Path, help="Explicit STAR settings file for this MCP session")
    args = parser.parse_args()
    if not args.settings.is_file():
        parser.error("The selected STAR settings file does not exist")
    try:
        asyncio.run(_serve(args.settings))
    except Exception:
        # Stdout belongs exclusively to MCP; diagnostics must not reveal settings.
        import sys
        print("STAR local MCP could not open its configured Studio connection.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
