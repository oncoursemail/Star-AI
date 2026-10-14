"""No per-tool prompts. Tool permission enforcement remains in code.

The Studio connector's tool list is discovered at runtime (star/studio.py). Only names classified
here are ever offered to a model; a tool this file does not know is reported and left out.
"""
from typing import Any
from ._lazy import lazy_attr
Draft202012Validator = lazy_attr("jsonschema", "Draft202012Validator")  # loaded on first validation

READ_TOOLS = frozenset({
    "list_roblox_studios", "get_studio_state", "search_game_tree", "inspect_instance",
    "script_read", "script_search", "script_grep", "get_console_output", "screen_capture",
    "search_asset", "skill", "http_get",
})
EDIT_TOOLS = frozenset({"multi_edit", "start_stop_play"})
# Drive a running playtest (walk, press keys, click). Nothing is saved, but they act in the place.
PLAYTEST_TOOLS = frozenset({"character_navigation", "user_keyboard_input", "user_mouse_input"})
# Full execute_luau is an unrestricted code execution primitive inside Studio.
# A model cannot make it safe by promising to use a particular instance path.
HIGH_RISK_TOOLS = frozenset({"execute_luau"})
# Known connector tools STAR never offers: they use the account's generation quota, upload to the
# account, read local files, bring in third-party content, capture other windows or start an agent.
BLOCKED_TOOLS = frozenset({
    "insert_asset", "generate_material", "generate_mesh", "generate_procedural_model", "generate_texture",
    "segment_mesh", "store_image", "upload_image", "subagent", "wait_job_finished",
    "list_plugin_guis", "capture_plugin_gui",
})
WRITE_TOOLS = EDIT_TOOLS | PLAYTEST_TOOLS | HIGH_RISK_TOOLS


def classify(discovered: list[dict]) -> dict[str, list[str]]:
    """Sort what the connector offers today. `unknown` is new to STAR and stays unused."""
    groups: dict[str, list[str]] = {"read": [], "edit": [], "playtest": [], "luau": [], "blocked": [], "unknown": []}
    for tool in discovered:
        name = tool.get("name", "") if isinstance(tool, dict) else ""
        group = ("read" if name in READ_TOOLS else "edit" if name in EDIT_TOOLS else
                 "playtest" if name in PLAYTEST_TOOLS else "luau" if name in HIGH_RISK_TOOLS else
                 "blocked" if name in BLOCKED_TOOLS else "unknown")
        groups[group].append(str(name))
    return {group: sorted(names) for group, names in groups.items()}


def _validate_schema(schema) -> None:
    """Apply the transport's bounded, reference-free schema check at every boundary."""
    from .studio import StudioTransportError, validate_tool_schema
    try:
        validate_tool_schema(schema)
    except StudioTransportError:
        raise ValueError("Unsafe or invalid MCP tool schema") from None


def allowed_registry(discovered: list[dict], may_edit: bool, allow_luau: bool = False) -> dict[str, dict]:
    if allow_luau and not may_edit:
        raise ValueError("Arbitrary Luau execution requires sandbox edit mode")
    acceptable = (READ_TOOLS | (EDIT_TOOLS | PLAYTEST_TOOLS if may_edit else frozenset())
                  | (HIGH_RISK_TOOLS if allow_luau else frozenset()))
    registry = {}
    for tool in discovered:
        name = tool.get("name", "")
        if name in acceptable and isinstance(tool.get("inputSchema"), dict):
            _validate_schema(tool["inputSchema"])
            if name in registry:
                raise ValueError("Duplicate tool name")
            registry[name] = tool
    return registry


def enforce(name: str, arguments: Any, registry: dict, studio_id: str, may_edit: bool, allow_luau: bool = False) -> None:
    if name not in registry or not isinstance(arguments, dict):
        raise ValueError("Unapproved or malformed MCP tool call")
    if name != "list_roblox_studios" and (not studio_id or arguments.get("studio_id") != studio_id):
        raise ValueError("Target does not match STAR_STUDIO_ID")
    if name in WRITE_TOOLS and not may_edit:
        raise ValueError("Writing is disabled for this run")
    if name == "execute_luau" and not allow_luau:
        raise ValueError("Full Luau execution must be explicitly enabled for a disposable place")
    if name == "execute_luau" and arguments.get("datamodel_type") != "Edit":
        raise ValueError("Luau execution is only allowed in the selected Edit DataModel")
    if name == "screen_capture" and not may_edit:
        # The connector requires capture_id (a label for the picture); moving the camera is an edit.
        if set(arguments) - {"studio_id", "datamodel_type", "capture_id"}:
            raise ValueError("Camera changes require edit mode")
    # Registries can be supplied directly or changed after discovery. Check again
    # before argument validation can resolve any untrusted schema reference.
    schema = registry[name].get("inputSchema") if isinstance(registry[name], dict) else None
    _validate_schema(schema)
    Draft202012Validator(schema).validate(arguments)
