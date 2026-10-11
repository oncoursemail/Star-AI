"""Roblox Studio's official local MCP launcher (Windows), or the owner's own launcher for a Studio elsewhere."""
from contextlib import asynccontextmanager
from datetime import timedelta
import asyncio
import json
import os
from pathlib import Path
import sys

# The owner's launcher for a Studio that is not on this PC, for example one reached over SSH:
# a JSON list, program first, e.g. ["ssh", "-o", "BatchMode=yes", "<host>", "<launcher script>"].
# It must speak the Studio connector's MCP over standard input and output. Read from the process
# environment only: a model, a project file or a tool result cannot set it.
COMMAND_ENV = "STAR_STUDIO_MCP_COMMAND"
INITIALIZE_SECONDS = 30
DISCOVERY_SECONDS = 20
INSTANCE_SECONDS = 15
MAX_TOOLS = 128
MAX_TOOL_BYTES = 64_000
MAX_DISCOVERY_BYTES = 256_000
MAX_INSTANCE_BYTES = 16_000
MAX_SCHEMA_NODES = 4_000
MAX_SCHEMA_DEPTH = 32


class StudioTransportError(RuntimeError):
    """A public diagnostic containing no launcher arguments or server-provided text."""


class StudioNoInstancesError(StudioTransportError):
    """Tool discovery responded but there is no connected Studio to select."""
    tool_count = 0


