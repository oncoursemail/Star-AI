"""Roblox Studio's official local MCP launcher (Windows)."""
from contextlib import asynccontextmanager
from datetime import timedelta
import os
from pathlib import Path
import sys


def launcher():
    if sys.platform != "win32":
        raise RuntimeError("This STAR starter targets Windows 11 for Roblox Studio")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is not set")
    path = Path(local) / "Roblox" / "mcp.bat"
    return "cmd.exe", ["/d", "/c", str(path)], path


@asynccontextmanager
async def connect():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    command, args, path = launcher()
    if not path.is_file():
        raise RuntimeError("Roblox Studio MCP launcher is missing. Enable Studio MCP and update Studio.")
    safe_vars = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"}
    env = {k: v for k, v in os.environ.items() if k.upper() in safe_vars}
    params = StdioServerParameters(command=command, args=args, env=env)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=120)) as client:
            await client.initialize()
            yield client


async def list_tools(client):
    results = []
    cursor = None
    visited = set()
    for _ in range(20):
        response = await client.list_tools(cursor=cursor)
        results.extend(x.model_dump(by_alias=True, exclude_none=True) for x in response.tools)
        cursor = getattr(response, "nextCursor", None)
        if not cursor:
            return results
        if cursor in visited:
            raise RuntimeError("Repeated MCP tool-list cursor")
        visited.add(cursor)
    raise RuntimeError("MCP tool-list pagination limit")
