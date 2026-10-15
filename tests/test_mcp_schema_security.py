"""Curated MCP schema controls using injected factories/HTTP and no network."""
import asyncio
from copy import deepcopy
import io
import json
from types import SimpleNamespace
import urllib.request

import httpx
from jsonschema.exceptions import ValidationError
import pytest

from star import studio, mcp_connections as connections
from star.mcp_connections import MCPGateway, LEGACY, MODERN, Server, StreamableHTTP, valid_schema


KEY = ("graphify_docs", "search_graphify_docs")


def plain_schema():
    return {"type": "object", "properties": {"query": {"type": "string"}},
            "required": ["query"], "additionalProperties": False}


def settings():
    return SimpleNamespace(mcp_graphify_docs=True, mcp_graphify_local=False, mcp_obsidian_live=False)


def request(arguments=None):
    return {"server": KEY[0], "tool": KEY[1], "arguments": {"query": "fixture"} if arguments is None else arguments}


@pytest.fixture
def offline_lookup(monkeypatch):
    calls = []
    def retrieve(request, *args, **kwargs):
        calls.append(request.full_url)
        return io.BytesIO(json.dumps({"type": "string"}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", retrieve)
    return calls


def client(schema, events):
    async def listing():
        events.append("discovery")
        return [{"name": KEY[1], "description": "Graphify docs fixture", "inputSchema": schema}]
    async def calling(*args):
        events.append("call")
        return {"isError": False, "output": "fixture"}
    return SimpleNamespace(list_tools=listing, call_tool=calling)


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef", "$recursiveRef"])
@pytest.mark.parametrize("uri", ["https://fixture.invalid/schema", "#/$defs/fixture"])
def test_gateway_discovery_drops_nested_reference_and_never_grants_call(offline_lookup, reference, uri):
    schema = plain_schema()
    schema["properties"]["query"] = {"allOf": [{reference: uri}]}
    schema["$defs"] = {"fixture": {"type": "string"}}
    events = []
    gateway = MCPGateway(settings(), factory=lambda _: client(schema, events))
    async def run():
        found = await gateway.search("graphify docs")
        assert found["tools"] == [] and not gateway.catalog and not gateway.disclosed
        with pytest.raises(PermissionError):
            await gateway.call("star_mcp_call", request())
    asyncio.run(run())
    assert events == ["discovery"] and gateway.calls == 0 and offline_lookup == []


def test_wire_discovery_response_with_dynamic_reference_never_reaches_a_tool_request(offline_lookup):
    schema = plain_schema()
    schema["properties"]["query"] = {"$dynamicRef": "https://fixture.invalid/schema"}
    methods = []
    def handler(request):
        body = json.loads(request.content)
        methods.append(body["method"])
        assert body["method"] == "tools/list"
        return httpx.Response(200, headers={"Content-Type": "application/json"}, json={
            "jsonrpc": "2.0", "id": body["id"], "result": {"tools": [{
                "name": KEY[1], "description": "Graphify docs fixture", "inputSchema": schema}]}})
    gateway = MCPGateway(settings(), factory=lambda server: StreamableHTTP(server, transport=httpx.MockTransport(handler)))
    async def run():
        assert (await gateway.search("graphify docs"))["tools"] == []
        with pytest.raises(PermissionError):
            await gateway.call("star_mcp_call", request())
    asyncio.run(run())
    assert methods == ["tools/list"] and gateway.calls == 0 and offline_lookup == []


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_mutated_disclosed_catalog_refuses_before_factory_or_resolver(offline_lookup, reference):
    schema = plain_schema()
    events = []
    factories = []
    def factory(server):
        factories.append(server.name)
        return client(schema, events)
    gateway = MCPGateway(settings(), factory=factory)
    async def run():
        found = await gateway.search("graphify docs")
        assert len(found["tools"]) == 1
        gateway.catalog[KEY]["inputSchema"]["properties"]["query"] = {
            reference: "https://fixture.invalid/fixture-secret"}
        with pytest.raises(ValueError, match="Unsafe or invalid"):
            await gateway.call("star_mcp_call", request())
    asyncio.run(run())
    assert factories == [KEY[0]] and events == ["discovery"]
    assert gateway.calls == 0 and offline_lookup == []


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_direct_http_client_blocks_reference_before_options_transport_or_resolver(monkeypatch, offline_lookup, reference):
    schema = plain_schema()
    schema["properties"]["query"] = {reference: "https://fixture.invalid/schema"}
    server = Server(KEY[0], "Fixture", "https://graphify.com/api/mcp", MODERN, frozenset({KEY[1]}))
    events = []
    def handler(request):
        events.append("transport")
        pytest.fail("A rejected schema must never open transport")
    connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
    def options():
        pytest.fail("A rejected schema must never load connection options/credentials")
    monkeypatch.setattr(connection, "_options", options)
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        asyncio.run(connection.call_tool(KEY[1], {"query": "fixture"}, schema))
    assert events == [] and offline_lookup == []


@pytest.mark.parametrize("kind", ["oversize", "cycle", "deep", "nodes", "invalid", "array", "missing_type"])
def test_bounded_schema_refusals_return_none_and_prevent_cached_and_direct_calls(offline_lookup, kind):
    schema = plain_schema()
    if kind == "oversize":
        schema["description"] = "x" * 16001
    elif kind == "cycle":
        schema["allOf"] = [schema]
    elif kind == "deep":
        nested = {}
        for _ in range(studio.MAX_SCHEMA_DEPTH + 1):
            nested = {"allOf": [nested]}
        schema["allOf"] = [nested]
    elif kind == "nodes":
        # A valid extension annotation fits the stricter serialized-character
        # limit, but exceeds the shared traversal's node budget.
        schema["x-fixture"] = [0 for _ in range(studio.MAX_SCHEMA_NODES + 1)]
    elif kind == "invalid":
        schema["properties"]["query"]["type"] = "invalid-fixture-type"
    elif kind == "array":
        schema["type"] = "array"
    else:
        del schema["type"]
    assert valid_schema(schema) is None
    events = []
    def forbidden(server):
        events.append("factory")
        pytest.fail("Invalid cached schemas cannot dispatch")
    gateway = MCPGateway(settings(), factory=forbidden)
    gateway.catalog[KEY] = {"inputSchema": schema}
    gateway.disclosed.add(KEY)
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        asyncio.run(gateway.call("star_mcp_call", request()))
    server = gateway.servers[KEY[0]]
    def handler(request):
        events.append("transport")
        pytest.fail("Invalid direct schemas cannot dispatch")
    connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        asyncio.run(connection.call_tool(KEY[1], {"query": "fixture"}, schema))
    assert events == [] and offline_lookup == [] and gateway.calls == 0


def test_valid_header_schema_and_arguments_keep_http_metadata_and_type_validation(offline_lookup):
    schema = plain_schema()
    schema["properties"]["query"]["x-mcp-header"] = "Search-Term"
    assert valid_schema(schema) is schema
    requests = []
    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["method"] == "tools/call" and body["params"]["arguments"] == {"query": "fixture"}
        assert request.headers["mcp-param-search-term"] == "fixture"
        return httpx.Response(200, headers={"Content-Type": "application/json"}, json={
            "jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "fixture"}]}})
    server = Server(KEY[0], "Fixture", "https://graphify.com/api/mcp", MODERN, frozenset({KEY[1]}))
    connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError):
        asyncio.run(connection.call_tool(KEY[1], {"query": 42}, schema))
    assert requests == []
    result = asyncio.run(connection.call_tool(KEY[1], {"query": "fixture"}, schema))
    assert result["output"] == "fixture" and result["untrusted"] is True and len(requests) == 1
    assert offline_lookup == []
    duplicate = deepcopy(schema)
    duplicate["properties"]["other"] = {"type": "string", "x-mcp-header": "search-term"}
    assert valid_schema(duplicate) is None


def test_gateway_preserves_discovery_read_allowlist_argument_errors_and_eight_call_budget(offline_lookup):
    schema = plain_schema()
    events = []
    gateway = MCPGateway(settings(), factory=lambda _: client(schema, events))
    async def run():
        with pytest.raises(PermissionError):
            await gateway.call("star_mcp_call", request())
        await gateway.search("graphify docs")
        with pytest.raises(ValidationError):
            await gateway.call("star_mcp_call", request({"query": 42}))
        assert gateway.calls == 0 and events == ["discovery"]
        for _ in range(8):
            assert (await gateway.call("star_mcp_call", request()))["result"]["output"] == "fixture"
        with pytest.raises(RuntimeError, match="budget"):
            await gateway.call("star_mcp_call", request())
        with pytest.raises(PermissionError):
            await gateway.call("star_mcp_call", {"server": KEY[0], "tool": "delete_graph", "arguments": {}})
    asyncio.run(run())
    assert gateway.calls == 8 and events == ["discovery"] + ["call"] * 8 and offline_lookup == []


def test_slow_drip_response_has_one_elapsed_deadline_and_closes_without_replay(monkeypatch):
    monkeypatch.setattr(connections, "CALL_SECONDS", .01)
    state = {"requests": 0, "chunks": 0, "closed": 0, "cancelled": False}
    class Drip(httpx.AsyncByteStream):
        async def __aiter__(self):
            try:
                # Each tiny chunk arrives far inside the socket read timeout,
                # while the total stream would run well beyond the call budget.
                for _ in range(1000):
                    state["chunks"] += 1
                    yield b" "
                    await asyncio.sleep(.002)
            except asyncio.CancelledError:
                state["cancelled"] = True
                raise
        async def aclose(self):
            state["closed"] += 1
    def handler(request):
        state["requests"] += 1
        return httpx.Response(200, headers={"Content-Type": "application/json"}, stream=Drip())
    server = Server(KEY[0], "Fixture", "https://graphify.com/api/mcp", MODERN, frozenset({KEY[1]}))
    connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
    with pytest.raises(TimeoutError):
        asyncio.run(connection.call_tool(KEY[1], {"query": "fixture"}, plain_schema()))
    assert state["requests"] == 1 and state["closed"] == 1 and state["cancelled"]
    assert 0 < state["chunks"] < 1000


def test_legacy_initialize_and_operation_share_the_same_elapsed_budget(monkeypatch):
    # 0.4 s per phase against a 0.6 s budget: each phase fits alone with 0.2 s to spare, so a
    # loaded machine cannot push initialize itself past the budget (it could with 0.05 / 0.08 s).
    monkeypatch.setattr(connections, "CALL_SECONDS", .6)
    methods = []
    cancelled = []
    async def handler(request):
        body = json.loads(request.content)
        method = body["method"]
        methods.append(method)
        if method == "notifications/initialized":
            return httpx.Response(202)
        try:
            # Each phase fits the full call budget independently. Together they
            # exceed it, so the already-started operation must be cancelled.
            await asyncio.sleep(.4)
        except asyncio.CancelledError:
            cancelled.append(method)
            raise
        result = {"protocolVersion": LEGACY, "capabilities": {"tools": {}}} if method == "initialize" else {
            "content": [{"type": "text", "text": "fixture"}]}
        return httpx.Response(200, headers={"Content-Type": "application/json", "Mcp-Session-Id": "fixture"},
                              json={"jsonrpc": "2.0", "id": body["id"], "result": result})
    server = Server("graphify_local", "Fixture", "http://127.0.0.1:8931/mcp", LEGACY, frozenset({"query_graph"}))
    connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
    with pytest.raises(TimeoutError):
        asyncio.run(connection.call_tool("query_graph", {"query": "fixture"}, plain_schema()))
    assert methods == ["initialize", "notifications/initialized", "tools/call"]
    assert cancelled == ["tools/call"]


def test_explicit_cancellation_remains_cancellation_with_no_retry(monkeypatch):
    monkeypatch.setattr(connections, "CALL_SECONDS", 1)
    async def run():
        entered = asyncio.Event()
        requests = []
        cancelled = []
        async def handler(request):
            requests.append(json.loads(request.content)["method"])
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        server = Server(KEY[0], "Fixture", "https://graphify.com/api/mcp", MODERN, frozenset({KEY[1]}))
        connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
        task = asyncio.create_task(connection.call_tool(KEY[1], {"query": "fixture"}, plain_schema()))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert requests == ["tools/call"] and cancelled == [True]
    asyncio.run(run())