def _identifier(value, limit=200):
    return (isinstance(value, str) and 0 < len(value) <= limit and value.strip() == value
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _route_message(path, stage, *, timeout=False):
    route = "local Windows launcher" if path is not None else "host-defined custom launcher"
    hint = ("Open the intended Studio and enable its official MCP server."
            if path is not None else
            "Verify the host-approved command, remote Studio listener and safe launcher; no fallback was attempted.")
    return f"Studio MCP {route}: {stage} {'timed out' if timeout else 'failed'}. {hint}"


def _errors(error):
    """The SDK's AnyIO task groups wrap request and cleanup failures."""
    if isinstance(error, BaseExceptionGroup):
        return [leaf for child in error.exceptions for leaf in _errors(child)]
    return [error]


def custom_launcher():
    """(program, arguments) from STAR_STUDIO_MCP_COMMAND, or None when it is not set."""
    raw = os.environ.get(COMMAND_ENV, "").strip()
    if not raw:
        return None
    if len(raw) > 22_000:
        raise RuntimeError(f"{COMMAND_ENV} must be a bounded JSON list of strings")
    try:
        parts = json.loads(raw)
    except ValueError:
        parts = None
    if (not isinstance(parts, list) or not 1 <= len(parts) <= 40
            or any(not isinstance(part, str) or not part or len(part) > 500
                   or any(ord(c) < 32 or ord(c) == 127 for c in part) for part in parts)
            or not parts[0].strip()):
        raise RuntimeError(f"{COMMAND_ENV} must be a JSON list of strings: the program, then its arguments")
    return parts[0], parts[1:]


def launcher(target=None):
    """An explicit host-selected route wins over legacy environment inference."""
    if target not in (None, "local_pc", "host_launcher"):
        raise StudioTransportError("Unknown Studio connection target; choose local_pc or host_launcher.")
    if target != "local_pc":
        custom = custom_launcher()
        if custom:
            return custom[0], custom[1], None
        if target == "host_launcher":
            raise StudioTransportError("The host-defined Studio launcher is not configured; no local fallback was attempted.")
    if sys.platform != "win32":
        raise RuntimeError("This STAR starter targets Windows 11 for Roblox Studio. For a Studio on another "
                           f"machine set {COMMAND_ENV}.")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is not set")
    path = Path(local) / "Roblox" / "mcp.bat"
    return "cmd.exe", ["/d", "/c", str(path)], path


@asynccontextmanager
async def connect(*, target=None):
    """Initialize a transport, not a health claim. Discover tools/instances separately.

    MCP SDK context managers stay in their owning task; only the request is timed.
    SDK cleanup terminates its local child tree, not necessarily a remote SSH child.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.shared.exceptions import McpError
    command, args, path = launcher(target)
    if path is not None and not path.is_file():
        raise RuntimeError("Roblox Studio MCP launcher is missing. Enable Studio MCP and update Studio.")
    safe_vars = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP",
                 "LOCALAPPDATA", "APPDATA", "USERPROFILE", "USERNAME", "HOMEDRIVE", "HOMEPATH",
                 "PROCESSOR_ARCHITECTURE"}
    if path is None:
        # A remote launcher is usually ssh: it needs the home folder for its key and known hosts.
        safe_vars |= {"HOME", "SSH_AUTH_SOCK"}
    # The SDK merges its own fixed safe defaults; do not pass ambient provider keys,
    # the custom command itself, or shell-function definitions to the child.
    env = {k: v for k, v in os.environ.items() if k.upper() in safe_vars and not v.startswith("()")}
    params = StdioServerParameters(command=command, args=list(args), env=dict(env),
                                   cwd=path.parent if path is not None else None)
    stage, caller_error = "process startup", None
    try:
        # A launcher can print host names, authentication errors and command arguments.
        # Keep its raw stderr out of public app diagnostics; expose our bounded errors.
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=120)) as client:
                    stage = "protocol initialization"
                    reply = await asyncio.wait_for(client.initialize(), timeout=INITIALIZE_SECONDS)
                    if getattr(getattr(reply, "capabilities", None), "tools", None) is None:
                        raise StudioTransportError("Studio MCP initialized without a tools capability; Studio tool health is unverified.")
                    stage = "transport shutdown"
                    try:
                        yield client
                    except BaseException as exc:
                        caller_error = exc
                        raise
    except Exception as exc:
        errors = _errors(exc)
        if caller_error is not None and all(error is caller_error for error in errors):
            if isinstance(caller_error, McpError):
                raise StudioTransportError(_route_message(path, "MCP request")) from None
            raise caller_error from None
        if all(isinstance(error, StudioTransportError) for error in errors):
            raise errors[0] from None
        raise StudioTransportError(_route_message(path, stage,
            timeout=any(isinstance(error, TimeoutError) for error in errors))) from None


async def list_tools(client):
    """Bound all pages together; a protocol handshake with zero tools is not healthy."""
    try:
        return await asyncio.wait_for(_discover_tools(client), timeout=DISCOVERY_SECONDS)
    except StudioTransportError:
        raise
    except TimeoutError:
        raise StudioTransportError("Studio MCP tool discovery timed out; Studio tool health is unverified.") from None
    except Exception:
        raise StudioTransportError("Studio MCP tool discovery failed; verify the Studio listener and connector.") from None


async def _discover_tools(client):
    results = []
    cursor = None
    visited = set()
    names, total = set(), 0
    for _ in range(20):
        response = await client.list_tools(cursor=cursor)
        page = response.tools
        if not isinstance(page, list) or len(page) + len(results) > MAX_TOOLS:
            raise StudioTransportError("Studio MCP tool count exceeds the discovery bound or the list is invalid.")
        for item in page:
            tool = item.model_dump(by_alias=True, exclude_none=True)
            if not isinstance(tool, dict) or not _identifier(tool.get("name"), 128):
                raise StudioTransportError("Studio MCP returned an invalid tool definition.")
            if tool["name"] in names:
                raise StudioTransportError("Studio MCP returned duplicate tool names; discovery is ambiguous.")
            for key in ("inputSchema", "outputSchema"):
                schema = tool.get(key)
                if key == "outputSchema" and schema is None:
                    continue
                validate_tool_schema(schema, input_schema=key == "inputSchema")
            size = _json_bytes(tool)
            total += size
            if size > MAX_TOOL_BYTES or total > MAX_DISCOVERY_BYTES:
                raise StudioTransportError("Studio MCP tool definitions exceed the discovery size bound.")
            names.add(tool["name"])
            results.append(tool)
        cursor = getattr(response, "nextCursor", None)
        if cursor is None or cursor == "":
            if not results:
                raise StudioTransportError("Studio MCP initialized but exposes zero tools; enable the Studio MCP server and verify its listener.")
            return results
        if not _identifier(cursor, 512):
            raise StudioTransportError("Studio MCP returned an invalid tool-list cursor.")
        if cursor in visited:
            raise StudioTransportError("Repeated MCP tool-list cursor")
        visited.add(cursor)
    raise StudioTransportError("MCP tool-list pagination limit")


def _schema_bounds(schema):
    """Expected Studio schemas are self-contained; never resolve external refs."""
    if not isinstance(schema, dict):
        raise StudioTransportError("Studio MCP returned an invalid tool schema.")
    stack, nodes = [(schema, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_SCHEMA_NODES or depth > MAX_SCHEMA_DEPTH:
            raise StudioTransportError("Studio MCP tool schema exceeds its complexity bound.")
        if isinstance(item, dict):
            if any(key in item for key in ("$ref", "$dynamicRef", "$recursiveRef")):
                raise StudioTransportError("Studio MCP schema references are unsupported; no resource lookup is allowed.")
            stack.extend((value, depth + 1) for value in item.values())
        elif isinstance(item, list):
            stack.extend((value, depth + 1) for value in item)


def validate_tool_schema(schema, *, input_schema=True):
    """Validate a bounded self-contained Studio schema without resolving resources.

    Host bridges use this same check before registering tools, even when their
    catalog did not pass through transport discovery. No schema is executed here.
    """
    from jsonschema import Draft202012Validator
    from jsonschema.validators import validator_for
    _schema_bounds(schema)
    if input_schema and schema.get("type") not in (None, "object"):
        raise StudioTransportError("Studio MCP returned an invalid tool schema: input must accept an argument object.")
    try:
        if _json_bytes(schema) > MAX_TOOL_BYTES:
            raise StudioTransportError("Studio MCP tool schema exceeds its size bound.")
        validator_for(schema, default=Draft202012Validator).check_schema(schema)
    except StudioTransportError:
        raise
    except Exception:
        raise StudioTransportError("Studio MCP returned an invalid tool schema.") from None


def _validate_studios(items):
    if isinstance(items, list) and not items:
        raise StudioNoInstancesError("The Studio MCP connector answered, but there are no connected Studios. Open a place and enable its MCP server.")
    if not isinstance(items, list) or not 1 <= len(items) <= 32:
        raise StudioTransportError("Studio MCP returned no connected Studios or an invalid instance list.")
    result, ids = [], set()
    for item in items:
        if (not isinstance(item, dict) or not _identifier(item.get("id"))
                or not isinstance(item.get("name"), str) or len(item["name"]) > 200
                or any(ord(c) < 32 or ord(c) == 127 for c in item["name"])):
            raise StudioTransportError("Studio MCP returned an invalid Studio instance.")
        if item["id"] in ids:
            raise StudioTransportError("Studio MCP returned duplicate Studio instance ids.")
        ids.add(item["id"])
        result.append({"id": item["id"], "name": item["name"]})
    return result


def parse_studios(result):
    """Validate the connector's existing {studios: [{id, name}]} result contract."""
    try:
        data = result.model_dump(by_alias=True, exclude_none=True) if hasattr(result, "model_dump") else result
        if (not isinstance(data, dict) or _json_bytes(data) > MAX_INSTANCE_BYTES
                or data.get("isError") is not None and data.get("isError") is not False):
            raise StudioTransportError("Studio MCP instance discovery failed or exceeds its response bound.")
        parts = data.get("content", [])
        if not isinstance(parts, list) or len(parts) > 16:
            raise StudioTransportError("Studio MCP returned invalid instance discovery content.")
        text = "\n".join(p["text"] for p in parts if isinstance(p, dict) and p.get("type") == "text"
                         and isinstance(p.get("text"), str))
        textual = json.loads(text) if text.strip() else None
        structured = data.get("structuredContent")
        source = structured if structured is not None else textual
        if not isinstance(source, dict):
            raise StudioTransportError("Studio MCP returned invalid instance discovery content.")
        items = _validate_studios(source.get("studios"))
        if structured is not None and textual is not None:
            if not isinstance(textual, dict) or _validate_studios(textual.get("studios")) != items:
                raise StudioTransportError("Studio MCP instance discovery representations disagree.")
        return items
    except StudioTransportError:
        raise
    except Exception:
        raise StudioTransportError("Studio MCP returned invalid instance discovery content.") from None


def select_studio(instances, studio_id):
    """Never silently select the first Studio when a requested id is missing."""
    items = _validate_studios(instances)
    if not _identifier(studio_id):
        raise StudioTransportError("Select a Studio instance explicitly before using its tools.")
    selected = next((item for item in items if item["id"] == studio_id), None)
    if selected is None:
        raise StudioTransportError("The selected Studio instance is not connected; no other instance was selected.")
    return selected


async def probe(client=None, *, studio_id=None, target=None):
    """Read-only discovery, not edit permission, responsiveness or build acceptance.

    Supplying an open client never launches a second connector. Without a client,
    the explicit host target is used; None retains legacy environment behavior.
    """
    if target not in (None, "local_pc", "host_launcher"):
        raise StudioTransportError("Unknown Studio connection target; choose local_pc or host_launcher.")
    if client is None:
        async with connect(target=target) as connected:
            return await probe(connected, studio_id=studio_id)
    tools = await list_tools(client)
    if "list_roblox_studios" not in {tool["name"] for tool in tools}:
        raise StudioTransportError("Studio MCP does not expose instance discovery; Studio health is unverified.")
    try:
        reply = await asyncio.wait_for(client.call_tool("list_roblox_studios", arguments={}), timeout=INSTANCE_SECONDS)
    except TimeoutError:
        raise StudioTransportError("Studio MCP instance discovery timed out.") from None
    except Exception:
        raise StudioTransportError("Studio MCP instance discovery failed.") from None
    try:
        instances = parse_studios(reply)
    except StudioNoInstancesError as error:
        error.tool_count = len(tools)
        raise
    selected = select_studio(instances, studio_id) if studio_id is not None else None
    return {"status": "tools_and_instances_discovered", "tool_count": len(tools),
            "studios": instances, "selected": selected}
