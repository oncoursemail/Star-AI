# STAR Intelligence Upgrade: Obsidian, Graphify and Agent Skills

**Research snapshot:** 2026-10-09  
**Scope:** one inspectable, offline-first, read-only integration slice for STAR Genesis.  
**Status:** source candidate on a development branch. The presence of working adapter source and passing mocked tests is *not* proof of live Windows/Qwen/Obsidian/Graphify acceptance. A release requires Windows CI, an owner-reviewed PR and a real model/Studio acceptance run.

## Executive findings

The three technologies complement one another but solve *different* problems:

| Capability | Best evidence | What STAR should do | What it must not claim |
|---|---|---|---|
| Obsidian | Explicit Markdown note from selected local vault | Discover decisions, past architecture, and verified references with snippets and direct note reads | Notes are not necessarily correct or approved; vault read access is not a model upgrade |
| Graphify | Local graph.json, node IDs, source paths, attributed edges | Discover components, navigate dependencies and connected concepts before edits | A graph can be stale, and INFERRED/AMBIGUOUS edges are not observed code execution |
| Agent Skills | Validated SKILL.md with name/description and optional reference files | Provide structured domain-specific workflows to a limited local model, progressively | A SKILL.md file cannot grant tool permissions, execute scripts, or add foundation-model weights |

The highest-return change is **tool relevance and progressively disclosed context**, not a larger always-on system prompt. A local 4K-8K context backend may spend significant budget if ten or more schemas and whole notebooks are injected on every turn. STAR now registers only selected tool groups on prompts matching their tasks, and fetches note/graph/skill details only when called. This is a conservative heuristic: it can miss an implicit request. Future evaluation should consider tool discovery through a deterministic intent classifier/sidecar.

## Source verification

