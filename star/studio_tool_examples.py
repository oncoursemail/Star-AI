"""Opt-in example calls for the Studio connector's tools (setting `studio_tool_examples`).

Small models copy the shape of a worked call far more reliably than they follow a schema: the
usual misses are a missing `studio_id`, a `datamodel_type` STAR refuses, or a dotted path in the
wrong form. One fixed example per error-prone tool is appended to the connector's own
description. The text is constant, so the tool list stays byte-identical from turn to turn (the
prompt cache is unaffected). Permissions are still decided only in `star/policy.py`.
"""
from __future__ import annotations

import json

EXAMPLE_STUDIO_ID = "STUDIO_ID"
_NOTE = f" ({EXAMPLE_STUDIO_ID} = the Selected studio_id from the context)"

# Each value is the exact JSON the model should imitate; keys must be arguments of the real tool.
TOOL_EXAMPLES: dict[str, str] = {
    "search_game_tree": '{"studio_id": "STUDIO_ID", "datamodel_type": "Edit", "path": "Workspace", "max_depth": 2}',
    "inspect_instance": '{"studio_id": "STUDIO_ID", "path": "Workspace.SpawnLocation"}',
    "script_read": '{"studio_id": "STUDIO_ID", "target_file": "game.ServerScriptService.Main"}',
    "script_search": '{"studio_id": "STUDIO_ID", "keywords": "shop, coins"}',
    "script_grep": '{"studio_id": "STUDIO_ID", "query": "RemoteEvent"}',
    "get_console_output": '{"studio_id": "STUDIO_ID"}',
    "screen_capture": '{"studio_id": "STUDIO_ID", "capture_id": "ScreenCapture_1"}',
    "multi_edit": ('{"studio_id": "STUDIO_ID", "datamodel_type": "Edit", "file_path": "game.ServerScriptService.Main", '
                   '"edits": [{"old_string": "local SPEED = 16", "new_string": "local SPEED = 24"}]}'),
    "start_stop_play": '{"studio_id": "STUDIO_ID", "is_start": true}',
    "execute_luau": ('{"studio_id": "STUDIO_ID", "datamodel_type": "Edit", "code": '
                     '"local part = Instance.new(\\"Part\\")\\npart.Anchored = true\\n'
                     'part.Position = Vector3.new(0, 5, 0)\\npart.Parent = workspace\\nreturn part:GetFullName()"}'),
}


def with_examples(discovered: list[dict]) -> list[dict]:
    """Copies of the tools with one example appended; the input list is not changed.

    An example is added only when every argument it names is still in the tool's schema, so a
    connector update that renames an argument drops the example instead of teaching a wrong call.
    """
    result = []
    for tool in discovered:
        example = TOOL_EXAMPLES.get(tool.get("name", "")) if isinstance(tool, dict) else None
        schema = tool.get("inputSchema") if example else None
        properties = schema.get("properties") if isinstance(schema, dict) else None
        if example and isinstance(properties, dict) and set(json.loads(example)) <= set(properties):
            tool = {**tool, "description": f"{tool.get('description', '')}\n\nExample call in STAR: {example}{_NOTE}"}
        result.append(tool)
    return result
