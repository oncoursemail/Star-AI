"""No per-tool prompts. Tool permission enforcement remains in code."""
from typing import Any
from jsonschema import Draft202012Validator

READ_TOOLS = frozenset({
    "list_roblox_studios", "get_studio_state", "search_game_tree", "inspect_instance",
    "script_read", "script_search", "script_grep", "get_console_output", "screen_capture",
    "search_asset", "skill", "http_get",
})
EDIT_TOOLS = frozenset({"multi_edit", "start_stop_play"})
# Full execute_luau is an unrestricted code execution primitive inside Studio.
# A model cannot make it safe by promising to use a particular instance path.
HIGH_RISK_TOOLS = frozenset({"execute_luau"})


def allowed_registry(discovered: list[dict], may_edit: bool, allow_luau: bool = False) -> dict[str, dict]:
    if allow_luau and not may_edit:
        raise ValueError("Arbitrary Luau execution requires sandbox edit mode")
    acceptable = READ_TOOLS | (EDIT_TOOLS if may_edit else frozenset()) | (HIGH_RISK_TOOLS if allow_luau else frozenset())
    registry = {}
    for tool in discovered:
        name = tool.get("name", "")
        if name in acceptable and isinstance(tool.get("inputSchema"), dict):
            # Do not fetch untrusted remote schema references.
            if '"$ref"' in __import__("json").dumps(tool["inputSchema"]):
                raise ValueError("External or complex tool $ref schemas are not enabled in STAR v0.1")
            Draft202012Validator.check_schema(tool["inputSchema"])
            if name in registry:
                raise ValueError("Duplicate tool name")
            registry[name] = tool
    return registry


def enforce(name: str, arguments: Any, registry: dict, studio_id: str, may_edit: bool, allow_luau: bool = False) -> None:
    if name not in registry or not isinstance(arguments, dict):
        raise ValueError("Unapproved or malformed MCP tool call")
    Draft202012Validator(registry[name]["inputSchema"]).validate(arguments)
    if name != "list_roblox_studios" and (not studio_id or arguments.get("studio_id") != studio_id):
        raise ValueError("Target does not match STAR_STUDIO_ID")
    if name in EDIT_TOOLS | HIGH_RISK_TOOLS and not may_edit:
        raise ValueError("Writing is disabled for this run")
    if name == "execute_luau" and not allow_luau:
        raise ValueError("Full Luau execution must be explicitly enabled for a disposable place")
    if name == "execute_luau" and arguments.get("datamodel_type") != "Edit":
        raise ValueError("Luau execution is only allowed in the selected Edit DataModel")
    if name == "screen_capture" and not may_edit:
        if set(arguments) - {"studio_id", "datamodel_type"}:
            raise ValueError("Camera changes require edit mode")
