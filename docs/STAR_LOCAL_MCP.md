# STAR local MCP

STAR Desktop now uses its own MCP server for Roblox Studio operations. This is an actual MCP SDK `Server` and client exchange over private in-memory streams in the desktop process. It opens no TCP listener. The host selects one Studio route and instance, then the server advertises only the policy-filtered tools allowed for that guarded session. Status discovery itself crosses STAR's MCP status tool; a saved setting alone is not a successful connection.

These instructions describe this source change. They do not upgrade an already installed STAR executable; a tested desktop build containing the change is still required.

## Connect the downloaded app to your PC

1. Open your place in Roblox Studio on the same PC as STAR.
2. In Studio's Assistant menu, open **Manage MCP Servers** and enable **Studio as an MCP server**, following the [official Roblox setup guide](https://create.roblox.com/docs/studio/mcp).
3. In STAR, use the chat's **Studio: this PC** shortcut or open **Tools → STAR local MCP · Roblox Studio**. Keep **This PC · your Studio** selected.
4. Choose **Test & discover Studio**, then select the actual open instance from the returned list. STAR rechecks membership before saving the choice; it never selects the first instance automatically.

The local-PC route bypasses any custom operator launcher, including a malformed one. The separate **Practice Studio · configured host** choice uses an explicitly configured host launcher and refuses to fall back to this PC when it is absent or invalid. Launcher commands, credentials, addresses and arbitrary argv are not editable through this panel or model tools. The model provider connection is independent of the Studio connection.

New profiles default to this PC. An older profile without an explicit route loses its previous Studio ID and edit/Luau grants because their implicit target is unknown. Existing explicitly saved routes survive migration. Changing route or selecting another instance clears edit and Luau permissions. Selection and configuration changes are refused while a chat task is active.

Discovery has a 15-second host deadline and a bounded UI wait. The UI reports when it last checked the connection, not continuous health. A verified empty list means STAR's local MCP answered and the connector exposed tools, but no Studio instance is available; it is not a usable selected connection. A failed probe clears stale choices. Each Studio task reconnects, rediscovers the tool catalog, verifies the selected instance, and applies the existing safe-place rules before offering edit capabilities. Discovery does not verify a completed build or grant permission to modify a published game.

## Tool and build-loop boundary

`desktop_core.run_task` opens `local_mcp.connect_studio`. Its `LocalStudioClient` passes the filtered offered catalog and guarded verdict into the agent. Each tool call crosses STAR's MCP server before the guard can dispatch to Roblox's connector. Unknown tools, mismatched Studio IDs, invalid arguments and unapproved mutations are refused. Luau additionally requires explicit host opt-in and the Edit DataModel. This bridge adds no general execution, network configuration, permission-granting or publication tool.

The three native keyboard, mouse, and character-navigation tools are currently omitted and refused. Their Studio-ID-only contract cannot atomically bind input to STAR's original native play request. Automated gameplay input requires a separately verified target-bound implementation; scene and console reads remain available.

The build-loop adapter's `session` is the local client itself, not the raw Roblox session. Its script reads, hierarchy reads, screenshots, writes and play requests therefore cross the same MCP boundary. Host-only stop cleanup and undo share the bridge's serialization lock and have bounded waits; they are not model-discovered recovery tools. Cleanup preserves the guard's cancellation shielding. Cancellation sends protocol cancellation without retrying the tool. Native work may already have happened or may continue after a client stops waiting, so cancellation alone does not prove rollback or native termination.

## Recovery and native history

The full change journal and automatic-undo receipts belong to the current connected session. They are inserted before awaiting native mutations and retain unknown outcomes. A new connection does not recreate those receipts or prove an earlier operation stopped; reconnect must never be described as permission for an autonomous retry. Inspect Studio and the reported changes before recovery.

The desktop always supplies a separate persistent uncertainty ledger in its host-selected local state directory. It records pending operation tokens before native mutation and clears them only after exact known-success confirmation. Its scope uses the explicit route plus frozen native DataModel session/place/universe/creator binding, rather than a transient connector Studio ID. Pending or corrupt ledger state refuses later mutations and undo across reconnects while reads and explicit stop remain available. The ledger stores bounded operation metadata, not script source, launcher argv or endpoints. No model tool clears or acknowledges this ledger; it does not persist the full journal or make native rollback automatic.

Roblox's built-in Assistant can own an outer native-history recording while executing Luau. STAR does not finish another owner's recording or invent a unique history boundary for it. Connector-owned creation and Luau history require manual native-history review when STAR cannot prove its own recording. Existing script source is restored only through a guarded reverse compare-and-set with identity/postimage checks, rather than claiming native history restores Source. See [Studio build repair](STUDIO_BUILD_REPAIR.md) for the target binding, uncertainty and undo limitations.

## Optional source stdio entry point

An operator running the source package with dependencies installed can use:

```text
python -m star.local_mcp --settings <explicit-settings-file>
```

This serves the same curated guarded contract on stdio using the explicitly selected configuration. The settings file's parent directory provides the host-selected local state scope. Stdout is reserved for MCP protocol messages; errors are sanitized on stderr. This is not a claim that the released windowed `STAR.exe` offers a usable stdio server, and it does not create a public HTTP MCP endpoint.

## What the checks establish

Offline regressions use the real SDK memory transport, a real guard and a synthetic connector with the observed tool schemas. They exercise the complete read/write/repair/play/stop loop through STAR MCP, unknown-tool refusal, failed reads, a write applied before its reply is lost, unread console output, failed stop, cancellation during native request and running play, and bounded serialized host cleanup. These checks validate routing and safety decisions; the synthetic connector does not execute real Luau or measure gameplay quality.

A disposable native PC Baseplate also passed own-MCP script creation/edit/readback, guarded existing-source restoration, anchored Part construction and two authored runtime assertions. The final own-MCP start verified the native Server session/request before confirmation; immediate stop used atomic ownership checks plus EndTest, returned to the original Edit session, and left no durable pending operation. The disposable process was then closed. Native visual capture and Brain 2 compatibility remain unaccepted.

This connection does not establish an autonomous Brain2 design/practice/self-learning service. Practice results require separate validation and owner approval before application to the user's chosen Studio. Native model quality, engine compatibility and actual game behavior need their own bounded acceptance evidence.
