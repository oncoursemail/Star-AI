"""Check STAR's own local MCP discovery or run its bounded build loop in a selected unsaved blank.

Prepare: open Roblox Studio, File > New > Baseplate (do not publish it), and make sure the Studio MCP
server is enabled (Assistant > Manage MCP Servers > Enable Studio as MCP server). Then:

    python scripts/studio_live_loop.py
    python scripts/studio_live_loop.py --edit --studio <exact-id> --state-dir <absolute-directory>
    python scripts/studio_live_loop.py --edit --studio <exact-id> --state-dir <absolute-directory> --undo

Discovery is read-only and selects no instance. Edits require an exact host-selected instance and
an explicit persistent state directory for the uncertainty ledger. This command constructs fresh
settings; it does not load the app profile. Only blank unsaved targets are allowed; it never saves
or publishes. Required screenshots must succeed before editing. The bounded loop builds, observes
a planted error, fixes it, then reports actual outcomes. Edits remain by default. --undo requests
guarded host recovery, but Assistant-owned creation/Luau history requires manual Studio review:
neither complete automatic rollback nor removal of every built object is promised.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from star import studio_loop  # noqa: E402
from star import local_mcp  # noqa: E402
from star.desktop_core import Settings  # noqa: E402
from star.studio import StudioTransportError  # noqa: E402

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


def wait_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("--wait must be a finite number from 0 through 30") from None
    if not math.isfinite(seconds) or not 0 <= seconds <= 30:
        raise argparse.ArgumentTypeError("--wait must be a finite number from 0 through 30")
    return seconds


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--edit", action="store_true", help="build, playtest and fix in a selected blank unsaved target; retain edits by default")
    parser.add_argument("--undo", action="store_true", help="explicitly request guarded host recovery; connector-owned history may require manual review")
    parser.add_argument("--studio", default="", help="exact instance ID from discovery, required with --edit; no first-instance fallback")
    parser.add_argument("--state-dir", type=Path, help="absolute persistent directory required with --edit; stores the uncertainty ledger")
    parser.add_argument("--target", choices=("local_pc", "host_launcher"), default="local_pc",
                        help="this PC by default, or the explicitly configured host practice launcher")
    parser.add_argument("--wait", type=wait_seconds, default=6.0, help="finite playtest settling seconds from 0 through 30 (default: 6)")
    return parser


def validate_arguments(arguments):
    if arguments.target not in {"local_pc", "host_launcher"}:
        raise ValueError("choose local_pc or host_launcher")
    if not math.isfinite(arguments.wait) or not 0 <= arguments.wait <= 30:
        raise ValueError("--wait must be a finite number from 0 through 30")
    if arguments.edit:
        if not arguments.studio or arguments.studio != arguments.studio.strip():
            raise ValueError("--edit requires --studio with an exact instance ID")
        if arguments.state_dir is None or not arguments.state_dir.is_absolute():
            raise ValueError("--edit requires --state-dir with an absolute persistent directory")
    elif arguments.studio or arguments.undo:
        raise ValueError("--studio and --undo require --edit; discovery does not select an instance")


def parse_arguments(argv=None):
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        validate_arguments(arguments)
    except ValueError as error:
        parser.error(str(error))
    return arguments


async def main(arguments) -> int:
    validate_arguments(arguments)
    settings = Settings(studio_target=arguments.target, studio_id=arguments.studio,
                        studio_edit=arguments.edit, studio_luau=arguments.edit,
                        studio_own_places=False)
    try:
        if not arguments.edit:
            status = await local_mcp.discover(target=settings.studio_target)
            print(json.dumps(status, indent=1, default=str))
            print("Discovery only: no instance selected or edited. Rerun with --edit, --studio and --state-dir for a blank-only check.")
            return 0 if status.get("studios") else 2
        async with local_mcp.connect_studio(settings, arguments.state_dir) as guarded:
            print("place:", json.dumps(guarded.verdict.public()))
            identity = guarded.verdict.identity
            if not guarded.verdict.editable or guarded.verdict.kind != "blank" or identity is None \
                    or identity.place_id != 0 or identity.game_id != 0:
                print("Refusing to edit: this check only builds in a blank, unsaved target.")
                return 3

            async def settle():
                await asyncio.sleep(arguments.wait)

            if arguments.undo:
                print("Guarded recovery requested. Assistant-owned creations/Luau may remain for manual Studio history review; complete rollback is not promised.")
            else:
                print("Edits will be retained. Inspect the change journal; connector-owned history may require manual recovery.")
            report = await studio_loop.run_build_loop(
                guarded, scripts=[{"path": SCRIPT, "class_name": "Script", "source": BROKEN}], luau_edits=[BUILD],
                fix=lambda errors: [{"path": SCRIPT, "class_name": "Script", "source": FIXED}],
                settle=settle, undo_at_end=arguments.undo)
            print(json.dumps(report, indent=1, default=str))
            return 0 if report["ok"] else 1
    except StudioTransportError as error:
        print(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(parse_arguments())))
