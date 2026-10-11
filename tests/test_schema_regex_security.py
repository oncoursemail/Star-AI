"""Offline regex-keyword controls: malicious patterns are never evaluated."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace
import urllib.request

import httpx
from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import ValidationError
import pytest
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session

from star import local_mcp, policy, studio
from star.mcp_connections import MCPGateway, MODERN, Server, StreamableHTTP, valid_schema
from tests.studio_fake import FakeStudio, TOOLS

SID = "selected-fixture"
KEY = ("graphify_docs", "search_graphify_docs")
PATTERN = "^(a+)+$"  # Data only: no slow input or regex benchmark is executed.


def plain_schema():
    return {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object",
            "properties": {"studio_id": {"type": "string"}, "query": {"type": "string"}},
            "required": ["query"], "additionalProperties": False}


def tool(schema, name="script_read"):
    return {"name": name, "inputSchema": schema}


def settings():
    return SimpleNamespace(mcp_graphify_docs=True, mcp_graphify_local=False, mcp_obsidian_live=False)


def request():
    return {"server": KEY[0], "tool": KEY[1], "arguments": {"query": "fixture"}}


@pytest.fixture(autouse=True)
def no_lookup(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: pytest.fail("No resource lookup is permitted"))


def nested_schema(location, keyword):
    bad = {keyword: PATTERN if keyword == "pattern" else {PATTERN: {"type": "string"}}}
    root = plain_schema()
    if location == "root":
        root.update(bad)
    elif location in ("properties", "$defs", "definitions", "dependentSchemas", "dependencies"):
        # The map key is an instance/definition name, while its value is schema.
        root[location] = {"fixture": bad}
    elif location in ("allOf", "anyOf", "oneOf", "prefixItems"):
        root[location] = [True, bad]
    elif location in ("tuple_items", "extends_list", "type_list", "disallow_list"):
        key = {"tuple_items": "items", "extends_list": "extends", "type_list": "type", "disallow_list": "disallow"}[location]
        root["properties"]["query"] = {key: ["string", bad] if key in ("type", "disallow") else [bad]}
    else:
        root[location] = bad
    return root


LOCATIONS = ["root", "properties", "$defs", "definitions", "dependentSchemas", "dependencies",
             "allOf", "anyOf", "oneOf", "prefixItems", "items", "tuple_items", "additionalItems",
             "additionalProperties", "unevaluatedProperties", "propertyNames", "contains", "unevaluatedItems",
             "not", "if", "then", "else", "contentSchema", "extends", "extends_list", "type_list", "disallow_list"]


@pytest.mark.parametrize("keyword", ["pattern", "patternProperties"])
@pytest.mark.parametrize("location", LOCATIONS)
def test_regex_keywords_refused_at_schema_positions_before_validator_selection(monkeypatch, keyword, location):
    import jsonschema.validators
    monkeypatch.setattr(jsonschema.validators, "validator_for", lambda *_a, **_k: pytest.fail("Unsafe schema reached check_schema"))
    with pytest.raises(studio.StudioTransportError) as error:
        studio.validate_tool_schema(nested_schema(location, keyword))
    assert studio.connection_diagnostic(error.value) == {"stage": "tool_discovery", "reason": "unsupported_schema_regex"}
    assert PATTERN not in str(error.value)


@pytest.mark.parametrize("schema", [
    {"pattern": "harmless"}, {"pattern": None}, {"patternProperties": {}},
    {"patternProperties": {".*": True}},
])
def test_all_regex_keywords_are_unsupported_not_stripped_or_classified_by_safety(monkeypatch, schema):
    events = []
    monkeypatch.setattr(Draft7Validator, "check_schema", classmethod(lambda *_a, **_k: events.append("schema")))
    monkeypatch.setattr(Draft7Validator.FORMAT_CHECKER, "check", lambda *_a, **_k: events.append("format"))
    with pytest.raises(studio.StudioTransportError, match="no regex evaluation"):
        studio.validate_tool_schema({"$schema": "http://json-schema.org/draft-07/schema#", **schema})
    assert events == [] and schema  # Caller schema was not stripped or rewritten.


@pytest.mark.parametrize("location", ["type_list", "disallow_list", "extends", "extends_list"])
def test_declared_draft3_schema_forms_cannot_bypass_the_same_guard(monkeypatch, location):
    import jsonschema.validators
    schema = nested_schema(location, "pattern")
    schema["$schema"] = "http://json-schema.org/draft-03/schema#"
    monkeypatch.setattr(jsonschema.validators, "validator_for", lambda *_a, **_k: pytest.fail("Legacy regex reached validator"))
    with pytest.raises(studio.StudioTransportError, match="regex schema keywords"):
        studio.validate_tool_schema(schema)


def test_literal_property_definition_dependency_names_and_annotation_data_remain_data():
    annotation = {"pattern": PATTERN, "patternProperties": {PATTERN: {"pattern": PATTERN}}}
    schema = plain_schema()
    schema["properties"].update({"pattern": {"type": "string"}, "patternProperties": {"type": "integer"}})
    schema["definitions"] = {"pattern": {"type": "string"}, "patternProperties": True}
    schema["dependencies"] = {"pattern": ["patternProperties"], "patternProperties": {"properties": {"pattern": True}}}
    schema["$defs"] = {"pattern": True}
    schema["dependentSchemas"] = {"patternProperties": {"properties": {"pattern": False}}}
    schema.update({"default": annotation, "examples": [annotation], "x-display": annotation,
                   "description": "pattern and patternProperties are literal input field names"})
    original = deepcopy(schema)
    studio.validate_tool_schema(schema)
    Draft7Validator(schema).validate({"query": "fixture", "pattern": "value", "patternProperties": 3})
    assert schema == original and valid_schema(schema) is schema
    # enum/const values are instances, even when they contain schema-like keys.
    for value_keyword in ("enum", "const"):
        value_schema = {"type": "object", value_keyword: [annotation] if value_keyword == "enum" else annotation}
        studio.validate_tool_schema(value_schema)
        Draft202012Validator(value_schema).validate(annotation)


def test_bool_subschemas_and_ordinary_type_errors_keep_the_original_contract():
    schema = {"type": "object", "properties": {"yes": True, "no": False}, "additionalProperties": False,
              "allOf": [True, {"not": False}]}
    studio.validate_tool_schema(schema)
    Draft202012Validator(schema).validate({"yes": "fixture"})
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate({"no": "fixture"})
    with pytest.raises(studio.StudioTransportError, match="invalid tool schema"):
        studio.validate_tool_schema({"properties": {"field": {"type": "invented"}}})
    with pytest.raises(studio.StudioTransportError):
        studio.validate_tool_schema(True)  # Existing tool-schema root API stays dict-only.


@pytest.mark.parametrize("keyword", ["pattern", "patternProperties"])
def test_studio_discovery_local_bridge_and_policy_registration_refuse_regex(keyword):
    schema = nested_schema("properties", keyword)
    class Listing:
        async def list_tools(self, **_kwargs):
            return SimpleNamespace(tools=[types.Tool.model_validate(tool(schema))], nextCursor=None)
    with pytest.raises(studio.StudioTransportError, match="regex schema keywords"):
        asyncio.run(studio.list_tools(Listing()))
    with pytest.raises(studio.StudioTransportError, match="regex schema keywords"):
        local_mcp.make_server(discovered=[tool(schema)], status={})
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.allowed_registry([tool(schema)], False)
    with pytest.raises(studio.StudioTransportError, match="regex schema keywords"):
        local_mcp.make_server(discovered=[{**tool(plain_schema()), "outputSchema": schema}], status={})


@pytest.mark.parametrize("keyword", ["pattern", "patternProperties"])
def test_mutated_policy_registry_refuses_before_argument_validator(monkeypatch, keyword):
    schema = plain_schema()
    registry = policy.allowed_registry([tool(schema)], False)
    schema["properties"]["query"] = {keyword: PATTERN if keyword == "pattern" else {PATTERN: True}}
    monkeypatch.setattr(policy.Draft202012Validator, "validate", lambda *_a, **_k: pytest.fail("Unsafe argument regex was evaluated"))
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.enforce("script_read", {"studio_id": SID, "query": "fixture"}, registry, SID, False)


def test_actual_memory_mcp_call_rechecks_forged_registry_before_guarded_dispatch(monkeypatch):
    bad = nested_schema("properties", "pattern")
    calls = []
    class Guard:
        studio_id = SID
        verdict = SimpleNamespace(editable=False)
        async def call_tool(self, *args, **kwargs):
            calls.append((args, kwargs))
            pytest.fail("Unsafe schema cannot reach the native guard")
    # Simulate a corrupted cached registry after the safe discovery check.
    monkeypatch.setattr(local_mcp, "allowed_registry", lambda *_a, **_k: {"script_read": tool(bad)})
    async def run():
        server, _ = local_mcp.make_server(guarded=Guard(), discovered=[tool(plain_schema())], status={})
        async with create_connected_server_and_client_session(server, read_timeout_seconds=timedelta(seconds=2)) as client:
            response = await client.call_tool("script_read", {"studio_id": SID, "query": "fixture"})
            assert response.isError and "refused" in response.content[0].text and PATTERN not in response.content[0].text
    asyncio.run(run())
    assert calls == []


@pytest.mark.parametrize("keyword", ["pattern", "patternProperties"])
def test_gateway_discovery_and_mutated_call_refuse_before_dispatch(keyword):
    schema = plain_schema()
    events = []
    async def listing():
        events.append("list")
        return [tool(schema, KEY[1])]
    async def calling(*_args):
        events.append("call")
        pytest.fail("Unsafe schema cannot dispatch")
    def factory(_server):
        events.append("factory")
        return SimpleNamespace(list_tools=listing, call_tool=calling)
    gateway = MCPGateway(settings(), factory=factory)
    async def run():
        assert len((await gateway.search("graphify docs"))["tools"]) == 1
        schema["properties"]["query"] = {keyword: PATTERN if keyword == "pattern" else {PATTERN: True}}
        with pytest.raises(ValueError, match="Unsafe or invalid"):
            await gateway.call("star_mcp_call", request())
        assert events == ["factory", "list"] and gateway.calls == 0
        assert (await gateway.search("graphify docs"))["tools"] == []
        assert gateway.catalog == {} and gateway.disclosed == set()
    asyncio.run(run())
    assert events == ["factory", "list", "factory", "list"]


@pytest.mark.parametrize("keyword", ["pattern", "patternProperties"])
def test_direct_http_refuses_before_credentials_or_transport(monkeypatch, keyword):
    schema = nested_schema("properties", keyword)
    server = Server(KEY[0], "Fixture", "https://graphify.com/api/mcp", MODERN, frozenset({KEY[1]}))
    connection = StreamableHTTP(server, transport=httpx.MockTransport(lambda _r: pytest.fail("No transport")))
    monkeypatch.setattr(connection, "_options", lambda: pytest.fail("No credential/options read"))
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        asyncio.run(connection.call_tool(KEY[1], {"query": "fixture"}, schema))


def test_actual_30_tool_catalog_and_valid_native_http_routes_remain_compatible():
    assert len(TOOLS) == 30 and len(asyncio.run(studio.list_tools(FakeStudio()))) == 30
    for entry in TOOLS:
        studio.validate_tool_schema(entry["inputSchema"])
    registry = policy.allowed_registry(deepcopy(TOOLS), True, True)
    policy.enforce("script_grep", {"studio_id": SID, "query": "fixture"}, registry, SID, True, True)
    schema = plain_schema()
    # Synthetic literal field names remain callable on both routes as data.
    schema["properties"].update({"pattern": {"type": "string"}, "patternProperties": {"type": "integer"}})
    literal_args = {"query": "fixture", "pattern": "literal", "patternProperties": 3}
    literal_registry = policy.allowed_registry([tool(schema)], False)
    policy.enforce("script_read", {"studio_id": SID, **literal_args}, literal_registry, SID, False)
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body["method"])
        return httpx.Response(200, headers={"Content-Type": "application/json"}, json={
            "jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "fixture"}]}})
    server = Server(KEY[0], "Fixture", "https://graphify.com/api/mcp", MODERN, frozenset({KEY[1]}))
    connection = StreamableHTTP(server, transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError):
        asyncio.run(connection.call_tool(KEY[1], {"query": 42}, schema))
    assert requests == []
    assert asyncio.run(connection.call_tool(KEY[1], literal_args, schema))["output"] == "fixture"
    assert requests == ["tools/call"]
