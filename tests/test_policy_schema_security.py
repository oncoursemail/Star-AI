"""Credential-free policy controls: no connector, HTTP, model or real profile."""
from copy import deepcopy
import io
import json
import urllib.request
import warnings

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
import pytest

from star import policy, studio
from tests.studio_fake import TOOLS


SID = "selected-fixture"


def tool(schema, name="script_read"):
    return {"name": name, "inputSchema": schema}


def plain_schema():
    return {"type": "object", "properties": {"studio_id": {"type": "string"}, "path": {"type": "string"}},
            "required": ["studio_id", "path"], "additionalProperties": False}


@pytest.fixture
def offline_lookup(monkeypatch):
    """Intercept the actual jsonschema default retriever; never open a URL."""
    lookups = []
    def retrieve(request, *args, **kwargs):
        lookups.append(request.full_url)
        return io.BytesIO(json.dumps({"type": "string"}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", retrieve)
    return lookups


def test_dynamic_reference_real_resolver_control_then_policy_blocks_every_lookup(offline_lookup):
    uri = "https://fixture.invalid/schema"
    schema = plain_schema()
    schema["properties"]["path"] = {"$dynamicRef": uri}
    # A positive control proves this fixture exercises jsonschema's real remote
    # retrieval path. Its urlopen implementation is an in-memory fake only.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        Draft202012Validator(schema).validate({"studio_id": SID, "path": "fixture"})
    assert offline_lookup == [uri]
    offline_lookup.clear()
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.allowed_registry([tool(schema)], False)
    for selected in (SID, "wrong-target"):
        with pytest.raises(ValueError):
            policy.enforce("script_read", {"studio_id": selected, "path": "fixture"},
                           {"script_read": tool(schema)}, SID, False)
    assert offline_lookup == []


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef", "$recursiveRef"])
@pytest.mark.parametrize("uri", ["https://fixture.invalid/schema", "#/$defs/fixture"])
@pytest.mark.parametrize("location", ["root", "property", "list"])
def test_all_reference_forms_and_locations_refuse_registration_and_forged_calls(offline_lookup, reference, uri, location):
    schema = plain_schema()
    if location == "root":
        schema[reference] = uri
    elif location == "property":
        schema["properties"]["path"] = {reference: uri}
    else:
        schema["allOf"] = [{"properties": {"path": {reference: uri}}}]
    schema["$defs"] = {"fixture": {"type": "string"}}
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.allowed_registry([tool(schema)], False)
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.enforce("script_read", {"studio_id": SID, "path": "fixture"},
                       {"script_read": tool(schema)}, SID, False)
    assert offline_lookup == []


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_reference_injection_after_valid_registration_cannot_bypass_call_check(offline_lookup, reference):
    schema = plain_schema()
    registry = policy.allowed_registry([tool(schema)], False)
    schema["properties"]["path"] = {reference: "https://fixture.invalid/schema"}
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.enforce("script_read", {"studio_id": SID, "path": "fixture"}, registry, SID, False)
    assert offline_lookup == []


@pytest.mark.parametrize("name,args,may_edit,allow_luau,reason", [
    ("script_read", {"studio_id": "other"}, False, False, "Target"),
    ("script_read", {"studio_id": SID}, False, False, "Target"),
    ("multi_edit", {"studio_id": SID}, False, False, "Writing"),
    ("execute_luau", {"studio_id": SID, "datamodel_type": "Edit"}, True, False, "explicitly enabled"),
    ("execute_luau", {"studio_id": SID, "datamodel_type": "Server"}, True, True, "selected Edit"),
    ("screen_capture", {"studio_id": SID, "capture_id": "fixture", "camera_position": []}, False, False, "Camera"),
])
def test_cheap_permission_checks_precede_all_schema_work(monkeypatch, name, args, may_edit, allow_luau, reason):
    def forbidden(*args, **kwargs):
        pytest.fail("A refused target or permission must not evaluate an untrusted schema")
    monkeypatch.setattr(studio, "validate_tool_schema", forbidden)
    selected = "" if name == "script_read" and args["studio_id"] == SID else SID
    with pytest.raises(ValueError, match=reason):
        policy.enforce(name, args, {name: tool({"$dynamicRef": "https://fixture.invalid/schema"}, name)},
                       selected, may_edit, allow_luau)


@pytest.mark.parametrize("bound", ["depth", "nodes", "bytes", "cycle"])
def test_schema_bounds_apply_to_registration_and_every_call(offline_lookup, bound):
    schema = plain_schema()
    if bound == "depth":
        nested = {}
        for _ in range(studio.MAX_SCHEMA_DEPTH + 1):
            nested = {"allOf": [nested]}
        schema["allOf"] = [nested]
    elif bound == "nodes":
        schema["allOf"] = [{} for _ in range(studio.MAX_SCHEMA_NODES + 1)]
    elif bound == "bytes":
        schema["description"] = "x" * (studio.MAX_TOOL_BYTES + 1)
    else:
        schema["allOf"] = [schema]
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.allowed_registry([tool(schema)], False)
    with pytest.raises(ValueError, match="Unsafe or invalid"):
        policy.enforce("script_read", {"studio_id": SID, "path": "fixture"},
                       {"script_read": tool(schema)}, SID, False)
    assert offline_lookup == []


def test_safe_policy_error_does_not_expose_schema_reference_or_exception_context(offline_lookup):
    import traceback
    schema = plain_schema()
    schema["properties"]["path"] = {"$dynamicRef": "https://fixture.invalid/fixture-secret"}
    with pytest.raises(ValueError, match="Unsafe or invalid") as error:
        policy.allowed_registry([tool(schema)], False)
    assert "fixture-secret" not in "".join(traceback.format_exception(error.value))
    assert offline_lookup == []


def test_bounded_self_contained_schema_preserves_argument_validation_and_all_actual_tools(offline_lookup):
    assert len(TOOLS) == 30
    for may_edit, allow_luau, expected in (
        (False, False, policy.READ_TOOLS),
        (True, False, policy.READ_TOOLS | policy.EDIT_TOOLS | policy.PLAYTEST_TOOLS),
        (True, True, policy.READ_TOOLS | policy.WRITE_TOOLS),
    ):
        assert set(policy.allowed_registry(deepcopy(TOOLS), may_edit, allow_luau)) == expected
    registry = policy.allowed_registry([tool(plain_schema())], False)
    policy.enforce("script_read", {"studio_id": SID, "path": "fixture"}, registry, SID, False)
    with pytest.raises(ValidationError):
        policy.enforce("script_read", {"studio_id": SID, "path": 42}, registry, SID, False)
    with pytest.raises(ValidationError):
        policy.enforce("script_read", {"studio_id": SID}, registry, SID, False)
    real = policy.allowed_registry(deepcopy(TOOLS), True, True)
    policy.enforce("screen_capture", {"studio_id": SID, "capture_id": "fixture"}, real, SID, False)
    policy.enforce("execute_luau", {"studio_id": SID, "datamodel_type": "Edit", "code": "return 1"}, real, SID, True, True)
    policy.enforce("list_roblox_studios", {}, real, "", False)
    assert offline_lookup == []
