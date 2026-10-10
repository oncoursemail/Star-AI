# STAR Frontier Intelligence and MCP Connections — Research & Implementation

**Research date:** October 9, 2026 (U.S. Central)  
**Repository:** https://github.com/oncoursemail/Star-AI  
**Feature branch:** \`feat/star-mcp-connections-2026\`  
**Status:** Draft source-level change. No claim of a live Windows release or a proven "best AI" benchmark.

> **Ground rule:** STAR is one local-first assistant. Extra tools are not extra chat products, additional model brains, or a trained superintelligence. The benefits must be measured as higher task success, better source fidelity, less latency, stronger security, and a coherent single-window experience. A new MCP server is a capability surface, not a trust boundary.

---

## Executive decision

For the next release candidate, add a **small, curator-controlled, read-only MCP bridge** in STAR's existing Python tool loop and React desktop, without bumping the existing MCP SDK dependency to v2 yet. This is a transitional protocol adapter for three well-understood endpoints, not an unrestricted MCP marketplace. It provides:

1. Stateless **2026-07-28** Streamable HTTP requests for compatible servers, including the required request metadata, method/tool routing headers, custom \`x-mcp-header\` arguments, and bounded JSON or request-scoped SSE responses.
2. Explicit **2025-11-25** sessionful HTTP compatibility for a local Graphify instance, with \`initialize\`, \`notifications/initialized\` and \`Mcp-Session-Id\` handling isolated from the modern path.
3. Reviewed, locked-down **Graphify Docs MCP**, **Graphify local code graph MCP**, and **Obsidian Local REST API MCP** presets. No arbitrary URLs, dynamic commands, installers, remote scripts, OAuth impersonation, or blind transport negotiation.
4. A task-local \`star_mcp_search\` + \`star_mcp_call\` interface. The model discovers a small relevant set of read-only tools before any call, then receives compact, source-attributed, size-capped results. It cannot call undisclosed tools, and a tool can never grant access to another tool.
5. A real **Test connection** action in the **same** STAR React UI, reporting discovery rather than inventing availability, plus separately persisted user opt-ins. Settings never contain auth tokens.

The early implementation is source/test-focused. Windows packaging, live Obsidian TLS, live Graphify, 2026 SDK interoperability, machine-performance measurements and model acceptance are *mandatory* release gates.

## 1. Where STAR actually started

Checked against the \`main\` codebase on October 9:

- \`star/agent.py\`: a functioning local OpenAI-compatible chat-completions/tool loop with no generic MCP-server manager. Single first system message, compacted project context, max model/tool calls, Studio MCP and workspace tools.
- \`star/policy.py\`: hardcoded Roblox Studio read/edit permissions; unrestricted \`execute_luau\` excluded by default.
- \`star/desktop_core.py\`: local model settings, project memory, reviewed knowledge retrieval and persistent SQLite chats, with local endpoint validation.
- \`star/intelligence.py\`: merged Obsidian Markdown-vault reader, Graphify exported node-link graph reader and Agent Skills discovery, with keyword-sensitive tool loading.
- \`star/react_shell.py\`: explicit Qt WebChannel action registry, safe file-picker, model/Studio tests and integrated data profile.
- \`frontend/src/Desktop.tsx\`: one React desktop with primary chat, tools, projects, settings and status. The separate open draft PR #27 attempts a larger conversation-first redesign; draft PR #28 separately proposes fast/auto/agent provider/Web tools. This change must be rebased/reconciled with both; do not discard their work.
- \`requirements.txt\`: \`mcp>=1.19,<2\` to preserve compatibility with established Roblox Studio SDK usage, \`httpx>=0.27,<1\` for outbound HTTP. Do not silently leap to MCP SDK v2 without real Studio tests.

Previous Obsidian/Graphify/Skills upgrade **PR #26 is merged**. This new work extends it; it does not delete or replace its local read-only adapters, approved skills, existing data, or Roblox workflows.

## 2. MCP protocol evolution: why connection design matters

**2025-11-25:** A compatible Streamable HTTP client initializes with \`initialize\`, receives negotiated protocol capabilities and possibly a session identifier, sends \`notifications/initialized\`, and includes \`Mcp-Session-Id\` on later requests. A local graph server may still rely on this behavior.

**2026-07-28:** A major breaking protocol revision removed the transport-level initialization handshake and protocol sessions. Every request carries self-describing \`params._meta\` with protocol version, client capabilities and preferably client identity. Required HTTP headers mirror the version, method, tool/resource name and any \`x-mcp-header\` primitive argument fields. Responses can be JSON or request-scoped SSE. New features include discoverable capabilities, cacheable lists, MRTR interactions and a formal extension model. In this candidate, STAR deliberately supports **basic tools/list and tools/call only**; it does not implement server-initiated requests, subscriptions, prompt/resource injection, or MRTR approval continuation.

### Wire-level comparison

| Capability | 2025-11-25 (STAR local Graphify preset) | 2026-07-28 (STAR modern presets) |
|---|---|---|
| Handshake | \`initialize\` + \`notifications/initialized\` | None; metadata on every request |
| Transport session | Optional \`Mcp-Session-Id\` | Removed |
| Version | Negotiated in initialize | Header + \`params._meta\` |
| Gateway routing | Older JSON-RPC body | \`Mcp-Method\`, \`Mcp-Name\` |
| Custom tool headers | Not mandated as in modern spec | \`Mcp-Param-*\` for annotated primitive properties |
| Response | JSON or request-bound SSE | JSON or request-bound SSE |
| Long-lived tasks, MRTR | Not in this adapter | Explicitly unsupported pending authorization UI |
| Authentication | Token or compatible local configuration | OAuth preferred where supported; in this candidate env bearer only for reviewed local services |

The client handles these two wire forms **explicitly** rather than guessing versions or rewriting user requests. If a server chooses an unknown version, returns malformed IDs, redirects to another origin, or requests unsupported interactions, STAR fails closed and reports that the integration is unavailable.

### Current MCP SDK decision

The new \`mcp\` Python SDK v2 line documents 2026 features and protocol changes, but this repository's Roblox Studio adapter uses the older range. Upgrading immediately could introduce harder-to-diagnose regressions, particularly on Windows/stdio. This PR avoids an SDK-major change; a later isolated compatibility PR should test v2 against the official Studio server, fake sessionful fixtures, real Obsidian and Graphify versions.

Sources:
- Official 2026 spec: https://modelcontextprotocol.io/specification/2026-07-28
- Official release explanation: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- Official transport: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports#streamable-http
- Source/release changelog: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx
- Python SDK releases: https://github.com/modelcontextprotocol/python-sdk/releases

## 3. Connector-by-connector research and exact restrictions

### 3.1 Graphify Docs MCP

- Hosted docs-search endpoint: \`https://graphify.com/api/mcp\`. This is not the authenticated Graphify repository graph and does **not** inspect STAR project source.
- The documented docs tool is \`search_graphify_docs\`.
- STAR preset: public HTTPS, modern stateless protocol mode, strictly **one** allowed tool; no secrets are necessary.
- Real operational validation: test discovered protocol revision, exact tool name and input schema; some deployments may not yet support 2026 semantics. STAR must not silently downgrade a remote HTTPS endpoint or relabel failure as success.
- Use case: ask STAR how to run a graph extraction, filter confidence levels, query AST relationships, or troubleshoot the Graphify exporter.

Official: https://www.graphiffy.com/mcp and https://graphify.com/api/mcp

### 3.2 Graphify local project graph MCP

Graphify's open-source code indexing tool \`graphifyy\` creates a \`graphify-out/graph.json\` export. It also has a separately installed MCP server that can expose graph queries to assistants using stdio or Streamable HTTP. Star already supports *reading the static graph file directly* via \`star/graphify_bridge.py\`. This candidate adds a second **explicit opt-in** mode for a running Graphify MCP server.

Recommended external installation and generation workflow (not automatically executed by STAR):

\`\`\`powershell
uv tool install "graphifyy[mcp]"
cd C:\Projects\YourRobloxGame
graphify extract . --code-only
python -m graphify.serve graphify-out/graph.json --transport http --host 127.0.0.1 --port 8931
\`\`\`

The executable and \`uv\` environment have to agree. \`uv tool install\` installs tools into an isolated environment; if \`python -m graphify.serve\` cannot find the module, use that environment's Python or the documented \`uv tool run --from 'graphifyy[mcp]' ...\` equivalent, after confirming the actual installed CLI. Do not expose \`--host 0.0.0.0\` unless an independently managed, authenticated service is deliberately intended. Port **8931** is a STAR configuration default, not a Graphify official default: it avoids collision with STAR's local Brain endpoint around 8080.

Read tool allowlist for initial stage:
\`query_graph\`, \`get_node\`, \`get_neighbors\`, \`shortest_path\`, \`list_prs\`, \`get_pr_impact\`. The full Graphify graph server advertises other tools (e.g. graph statistics, communities, PR triage). Review each schema and side effect before including it. An innocuous tool named \`query_graph\` is not automatically trusted merely because it is a documented name—read capabilities are confirmed with inspected server schemas and future runtime tests.

Graph facts are not always truths:
- An edge marked extracted has different evidentiary status from inferred or ambiguous edges.
- A graph can be stale after project edits; date/version and source revision must be included in audit outcomes.
- Luau support must be tested against real Roblox projects, including \`.luau\`, remote events, client/server execution boundaries and assets. Code AST alone does not understand Studio live instances or geometry.
- Prefer direct static Graphify JSON when no server needs to run, and MCP when reusable live graph queries justify the extra dependency.

Official: https://www.graphiffy.com/docs , https://www.graphiffy.com/mcp , https://github.com/Graphify-Labs/graphify/blob/v8/README.md

### 3.3 Graphify hosted OAuth graph: specifically excluded from this PR

Graphify separately offers hosted \`https://api.graphify.com/mcp\` with browser OAuth, workspace/repository selection and potentially memory-writing tools. It is **not** the same service as the public docs endpoint, and a general-purpose unauthorized HTTP POST cannot replace its OAuth authorization-code flow.

Future support needs: browser login, PKCE, authorization issuer verification, Client ID Metadata Document handling, secure OS credential storage, strict token audience binding, consent to selected repo/workspace, cross-account isolation, revocation, and per-tool write scopes. Some Graphify tools capture user queries as persistent workspace memory, which must be considered a write even if a tool label sounds read-only.

**Do not send project secrets to hosted Graphify as an accidental fallback when local graph mode is disconnected.**

Official: https://graphify.com/mcp and https://github.com/Graphify-Labs/graphify-mcp

### 3.4 Obsidian Local REST API live MCP

Current stable approach from earlier STAR: direct local, read-only Markdown vault operations. The *new* MCP option uses Obsidian's community Local REST API plugin (coddingtonbear), which documents both the modern and legacy MCP protocol. Its secured local endpoint is \`https://127.0.0.1:27124/mcp/\`.

The Obsidian plugin also exposes methods capable of writing/deleting notes and potentially executing registered Obsidian commands. Enabling its API service does **not** mean the model is authorized to call every exposed tool.

Allow only exact reviewed read operations initially:
- \`vault_list\`: list note paths;
- \`vault_read\`: read Markdown note;
- \`vault_get_document_map\`: document structure/heading map;
- \`active_file_get_path\`: current selected note location;
- \`search_simple\` and \`search_query\`: search indexed notes;
- \`tag_list\`: enumerate tags.

Deny all unreviewed tool names and writes, including \`vault_delete\`, \`vault_write\`, \`vault_append\`, \`command_execute\`, file upload, or editing frontmatter. Even read calls can expose personal data and therefore require user opt-in; they are not silently enabled.

Authentication:
- Set \`STAR_OBSIDIAN_MCP_TOKEN\` as an environment secret *outside* the public repository and STAR Settings JSON.
- The plugin uses local HTTPS with a potentially private CA. If the Windows machine does not already trust it, export/locate the plugin's CA and set \`STAR_OBSIDIAN_MCP_CA_BUNDLE\` to a checked local certificate-bundle file.
- Never use \`verify=False\` or force-insecure HTTPS. Never send the token to \`http://\`, redirects, a different port, or a web page rendered inside STAR.
- A client can use a mock test and report what it verifies. A real "connected" status requires a successful live \`tools/list\` response from the user's local process and a recognized read-only schema.

Official: https://github.com/coddingtonbear/obsidian-local-rest-api , https://coddingtonbear.github.io/obsidian-local-rest-api/

## 4. The STAR MCP bridge: technical diagram

\`\`\`text
                            ONE STAR REACT DESKTOP
                                    |
                          Qt WebChannel allowlist
                           |                   |
                Settings / test MCP      Chat + model task
                           |                   |
                           |               star/agent.py
                           |                   |
                           +------ MCPGateway --+
                                        |
                        only on relevant user requests
                             search → disclose → call
                                        |
                          typed + validated JSON args
                                        |
                 +----------------------+----------------------+
                 |                      |                      |
         Graphify docs (HTTPS)  Graphify graph (loopback)  Obsidian plugin (TLS)
          2026 stateless        2025 sessionful             2026 stateless
          public docs tool      strict graph queries        strictly read only
                 |                      |                      |
                 +----------------------+----------------------+
                                        |
                     normalized, truncated tool evidence
                           project-scoped conversation
                                  existing audits
\`\`\`

There is no second assistant persona, no arbitrary tool daemon, no import of executable \`SKILL.md\` scripts and no automatic note synchronization into trusted memory. All calls are made from Python behind the installed app, never through direct public-browser JavaScript.

### Runtime contract

\`star_mcp_search(query, limit<=6)\`:

1. Registered only if an MCP source is enabled **and** the prompt explicitly references MCP, connectors, live vault notes or a connected source.
2. Discovery runs only for configured endpoints, using a limited catalog request; no unrequested tool actions occur.
3. Discard names outside the exact connector allowlist, invalid/massive schemas, and external \`$ref\` schema dependencies.
4. Return only matching names, descriptions, input schemas and provenance; add only the returned exact names to that task's grant list.

\`star_mcp_call(server, tool, arguments)\`:

1. Reject unknown or disabled servers and all undisclosed tools, even if the model tries to guess a tool name.
2. Validate arguments against the *discovered* JSON Schema. For modern HTTP, mirror designated primitive parameters into \`Mcp-Param-*\` headers with the spec's base64 sentinel when needed.
3. Enforce eight read calls per task, response byte limits, timeout limits and no redirected requests. Model arguments cannot set transport URL, auth headers, TLS options, or executable names.
4. Return bounded text evidence and its source. Non-text blobs are intentionally omitted, not opened.
5. Tool JSON and note content are **data**, never a system/developer/user instruction or consent signal. Error bodies, tokens and internal host exception messages do not go back to the model/UI.

### Current deliberate limitations

This is a **strict tool-only client subset**, not a full MCP SDK implementation. It does not yet support:
- MCP Apps UI extensions, generalized \`resources/read\` or \`prompts/get\`;
- MRTR \`input_required\` rounds, sampling, elicitation, paid transactions, or server-requested privileged callbacks;
- subscription streams, task polling, cross-call long-running handles;
- OAuth login flow, arbitrary remote-host config, custom bearer storage in UI;
- general stdio server installation, sandboxed subprocess launch or filesystem-wide scans;
- dynamic policy elevation or tool permission inference from server-provided labels;
- live telemetry or performance claims absent measured traces.

These belong in separately reviewed stages.

## 5. Why lazy tool discovery matters for speed *and* accuracy

A common architecture mistake is loading 50–100+ tool schemas into a small local model at the beginning of every conversation. That creates unnecessary prompt-token overhead, erodes usable context, and can harm tool choice when descriptions are similar.

Major agent platforms independently recommend dynamically loading relevant tools:
- OpenAI Tool Search: https://developers.openai.com/api/docs/guides/tools-tool-search
- Anthropic Advanced Tool Use: https://www.anthropic.com/engineering/advanced-tool-use
- Claude tool-search docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool

Vendor-published measurements show large reductions in tool-schema token overhead on specific benchmarks, but **STAR has not measured that gain yet**. Local model performance depends on quantization, available RAM/VRAM, prompt cache, model tool-call reliability and request patterns.

Recommended optimization order:
1. **No tools** for everyday writing, explanation, math, and casual chat: keep immediate text streaming.
2. **Only relevant tools** for an explicit edit, question about local files, vault/MCP tool query, or Studio interaction.
3. Search/disclose compact tool schemas rather than loading whole server catalogs into system context.
4. Keep model first-token latency and total task-time budgets visible, not only token-per-second throughput.
5. Cache validated tool catalogs by server identity + version/ETag/\`ttlMs\` in a later revision; inspect cache invalidation, revoked tool rights and schema changes. In this candidate, deliberately re-discover each task rather than risk stale privileges.
6. Prefer deterministic short local lookup before embedding/RAG/cloud reranking when the answer is exact.
7. Do not create extra model calls or subagents for trivial tasks.

More aggressive provider routing should be combined with **PR #28**, not reimplemented independently in this branch.

## 6. Intelligent memory and accurate research: next engineering stages

STAR already has candidate/reviewed notes and checkpoints. The next accuracy improvement is **retrieval quality plus provenance**, not unreviewed auto-summarization into system context.

A proposed staged memory architecture:
- **L0:** current prompt + stable high-priority policy only.
- **L1:** conversation-tail messages for same chat thread, with edit intent and task constraints.
- **L2:** trusted reviewed project decisions and last accepted build/test evidence.
- **L3:** SQLite FTS5/BM25 full-text chunks with source path, revision, line numbers and checksum; not necessarily exposed as "approved".
- **L4:** optional embedding-based semantic retrieval with bounded GPU/CPU costs, reranking and stale-index invalidation.
- **L5:** graph neighborhood retrieval for dependency questions; graph edges have confidence/provenance.
- **L6:** optional remote MCP sources, only when authorized and specifically relevant.

Each source must be labeled as **user-approved**, **retrieved source**, **model-generated candidate**, **tool-observed execution**, or **external unverified**. Do not treat an AI-authored summary or a graph-inferred relationship as higher-confidence than direct source.

SQLite FTS5/BM25 is a strong local-first next step, with lightweight exact retrieval and low startup overhead. Compare keyword-only vs BM25 vs BM25 + local embeddings before adding a vector database or long-lived external services.

Official: https://www.sqlite.org/fts5.html

## 7. Models and inference — what could truly make STAR better?

**Tooling does not retrain weights.** Quality comes from a good model/provider, effective context, predictable tools, sufficient computation, strong evaluation, and user experience. A multi-model architecture can improve latency/quality/cost tradeoffs, but it is not equivalent to discovering a superior foundation model.

A sound router would eventually offer:
- **Fast**: local small model; streaming; minimum tools; short contexts.
- **Balanced/Auto**: choose from tested local or user-authorized providers based on real benchmarks and privacy limits.
- **Deep/Agent**: planner with explicit checks, parallel *read-only* evidence gathering where resource ownership does not collide, controlled edits, and test-first verification.
- **Vision/Media**: image reference recognition through an actual multimodal model; ComfyUI only where user authorized image generation/editing, not random generated placeholders in Roblox UI.
- **Coding/Roblox**: Luau-aware linting, Studio scopes, code graph, test runner and screenshots—not arbitrary script execution on live game servers.

Possible vendor/provider future options may include OpenAI-compatible hosted models, Groq, Cerebras, OpenRouter, and Gemini with model-specific API adapters; their functionality and pricing must be checked at implementation time. Existing **draft PR #28 already proposes a provider and agent workflow**; resolve its interface rather than adding duplicate vendor SDK stacks here.

For local inference, evaluate fixed hardware with reproducible parameters:
- quantization Q4/Q5/Q8 tradeoffs, model architecture and context length;
- GPU layer count and KV cache memory footprints;
- prompt-prefix caching and persistent model warmness;
- llama.cpp / LM Studio / Ollama compatibility;
- chat-template format and tool-call JSON validity;
- capacity at low RAM/VRAM and CPU fallback;
- 4K, 8K, 16K context and image-in-prompt stability.

Do not claim e.g. a 30% speed gain without benchmark logs. Turn-level p50/p95 first-token latency, completion quality and tasks completed matter more than raw TPS.

References: https://github.com/ggml-org/llama.cpp ; https://lmstudio.ai/docs ; https://docs.ollama.com ; existing STAR \`docs/STAR_BRAIN_DOWNLOAD_RESEARCH.md\`.

## 8. Security analysis and attack scenarios

Threat surfaces to test:

| Attack | Failure mode | STAR initial protection | Remaining risk |
|---|---|---|---|
| Prompt injection in vault notes | Retrieved text asks model to disregard prior instructions | Label content untrusted; no tool privileges from content | Local model could still be misled; evaluate with adversarial fixtures |
| Malicious MCP tool descriptions | Server advertises tool named like a read tool with harmful side effects | Exact per-server allowlist + user opt-in | A compromised supposedly read-only server could secretly mutate; use trusted plugin and permissions |
| Arbitrary endpoint/SSRF | Tool coerces STAR to visit private services | Fixed reviewed host/port/path, no arbitrary URLs/redirects | Trusted local daemon may itself access broader resources |
| Bearer-token redirect | Server 302s auth request to attacker | No redirects, exact URL, TLS verification | Environment tokens can be exposed by a compromised local process |
| Tool schema injection | Remote \`$ref\` or malicious \`x-mcp-header\` | Check schema, reject \`$ref\`, size cap, primitive headers | Complex schema validation workload should be benchmarked/fuzzed |
| Session confusion | Legacy server returns spoofed session | Validate bounded ASCII \`Mcp-Session-Id\`, keep it task-local | Legacy interoperability is not universally guaranteed |
| Resource exhaustion | Server streams huge payload or hangs | 320KB response cap and timeouts; 8 call budget | Many concurrent users could still create aggregate pressure |
| Silent data writes | Tool named "search" records query in cloud memory | Hosted OAuth Graphify intentionally excluded | Other remote servers may log questions by default; disclosure and privacy policy review |
| Malicious skill installation | SKILL.md scripts request shell/publish permissions | Skills remain reference-only, executable authorizations unchanged | Skill text may still bias decisions; test boundaries |
| Secret storage | Credentials persisted to SQLite, logs or GitHub | Environment outside app profile; no React bootstrap tokens | OS keychain is more robust for a future interactive setup |

Refer to:
- MCP security: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- OWASP MCP Top 10: https://owasp.org/www-project-mcp-top-10/
- MCP registry provenance: https://registry.modelcontextprotocol.io/
- MCP Inspector: https://github.com/modelcontextprotocol/inspector

The official registry is discovery metadata, **not** a proof that a tool runs safely or an endorsement to auto-install executable packages. In the current candidate, third-party registries cannot directly add new endpoints.

## 9. Concrete tool testing, not marketing

All tests must distinguish offline mocks from actual external service operation.

| Test family | Fixture | Acceptance |
|---|---|---|
| Protocol modern | In-process \`httpx.MockTransport\` checks \`_meta\`, \`Mcp-Method\`, \`Mcp-Name\`, header values | 2026 request and response parsed; session header absent |
| Protocol legacy | In-process initialize, notification, session ID and SSE fixtures | Correct order, no modern-only header pollution |
| Tool catalog | Include harmless and malicious tool names in fake \`tools/list\` | Only exact reviewed read tool exposed |
| Tool policy | Guess undisclosed tool; give schema-invalid args | Rejected before HTTP call |
| TLS + tokens | Obsidian missing API token, bad CA path, HTTP 401 | No unsafe TLS fallback, no tokens in status/error |
| Redirect | Return HTTP 302/307 to unrelated host | No following, no leaked bearer |
| Response bounds | Oversized streamed SSE/JSON, wrong JSON-RPC ID, malformed schema | Deterministic failure and readable generic error |
| Model bridge | Fake tool-calling local-model responses invoking search then call | Correct two-step tool protocol and one system role |
| Desktop | React TypeScript/Vitest/Vite; mock Qt WebChannel | Settings, toggles, status, browse flow and error states |
| Windows executable | Real bundled PyInstaller with Python/C++ deps | App launches and Qt shell can discover an active local test MCP |
| Live Obsidian | Disposable vault + plugin with test notes, trusted CA | Read-only search, tags, no edits, offline handling |
| Live Graphify | Disposable Luau repo + graph; serve on localhost | Known edge/path query, confidence and stale-index warnings |
| Negative tests | Old Studio session + MCP connected simultaneously | No permissions leak to Studio edit mode |

**Proposed scorecard, not measured results:**
- Ordinary chat: <=10% regression in median time-to-first-visible-token relative to current main, p95 tracked.
- MCP discovery: >=95% recall of correct whitelisted tool on curated prompts; 0 false grant of unauthorized tool.
- Note/graph tasks: >=90% source-supported claims in a manually verified test set; no silent hallucinated references.
- Security: 0 credential leaks, unauthorized writes, cross-vault reads, shell calls, redirects.
- Roblox live smoke: applicable scripts, GUI events and Studio state match observed test evidence; unit tests alone not sufficient.
- Crash resilience: invalid/missing external MCP does not prevent plain conversations or overwrite chat databases.

Collect actual wall-clock timings, GPU/RAM statistics, tool-call counts, server versions and user-relevant success/failure evidence. Use OpenTelemetry-style spans where appropriate and redact payloads/credentials.

Official test utilities and telemetry:
- https://github.com/modelcontextprotocol/inspector
- https://opentelemetry.io/docs/specs/semconv/
- https://www.sqlite.org/fts5.html

## 10. Future architecture tiers

**Tier 1: Ship the small, safe, tested MCP bridge.**
Reviewed endpoints, read-only source retrieval, reliable error states, zero silent writes; do not merge until core CI+Windows+real connector tests pass.

**Tier 2: First-class per-project connection profiles.**
One source registry inside STAR Settings, scoped enable/disable, connected vs configured vs unhealthy vs blocked, per-workspace grants, editable notes credentials in OS vault, human-readable audit trail, no duplicate chat UI.

**Tier 3: Trustworthy data retrieval.**
SQLite FTS5, source-aware snippets, local embedding opt-in, source selection by task, stale revision warnings, visual graph explorer, direct source file navigation, score groundedness.

**Tier 4: OAuth + cloud tools.**
Strict issuer/audience-binding with PKCE/CIMD, consent granularity, per-tool read/write authorization, resource/server identity pinning, revocation. Hosted Graphify and vendor tools remain outside Tier 1.

**Tier 5: Controlled action and self-building.**
Tool impact previews, diffs, explicit confirmation for high-risk writes, isolated worktrees, deterministic tests, screenshots and Roblox acceptance, human-reviewed draft PRs, rollback. Self-generated code cannot edit the validation fixtures or core policy unchecked.

**Tier 6: Robust agent performance.**
Fast/Auto/Agent routing benchmarked against user tasks, no speculative extra reasoning loops for simple chat; ability to partition read-only tasks safely, avoid two agents editing same resource, synchronize one user-facing answer.

**Tier 7: Extended MCP specification capabilities.**
When the newer SDK and user interface can support them, add cache TTL/schema invalidation, \`server/discover\`, request-scoped subscriptions, resources, prompts, MRTR explicit approval rounds, task extensions and MCP Apps only behind controlled review and domain boundaries. Never equate partial HTTP-tool support with all of MCP.

## 11. End-user setup: without surprises

After a reviewed build lands:
1. Open **STAR > Settings > MCP connections**. Select which of the three reviewed endpoints to use. All start disabled.
2. Click **Save settings** and navigate to **Developer tools > Connected tools**.
3. For public Graphify documentation MCP, click **Test connection**. The result reports real tool discovery count, or explicit failure.
4. For local Graphify, generate a graph and start the Graphify MCP server on port 8931 (or choose the actual port) *yourself*. Then test. If Graphify is not running, STAR chat remains operational.
5. For live Obsidian, install/enable the trusted Local REST API plugin inside Obsidian. Set \`STAR_OBSIDIAN_MCP_TOKEN\` in STAR's launch environment and configure a trusted CA if necessary. Never paste API tokens into chat or the public React website.
6. Ask in chat, for example: "Use my MCP connection to search Graphify docs about Luau," or "Search connected Obsidian MCP for the approved VALEN map design decision." The agent first discovers the relevant tools, then requests specific reads.
7. Disconnect at any time in Settings. Disabling means the next task cannot discover or invoke the connection; existing chat history remains local.

Credentials in process-level env are a **temporary developer-oriented setup**. A production-grade interactive installation needs an OS-protected credential manager and an explicit connect/revoke UX.

## 12. Source ledger and verification discipline

Every source below was verified for relevance to this architecture; external webpages remain untrusted and can change.

| Area | Primary source | Why used |
|---|---|---|
| MCP revision | https://blog.modelcontextprotocol.io/posts/2026-07-28/ | Version timing, stateless design, extensions, deprecations |
| MCP transport | https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/transports/streamable-http.mdx | Headers, SSE/JSON, x-mcp-header, bytes |
| MCP changelog | https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx | Explicit breaking changes |
| MCP security | https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/tutorials/security/security_best_practices.mdx | SSRF, OAuth and tool trust |
| Obsidian plugin | https://github.com/coddingtonbear/obsidian-local-rest-api | Local endpoint, auth, concrete tool names |
| Obsidian OpenAPI | https://github.com/coddingtonbear/obsidian-local-rest-api/blob/main/docs/openapi.yaml | 2026 request fixtures, tested API semantics |
| Graphify local CLI | https://github.com/Graphify-Labs/graphify/blob/v8/README.md | Code graphs, local server and HTTP commands |
| Graphify local MCP | https://www.graphiffy.com/mcp | Tool capabilities, local/hosted distinctions |
| Graphify hosted | https://graphify.com/mcp | OAuth endpoint and memory-writing implications |
| Graphify hosted metadata | https://github.com/Graphify-Labs/graphify-mcp | Hosted API not source for local server |
| OpenAI tool search | https://developers.openai.com/api/docs/guides/tools-tool-search | Deferred loading/context design |
| Anthropic tool search | https://www.anthropic.com/engineering/advanced-tool-use | Tool explosion and selection errors |
| Skills | https://agentskills.io/specification | Small reusable capability descriptions, no implicit code execution |
| Retrieval | https://www.sqlite.org/fts5.html | Local ranked full-text memory |
| Inspector | https://github.com/modelcontextprotocol/inspector | Manual and CLI MCP compatibility |
| Observability | https://opentelemetry.io/docs/specs/semconv/ | Consistent spans and timing observations |
| Security risks | https://owasp.org/projects/mcp-top-10 | Token, permission and tool-poisoning threat catalog |
| Repo baseline | https://github.com/oncoursemail/Star-AI | Existing tools, UI, policies and release flows |
| PR #27 | https://github.com/oncoursemail/Star-AI/pull/27 | Unified UX conflict/reconciliation |
| PR #28 | https://github.com/oncoursemail/Star-AI/pull/28 | Model/provider/agent improvements to combine later |

---

**Conclusion:** A "best AI ever" label is not defensible from tool count or unit tests. This candidate supplies a real, reviewable, safer MCP capability foundation. A genuinely excellent STAR would integrate proven retrieval, dependable model routing, high-quality workflows, fast UI, source attribution, test-backed behavior and user-controlled connections, then demonstrate that quality with reproducible evaluations and live Windows acceptance.
