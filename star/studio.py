"""Roblox Studio's official local MCP launcher (Windows), or the owner's own launcher for a Studio elsewhere."""
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

# The owner's launcher for a Studio that is not on this PC, for example one reached over SSH:
# a JSON list, program first, e.g. ["ssh", "-o", "BatchMode=yes", "<host>", "<launcher script>"].
# It must speak the Studio connector's MCP over standard input and output. Read from the process
# environment only: a model, a project file or a tool result cannot set it.
COMMAND_ENV = "STAR_STUDIO_MCP_COMMAND"


def custom_launcher():
    """(program, arguments) from STAR_STUDIO_MCP_COMMAND, or None when it is not set."""
    raw = os.environ.get(COMMAND_ENV, "").strip()
    if not raw:
        return None
    try:
        parts = json.loads(raw)
    except ValueError:
        parts = None
    if (not isinstance(parts, list) or not 1 <= len(parts) <= 40
            or any(not isinstance(part, str) or not part or "\x00" in part or len(part) > 500 for part in parts)):
        raise RuntimeError(f"{COMMAND_ENV} must be a JSON list of strings: the program, then its arguments")
    return parts[0], parts[1:]


def launcher():
    custom = custom_launcher()
    if custom:
        return custom[0], custom[1], None
    if sys.platform != "win32":
        raise RuntimeError("This STAR starter targets Windows 11 for Roblox Studio. For a Studio on another "
                           f"machine set {COMMAND_ENV}.")
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
    if path is not None and not path.is_file():
        raise RuntimeError("Roblox Studio MCP launcher is missing. Enable Studio MCP and update Studio.")
    safe_vars = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"}
    if path is None:
        # A remote launcher is usually ssh: it needs the home folder for its key and known hosts.
        safe_vars |= {"HOME", "SSH_AUTH_SOCK"}
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
