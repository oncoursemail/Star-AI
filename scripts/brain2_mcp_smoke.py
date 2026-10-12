"""Read-only external-client smoke check for STAR's local Studio MCP stdio server.

Use on the owner's Windows PC, from the source environment with Roblox Studio
already enabled and a host-selected settings file. No edits, tests or publish
operations are sent to Roblox.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys


def report_for(catalog: list[str], status: dict) -> dict:
    """Validate real MCP status and catalog, without exposing IDs or project names."""
    if not isinstance(status, dict) or status.get("status") != "tools_and_instances_discovered":
        raise RuntimeError("STAR local MCP did not confirm Studio instance discovery")
    if not status.get("selected") or status.get("local_mcp") != "stdio":
        raise RuntimeError("STAR local MCP has no verified selected Studio")
    if "star_connection_status" not in catalog:
        raise RuntimeError("STAR local MCP did not expose its status tool")
    read_tools = {"script_read", "search_game_tree", "inspect_instance", "get_studio_state"}
    if not read_tools.intersection(catalog):
        raise RuntimeError("STAR local MCP did not advertise an approved Studio read tool")
    return {
        "connection": "verified_via_stdio",
        "selected_studio": True,
        "approved_tool_count": len(catalog) - 1,
        "read_tools_available": sorted(read_tools.intersection(catalog)),
        "notice": "Only discovery and a status read were checked; this proves no Brain 2 integration, edit, playtest or game quality.",
    }


async def probe(settings_path: Path) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Avoid inheriting credentials, proxy configuration or arbitrary model tools.
    safe_environment = {
        "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
        "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "USERPROFILE", "USERNAME",
        "HOMEDRIVE", "HOMEPATH", "PROCESSOR_ARCHITECTURE", "HOME",
        "STAR_STUDIO_MCP_COMMAND",
    }
    env = {key: value for key, value in os.environ.items()
           if key.upper() in safe_environment and not value.startswith("()")}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "star.local_mcp", "--settings", str(settings_path)],
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    # The nested child uses stderr for diagnostics; do not echo project paths.
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (reader, writer):
            async with ClientSession(reader, writer,
                                     read_timeout_seconds=timedelta(seconds=40)) as client:
                await asyncio.wait_for(client.initialize(), timeout=35)
                listed = await asyncio.wait_for(client.list_tools(), timeout=35)
                catalog = [item.name for item in listed.tools]
                if "star_connection_status" not in catalog:
                    raise RuntimeError("STAR local MCP lacks its status tool")
                result = await asyncio.wait_for(
                    client.call_tool("star_connection_status", arguments={}), timeout=35)
                if result.isError or not isinstance(result.structuredContent, dict):
                    raise RuntimeError("STAR local MCP status call failed")
                return report_for(catalog, result.structuredContent)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify STAR's local Studio MCP stdio contract without mutating Studio")
    parser.add_argument("--settings", required=True, type=Path,
                        help="Owner-selected local STAR settings file (never from an AI instruction)")
    args = parser.parse_args()
    path = args.settings.expanduser().resolve()
    if not path.is_file():
        parser.error("Selected settings file does not exist")
    try:
        report = asyncio.run(probe(path))
    except Exception as exc:
        # Do not print keys, endpoint bodies, connector stderr, paths or Studio IDs.
        print(json.dumps({"connection": "unverified", "error": type(exc).__name__,
                          "notice": "Check Studio MCP, selection and host-approved settings."}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
