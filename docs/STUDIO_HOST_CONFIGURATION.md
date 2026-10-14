# Operator configuration for Practice Studio

The repaired desktop defaults to **This PC**. That route uses the user's official
Roblox Studio MCP launcher and ignores both host environment configuration and
the operator file described here, even when either is damaged.

**Practice Studio (configured host)** is an explicit owner choice. It resolves a
launcher in this order:

1. A nonempty `STAR_STUDIO_MCP_COMMAND` process environment value, a JSON argv list.
2. Otherwise, the `command` list in `<explicit STAR data home>/studio/remote.json`.

The operator file is compatible with the separate Studio server client's file:

```json
{"target": "server", "command": ["operator-launcher", "operator-approved-argument"]}
```

Only `command` is consumed. `target` and other fields cannot select a route, an
instance, edit permission, Luau permission, or account ownership. The normal UI
still tests the selected route, displays actually discovered instances, and
requires the owner to select the exact instance before enabling edits and Luau.
Changing the UI route still clears the selection and both permissions.

Commands are host/operator configuration, not editable model or desktop Settings
fields. The command is never included in the discovery/status DTO or model tool
catalog. The environment override is preserved; a malformed nonempty environment
value refuses the operation rather than falling back to a file or this PC.

## What Settings shows (star/studio_host.py, read-only in v0.9.0)

Settings > Roblox Studio offers the two routes ("This PC", "STAR Studio server") and,
for the server route, shows whether a connection exists on this PC. It cannot store,
change or remove one: in v0.9.0 the desktop never writes a command.

- One bridge action, `studioHostStatus`: `{configured, source}` with source
  `environment`, `settings` (the operator's file), `none` or `invalid` (a damaged or
  linked file: nothing is used until the operator repairs it). The stored text is
  never returned.
- "Test connection" in that section is the existing `discoverStudio` check of the
  selected route; instance selection and the edit and Luau permissions stay where
  they were (Tools).
- A way to type the server's address and command into Settings (bridge actions
  `studioHostSave` and `studioHostClear`, bounded to `ssh` in key-only mode) was
  built on branch `star/settings-ui-20261011` and is left out of this release until
  it has had its own review. The bridge refuses both action names.

Each connection resolves argv once and passes an immutable tuple directly to the
transport. It does not modify the process environment. Concurrent explicit data
homes therefore have independent file commands. A later file/environment change
does not change an already-open connection. After changing operator configuration,
test the practice route again and select the intended instance before authorizing
another task; a cached report describes its earlier check, not current health.

Files are read without creation or repair. Input is limited to 22,000 bytes, with
1–40 nonempty string arguments of at most 500 characters and no control characters.
An empty `command` list or missing file means unconfigured. Invalid JSON, duplicate
keys, invalid argv, unreadable/oversize/nonregular files, relative or linked profile
roots/ancestors, links/reparse points, multiple hard links, a replaced ancestor,
or a changed file during reading refuse configuration. Public
failures do not expose argv, file contents, host addresses, or raw exception text.

Discovery, selection, and task creation use the settings file's parent for command
configuration:
React snapshot/check/select, Qt check/select, `desktop_core.check_studio`, and
the optional host-only `studio_configuration_home` forwarded through `run_task`
to `local_mcp.connect_studio`. Pure connection services do not infer a user profile.
This command-only override does not move chats, memory, credentials/account checks,
runs, or the durable uncertainty ledger from their existing application data home.
Direct callers default command configuration to their existing explicit home. The
source stdio entry point continues to use the explicit settings file's parent.

This bridge retains the real private-memory STAR MCP exchange, bounded transport
and discovery, exact instance selection, policy filtering, edit/Luau opt-ins,
durable uncertainty ledger, native session binding and guarded stop/undo. It does
not replace those protections with the separate remote client's helpers or add
an automatic retry, publish step, account grant, or background learning service.

Offline tests use synthetic files and injected connectors, including actual MCP
exchanges over memory. They verify routing and refusal behavior; they do not prove
a deployed server, remote process cleanup, or game quality. Launcher/watchdog
lifecycle fixes and a live configured-host acceptance remain separate work.
