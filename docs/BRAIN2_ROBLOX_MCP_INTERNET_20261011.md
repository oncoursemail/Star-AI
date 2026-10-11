# Brain 2 ↔ STAR ↔ Roblox Studio MCP: integration research and acceptance plan

**Researched October 11, 2026 · Target base:** star/claude-integration-20261010
**Status:** bounded MCP Registry discovery is implemented and offline tested in this branch. The separate private Brain 2 service and owner's native Windows Studio have **not** passed end-to-end acceptance under this branch.

## Executive decision

Use **the official Roblox Studio MCP server** and STAR's existing local guarded MCP layer. Do not build an unofficial Studio plugin, put the Studio stdio server on the public internet, give a model arbitrary PC shell authority, auto-install Registry packages, or bypass per-place approvals. Brain 2 should call the host-selected STAR server as an MCP **client**. The public registry is a tool **discovery** plane, never a privilege source.

Architecture:

\`\`\`text
STAR Desktop / selected model (Agent + explicit Research)
  ├── web_search.py -> Brave/Tavily public search (when configured)
  ├── mcp_registry.py -> official public MCP Registry (metadata only; new)
  ├── mcp_connections.py -> curated live read-only MCP presets (user opt-in)
  ├── tool_workshop.py -> preview/approval of local read-only recipes
  ├── local_mcp.py -> private, guarded MCP Server/client
  │    └── studio.py -> official Roblox Studio MCP stdio launcher
  │         └── one host-selected, authorized Studio/Place
  └── roblox_cloud.py -> Open Cloud API, private test place + owner approval

Independent Brain 2 service
  └── compatible MCP client -> STAR local_mcp.py stdio (same PC)
       not directly to unrestricted Studio, account keys, or process control
\`\`\`

## 1. Existing state in the checked repository

- \`star/studio.py\` already invokes Roblox's official native MCP launcher using the Python MCP SDK.
- \`star/local_mcp.py\` already wraps Studio in an actual MCP server/client with a private in-memory path for the desktop and an optional, explicitly configured source stdio entry point.
- \`star/studio_loop.py\` binds operations to the selected Studio and implements guarded edit/play/stop, uncertainty and recovery.
- \`star/policy.py\` excludes unapproved tools, high-risk asset generation and unrestricted Luau in normal mode; native input tools are blocked because their contract cannot atomically bind the owning play session. **A Studio ID is a routing key, not a sandbox.**
- \`star/roblox_cloud.py\` supports the owner's scoped Open Cloud key and private test experience; API writes require separate owner approval. It cannot safely be used to modify arbitrary experiences.
- \`star/agent.py\` routes approved tool calls. \`star/mcp_connections.py\` only allows curated external read-only connectors. \`star/web_search.py\` returns Brave/Tavily snippets when separately enabled.
- Brain 2 is an **independent service**, not a complete independently auditable service in this public repo. STAR draft PR #49 reports partial external compatibility, while native Brain 2 build/play/stop, teardown and visual acceptance were still unresolved. This branch must not be described as a completed Brain 2 deployment.

## 2. Official Roblox Studio MCP and setup

Reference: https://create.roblox.com/docs/studio/mcp

1. Install/update Roblox Studio. Open a disposable unsaved Baseplate.
2. Open Studio Assistant → … → **Manage MCP Servers** → enable **Studio as an MCP server**.
3. Use the official local launcher; on Windows Roblox documents a command such as \`cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat\`. The existing \`star/studio.py\` resolves the installed launcher and verifies discovery. On macOS the packaged StudioMCP executable path differs.
4. With STAR, select **This PC / your Studio**; confirm the returned native \`list_roblox_studios\` session and its \`studio_id\` rather than treating a transport handshake as a real Studio connection.
5. STAR should read hierarchy, scripts, state, console and a screenshot before proposing edits. Enable edit/Luau only for an owned disposable project after the host's verdict and consent.

Native tools offered by the official server include: \`list_roblox_studios\`, \`script_read\`, \`script_search\`, \`script_grep\`, \`search_game_tree\`, \`inspect_instance\`, \`get_studio_state\`, \`get_console_output\`, \`screen_capture\`, \`multi_edit\`, \`execute_luau\`, \`start_stop_play\`, \`search_asset\`, \`insert_asset\`, \`generate_mesh\`, \`generate_material\`, \`generate_procedural_model\` and simulated player inputs. Some tools use uploaded account assets or quota. **Availability in the official catalog is not authorization in STAR.**

**Real Studio acceptance:** read script, verify unmodified source, create a test Script with guarded ownership, read back exact bytes, perform one anchored construction in Edit, run two assertions in a disposable Server test, inspect outputs and visual evidence, stop only an owned play session, verify Edit restore and no pending ledger entries, then verify an unrelated Studio instance is unchanged. Repeat tests for cancellation, dropped mutation response, stale studio_id, changed target and unexpected Studio close. Do not blindly retry uncertain writes.

## 3. Brain 2 local MCP contract

STAR offers the following **source-level optional stdio server** (requires valid local settings, dependencies and a configured Studio):

\`\`\`powershell
python -m star.local_mcp --settings C:\Path\To\OwnerSelectedSettings.json
\`\`\`

This command is NOT an internet-facing HTTP service and does NOT mean the Windows installed STAR.exe exposes that entry point.

The source tree also includes a **read-only external MCP client probe** that checks the real stdio initialization, available approved tools and status of a selected Studio without editing any place:

```powershell
python scripts/brain2_mcp_smoke.py --settings C:\Path\To\OwnerSelectedSettings.json
```

A success report says `verified_via_stdio`. Failure returns a nonzero exit code with a sanitized summary. This probe verifies the STAR MCP endpoint from an external Python client; it does **not** run the private Brain 2 service or prove play/edit/publish capabilities. A compatible Brain 2 MCP client on the same host can spawn it with an explicitly configured settings file and request \`tools/list\` then \`star_connection_status\`. The host must supply the command/path; never derive them from a model prompt, web result or Registry metadata.

To verify Brain 2, its separately deployed maintainer must provide:

- Actual launcher/binary, host OS and process lifetime; ownership of subprocesses; isolation of unsaved Studio windows and profiles.
- MCP protocol and transport compatibility for initialize, capabilities, \`tools/list\`, \`tools/call\`, cancellation and subprocess stdout hygiene; schema validation and bounded responses.
- Explicit per-place authorizations, selected Studio instance ID, allowed tool set, immutable edit target and shared lock ownership. **One controller at a time** for state-changing Studio activity.
- Unknown-outcome journal, non-replayed writes, guarded undo with script pre/postimage, and native session-bound play/stop.
- Logs/test receipts from a real disposable Windows Studio, not only a fake connector. PR #49 warns that some Brain 2 restart/teardown paths could bypass a live-client lock or disturb other Studio work; address those separately before enabling remote service takeover.

A remote Brain 2 process on another computer cannot directly use the local stdio pipe. Remote use needs a separately reviewed authenticated relay, strict identity/rate limits and host-controlled approval; none is included in this change.

## 4. Internet access: existing and proposed

Current research is **search**, not unlimited authenticated internet browsing: Brave/Tavily can return source-linked snippets. Without configured provider credentials it is unavailable. It does not automatically read whole web pages, run a browser, download files or act in user accounts.

Future verified browser research should provide:
- Search -> bounded fetch -> extraction -> provenance/citations -> cross-check and cache.
- Public HTTP(S) egress allowlist or secure DNS resolution with rebinding/SSRF defense; deny private, loopback, link-local, cloud-metadata and reserved IP ranges even across redirects.
- Strict MIME, decompressed-size, read-time, per-domain quota and redirect limits; no implicit cookies, local files or token forwarding.
- Provenance records, content hashes, crawl freshness and explicit distinction between first-party documentation and untrusted forum/user-generated text.
- Offline deterministic tests and separate real-network acceptance; consent and service-policy respect for credentials and authenticated pages.

## 5. Thousands of *discoverable* tools, not thousands of live grants

Official public MCP Registry: https://registry.modelcontextprotocol.io and https://registry.modelcontextprotocol.io/v0.1/servers.
Reference specification: https://github.com/modelcontextprotocol/registry

The registry accepts GET requests with name-substring \`search\`, \`limit\`, \`version=latest\` and an opaque \`cursor\`. Registry records contain publisher-supplied descriptions, distributions, install commands and optional remote endpoints. Namespace verification is **not** a connector security audit. Counts can change; never claim a precise number of working servers until measured.

New \`star/mcp_registry.py\` and Agent wiring provide \`star_mcp_registry_search\`, available only in **Agent + explicit Research** turns with matching prompts. It:
- Makes bounded requests exclusively to the registry fixed HTTPS endpoint; disables environment proxies and redirects.
- Uses at most four requests per turn, at most 20 results per page and a 192 KB response cap.
- Sanitizes descriptions, validates names, exposes only safe source-repository URLs, and excludes package/install commands, remote endpoints, secrets and untrusted arbitrary fields.
- Preserves cursor pagination and marks every candidate \`metadata_only_not_connected\`.
- Cannot install, execute, register, connect to or authorize a discovered server. Existing curated live MCP connection allowlists are unchanged.

Future scalability architecture:
1. **Metadata plane:** indexed tool descriptions and versioned schemas, publisher verification, cryptographic hashes, local embeddings/keyword search, changed-tool detection, health checks and opt-in catalogue sync with ETags.
2. **Authorization plane:** separate per-server and per-operation scopes: \`public_read\`, \`network_read\`, \`workspace_write\`, \`studio_edit\`, \`sandbox_execute\`, \`account_write\`. The host grants permissions; the model/Registry/web text never can.
3. **Execution plane:** reviewed and pinned sandbox packages, least-privilege subprocess/service account, no automatic arbitrary \`npx\`/\`uvx\` installation, separate credentials, destination restrictions, bounded I/O, cancellation and change receipts.
4. **Planner plane:** retrieve a top-K relevant tool subset, rather than putting thousands of JSON schemas in the LLM context. Match prerequisites, cost, latency, side effect, evidence and confidence; parallelize read-only research but serialize conflicting Studio writes.
5. **Evaluation:** offline prompt/tool-selection regression fixtures, guarded Studio native tasks, screenshot/design comparison, repair/undo, timeout and secret-leak tests; record p50/p95 latency, tool selection accuracy, task completion and provenance.

## 6. Acceptance gates and implementation order

| Capability | This branch / current code | Required proof |
|---|---|---|
| Official Studio MCP client + STAR guarded bridge | Existing code | Native host test with selected Studio |
| Brain 2 -> STAR stdio server | Design documented; private Brain 2 not changed | Real Brain 2 client transcript, no competing controller |
| Research search | Existing Brave/Tavily opt-in | Configured credential and live citation check |
| MCP Registry discovery | **Added code, unit tests and Agent wiring** | CI then optional live API check |
| Thousands of executable tools | **Not implemented** | Reviewed connector manager + per-tool grants and sandbox |
| Studio unrestricted Luau/asset generation | **Intentionally blocked** by current policy | Dedicated high-risk feature review/quotas/test place |
| Live Roblox publishing | **Not enabled** | Separate explicit owner-approved release workflow |

Implementation order:
1. Validate this PR offline and on Windows without changing established MCP/Studio policy.
2. Fix the separately deployed Brain 2 service's restart/teardown/lock issues and integrate as a host-approved client; native smoke-test.
3. Create an audited connector manager for trusted stdio/Streamable HTTP, with opt-in installation and exact schemas.
4. Add secure full-page public-web reading and research citation validation.
5. Add individually reviewable Studio generation/building workflows with source provenance and quota protections.
6. Evaluate multi-agent creative loops on held-out Roblox tasks, with real screenshots and undo/recovery.

**Do not claim** this PR provides an unrestricted browser, thousands of installed tools, live Brain 2 compatibility or complete control of arbitrary Roblox games. The available evidence proves only a bounded discovery helper and compatibility with the existing Python tool loop pending CI and native acceptance.

### Primary sources

- Official Roblox Studio MCP https://create.roblox.com/docs/studio/mcp
- Roblox Open Cloud https://create.roblox.com/docs/cloud
- Roblox API keys https://create.roblox.com/docs/cloud/auth/api-keys
- Roblox Luau execution API https://create.roblox.com/docs/cloud/reference/features/luau-execution
- Official Roblox Studio agent plugin https://github.com/Roblox/roblox-studio-agent-plugin
- MCP Registry https://github.com/modelcontextprotocol/registry
- MCP Python SDK https://github.com/modelcontextprotocol/python-sdk
- STAR local MCP \`docs/STAR_LOCAL_MCP.md\`
- STAR native acceptance and private Brain 2 limitations https://github.com/oncoursemail/Star-AI/pull/49
