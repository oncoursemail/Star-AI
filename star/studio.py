"""Roblox Studio's official local MCP launcher (Windows), or the owner's own launcher for a Studio elsewhere."""
from contextlib import asynccontextmanager
from datetime import timedelta
import asyncio
import json
import os
from pathlib import Path
import stat
import sys

# The owner's launcher for a Studio that is not on this PC, for example one reached over SSH:
# a JSON list, program first, e.g. ["ssh", "-o", "BatchMode=yes", "<host>", "<launcher script>"].
# It must speak the Studio connector's MCP over standard input and output. Legacy calls read the
# process environment; the desktop also accepts a validated snapshot from its explicit operator
# data home. A model, a project file or a tool result cannot set the command.
COMMAND_ENV = "STAR_STUDIO_MCP_COMMAND"
MAX_COMMAND_BYTES = 22_000
INITIALIZE_SECONDS = 30
DISCOVERY_SECONDS = 20
INSTANCE_SECONDS = 15
INSTANCE_POLL_SECONDS = 0.25
MAX_TOOLS = 128
MAX_TOOL_BYTES = 64_000
MAX_DISCOVERY_BYTES = 256_000
MAX_INSTANCE_BYTES = 16_000
MAX_SCHEMA_NODES = 4_000
MAX_SCHEMA_DEPTH = 32


_DIAGNOSTIC_REASONS = {
    "unknown": frozenset({"connection_failed"}),
    "configuration": frozenset({"invalid", "unknown_target", "not_configured", "unsupported_platform",
                                "missing_environment", "missing_launcher"}),
    "process_startup": frozenset({"failed", "timeout"}),
    "initialization": frozenset({"failed", "timeout", "invalid_response"}),
    "capability": frozenset({"tools_not_declared"}),
    "tool_discovery": frozenset({"failed", "timeout", "invalid_catalog", "duplicate_names", "limit_exceeded",
                                 "invalid_schema", "unsupported_schema_reference", "empty_catalog",
                                 "invalid_cursor", "repeated_cursor"}),
    "instance_discovery": frozenset({"failed", "timeout", "invalid_response", "limit_exceeded",
                                     "representations_disagree", "no_instances", "tool_unavailable"}),
    "selection": frozenset({"required", "unavailable"}),
    "shutdown": frozenset({"failed", "timeout"}),
    "request": frozenset({"failed"}),
    "probe": frozenset({"timeout", "invalid_evidence"}),
}


class StudioTransportError(RuntimeError):
    """Host-authored message and fixed codes; never pass connector exception text."""

    def __init__(self, message, *, stage="unknown", reason="connection_failed"):
        if (type(stage) is not str or type(reason) is not str
                or reason not in _DIAGNOSTIC_REASONS.get(stage, ())):
            raise ValueError("Invalid Studio connection diagnostic code")
        super().__init__(message)
        self._diagnostic = (stage, reason)


def connection_diagnostic(error):
    """Copy only validated fixed codes, never arbitrary exception attributes/text."""
    if isinstance(error, StudioTransportError):
        pair = error.__dict__.get("_diagnostic")
        if (type(pair) is tuple and len(pair) == 2 and all(type(part) is str for part in pair)
                and pair[1] in _DIAGNOSTIC_REASONS.get(pair[0], ())):
            return {"stage": pair[0], "reason": pair[1]}
    return {"stage": "unknown", "reason": "connection_failed"}


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


def validate_command(parts):
    """Freeze host-only argv; no shell parsing and no public argument diagnostics."""
    if (type(parts) not in (list, tuple) or not 1 <= len(parts) <= 40
            or any(not isinstance(part, str) or not part or len(part) > 500
                   or any(ord(c) < 32 or ord(c) == 127 for c in part) for part in parts)
            or not parts[0].strip()):
        raise StudioTransportError("The host-defined Studio launcher command is invalid.", stage="configuration", reason="invalid")
    try:
        if _json_bytes(parts) > MAX_COMMAND_BYTES:
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        raise StudioTransportError("The host-defined Studio launcher command is invalid.", stage="configuration", reason="invalid") from None
    return tuple(parts)


def custom_launcher():
    """(program, arguments) from STAR_STUDIO_MCP_COMMAND, or None when it is not set."""
    raw = os.environ.get(COMMAND_ENV, "").strip()
    if not raw:
        return None
    try:
        if len(raw.encode("utf-8")) > MAX_COMMAND_BYTES:
            raise ValueError
        parts = json.loads(raw)
        if type(parts) is not list:
            raise ValueError
        command = validate_command(parts)
    except (ValueError, UnicodeError, RecursionError, StudioTransportError):
        raise StudioTransportError("The host-defined Studio launcher environment must be a bounded JSON list of strings.",
                                   stage="configuration", reason="invalid") from None
    return command[0], list(command[1:])


