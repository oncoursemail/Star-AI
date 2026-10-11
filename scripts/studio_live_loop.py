"""The live check of STAR's Studio build loop, against a real Roblox Studio through the official MCP connector.

Prepare: open Roblox Studio, File > New > Baseplate (do not publish it), and make sure the Studio MCP
server is enabled (Studio settings > MCP). Then:

    python scripts/studio_live_loop.py                # reads only: instances, place identity, tree, screenshot
    python scripts/studio_live_loop.py --edit         # the full loop, in a blank unsaved Baseplate only
    python scripts/studio_live_loop.py --edit --keep  # ...and leave what was built (default: undo at the end)

The sandbox rule is the one the app uses (star/studio_loop.py): with --edit the script still refuses
any place that is not a blank, unsaved place. It never saves and never publishes. Expected result of
--edit: every step "ok", the first playtest shows the planted error, the second playtest is clean,
three edits are reported, and after the undo the script and the two parts are gone again.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from star import studio_loop  # noqa: E402
from star.policy import classify  # noqa: E402
from star.studio import connect, list_tools  # noqa: E402

BROKEN = """-- Made by STAR's live check. Safe to delete.
local part = workspace:FindFirstChild("StarCheckDoor")
print("STAR check: door is", part.Name)
print("STAR check: opening", workspace.StarCheckMissing.Name)
"""
FIXED = """-- Made by STAR's live check. Safe to delete.
local part = workspace:FindFirstChild("StarCheckDoor")
print("STAR check: door is", part and part.Name)
print("STAR check: ready")
"""
BUILD = """local door = Instance.new("Part")
door.Name = "StarCheckDoor"
door.Anchored = true
door.Size = Vector3.new(6, 8, 1)
door.Position = Vector3.new(0, 4, -20)
door.Parent = workspace
local sign = Instance.new("Part")
sign.Name = "StarCheckSign"
sign.Anchored = true
sign.Size = Vector3.new(4, 2, 1)
sign.Position = Vector3.new(0, 10, -20)
sign.Parent = workspace
return "built"
"""
SCRIPT = "ServerScriptService.StarCheck"


async def main(arguments) -> int:
    async with connect() as session:
        discovered = await list_tools(session)
        groups = classify(discovered)
        print("connector tools:", json.dumps({group: len(names) for group, names in groups.items()}),
              "| new to STAR:", groups["unknown"])
        listed = studio_loop.studios(await session.call_tool("list_roblox_studios", arguments={}))
        print("studio instances:", json.dumps(listed))
        if not listed:
            print("No Studio instance is connected. Open Studio with a new Baseplate and enable its MCP server.")
            return 2
        chosen = next((item for item in listed if item["id"] == arguments.studio), listed[0])
        guarded = await studio_loop.open_guarded(session, discovered, studio_id=chosen["id"],
                                                 opted_in=arguments.edit)
        print("place:", json.dumps(guarded.verdict.public()))
        if arguments.edit and guarded.verdict.kind != "blank":
            print("Refusing to edit: this check only builds in a blank, unsaved Baseplate.")
            return 3

        async def settle():
            await asyncio.sleep(arguments.wait)

        report = await studio_loop.run_build_loop(
            guarded, scripts=[{"path": SCRIPT, "class_name": "Script", "source": BROKEN}], luau_edits=[BUILD],
            fix=lambda errors: [{"path": SCRIPT, "class_name": "Script", "source": FIXED}],
            settle=settle, undo_at_end=arguments.edit and not arguments.keep)
        print(json.dumps(report, indent=1, default=str))
        return 0 if (report["ok"] or not arguments.edit) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--edit", action="store_true", help="build, playtest, fix and undo in a blank Baseplate")
    parser.add_argument("--keep", action="store_true", help="do not undo at the end")
    parser.add_argument("--studio", default="", help="instance id from the list (default: the first)")
    parser.add_argument("--wait", type=float, default=6.0, help="seconds to let a playtest run")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
