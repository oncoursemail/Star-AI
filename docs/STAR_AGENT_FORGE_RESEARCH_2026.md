# STAR Agent Forge — Multi-Agent Execution, Self-Created Tools and Evidence-Driven Memory

**Research and implementation review:** October 9, 2026  
**Base:** STAR's latest MCP integration candidate, PR #30  
**Stacked feature PR:** https://github.com/oncoursemail/Star-AI/pull/37  
**Source:** https://github.com/oncoursemail/Star-AI  
**Status:** testable draft source code, NOT a released Windows installer, new trained foundation model, production-safe arbitrary execution environment, or evidence of superior frontier intelligence.

## Executive decision

Build a **verified agent harness**, not an unbounded number of autonomous model copies.

STAR already had a real local Qwen-compatible model loop, project-scoped knowledge, Agent Skills discovery, Obsidian read-only Markdown/MCP support, Graphify export queries and a draft curated 2026/legacy MCP gateway. The additions here address three remaining structural gaps:

1. **Subagents that really execute:** \`star/orchestration.py\` described a dependency graph, but never ran workers. \`star/specialist_agents.py\` now executes constrained, separate model completions, preserving dependencies and returning evidence-labeled candidate reports.
2. **Reusable tools Star can propose:** \`star/selfbuild.py\` could propose Python source in isolated worktrees, but only syntax-checks it and never executes it. \`star/tool_workshop.py\` adds a *declarative* tool composer with previews and human review. Approved recipes can safely run because every operation is a fixed, existing read-only adapter—not generated Python code.
3. **Search that finds the right prior decision:** Previously, reviewed knowledge was found with basic keyword SQL LIKE sorted by newest first. \`star/knowledge.py\` now implements optional SQLite FTS5/BM25 ranking with a one-time legacy note migration and fallback to the old retrieval path.

These three improvements retain the original single STAR chat, original SQLite chats, strict Roblox Studio edit scope, private user data directory, model lifecycle and authentication boundaries.

## 1. Independent research — what works in good agent harnesses

### Agent orchestration: manager remains responsible

OpenAI's Agents SDK distinguishes two common patterns:

- **Agents-as-tools:** a manager agent retains user-facing responsibility and calls specialists for bounded subtasks;
- **Handoffs:** a specialist takes over the conversation and owns later responses.

STAR's user experience should keep **one principal assistant**, so we use the first pattern. The main agent decomposes a request into 1–3 subtasks; specialists each get exactly one scoped goal and selected read-only evidence, respond with candidate analysis, and the main agent reconciles findings. They do not inherit the parent agent's tool schemas, writable workspace, GitHub credentials, Obsidian token, MCP sessions, Roblox Studio edit scope or previous entire user transcript.

References:
- https://openai.github.io/openai-agents-python/multi_agent/
- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/handoffs/
- https://www.anthropic.com/engineering/building-effective-agents
- https://www.anthropic.com/engineering/multi-agent-research-system

Anthropic has reported significant research-time reductions in its own parallel architecture, but its benchmark assumes sufficient model and search capacity. **This is not transferable as a promised speed gain** to a 32GB-RAM consumer computer hosting one local model. For STAR we select **one concurrent specialist by default** and allow at most two after deliberate user configuration. More parallel calls can increase waiting time, RAM contention and context interference with a single local inference server.

### Dynamic tools: design and evaluate, don't add hundreds blindly

Tool count is not the same as capability. Every tool schema consumes prompt budget; every ambiguous tool name makes model selection harder. Research on tool design favors clear names, parameter contracts, predictable error codes, source attribution and evaluation fixtures.

A safe way to become "able to create more tools" is an explicit **proposal → simulation/preview → evaluation → review → activation** lifecycle. A model may write a candidate spec, but may not promote itself, silently expand permissions, access a new host, execute a generated script or change its own tests.

References:
- https://www.anthropic.com/engineering/writing-tools-for-agents
- https://www.anthropic.com/engineering/advanced-tool-use
- https://www.anthropic.com/engineering/code-execution-with-mcp
- https://agentskills.io/specification
- https://openai.github.io/openai-agents-python/guardrails/

**Tradeoff:** Some advanced platforms permit agents to write code that calls MCP tools. That can be efficient with a true process sandbox and strict capabilities. Star's current repository does not yet have a properly isolated interpreter/process runner for arbitrary generated code, and its users may own valuable Roblox assets, local source repositories or Obsidian notes. This stage therefore allows only *interpreted, typed, declarative recipes* composed from already reviewed operations. The old isolated-worktree builder can still propose Python skill code for human review, but neither workflow runs arbitrary generated Python without a future sandbox/gate.

### Memory: retrieval relevance and source provenance matter more than length

SQLite FTS5 provides an indexed inverted search and \`bm25()\` scoring. It is usually light enough for existing SQLite-based desktop apps, avoiding a separately hosted vector database. The document score is not a confidence score: lower BM25 ranks mean better lexical matching, not that a statement is correct.

For STAR this means:
- separate projects remain separate in SQL queries;
- unreviewed model-generated memories are **not** trusted project decisions;
- results retain \`source\`, \`revision\`, \`reviewed\`, \`kind\`, \`id\`;
- legacy data is indexed, not erased or copied into a new user-profile directory;
- query text is converted into literal safe terms for FTS \`MATCH\`, not passed as arbitrary expressions;
- if FTS5 isn't compiled into an unusual local Python build, the existing keyword path still works.

Reference: https://www.sqlite.org/fts5.html

## 2. What the actual code does

### A. \`star/specialist_agents.py\`

**Input schema (\`star_delegate_research\`):**

\`\`\`json
{
  "tasks": [
    {
      "id": "ui",
      "role": "ui",
      "goal": "Compare the current UI with the approved reference",
      "sources": ["knowledge", "workspace", "obsidian"]
    },
    {
      "id": "review",
      "role": "review",
      "goal": "Identify overlap, security, and validation failures",
      "dependencies": ["ui"],
      "sources": ["graphify"]
    }
  ]
}
\`\`\`

The role comes from STAR's existing finite set (planner/research/luau/ui/animation/environment/review/integration). Source choices are limited to knowledge, Obsidian, workspace, Graphify, and skills. Task graph validation uses \`TaskPlan\`: rejects cycles, unknown dependencies, duplicate IDs and invalid resource names. All tasks have an empty write set.

A worker gets:
- its own initial system instructions;
- its exact task and role;
- bounded, source-labeled snippets obtained through the existing user-enabled adapters;
- short candidate results from completed dependencies.

It does **not** get the parent system prompt, persistent secrets, original full chat transcript, any tools, browsing, filesystem writes, MCP or Studio access. Model tool calls inside a worker are rejected; results are not auto-promoted into reviewed memory.

At most three tasks per invocation, two delegations per agent turn, one or two concurrent workers, 75 seconds per worker completion, fixed maximum output tokens, and compact report truncation. Failed workers are labeled failed, and dependent workers are blocked rather than silently receiving fabricated evidence. The parent synthesizes the final answer.

**Evidence correctness:** A model answer that says "I tested the game" is not proof of a Studio test. The system instructions explicitly prohibit unobserved claims, and the returned report labels all prose as model-generated candidate analysis. Future empirical agent evaluations should also use tool logs and external graders.

### B. \`star/tool_workshop.py\`

Each project stores its tool proposals in private \`%APPDATA%\\STAR\\tool-workshop.sqlite3\` on Windows, distinct from the versioned app installation. The store has statuses:
\`pending\`, \`approved\`, \`disabled\` (plus schema support for \`rejected\`).

STAR may use:
- \`star_toolforge_list\`: discover current tool candidates and approved recipes;
- \`star_toolforge_propose\`: create a **pending** immutable name, description, and list of read-only source steps;
- \`star_toolforge_test\`: preview a pending candidate on a query; a successful preview records bounded evidence;
- \`star_toolforge_run\`: run a tool that has both passed the preview gate and been explicitly approved in the native React developer interface.

The model has **no** \`star_toolforge_approve\`, \`star_toolforge_disable\`, file-writing or custom-code execution tool.

#### Supported "source primitives"

| Primitive | Reads | Actual adapter | Side effects |
|---|---|---|---|
| \`knowledge\` | Project-reviewed decisions and other notes only | \`KnowledgeStore.find\` or ranked retrieval | No external writes |
| \`workspace\` | Matching source code lines in selected directory | \`Workspace.call('workspace_search')\` | No source writes |
| \`obsidian\` | Keyword-ranked Markdown snippets | \`ObsidianVault.search\` with configured opt-in | No vault writes |
| \`graphify\` | Existing exported nodes and relationships | \`GraphifyGraph.query\` | No graph modifications |
| \`skills\` | Names and short descriptions of local Agent Skills | \`SkillLibrary.list\` | No skill execution |

There are no primitives for network calls, arbitrary MCP connections, Python, JavaScript, Luau execution, Studio editing, file deletion, file uploads, publishing, shell, model provider API calls or website actions. Each step takes the **same bounded runtime query**, not a string template that can write arbitrary program instructions. The model may compose up to four unique primitives. Each source result is capped by limit and total size; missing/disconnected sources produce explicit errors.

Example of a proposed reusable VALEN tool:

\`\`\`json
{
  "name": "valen-project-research",
  "description": "Combine reviewed decisions, approved Obsidian notes and the local code graph",
  "steps": [
    {"source": "knowledge", "limit": 4},
    {"source": "obsidian", "limit": 4},
    {"source": "graphify", "limit": 3}
  ]
}
\`\`\`

Model proposes; owner opens Developer Tools; owner tests with e.g. "inventory replication"; sees direct records and provenance; owner clicks **Approve**. On later relevant requests STAR can run the approved recipe. If the graph hasn't been exported, the preview fails and approval remains unavailable.

Limits: 30 proposals per project, two new proposals per chat task, four source operations per recipe, eight recipe executions per agent task. A different project cannot activate or read another project's recipes by ID.

### C. \`star/knowledge.py\` FTS5

Existing knowledge schema is preserved:
\`knowledge.sqlite3\` holds the original notes and content-addressed artifacts. An external-content FTS5 index is created within that same DB, with rowid linked to the old note IDs. A first-use migration indexes already existing notes. SQL triggers keep the index updated on note insertion/deletion/text update. No recorded human approvals or source revisions are changed.

Search uses literal token prefixes combined through a bounded OR expression, BM25 result order, an exact project predicate, and an independently enforced \`reviewed=1\` predicate. A missing FTS5 module falls back to \`find\`.

Project retrieval now calls \`find_ranked\` for relevant reviewed context, and the Tool Workshop and specialist worker can use the same approved knowledge.

**Important:** External tool output and AI summaries must not be put into \`reviewed\` state automatically. A better index can improve finding an answer but cannot certify correctness. If a project has not recorded approved facts, STAR should report missing evidence.

## 3. One unified interface, not a new mini-app

The user should still have exactly one Star AI chat. Developer Tools now contains, on a draft branch:

- A *Tool Workshop* section showing approved vs pending tools and their read-only sources;
- A live preview field with result snippets;
- **Test preview**, **Approve**, **Disable**, and **Refresh** controls;
- A *Specialist Research* section showing whether subagents are enabled and current concurrency;
- Existing Graphify, Obsidian, Agent Skills and MCP connection controls remain in the same navigation.

Settings has:
- \`tool_workshop_enabled\` toggle (no separate model process);
- \`specialists_enabled\` toggle;
- \`specialist_parallelism\` select (1 default, 2 optional);
- existing Studio edit, workspace-write and live MCP/Obsidian flags, unchanged.

Native Qt WebChannel handles exactly four new management actions:
\`listCustomTools\`, \`previewCustomTool\`, \`approveCustomTool\`, \`disableCustomTool\`.
These have explicit validation in Python and do not accept arbitrary file paths, executable commands, code, URLs, or authorizations. A random website does not receive the native bridge.

## 4. The next useful integrations, researched and ordered by value

**These are researched candidates, not newly implemented connectors in this PR.**

| Priority | Integration | Why it matters to STAR | Boundary |
|---|---|---|---|
| 1 | GitHub official MCP server | PR/issue/code searches, protected draft reviews and source history | Start \`--read-only\`, limited repos/toolsets; no auto-merge |
| 1 | Roblox Studio official MCP | Inspect scripts, GUI, place hierarchy, screenshots/playtests | Existing STAR scoped MCP; never bypass Studio policy |
| 1 | Roblox Open Cloud | Game/experience metadata, owned assets, universe config, datastore inspection | Key/OAuth scopes; no player-data writes or publication without approval |
| 2 | Microsoft Playwright MCP | Browser tests, React UI snapshots and accessibility assertions | Isolated browser/profile and domain restrictions |
| 2 | Figma official MCP | Editable design tokens, frames, native auto layout to code | Respect document access/license and separate write approval |
| 2 | Rojo/Rokit/Wally/Luau LSP | Deterministic filesystem-first Roblox code builds and reproducible dependencies | Version-pinned subprocesses only inside vetted build environments |
| 2 | Obsidian live MCP | Live notes, headings, tags and search | Existing candidate read-only MCP; no commands, deletes or note writes |
| 2 | Graphify local MCP | Code/dependency queries beyond the static graph file | Inspect supported \`.luau\` coverage, source revisions and stale edges |
| 3 | Blender + asset validation | Proper mesh/UV/rig topology inspection, imports, preview renders | Need true per-process sandbox; scripts can be arbitrary code |
| 3 | ComfyUI vision/image tools | Image generation/editing inside STAR chat using real workflows | Limit local VRAM pressure and media/file writes |
| 3 | YouTube/video ingestion | Public transcripts/frames, source-link research on tutorials | Terms, license, rate limits; no false claim that sampled frames = watched full video |
| 4 | Hosted tool marketplace | Expand curated MCP services after registry validation | OAuth issuer/audience binding; permissions per server/tool |
| 4 | Long-running tasks / MCP Apps | Resumable complex sessions and embedded provider UI | Protocol 2026 Tasks extension, explicit user consent and persistence |

Primary sources:
- GitHub MCP read-only/toolset controls: https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md
- Roblox Open Cloud and scope granularity: https://create.roblox.com/docs/cloud and https://create.roblox.com/docs/cloud/auth/api-keys
- Roblox Open Cloud storage permissions: https://create.roblox.com/docs/cloud/guides/data-stores
- Figma MCP: https://developers.figma.com/docs/figma-mcp-server/
- Playwright MCP: https://github.com/microsoft/playwright-mcp and https://github.com/microsoft/playwright.dev/blob/main/mcp/introduction.mdx
- Roblox package manager: https://github.com/UpliftGames/wally
- Agent Skills: https://agentskills.io/specification
- Obsidian Local REST API MCP: https://github.com/coddingtonbear/obsidian-local-rest-api
- Graphify local: https://www.graphiffy.com/mcp
- Modern MCP core: https://blog.modelcontextprotocol.io/posts/2026-07-28/

### Why not add every MCP tool immediately?

The 2026 MCP revision enables dynamic tool discovery and authorization but it is not a permission oracle. An external server could describe a dangerous tool as read-only or return malicious text. The correct progression is:

\`\`\`text
Candidate plugin from verified source
    ↓
Pin identity, version and address
    ↓
Inspect capabilities and schemas
    ↓
Choose per-project read/write scope
    ↓
Verify no hidden writes or network actions
    ↓
Test in a disposable environment
    ↓
Add to STAR registry with explicit user opt-in
    ↓
Run regression/evaluation suites
    ↓
Publish a reviewed, reversible update
\`\`\`

Do not automatically execute \`npx\`/Python packages from a marketplace in the primary STAR process. Registry metadata can improve discovery, but does not establish package integrity or code safety.

## 5. Longer-term AI self-improvement (technical, not magical)

The goal is **a measurable cycle of finding problems, proposing changes, proving improvements and retaining reviewed experience**.

### Stage A — Skill & read-only tool proposals (this draft)

The model notices repeatable patterns, proposes a named declarative tool, runs approved preview reads, captures evidence, then waits for owner review. Project-specific feedback and errors help future tool selection. Never call this model-weight training.

### Stage B — Candidate code tools in a process sandbox

Existing \`star/selfbuild.py\` already generates candidate Python modules in isolated Git worktrees. That *source* isolation is insufficient to safely execute arbitrary code. The next stage would need:
- separate sandboxed OS identity, restricted filesystem mount, process/network/resource limits, no secret environment, no unsandboxed Studio APIs;
- version-pinned dependencies and vetted packages;
- AST/static checks plus independently maintained tests;
- deterministic test fixtures for expected behavior and unintended side effects;
- logs and diff reviews, short-lived GitHub App draft PR and rollback support;
- independent approval for core policy changes and repository workflow updates.

Until these exist, generated Python stays **candidate source only**, and "Tool Workshop" recipes remain the only runtime-executed self-created tools.

### Stage C — Agent skill quality evaluation

Track per-skill and per-tool metrics:
- whether the agent selected the intended tool;
- whether it constructed correct structured arguments;
- whether a result was actually grounded in retrieved evidence;
- calls, tokens/bytes, latency and failures;
- security denials and accidental writes;
- test fixture coverage and real project outcomes.

Use a source-blind human acceptance subset and adversarial prompts with untrusted Obsidian notes and MCP descriptions. Improve tools only if reliability grows without unsafe regressions.

Official guide: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

### Stage D — Self-evaluation, not self-proclaimed intelligence

A proposed policy or tool change must outperform the prior version on relevant real tasks, not just generate a persuasive analysis. Track fixed evaluation datasets and a separate holdout set. Never let a self-writing model edit its own graders or retrospectively label its tests as passed.

## 6. Hardware/performance decisions

STAR's on-device local models may run on memory-constrained desktops. Three additional specialist calls can *worsen* perceived latency, even when the result has better coverage. Therefore:

- Default concurrency **1**, not arbitrary 20+ parallel local Qwen calls.
- Hard cap at 3 individual specialist goals, 2 invocations per parent turn.
- Reuse the already-configured local model (no forced provider key or new model install).
- Do not turn on specialist tool schemas for ordinary chat; reveal them on explicit agent/delegation requests.
- Model work done by a specialist is candidate analysis, not a new trained expert.
- Keep a small context: source excerpts limited before reaching workers, short outputs and no full previous chat duplication.
- Prefer one deterministic FTS query to a model call for simple project-memory questions.
- Use two specialists in parallel only if measured on the actual inference engine under load and observed stable RAM/VRAM usage.

Local model benchmark plan should distinguish:
\`TTFT\` (first visible token), \`latency_total\`, task success, per-model cache hit, prompt input token count, output count, tool schema overhead, GPU peak memory, process RSS, tool failures, response groundedness.

Proposed gates, **not measured performance claims**:
- simple-chat p50 TTFT no worse than the earlier STAR main baseline by more than 10%;
- enabled Tool Workshop adds no network requests by merely opening the tools page;
- a 3-worker task never launches more than 2 workers simultaneously and never issues unexpected tool calls;
- FTS search median latency lower than current LIKE-based scan at a representative 5,000-note local dataset;
- approved recipe accuracy and evidence provenance manually assessed on 50 realistic project tasks;
- zero unauthorized approvals, code execution, external writes or cross-project reads in adversarial fixtures.

## 7. Release and reconciliation gates

These changes were authored from \`feat/star-mcp-connections-2026\` (MCP PR #30), not blindly from \`main\`. The repository has multiple overlapping active contributors. The following must be reviewed before merge:

1. Check the final head of MCP PR #30 and the stacked PR #37 for a clean ancestry; if PR #30 is merged, rebase/retarget #37 onto new main.
2. Reconcile other open UI/AI branches (e.g., unified chat redesign PR #27 and fast-brain successor) by reviewing their latest source and merge order, not replacing whole files.
3. Run full offline Python tests, TypeScript typecheck, frontend tests, Vite build, screenshot capture, Windows PyInstaller packaging and packaged-app smoke test.
4. Verify old \`%APPDATA%\\STAR\` chats, settings, models, knowledge and approved reference artifacts survive upgrades. Tool Workshop creates its own new DB and does not delete any original tables.
5. Test FTS5 against a *copy* of a legacy profile and a large realistic data set before deploying to a real user's knowledge DB.
6. Test with actual local model tool-call protocol, a Qwen-compatible backend, Studio MCP, disconnected Obsidian and Graphify, malformed MCP server schemas and offline restarts.
7. Test UI 100/125/150% Windows scaling and 1050×680 resolution; no sloppy shapes, overlapping text or scroll traps.
8. Record real latency and user acceptance; unit tests alone do not prove AAA game production or model intelligence.
9. Never publish or auto-merge without owner's review of functionality, privacy and permitted scope.

## 8. Source links for continued learning and implementation

These are primary specifications, implementation repositories or first-party engineering references:

1. OpenAI multi-agent architecture — https://openai.github.io/openai-agents-python/multi_agent/
2. OpenAI handoffs and model context filtering — https://openai.github.io/openai-agents-python/handoffs/
3. OpenAI tool guardrails — https://openai.github.io/openai-agents-python/guardrails/
4. OpenAI Agents SDK — https://openai.github.io/openai-agents-python/
5. Anthropic effective agents — https://www.anthropic.com/engineering/building-effective-agents
6. Anthropic multi-agent research — https://www.anthropic.com/engineering/multi-agent-research-system
7. Anthropic writing tools with agents — https://www.anthropic.com/engineering/writing-tools-for-agents
8. Anthropic advanced tool use — https://www.anthropic.com/engineering/advanced-tool-use
9. Anthropic code with MCP — https://www.anthropic.com/engineering/code-execution-with-mcp
10. Anthropic agent evals — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
11. Agent Skills open specification — https://agentskills.io/specification
12. MCP 2026 release — https://blog.modelcontextprotocol.io/posts/2026-07-28/
13. MCP 2026 tools — https://modelcontextprotocol.io/specification/2026-07-28/server/tools
14. MCP Python SDK — https://github.com/modelcontextprotocol/python-sdk
15. SQLite FTS5 — https://www.sqlite.org/fts5.html
16. Obsidian Local REST API — https://github.com/coddingtonbear/obsidian-local-rest-api
17. GitHub MCP read-only profiles — https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md
18. Roblox Open Cloud — https://create.roblox.com/docs/cloud
19. Roblox data stores — https://create.roblox.com/docs/cloud/guides/data-stores
20. Figma MCP — https://developers.figma.com/docs/figma-mcp-server/
21. Playwright MCP — https://github.com/microsoft/playwright-mcp
22. Wally Roblox — https://github.com/UpliftGames/wally
23. STAR main repository — https://github.com/oncoursemail/Star-AI
24. STAR earlier MCP candidate — https://github.com/oncoursemail/Star-AI/pull/30

---

## Final engineering assessment

STAR's next generation should not be defined by a marketing claim that it has "the most tools" or "has become smarter and smarter" merely because it can create scripts. An excellent local assistant will excel at measured workflows: it retrieves the correct reviewed evidence, uses only the necessary tools, delegates cleanly where beneficial, generates safe reusable tool proposals, and verifies changes against real outcomes without losing past context or user data.

**This candidate concretely implements: (a) running specialist model calls, (b) reviewable dynamic read-only tools, (c) BM25 ranked reviewed memory, (d) a cohesive native management UI, and (e) regression fixtures.** It intentionally does not deliver unbounded autonomous code execution, direct GitHub publishing or live-game changes.