def _plain_file(info):
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and not getattr(info, "st_file_attributes", 0) & 0x400)


def _directory_stamp(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError
    return info.st_dev, info.st_ino


def configured_command(home=None):
    """Snapshot operator argv: environment first, then this explicit home's file.

    The file's target field never selects a route or grants permissions. Missing
    configuration is unconfigured; malformed/unreadable/linked files fail closed.
    No file is created, repaired, or disclosed to the UI/model.
    """
    try:
        profile = Path(home) if home is not None else None
        if profile is not None and (not profile.is_absolute() or ".." in profile.parts):
            raise ValueError
        # Never treat a linked ancestor as this explicit host-selected profile.
        parents, profile_exists = [], True
        if profile is not None:
            for parent in [*reversed(profile.parents), profile]:
                try:
                    parents.append((parent, _directory_stamp(parent)))
                except FileNotFoundError:
                    profile_exists = False
                    break
        custom = custom_launcher()
        if custom is not None:
            if any(_directory_stamp(parent) != stamp for parent, stamp in parents):
                raise ValueError
            return (custom[0], *custom[1])
        if profile is None or not profile_exists:
            return None
        folder = profile / "studio"
        path = folder / "remote.json"
        try:
            parents.append((folder, _directory_stamp(folder)))
        except FileNotFoundError:
            return None
        try:
            before = path.lstat()
        except FileNotFoundError:
            return None
        if not _plain_file(before) or before.st_size > MAX_COMMAND_BYTES:
            raise ValueError
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not _plain_file(opened) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError
            raw = stream.read(MAX_COMMAND_BYTES + 1)
            after = os.fstat(stream.fileno())
        if (len(raw) > MAX_COMMAND_BYTES or len(raw) != after.st_size
                or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
            raise ValueError
        if any(_directory_stamp(parent) != stamp for parent, stamp in parents):
            raise ValueError
        current = path.lstat()
        if (not _plain_file(current) or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError

        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError
                result[key] = value
            return result

        saved = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys)
        if type(saved) is not dict or "command" not in saved:
            raise ValueError
        parts = saved["command"]
        return None if type(parts) is list and not parts else validate_command(parts)
    except (OSError, ValueError, UnicodeError, RecursionError, StudioTransportError):
        raise StudioTransportError("The host-defined Studio launcher configuration is invalid or unavailable.",
                                   stage="configuration", reason="invalid") from None


def launcher(target=None, *, command=None):
    """An explicit host-selected route wins over legacy environment inference."""
    if target not in (None, "local_pc", "host_launcher"):
        raise StudioTransportError("Unknown Studio connection target; choose local_pc or host_launcher.",
                                   stage="configuration", reason="unknown_target")
    if target != "local_pc":
        if command is not None:
            if target != "host_launcher":
                raise StudioTransportError("An explicit Studio command requires the configured-host target.",
                                           stage="configuration", reason="invalid")
            argv = validate_command(command)
            return argv[0], list(argv[1:]), None
        custom = custom_launcher()
        if custom:
            return custom[0], custom[1], None
        if target == "host_launcher":
            raise StudioTransportError("The host-defined Studio launcher is not configured; no local fallback was attempted.",
                                       stage="configuration", reason="not_configured")
    if sys.platform != "win32":
        raise StudioTransportError("This STAR starter targets Windows 11 for Roblox Studio. For a Studio on another "
                                   f"machine set {COMMAND_ENV}.", stage="configuration", reason="unsupported_platform")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise StudioTransportError("LOCALAPPDATA is not set", stage="configuration", reason="missing_environment")
    path = Path(local) / "Roblox" / "mcp.bat"
    return "cmd.exe", ["/d", "/c", str(path)], path


@asynccontextmanager
async def connect(*, target=None, command=None):
    """Initialize a transport, not a health claim. Discover tools/instances separately.

    MCP SDK context managers stay in their owning task; only the request is timed.
    SDK cleanup terminates its local child tree, not necessarily a remote SSH child.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.shared.exceptions import McpError
    from pydantic import ValidationError
    try:
        program, args, path = launcher(target, command=command)
        if path is not None and not path.is_file():
            raise StudioTransportError("Roblox Studio MCP launcher is missing. Enable Studio MCP and update Studio.",
                                       stage="configuration", reason="missing_launcher")
    except StudioTransportError:
        raise
    except Exception:
        raise StudioTransportError("Studio MCP launcher configuration could not be checked.",
                                   stage="configuration", reason="invalid") from None
    safe_vars = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP",
                 "LOCALAPPDATA", "APPDATA", "USERPROFILE", "USERNAME", "HOMEDRIVE", "HOMEPATH",
                 "PROCESSOR_ARCHITECTURE"}
    if path is None:
        # A remote launcher is usually ssh: it needs the home folder for its key and known hosts.
        safe_vars |= {"HOME", "SSH_AUTH_SOCK"}
    # The SDK merges its own fixed safe defaults; do not pass ambient provider keys,
    # the custom command itself, or shell-function definitions to the child.
    env = {k: v for k, v in os.environ.items() if k.upper() in safe_vars and not v.startswith("()")}
    stage, caller_error = "process_startup", None
    try:
        params = StdioServerParameters(command=program, args=list(args), env=dict(env),
                                       cwd=path.parent if path is not None else None)
        # A launcher can print host names, authentication errors and command arguments.
        # Keep its raw stderr out of public app diagnostics; expose our bounded errors.
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=120)) as client:
                    stage = "initialization"
                    reply = await asyncio.wait_for(client.initialize(), timeout=INITIALIZE_SECONDS)
                    if getattr(getattr(reply, "capabilities", None), "tools", None) is None:
                        raise StudioTransportError("Studio MCP initialized without a tools capability; Studio tool health is unverified.",
                                                   stage="capability", reason="tools_not_declared")
                    stage = "shutdown"
                    try:
                        yield client
                    except BaseException as exc:
                        caller_error = exc
                        raise
    except Exception as exc:
        errors = _errors(exc)
        if caller_error is not None and all(error is caller_error for error in errors):
            if isinstance(caller_error, McpError):
                raise StudioTransportError(_route_message(path, "MCP request"), stage="request", reason="failed") from None
            raise caller_error from None
        if caller_error is None and all(isinstance(error, StudioTransportError) for error in errors):
            if all(error is errors[0] for error in errors):
                raise errors[0] from None
            # Different typed failures in one group have no single established phase.
            raise StudioTransportError(_route_message(path, "connection cleanup")) from None
        timeout = any(isinstance(error, TimeoutError) for error in errors)
        reason = "timeout" if timeout else "failed"
        if stage == "initialization" and all(isinstance(error, ValidationError) for error in errors):
            reason = "invalid_response"
        display = {"process_startup": "process startup", "initialization": "protocol initialization",
                   "shutdown": "transport shutdown"}[stage]
        raise StudioTransportError(_route_message(path, display, timeout=timeout), stage=stage, reason=reason) from None


async def list_tools(client):
    """Bound all pages together; a protocol handshake with zero tools is not healthy."""
    try:
        return await asyncio.wait_for(_discover_tools(client), timeout=DISCOVERY_SECONDS)
    except StudioTransportError:
        raise
    except TimeoutError:
        raise StudioTransportError("Studio MCP tool discovery timed out; Studio tool health is unverified.",
                                   stage="tool_discovery", reason="timeout") from None
    except Exception:
        raise StudioTransportError("Studio MCP tool discovery failed; verify the Studio listener and connector.",
                                   stage="tool_discovery", reason="failed") from None


async def _discover_tools(client):
    results = []
    cursor = None
    visited = set()
    names, total = set(), 0
    for _ in range(20):
        response = await client.list_tools(cursor=cursor)
        page = response.tools
        if not isinstance(page, list):
            raise StudioTransportError("Studio MCP returned an invalid tool list.", stage="tool_discovery", reason="invalid_catalog")
        if len(page) + len(results) > MAX_TOOLS:
            raise StudioTransportError("Studio MCP tool count exceeds the discovery bound or the list is invalid.",
                                       stage="tool_discovery", reason="limit_exceeded")
        for item in page:
            tool = item.model_dump(by_alias=True, exclude_none=True)
            if not isinstance(tool, dict) or not _identifier(tool.get("name"), 128):
                raise StudioTransportError("Studio MCP returned an invalid tool definition.", stage="tool_discovery", reason="invalid_catalog")
            if tool["name"] in names:
                raise StudioTransportError("Studio MCP returned duplicate tool names; discovery is ambiguous.",
                                           stage="tool_discovery", reason="duplicate_names")
            for key in ("inputSchema", "outputSchema"):
                schema = tool.get(key)
                if key == "outputSchema" and schema is None:
                    continue
                validate_tool_schema(schema, input_schema=key == "inputSchema")
            size = _json_bytes(tool)
            total += size
            if size > MAX_TOOL_BYTES or total > MAX_DISCOVERY_BYTES:
                raise StudioTransportError("Studio MCP tool definitions exceed the discovery size bound.",
                                           stage="tool_discovery", reason="limit_exceeded")
            names.add(tool["name"])
            results.append(tool)
        cursor = getattr(response, "nextCursor", None)
        if cursor is None or cursor == "":
            if not results:
                raise StudioTransportError("Studio MCP initialized but exposes zero tools; enable the Studio MCP server and verify its listener.",
                                           stage="tool_discovery", reason="empty_catalog")
            return results
        if not _identifier(cursor, 512):
            raise StudioTransportError("Studio MCP returned an invalid tool-list cursor.", stage="tool_discovery", reason="invalid_cursor")
        if cursor in visited:
            raise StudioTransportError("Repeated MCP tool-list cursor", stage="tool_discovery", reason="repeated_cursor")
        visited.add(cursor)
    raise StudioTransportError("MCP tool-list pagination limit", stage="tool_discovery", reason="limit_exceeded")


def _schema_bounds(schema):
    """Expected Studio schemas are self-contained; never resolve external refs."""
    if not isinstance(schema, dict):
        raise StudioTransportError("Studio MCP returned an invalid tool schema.", stage="tool_discovery", reason="invalid_schema")
    stack, nodes = [(schema, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_SCHEMA_NODES or depth > MAX_SCHEMA_DEPTH:
            raise StudioTransportError("Studio MCP tool schema exceeds its complexity bound.", stage="tool_discovery", reason="limit_exceeded")
        if isinstance(item, dict):
            if any(key in item for key in ("$ref", "$dynamicRef", "$recursiveRef")):
                raise StudioTransportError("Studio MCP schema references are unsupported; no resource lookup is allowed.",
                                           stage="tool_discovery", reason="unsupported_schema_reference")
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
        raise StudioTransportError("Studio MCP returned an invalid tool schema: input must accept an argument object.",
                                   stage="tool_discovery", reason="invalid_schema")
    try:
        if _json_bytes(schema) > MAX_TOOL_BYTES:
            raise StudioTransportError("Studio MCP tool schema exceeds its size bound.", stage="tool_discovery", reason="limit_exceeded")
        validator_for(schema, default=Draft202012Validator).check_schema(schema)
    except StudioTransportError:
        raise
    except Exception:
        raise StudioTransportError("Studio MCP returned an invalid tool schema.", stage="tool_discovery", reason="invalid_schema") from None


def _validate_studios(items, *, allow_empty=False):
    if isinstance(items, list) and not items:
        if allow_empty:
            return []
        raise StudioNoInstancesError("The Studio MCP connector answered, but there are no connected Studios. Open a place and enable its MCP server.",
                                     stage="instance_discovery", reason="no_instances")
    if not isinstance(items, list):
        raise StudioTransportError("Studio MCP returned no connected Studios or an invalid instance list.",
                                   stage="instance_discovery", reason="invalid_response")
    if len(items) > 32:
        raise StudioTransportError("Studio MCP instance list exceeds its count bound.",
                                   stage="instance_discovery", reason="limit_exceeded")
    result, ids = [], set()
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        if (not isinstance(item, dict) or not _identifier(item.get("id"))
                or name is not None and (not isinstance(name, str) or len(name) > 200
                    or any(ord(c) < 32 or ord(c) == 127 for c in name))):
            raise StudioTransportError("Studio MCP returned an invalid Studio instance.", stage="instance_discovery", reason="invalid_response")
        if item["id"] in ids:
            raise StudioTransportError("Studio MCP returned duplicate Studio instance ids.", stage="instance_discovery", reason="invalid_response")
        ids.add(item["id"])
        result.append({"id": item["id"], "name": "Unnamed Studio" if name is None else name})
    return result


def parse_studios(result):
    """Validate the connector's existing {studios: [{id, name}]} result contract."""
    try:
        # Preserve nulls until the two raw representations have been compared.
        data = result.model_dump(by_alias=True, exclude_none=False) if hasattr(result, "model_dump") else result
        if not isinstance(data, dict) or data.get("isError") is not None and data.get("isError") is not False:
            raise StudioTransportError("Studio MCP instance discovery failed or exceeds its response bound.",
                                       stage="instance_discovery", reason="invalid_response")
        if _json_bytes(data) > MAX_INSTANCE_BYTES:
            raise StudioTransportError("Studio MCP instance discovery exceeds its response bound.",
                                       stage="instance_discovery", reason="limit_exceeded")
        parts = data.get("content", [])
        if not isinstance(parts, list):
            raise StudioTransportError("Studio MCP returned invalid instance discovery content.", stage="instance_discovery", reason="invalid_response")
        if len(parts) > 16:
            raise StudioTransportError("Studio MCP instance discovery exceeds its content count bound.",
                                       stage="instance_discovery", reason="limit_exceeded")
        text = "\n".join(p["text"] for p in parts if isinstance(p, dict) and p.get("type") == "text"
                         and isinstance(p.get("text"), str))
        has_text = bool(text.strip())
        textual = json.loads(text) if has_text else None
        structured = data.get("structuredContent")
        source = structured if structured is not None else textual
        if not isinstance(source, dict):
            raise StudioTransportError("Studio MCP returned invalid instance discovery content.", stage="instance_discovery", reason="invalid_response")
        raw_items = source.get("studios")
        items = _validate_studios(raw_items, allow_empty=True)
        if structured is not None and has_text:
            if not isinstance(textual, dict):
                raise StudioTransportError("Studio MCP instance discovery representations disagree.",
                                           stage="instance_discovery", reason="representations_disagree")
            _validate_studios(textual.get("studios"), allow_empty=True)
            if textual.get("studios") != raw_items:
                raise StudioTransportError("Studio MCP instance discovery representations disagree.",
                                           stage="instance_discovery", reason="representations_disagree")
        if not items:
            _validate_studios([])
        return items
    except StudioTransportError:
        raise
    except Exception:
        raise StudioTransportError("Studio MCP returned invalid instance discovery content.",
                                   stage="instance_discovery", reason="invalid_response") from None


async def list_studios(client, *, tool_count=0):
    """Poll only validated empty discovery replies within one aggregate deadline.

    An unanswered request, MCP error or malformed response is never retried.
    Only a deadline reached while waiting after a valid empty reply means no
    instances; a deadline inside a request remains a visible timeout.
    """
    last_empty, requesting = None, False
    try:
        async with asyncio.timeout(INSTANCE_SECONDS):
            while True:
                requesting = True
                reply = await client.call_tool("list_roblox_studios", arguments={})
                requesting = False
                try:
                    return parse_studios(reply)
                except StudioNoInstancesError as error:
                    error.tool_count = tool_count
                    last_empty = error
                await asyncio.sleep(INSTANCE_POLL_SECONDS)
    except TimeoutError:
        if last_empty is not None and not requesting:
            raise last_empty from None
        raise StudioTransportError("Studio MCP instance discovery timed out.", stage="instance_discovery", reason="timeout") from None
    except StudioTransportError:
        raise
    except Exception:
        raise StudioTransportError("Studio MCP instance discovery failed.", stage="instance_discovery", reason="failed") from None


def select_studio(instances, studio_id):
    """Never silently select the first Studio when a requested id is missing."""
    items = _validate_studios(instances)
    if not _identifier(studio_id):
        raise StudioTransportError("Select a Studio instance explicitly before using its tools.", stage="selection", reason="required")
    selected = next((item for item in items if item["id"] == studio_id), None)
    if selected is None:
        raise StudioTransportError("The selected Studio instance is not connected; no other instance was selected.",
                                   stage="selection", reason="unavailable")
    return selected


async def probe(client=None, *, studio_id=None, target=None):
    """Read-only discovery, not edit permission, responsiveness or build acceptance.

    Supplying an open client never launches a second connector. Without a client,
    the explicit host target is used; None retains legacy environment behavior.
    """
    if target not in (None, "local_pc", "host_launcher"):
        raise StudioTransportError("Unknown Studio connection target; choose local_pc or host_launcher.",
                                   stage="configuration", reason="unknown_target")
    if client is None:
        async with connect(target=target) as connected:
            return await probe(connected, studio_id=studio_id)
    tools = await list_tools(client)
    if "list_roblox_studios" not in {tool["name"] for tool in tools}:
        raise StudioTransportError("Studio MCP does not expose instance discovery; Studio health is unverified.",
                                   stage="instance_discovery", reason="tool_unavailable")
    instances = await list_studios(client, tool_count=len(tools))
    selected = select_studio(instances, studio_id) if studio_id is not None else None
    return {"status": "tools_and_instances_discovered", "tool_count": len(tools),
            "studios": instances, "selected": selected}