1. Official Agent Skills specification: https://agentskills.io/specification and https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx. Required YAML frontmatter has \`name\` and \`description\`; SKILL.md carries Markdown instructions, optional \`references/\`, \`assets/\`, and \`scripts/\`. Names must match the parent directory and contain only lowercase letters/numbers/single hyphens. Metadata should be discovered first, instructions loaded upon need, assets last. \`allowed-tools\` is experimental declaration, not permission for STAR.
2. Obsidian stores local vaults as Markdown files: https://help.obsidian.md/Files+and+folders/How+Obsidian+stores+data. Existing \`.obsidian\` settings and plugin directories must not be indexed or mutated in a research assistant.
3. Obsidian community Local REST API **with built-in MCP**: https://community.obsidian.md/plugins/obsidian-local-rest-api and https://coddingtonbear.github.io/obsidian-local-rest-api/. Authenticated Streamable HTTP MCP at \`https://127.0.0.1:27124/mcp/\` uses bearer key; local TLS certificate trust is required. It offers extensive **write** capabilities; this is intentionally *not* exposed in the new read-only adapter. Another plugin also exists at https://community.obsidian.md/plugins/cli-rest-mcp, but is not interchangeable and may allow CLI actions.
4. Graphify Labs: https://github.com/Graphify-Labs/graphify and https://www.graphiffy.com/docs. The official package is \`graphifyy\` (double y) on PyPI, the command is \`graphify\`. The exporter creates \`graphify-out/graph.json\`, \`graph.html\`, and \`GRAPH_REPORT.md\`. Code AST extraction can stay local without an LLM; semantic multimedia/document passes may use provider models/API keys and cost/network. Exported graph format is NetworkX node-link; some code paths write \`links\`, others \`edges\`: https://github.com/Graphify-Labs/graphify/blob/v8/graphify/paths.py . Nodes commonly have \`id\`, \`label\`, \`source_file\`, \`file_type\`; edges have \`source\`, \`target\`, \`relation\`, \`confidence\`, \`source_file\`. Provenance may be \`EXTRACTED\`, \`INFERRED\`, \`AMBIGUOUS\`.
5. Graphify has its own optional MCP server: \`python -m graphify.serve graphify-out/graph.json\` and HTTP transport with explicit host/API-key options. STAR does *not* launch arbitrary third-party stdio servers in this release; local query adapter has much smaller attack surface.
6. MCP security: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices . Treat tool output and webpages as data, not policy. Validate schemas and arguments at execution, isolate tool capabilities, and do not store access tokens in source or logs.

**Caveat:** graph algorithms or retrieval schemes do not mathematically increase reasoning capability. They can improve factual accuracy and reduce forgotten context if the relevant source is found and interpreted correctly; they can also introduce noise and latency. The benchmark below measures real improvement.

## How the implementation fits STAR

\`\`\`text
React Desktop  ─── Qt WebChannel allowlisted actions ─── desktop_core Settings
                            │                                   │
                            │                  STAR local agent / Qwen or LM Studio
                            │                                   │
                            └── integration status       intent-based tool exposure
                                                                │
                                ┌──────────────────┬────────────┴────────────┐
                                ▼                  ▼                         ▼
                           Agent Skills        Obsidian                  Graphify
                         discover/load/read   search/list/read        stats/query/explain/path
                                │                  │                         │
                         local SKILL.md       Markdown vault       graphify-out/graph.json
                                └──────────────────┴─────────────┬───────────┘
                                                                 ▼
                                         validated JSON tool results with provenance
                                                                 │
                                                existing agent history, checkpoints,
                                                project-scoped reviewed knowledge
\`\`\`

Existing STAR components preserved:
- \`star/agent.py\`: model/tool loop, single first system message, bounded tools and compaction;
- \`star/policy.py\`: unchanged Roblox Studio scope and edit controls, no arbitrary execute_luau;
- \`star/workspace.py\`: independently authorized workspace reads and writes;
- \`star/knowledge.py\`: reviewed/candidate knowledge separation and immutable image artifacts;
- \`star/react_shell.py\`: explicit command allowlist, no generic JavaScript shell/secret endpoint;
- \`star/desktop_core.py\`: app profile stored outside installer application directory.

There is **no automatic Obsidian-to-reviewed-memory sync**. Notes only enter a model response after an authorized call. Skills are instructions, not executable imports. Graphify's \`graph.json\` only becomes visible to STAR if present inside the selected workspace and graph queries are enabled.

### Tool contracts included

| Tool | Arguments | Purpose | Mutation? |
|---|---|---|---|
| \`star_skill_catalog\` | none | Name/description of available skills | No |
| \`star_skill_load\` | name | Body of one local SKILL.md, bounded | No |
| \`star_skill_reference\` | name, path | A small text reference file | No |
| \`star_obsidian_search\` | query, limit | Keyword-ranked Markdown matches, excerpts | No |
| \`star_obsidian_list\` | limit | Local vault Markdown file paths | No |
| \`star_obsidian_read\` | path | A selected note, truncated | No |
| \`star_graphify_stats\` | none | Graph count/metadata from file | No |
| \`star_graphify_query\` | question, limit | Top-matching graph nodes with direct edges | No |
| \`star_graphify_explain\` | concept | Direct graph neighborhood | No |
| \`star_graphify_path\` | start, end | Bounded breadth-first relationship chain | No |

Implementation files: \`star/agent_skills.py\`, \`star/obsidian_bridge.py\`, \`star/graphify_bridge.py\`, \`star/intelligence.py\`. They are Python modules in the standard desktop runtime and need no additional packages beyond existing \`jsonschema\`. New configuration fields are \`obsidian_vault\`, \`obsidian_enabled\`, \`skills_enabled\`, and \`graphify_enabled\`.

### Security details

- **Obsidian OFF by default.** Enabling requires an existing vault path. Search recursively covers Markdown, skips hidden folders, excludes symlink files/folders, protects \`.obsidian\`, caps candidate notes and note bytes, never edits note contents, and does not need plugin token or network.
- **Graphify locally authorized by workspace path.** Read \`graphify-out/graph.json\` only; enforce workspace containment, symlink exclusion, 20MB file cap, 60K nodes/160K edges cap, result caps, and annotate confidence/provenance. Never run graphify CLI on user files automatically or open its HTTP server.
- **Agent Skills read-only.** Discovery supports \`<workspace>/.agents/skills/\`, \`<workspace>/skills/\` and \`<STAR app data>/skills/\`. A starter pack is created without overwriting existing skill files. Skills cannot request additional privileges or run bundled scripts. Reference reading only supports small Markdown/text/JSON/YAML files under \`references/\` or \`assets/\`.
- **Tool execution is checked twice:** only contextually registered groups appear in the model's tool schemas, and each call is checked against its enabled set and JSON Schema. Calling an omitted tool fails. Existing workspace and Roblox checks remain separate.
- **No provider credentials or .env:** no automatic API key registration, authenticated remote MCP, Internet crawl, or arbitrary command execution.
- **Prompt-injection stance:** never blindly follow instructions embedded in notes, graph metadata, tool outputs or skills. They are untrusted references; repository and user policy control permissions.

## Getting STAR ready (Windows)

**Step A: Agent Skills (no separate install required)**

1. Update to a **reviewed build that includes the candidate**. The new starter skills are written to your local STAR application data under \`skills/\`.
2. Open STAR → Developer tools: see the detected skill count. In Settings enable Agent Skills.
3. You may add manually reviewed skill directories under \`<project>/.agents/skills/<name>/SKILL.md\`. The directory name must match frontmatter \`name\`; the required \`description\` should explain when to use it.
4. Ask: "Use your Roblox UI skill to inspect this interface and give an implementation plan." STAR should call the catalog, then load the appropriate skill and only any needed references. A loaded skill still cannot authorize an edit by itself.

**Step B: Obsidian vault (no plugin required for current read-only adapter)**

1. Keep your existing Obsidian vault local as usual.
2. In STAR Settings → Knowledge & expert tools, choose the vault root folder; check **Allow read-only Obsidian vault access**; Save.
3. Ask: "Search my Obsidian notes for VALEN design decisions; cite the note paths you used."
4. STAR returns search results and may read the matched note. For better recall, put project names and clear headings into notes.
5. Optional *future extension:* the Local REST API with MCP adds live metadata, full-text search, tags/frontmatter editing and notes creation. This will require separate local-only authentication, UI permissions, secret storage outside settings.json, transport compatibility tests and confirmation for writes. It is not implemented.

**Step C: Graphify export**

From a developer terminal, in a project directory you own:

\`\`\`powershell
uv tool install graphifyy
cd C:\path\to\your\project
graphify extract . --code-only
\`\`\`

The \`graphify extract . --code-only\` command is documented for deterministic local code AST extraction. It skips docs/media; no cloud model is required. This CLI install/build step happens **outside STAR**, by the user; STAR never auto-installs or executes it. For richer documentation-oriented graphs, inspect Graphify's privacy/cost settings before enabling semantic passes, e.g. \`graphify extract ./docs --backend ollama\` (may consume local VRAM) or a provider-specific backend (may send content off-machine).

Select the **same project root** in STAR Settings → Workspace folder. Enable Graphify queries. When \`<project>/graphify-out/graph.json\` exists, the Developer tools page shows **Export detected**. Ask: "Trace from Inventory UI to DataStore through the Graphify graph; distinguish extracted and inferred edges."

If the graph is stale after significant code edits, run \`graphify update .\` from the project root. Do not equate "export present" with "latest source captured"; AST indexing should be compared with your current commit/file timestamps. Graphify's native \`graph.html\` remains available to view separately; STAR's React graph visualization is *not yet implemented*.

## Performance research and acceptance criteria

Progressive disclosure improves context efficiency when many tools and references exist. However, **avoid promising it will always be faster**. Benchmark against identical offline conditions/model/hardware (cold and warm), including:

| Benchmark | Baseline and new behavior | Proposed release gate |
|---|---|---|
| Ordinary chat | No unnecessary schema injection; streaming remains active when there are no active tools | No regression in p50/p95 first-visible-token latency beyond 10%, measured not guessed |
| Obsidian retrieval | Exact project decision from 100+ representative notes, note path correctly cited | ≥ 90% correct grounded answers; zero cross-vault reads |
| Graphify dependency task | Real checked-in graph and scripted source change, correct relation trace | ≥ 85% precision on manually labeled relationships; extracted vs inferred distinguished |
| Skills | Skill selection given 30 diverse prompts, proper lazy-load of SKILL.md and refs | ≥ 90% right skill or deliberate abstention; never auto-execute script |
| Security | Traversal, symlink, malformed/oversized JSON/Markdown, prompt injection and stale graph | Zero unauthorized reads, writes or subprocesses; correct explicit error messages |
| Model stability | Qwen tool-calling and no-tool message, compaction, data privacy | No system-role regression, no missing-call-ID exception |
| Real runtime | Windows 11 packaged PyInstaller, 100–150% scaling, 8GB-class VRAM | CI success plus manual GUI/model acceptance; not satisfied by mock tests |

Targets above are **proposed goals**, not observed benchmark scores.

### What must be done before declaring the release production-ready

1. Merge only after owner review and successful Python, TypeScript, build/test and dependency audit. Protect the repo's existing release workflows.
2. In Windows, test real llama.cpp/Qwen tool selection, multi-turn results and the 4K context case. The backend may refuse large schemas even if the code compiles.
3. Test against real Obsidian vaults including Unicode notes and Windows path casing. Ensure privacy/offline behavior and no writes.
4. Test Graphify on an actual Roblox/Luau repo. Inspect code extraction coverage: some Luau syntax may not have Graphify's Python/TS-quality AST path; unsupported languages require a separate extraction strategy. Inspect graph source, don't assume it understands all Roblox assets.
5. Install updated Windows Setup over older STAR and verify chat SQLite, approved project references, settings and models survived unchanged.
6. Measure p50/p95 TTFT, full request time, context bytes, token use (where supplied), unauthorized tool rates and accuracy before asserting actual improvement.

## Subsequent phases worth pursuing (not in this PR)

**Phase 2: Semantic/hybrid note recall.** FTS5/BM25 for exact text, optional local embeddings for semantic recall, provenance snippets, freshness invalidation and user-approved memory promotion. Compare BM25 alone against vector+rereanking before adding GPU contention.

**Phase 3: First-class tool management.** Explicit per-project tool catalog, allow/disable/status/errors, runtime health checks, sensible discoverability when implicit prompts lack a trigger, budget-aware planning and user-visible source references.

**Phase 4: Obsidian authenticated MCP.** Add an opt-in local HTTPS MCP client with OS keychain storage, pinned/local CA validation, protocol negotiation, tool-level read/write ACLs, preview/diff and explicit confirmation before changes. Default read-only. Do not expose full vault CRUD to a local model without guards.

**Phase 5: Graphify incremental graph and UI.** Optional background incremental *read-only* graph refresh by user-approved job; graph node/edge browser, click-to-source, filters for confidence, stale indicators and integration with STAR's project UI. Auto-indexing is an external side effect, so never enable by merely viewing a graph.

**Phase 6: Evaluation-driven tool orchestration.** Dependence graph tasks, parallel read-only research where safe, staged code edits in isolated worktrees, regression tests, Studio screenshot testing, failures with traces, and human-reviewed draft PRs. Do not confuse subagent count with success or override STAR's established Roblox permission gate.

---

**Bottom line:** The delivered code is a *real, scoped first slice* that lets STAR discover Agent Skills, search an explicitly chosen Obsidian Markdown vault and inspect an existing Graphify export through its local model's function-calling loop. It is not yet full third-party MCP support, a deployed Windows build, an automatically regenerated graph, or a demonstrably improved foundation model. Its value is testable grounding and controlled workflows.
