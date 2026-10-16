# STAR AI 2.0 — Universal Open-Agent Fleet, One-Chat Orchestration, Game Engines, and Verified Collective Learning

**Research checkpoint:** 2026-10-15. **Branch:** `star/open-agent-universe-game-engines-20261015` (reviewable draft against `star/next`). **Classification:** source-linked research + bounded, read-only agent-catalog prototype. **NOT SHIPPED:** no external CLI/model/provider connected, no token spent, no game engine launched/built, no automatic lessons promoted. All user accounts, repository secrets, private media, and chat logs remain outside the public repo.

## 0. Owner requirement, interpreted accurately

STAR should be a **single conversation with a full cooperative AI workforce**, not a service switcher: start with STAR's own private model, use any legitimate installed or consented model/agent where it helps (free-first), coordinate agents and tools in parallel, share exactly the information they need, and **learn from independently verified results**. STAR should gain excellent Roblox, Godot, Unity, Unreal, Blender, web/desktop, media/VFX, and future proprietary game-engine building abilities.

An **AI agent** is a software harness that invokes models/tools. An **AI model** supplies inference. An **MCP server** supplies tools/data. An **SDK/orchestrator** controls an agent loop. They are NOT synonyms: an MIT CLI that calls a billable Claude API is not “free inference.” A ChatGPT/Claude consumer plan is not always a generic developer API license. Models across companies cannot automatically rewrite each other's model weights; what STAR can share is permitted, reviewable skill instructions, project memory, summaries, tests, and artifacts. The benchmark target is **quality accepted by owner per dollar and minute**, not number of active agents.

## 1. Audited STAR baseline and integration constraint

At `star/next`:
- `star/orchestration.py` is a validated task DAG and path conflict planner; `star/agent_runtime.py` executes bounded independent tasks with deadlines and failure propagation; `star/team_service.py` has local/LAN read-only specialists. These are *not yet* a universal cloud/CLI conductor.
- `star/providers.py` includes on-device, STAR Server LAN, and API-key provider routes (GroqCloud, OpenRouter, Gemini, Cerebras), NOT proof of access to Grok from xAI or consumer ChatGPT/Claude accounts.
- `star/model_fleet.py`, `star/resource_planner_service.py` and existing local GGUF/llama.cpp paths enforce memory/compute limits.
- `star/game_projects.py`, `star/engine_evidence.py` already do safe **read-only** Godot/Unity/Unreal project discovery, dependency inspection and command preview; `docs/UNIVERSAL_GAME_DEVELOPMENT_RESEARCH.md` and `docs/research/engines/*` already cover many game-engine research candidates. No actual autonomous Unreal/Unity/Godot editor code-writing bridge is claimed.
- `star/knowledge.py`, `star/learning.py`, `star/eval_gate.py` and night-school preserve project-scoped, evidence-gated learning. Draft [#413](https://github.com/oncoursemail/Star-AI/pull/413) introduces cross-provider **candidate-only** evidence contracts; it isn't in `star/next`.
- Existing [Agent Fleet #406](https://github.com/oncoursemail/Star-AI/issues/406), [Free API #407](https://github.com/oncoursemail/Star-AI/issues/407), [Conductor epic #414](https://github.com/oncoursemail/Star-AI/issues/414), [STAR next staging #368](https://github.com/oncoursemail/Star-AI/pull/368) are important coordination points. Do not duplicate their runtimes or silently merge anything to public release.

**This candidate's only executable addition:** `star/agent_ecosystem.py` + `tests/test_agent_ecosystem.py` are a *read-only, source-linked provider/agent catalogue and conservative eligibility preview* that distinguishes open agent software from actual authenticated/zero-charge/host-tested model access. It makes no CLI/network calls and never changes authorization. Real host probes, agents, and UI wiring belong in subsequent reviewed PRs.

## 2. The actual free/open-agent universe (not just Codex and Claude)

The source-linked catalog is curated, not literally every project on the internet; the extension point is open and adapters must be evaluated/approved before appearing as connected. All “free harness” entries still have their own license, executable risk, models, and service terms.

### Tier A — highest-value first integrations

| Candidate and primary source | What STAR can borrow | Actual money/access implication | Suggested integration |
|---|---|---|---|
| **[Gemini CLI](https://github.com/google-gemini/gemini-cli)** | Open-source code/research/web/terminal/MCP agent; large provider context; eligible personal Google account quota | [Google's CLI docs](https://google-gemini.github.io/gemini-cli/docs/quota-and-pricing.html) list a free-account tier with 1000 model requests/day and 60/minute, but provider may dynamically change availability and model family | Genuine CLI/ACP capability probe, signed-in state, quota/refusal; first free-account candidate |
| **[OpenCode](https://github.com/anomalyco/opencode)** | Headless `opencode serve` and `opencode acp`, session events, broad provider model configuration | Open software, inference may be local/free/paid depending on choice; HTTP server must use loopback+auth | Prioritize ACP, else authenticated local server SDK with actual streaming and approvals |
| **[goose](https://github.com/aaif-goose/goose)** | Open-source general agent, CLI, API, skills and MCP; can act as an ACP server and compose with coding agents | Open-source agent; bring your own local/hosted model; all extension/network permissions must be scoped | Local ACP worker for noncoding/research/data tools; profile Rust process overhead |
| **[OpenHands SDK + Agent Canvas](https://github.com/OpenHands/software-agent-sdk)** | SDK workspace/event model, Docker/Kubernetes ephemeral workspaces; [Canvas](https://github.com/OpenHands/OpenHands) fronts Claude, Codex, Gemini, Pi, OpenCode, and native agent backends | Self-hosted software is not free GPU inference or cloud hosting | Benchmark its isolation/events; integrate one SDK backend rather than replacing STAR frontend |
| **[Aider](https://github.com/Aider-AI/aider)** | Terminal pair programmer, codebase repo map, structured code edits, test-driven repair | Open source; BYO cloud key or adequate local model | Optional single-task coding worker and source-map benchmarking |
| **[Cline](https://github.com/cline/cline)** | Coding agent in IDE/CLI/desktop, tool approvals, browser+MCP | Open source; model inference separate | CLI/SDK pilot only if reliable noninteractive stream and permission control |
| **[Continue CLI](https://github.com/continuedev/continue)** | Configurable CLI `cn -p`, `--readonly`, `--allow`, local/remote models and editable rules | Open CLI, available providers and Continue account or API key may be necessary | Good strictly read-only reviewer when configured/probed |
| **[Pi](https://github.com/badlogic/pi-mono)** | Compact coding agent, SDK, `pi --mode rpc` JSONL, extensible skills/tools | Software open; BYO providers/subscriptions; extensions can execute code | First-class typed RPC adapter candidate; no external extensions by default |
| **[Kilo Code](https://github.com/Kilo-Org/kilocode)** | Headless coding/plan/review/debug roles, many provider options, MCP | OSS harness, provider charges/quotas; **never turn on `--auto` in unsandboxed teams** | Scoped `kilo run` CLI as Rilo has researched |
| **[Qwen Code](https://github.com/QwenLM/qwen-code)** | Open-source coding-agent UI, flexible model providers | **[Current official provider guide](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/model-providers/): the Qwen OAuth free tier ended on 2026-04-15.** It can still be used with separately configured models; don't list 2,000 free requests/day | BYO-model CLI adapter; test whether local/honest no-spend route exists |
| **[SWE-agent](https://github.com/SWE-agent/SWE-agent)** | Research-driven repository issue repair agent and tool/evaluation design | Code open; model and sandbox costs extra | Benchmark worker harness or use as inspiration for repair tasks |

### Tier B — specialized and complementary

| Candidate | Useful capability | Guardrail / next step |
|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | Open-source CLI/gateway and proposed memory/skill self-improvement mechanisms; CLI/desktop automation | Learn how skills are proposed and versioned; STAR must independently verify every candidate, never auto-import shared credentials or write private memory to GitHub |
| [Plandex](https://github.com/plandex-ai/plandex) | Multi-file/multi-step plan and cumulative diff review sandbox; practical lesson in checkpointed large-project editing | Windows native support is limited (WSL recommended), cloud hosting wind-down; compare its diff/eval behavior under rights-cleared fixtures |
| [OpenClaw](https://github.com/openclaw/openclaw) | Broad personal-assistant/Discord/messaging gateway and pluggable model/agent harness architecture | Risk of privileged broad device/credential access; opt-in dedicated sandbox only; do NOT introduce a second permission master into STAR |
| [Browser Use](https://github.com/browser-use/browser-use) | Open-source browser agent, local Playwright/Chromium + selectable LLM | Python library free; hosted inference/browser costs extra; isolate profiles, approvals and network |
| [Google ADK](https://github.com/google/adk-python) | Framework for Google-style agents, event graphs, skill catalog and MCP; [agent-to-MCP bridge](https://github.com/google/adk-python/blob/main/docs/guides/tools/mcp_tool/agent_to_mcp/index.md) | This is an SDK, **not a free model**. Use ADK agents as bounded tools only with owner-selected auth |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | Enterprise agent/orchestration SDK with *sequential, concurrent, handoff, group chat, magentic* patterns, checkpoint/human approval | Its 1.0 successor makes [AutoGen](https://github.com/microsoft/autogen) a maintenance-mode legacy option. Study abstractions, don't rewrite STAR's scheduler |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/) | Managers call agents-as-tools or hand off ownership; guardrails, tracing, sandbox tools, MCP | Library alone is free but production model/tool requests may incur API costs |
| [Claude Agent SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/overview) | Real agent loop, subagents and tools; subscription-backed use where terms officially permit | Distinguish allowed subscription harness use from metered Anthropic direct Messages API |
| [Codex app-server](https://openai.com/index/unlocking-the-codex-harness/) | Bidirectional structured local agent events, state, approvals, resumable coding runs | Official ChatGPT-plan integration for eligible apps requires consent; no entitlement assumption |
| [GitHub Copilot SDK](https://github.com/github/copilot-sdk) | Coding agent harness and programmatic workflows, potentially existing account access | Verify subscription/terms/entitlement and real SDK API; no account token scraping |
| [Ollama](https://github.com/ollama/ollama) & [llama.cpp](https://github.com/ggml-org/llama.cpp) | Private local model hosting, dynamic model selection, tool calls through host-managed wrappers | Not editing agents; weights, RAM, CPU/GPU time and electricity still required |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | Local image/video/audio/3D node graphs and API workflows | Media-generation *workflow engine*, not coder; custom nodes and model-specific licenses require review |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | UI structure/screenshot/interaction and web-app visual regression | Not an inference model; use restricted domain/project and separate browser profile |
| [Blender MCP](https://github.com/ahujasid/blender-mcp) | Blender scene, model, material and render tools | Third-party community project; arbitrary Python/telemetry/plugin exposure needs explicit review |
| [Roblox Studio built-in MCP](https://create.roblox.com/docs/studio/mcp) | Native Studio DataModel/Luau and testing/editing of owner-approved sandbox place | Keep existing STAR Studio authorization/undo; this is a tool, not an AI model |

**No reliable “all models free forever” route exists.** An agent catalogue needs a **time-stamped entitlement and capability check** that says `installed`, `model login verified`, `scoped approval`, `free quota confirmed`, `remaining?`, `usage billed?`, `local-only?`, `last checked`. Unknown means unknown, not connected/free. No limit evasion through account rotation. Frontend must not advertise provider aliases as verified best-tier or verified no-charge.

## 3. OpenAI/ChatGPT tool inventory, researched as product vs API

**Important:** tools visible inside the ChatGPT product are *not automatically callable from the public API* or exportable to STAR. STAR must use sanctioned app/connector integrations and implement comparable features itself when an embedded surface isn't exposed.

| Tool surface | Official evidence | What to adapt to STAR |
|---|---|---|
| **OpenAI platform Responses tools** | [Tools overview](https://developers.openai.com/api/docs/guides/tools) | web search with citations, vector/file search, image generation/editing, sandbox Python/code interpreter, shell, structured apply_patch, computer use, function calling, remote MCP, skills, deferred tool search and programmatic tool orchestration |
| **Agent managers and handoffs** | [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/) | Coordinator keeps user-facing thread; agents-as-tools for bounded specialist work; explicit handoff when specialist should take over |
| **Codex local coding harness** | [Codex App Server engineering](https://openai.com/index/unlocking-the-codex-harness/) and [repository](https://github.com/openai/codex) | Persistent native per-agent conversations, edits, approvals, structured progress; do not parse random terminal styling when structured events exist |
| **Multi-agent hosted orchestration** | [Multi-agent Responses API](https://developers.openai.com/api/docs/guides/responses-multi-agent) and [Agents API](https://developers.openai.com/api/docs/guides/agents-api/multi-agent) | Distinguish provider-managed subagents from STAR-hosted heterogeneous workforce; provider APIs may charge separately |
| **Tool search** | [Deferred tool loading](https://developers.openai.com/api/docs/guides/tools-tool-search) | STAR has many MCP/engine tools—keep only compact names in context; lazily load exact validated schemas |
| **Code/file execution** | [Shell](https://developers.openai.com/api/docs/guides/tools-shell), [Code Interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter), [Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) | Host-controlled execution sandboxes, exact artifact hashes, test receipts, bounded file diffs |
| **ChatGPT Work browser/app plugins** | [ChatGPT cloud browser](https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt), [plugins](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt) | Product-specific account/site actions must remain within documented integrations; STAR can build its own scoped browser+MCP/connector experiences; user consent for account flows |
| **Developer docs as tool** | [OpenAI Docs MCP](https://developers.openai.com/learn/docs-mcp) | Add an approved **read-only** documentation connector to stay source-current; don't confuse it with the paid model API |

**Recommended reusable STAR plugin capabilities:** Search, Read Docs, Search Local Project, Code/Terminal Sandbox, Tests, Browser Preview/Screenshot, UI QA, Image/Video/Audio, Blender/3D, Godot/Unity/Unreal/Roblox, GitHub Draft PR, Memory/Skill Proposals, Monitoring, Debugger, and Approved External Accounts. Every tool has source/licence/schema/version/owner/permissions/cost/timeout/cancellation.

## 4. Anthropic/Claude tool inventory and what to port

| Official component | Benefit for STAR |
|---|---|
| [Claude Platform tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference) | Server: web search, web fetch, code execution, advisor, tool search, MCP connector. Client: memory, bash, text editor, desktop computer use and browser toolsets. Version and model compatibility matter |
| [Claude Code custom subagents](https://code.claude.com/docs/en/sub-agents) | Independent limited context and permissions for reviewer/designer/repair/asset specialist roles; each additional model call consumes quota |
| [Claude Code lifecycle hooks](https://code.claude.com/docs/en/hooks-guide) | Deterministic after-edit tests, before-command permissions, task completion notifications and evidence capture. Hooks are code execution and must be reviewed/pinned |
| [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/agent-setup) | Versioned agent configuration (model/tools/MCP/skills), persistent sessions, autonomous workflows; typically hosted metered API use |
| [Claude Managed Agents session threads](https://platform.claude.com/docs/en/managed-agents/session-threads) | Good reference for subagent event streams, per-thread approvals and joint top-level timeline |
| [Claude tool combinations](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-combinations) | Web search→fetch→verify, bash+editor debugging, and intentionally slower screenshot-based computer automation when no direct API |
| [Official SDKs](https://platform.claude.com/docs/en/cli-sdks-libraries/overview) | Agent SDK vs direct Messages API are distinct pricing/auth surfaces; source-supported clients in several languages |

**Shared tool principle:** A model requesting a tool is not the executor. STAR's central host must decide whether a task's declared grant permits that exact operation; external agents get only the relevant grants and outputs. Avoid handing all tools to all models; tools-as-needed saves context and limits blast radius. This also makes evidence independently observable.

## 5. STAR Conductor: one chat, genuine team, not duplicated windows

Proposed experience:

```text
USER: "Make a polished multiplayer game and teach STAR everything that worked"
   |
   v
STAR Conversation / Project Memory / Owner-Approved Tools
   |
   +---- Mission contract: scope, output, reference, budget, privacy
   |
   +---- Planner candidate: STAR / Gemini / Claude / Codex / OpenCode / selected
   |        [model proposes plan, NEVER grants its own permissions]
   v
Host-owned DAG + Worktree Scheduler + CPU/RAM/VRAM Lease + Token/Cost Budget
   |
   +-- Gemini CLI / OpenCode: research & code proposal [parallel where independent]
   +-- local fast model: source indexing, repeat lint, simple tasks
   +-- Claude/Codex/other advanced subscription: architecture or hard repairs
   +-- specialist: Godot/Unity/Unreal/Studio/Blender engine-specific bridge
   +-- ComfyUI: image/texture/visual variants (if approved and resource-admitted)
   +-- independent verifier: tests, screenshots, frames, security, owner style gate
   |
   v
ONE THREAD: source-linked progress + status + artifacts + failures + decisions
   |
   v
ONE INTEGRATION PROPOSAL: reviewed diff/engine build/playable proof
   |
   v
LEARNING CANDIDATES → independent paired evaluation + owner review → shared skill
```

### Three different things under “one chat”

1. **Unified presentation:** one conversation feed, filterable internal agent messages, live task tree, source/handoff links; tool output inline collapsible. Only STAR and user are top-level speakers by default. Visible specialist content is summarized without hiding necessary errors.
2. **Shared mission state:** a canonical append-only project/run ledger stores goal, branch SHA, task DAG, dependency state, resource leases, cancellation, allowed tool classes, artifacts, approvals, trusted test receipts and retrieved evidence pointers. This state is versioned and resumable; agents do not need full conversation transcripts.
3. **Shared knowledge and training data:** promoted, rights-cleared, project-scoped skill cards and examples are selectively retrieved into each agent's next task. It is NOT a global, writable prompt blob and NOT hidden model reasoning or cross-account training.

Use an `AgentEvent` stream with `run_id`, `task_id`, `agent_id`, `provider`, `seq`, `timestamp`, `type`, `source_rev`, bounded body, evidence IDs and permission scope. Events: `planning`, `working`, `tool_requested`, `tool_approved`, `tool_denied`, `artifact_ready`, `check_failed`, `check_passed`, `blocked`, `awaiting_owner`, `completed`, `cancelled`. Never assign `completed` merely because the subprocess exit code is 0; distinguish tool/agent reported vs independently verified.

### Orchestration protocol choice

- **Agent Client Protocol (ACP)** for provider-local editor↔agent sessions and streaming; feature-probe each ACP version; [official project](https://agentclientprotocol.com/) has an evolving v2 draft, so never assume every agent supports the exact same capabilities.
- **MCP (2026-07-28)** for reusable tools, not identity or shared memory. Host owns tool grants, version pins, network/file scopes, and external data egress; [tools spec](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx).
- **A2A** for authorized remote/Brain 2 agent-to-agent tasks **only after** local multi-agent functionality and authenticated network transports pass tests; [A2A spec](https://a2a-protocol.org/latest/specification/).
- **Native SDK/JSON-RPC** for Codex app-server, Pi RPC, Claude Agent SDK, OpenHands and specialist runtimes when ACP loses required semantics. Do not reduce all frameworks to lossy stdout parsing.

Avoid a second orchestrator in each adapter. The host runtime maintains the ONLY authoritative permission and state machine. A selected “Claude conductor” or “Gemini conductor” means *that model proposes, triages, revises and synthesizes a mission*, not that it gains arbitrary host power.

**Compare implementation patterns:** Microsoft Agent Framework 1.0's [orchestrations](https://learn.microsoft.com/agent-framework/workflows/orchestrations/) (parallel, sequential, handoff, group chat, magentic), [LangGraph checkpoints](https://langchain-ai.github.io/langgraph/concepts/durable_execution/) and OpenAI Agents SDK managers-as-tools. Keep STAR's existing `TaskPlan`/resource ownership rather than mass-migrating infrastructure. Both checkpoint stores and learned-fact stores need project/source identity and rollback semantics.

### Smarter orchestration than always launching 10 agents

1. Task triage: fast factual query → one local model; simple edit → one capable coder + deterministic lint; large complex project → specialist fan-out.
2. Capability admission: exact engine/tool/version authorization; no cloud private project transfer by default; no unmeasured model rights.
3. Adaptive routing: historically observed **time to accepted correct artifact** on task family, not benchmark marketing, model size or subscription tier. Start deterministic; shadow-test contextual routing later.
4. Resource leases: on 32 GB RAM/8 GB VRAM Brain 1, keep GPU capacity for the actual local model and avoid simultaneous huge GGUF reloads. Background indexing and CLI/network agents are different resource classes; protect real-time chat and Brain 2 Studio gameplay.
5. Independent worktrees + selected read-only evidence. Worktrees avoid ordinary file conflicts but **do not sandbox the OS**; CPU, disk, network and secret access still need operating-system isolation.
6. Reviewer and integration as separate roles; permission checkpoint before any write, push, merge, external account action or public game publishing. Neither source snippet nor worker text may edit protected graders.

## 6. Teaching all participating agents — STAR Shared Skill Fabric

A single user correction could eventually improve STAR local chat and future tasks delegated to every consenting compatible external agent, without copying vendor model internals.

### Verification-first learning loop

```text
Observed failure or negative owner visual feedback
     ↓
Frozen input+source revision+screenshots+tool logs+reproduction
     ↓
Different agents propose independent hypotheses / repair candidates
     ↓
One controlled change per candidate; reproducible tests and side-by-side outputs
     ↓
Host-owned verifier + actual editor runtime + owner qualitative assessment
     ↓
Generate narrow task-scoped skill candidates with positive AND negative examples
     ↓
STAR paired evaluation + sealed project-disjoint holdouts
     ↓
Trial/promote or reject, with expiry, rollback and source revocation
     ↓
STAR retrieval AND permitted future external agent briefs (not their weights)
```

**Four distinct mechanisms:**
- **Cross-agent teaching by context:** Short rights-cleared Markdown/SKILL.md guidance delivered only when task relevant; feedback summary includes exact corrected code or image comparison. Works with many different providers in one project and is the primary path.
- **Tool/skill evolution:** Reviewed fixed-schema tool recipes, test scripts, lints, game-engine adapters and style constraints. These can measurably improve agents without any weight updates. New executable tool permissions remain owner-controlled.
- **Adaptive routing:** Infer best available model/tool choice per task class from real completed tests with uncertainty and provider cost. Resist overfitting, gaming tests and stale quota assumptions.
- **Optional local model weight fine-tuning:** Only when legally permitted data, suitable GPU/time, base-model license, independent frozen evals and owner approval are available. Never claim “Claude/ChatGPT/Grok learned new weights” from an external run.

Study [DSPy GEPA](https://dspy.ai/3.0.4/api/optimizers/GEPA/overview/) for text/prompt evolution using trace-aware feedback and the [scientific method](https://github.com/K-Dense-AI/scientific-agent-skills) for experimental design. Run all optimizer candidates in a controlled offline lab and compare with unchanged tests; no optimizer can see or rewrite protected holdout answers.

### Proposed new differentiated feature: STAR Proof-Carrying Skill Capsules

Instead of letting agents exchange dozens of screens of untrusted chat, exchange small versioned, rights-cleared capsules:
`{task_family, toolchain+engine_versions, project_scope, tested_procedure, source_hashes, artifact_hash, independent_test_refs, before_after_visual_refs, negative_constraints, owner_verdict, expiry}`.

- **Model-agnostic:** plain compact document plus machine-verifiable test/artifact references can be consumed by Claude, Gemini, Pi, OpenCode or a local model.
- **Causally useful:** "before" task fails test X, "after" passes exact test X under frozen conditions; one-change-at-a-time experiments reduce random design drift.
- **Safe:** private assets never appear in the public repo, lessons are not auto-granted filesystem permissions, and a capsule cannot declare its own checker trust.
- **Speed-oriented:** cache evidence by branch SHA, source rights and engine version, then provide the smallest relevant capsule on task start.

**Novelty disclaimer:** This is a proposed combination and engineering experiment, NOT a verified world's-first invention or proven self-improving superintelligence. Benchmark against simple retrieval, ordinary Rilo parallel fan-out and existing STAR Teams; report win/loss and wall time.

## 7. GAME ENGINE INTELLIGENCE: serious support beyond Roblox

### Phase 1: existing-engine adapters

| Engine | First dependable operation | Advanced operation after verification | References |
|---|---|---|---|
| **Roblox** | Native Studio read-only graph and Luau lints; private test place snapshots | Owner-scoped edits, multiple isolated Studio tests, VFX/animation UI screenshots and gameplay bots | [Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp) |
| **Godot** | Detect `project.godot`, analyze GDScript/scenes, headless parse/import, capture errors | Authorized scene edit, export preset, real visual/play tests | [Godot CLI](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html) |
| **Unity** | Match installed editor/version, read C# and assets, batchmode static validation and Test Framework | Isolated editor MCP plugin under explicit version+permissions; prefab/scene edits, Play Mode capture, build profiling | [Unity CLI](https://docs.unity.com/en-us/engine/6000.5/manual/unity-editor/command-line-arguments/editor), [MCP for Unity](https://github.com/CoplayDev/unity-mcp) |
| **Unreal Engine** | `.uproject` discovery, .h/.cpp compile diagnostics, Unreal Automation Tool/Gauntlet receipts | Approved editor Python/Blueprint bridge, screenshot tools, asset import, packaging/profile on configured machine | [UAT](https://dev.epicgames.com/documentation/unreal-engine/unreal-automation-tool-overview-for-unreal-engine), [Gauntlet](https://dev.epicgames.com/documentation/unreal-engine/gauntlet-automation-framework-overview-in-unreal-engine) |
| **Blender** | Existing STAR worker render/mesh checks, curated glTF/FBX export and pivot/material/rig validation | Scoped native scene creation and genuine render comparison; no unreviewed bpy scripts | [Blender Python](https://docs.blender.org/api/current/), [community MCP](https://github.com/ahujasid/blender-mcp) |
| **Bevy / Rust** | Cargo manifest/dependency/compile/test/asset file analysis | Standalone Rust 2D/3D game sample with ECS and automated screenshots | [Bevy](https://bevy.org/) |
| **Other already researched** | Existing `docs/research/engines/*` covers Cocos, Defold, GameMaker, LÖVE, MonoGame, O3DE, Phaser, PICO-8, raylib, Ren'Py, RPG Maker, s&box, SDL3, Stride, Three.js, UEFN/Verse etc. | Extend manifest detection and *read-only* project scaffolding where tests/sources justify it; no instant runtime adapter promises | See existing per-engine files |

**Recommended engine-neutral artifact representation (experimental, NOT automatically convertible):**
- Scene/entity hierarchy, coordinate system and units;
- Mesh/material/texture, UVs, PBR and legal provenance;
- Transform, animation rig/action, physics/collision, camera, lights and VFX;
- Engine-specific scripts/components/replication and prefab/resources;
- UI semantic tree with constraints/layout/fonts, not screenshots as widgets;
- Export/license and target-platform compatibility manifest;
- Validation receipts per target engine.

Use glTF 2.0 for many meshes/rigs where supported, but keep coordinate conventions, bone maps, animations, shaders, visual scripts, networking and UI semantics as explicit per-engine conversion and validation tasks. These systems do NOT roundtrip losslessly just by changing file extensions.

**Studio Lab equivalence** for each engine: a disposable owned test project with run ID, exact engine version, deterministic script/scene build, logs, a stable camera reference, runtime FPS/memory snapshots, screenshot comparisons, rollback, and approval before publishing.

### Phase 2: STAR's own game engine — **STAR Forge Engine** (working title only)

**Do not start by independently reinventing a AAA renderer, a physics engine, animation system, IDE, asset pipeline, scripting VM, multiplayer replication and build/export from scratch.** First ship a verifiable small unique engine that STAR can actually edit and test.

Three options evaluated:
- **Custom editor/product on top of [Godot](https://github.com/godotengine/godot) (MIT):** Fastest end-to-end engine launch, rich existing engine. Good if goal is a Star-branded AI-assisted editor rather than original low-level engine; license notices/third-party attributions required.
- **STAR Forge modular runtime on [Bevy](https://bevy.org/) (Rust, MIT/Apache) with [Rapier](https://rapier.rs/docs/) physics and existing Bevy rendering (wgpu under the hood):** Best candidate for **STAR-owned runtime/editor/tool protocol** without implementing rendering and ECS from bare metal. Tradeoffs: early-stage editor ecosystem and Rust compile costs.
- **Whole renderer from [wgpu](https://wgpu.rs/) + custom ECS + physics:** Maximum technical ownership but multi-year engineering risk with much weaker near-term production quality. Only after concrete profiling justifies an architectural fork.

**Preferred phased path:** Build STAR Forge as a **unique AI-native Bevy-based game creation toolchain**, with an owner-facing editor and Rust runtime, and only later replace subsystems as justified by measured wins. "Our own engine" means owned product/editor APIs, data format, renderer extensions, game runtime and roadmap—not claiming ownership of all permissively licensed dependencies.

#### First real vertical slice, acceptance-based

1. New, separate experimental engine project, version-locked crate dependencies, no automatic build/install on user's Brain 1/2.
2. One playable **small stylized 3D arena**: camera, basic real meshes, player motion, collision, scene file save/load, dynamic lights, one sound and polished minimal in-game HUD. Assets documented and editable.
3. Typed host-owned scene protocol: `create_entity`, `set_transform`, `set_material`, `attach_mesh`, `save_scene`, `simulate`, `capture_screenshot`, `undo`. Commands have scope and reversible edit receipts; no raw model-controlled Rust code executor.
4. **Offline test**: schema roundtrip, invalid content refusal, deterministic object positions, collision and scene loads.
5. **Native visual test:** fixed camera/time screenshot of actual compiled runtime; compare reference composition and report user-visible differences; performance at 1080p with measured p50/p95 and render hardware recorded.
6. Explicit owner acceptance before any declaration of “playable.” A green `cargo test` cannot prove the game looks good.
7. Only after proven: asset browser, material editor, animation timeline, VFX, terrain/LOD, networking/multiplayer, prefab versioning, script hot reload, multi-platform export and AI-assisted in-editor creation.

The engine's differentiation should be **AI-native typed editing, proof-carrying scene changes, visually grounded self-repair and replayable procedural projects**, not another generic cube-demo launcher.

## 8. Content production, UI/VFX and image/animation quality

Model count will not fix STAR producing "AI-looking" interfaces. That needs:

- **Visual reference contracts:** owner's approved screenshot/artboard, negative constraints (no neon/glows, no random circles, no labels over icons, real avatar rig identity), design tokens and tolerances hashed and versioned.
- **Editable UI deliverables:** native React/CSS, Roblox UI Instances, Unity UXML/UIToolkit, Godot Control scenes—not a rasterized picture of a UI.
- **Automated screenshot loops:** Playwright for STAR web UI, native Windows DPI snapshots; exact renderer/Studio screenshots; overlap/contrast/hierarchy/keyboard/focus and 30–60Hz animations checked separately; approval-based pairwise ranking.
- **Art generation:** ComfyUI local reproducible workflows for images/textures/sprites; Blender meshes/PBR/rigs; treat 3D generator output as *untrusted geometry requiring topology, collision, scale, pivots and license checks*.
- **VFX:** control over emitters, particles, flipbooks, occlusion/bloom, bandwidth and frame pacing; validate in live target engine with GPU overdraw metrics and stable timed frames rather than one favorable still.
- **Audio:** generated or edited original assets with source/license metadata, spatial placement, clipping/levels and user approval.

STAR already has `docs/STAR_VISUAL_CRAFT_RESEARCH_2026.md`, `star/roblox_ui_compiler.py`, `star/roblox_vfx_compiler.py`, `star/blender_*`, `star/comfy.py`, `star/design_system.py`; **integrate/test these** before creating another parallel visual subsystem.

## 9. Speed: measured intelligence-per-second

Benchmarks must separate:
- **TTFT** (time-to-first real content), total task wall time, **time to accepted artifact**, parallel throughput, independent pass rate, p50/p95 engine frame time, RAM/VRAM peak, GPU stalls and request cost.
- **Speculative decoding**: [llama.cpp spec](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md) supports draft-target verification; useful only if accepted token ratio and memory overhead actually improve the target PC.
- **Prefix/KV caching and continuous batching**: [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) allows prompt/cache reuse and concurrent slots; on 8GB VRAM, oversized caches, multiple models and long contexts can regress latency.
- **Memory/retrieval**: static, source-hash content caching; exact/FTS keywords first for Luau symbols, then bounded embedding rerank, then stronger model. Cache invalidation on source edits/deletion and per-project access.
- **Tool discovery on demand**: use short schema abstracts, lazy loading by task rather than 200 MCP schemas in every prompt; compare no-search, one-search, and adaptive routing on the same held-out task set.
- **Race 2–4 independent candidates** only for hard problems and when host-owned tests can select a winner; cancel losers, preserve receipts. Cheap first-draft/syntax can be completed by a fast local or permitted quota model.
- **Preempt and queue**: real UI chat gets priority; gameplay/Studio test on Brain 2 should hold GPU/CPU leases; safe background research can run only within spare machine headroom.
- **Cost**: run protected zero-spend mode by default. API models can be faster/stronger for selected difficult tasks but require explicit approval/limits; subtract delays due to rate limiting, cache misses and tool startup.

Measured user hardware (historical target) Brain 1 Windows 11, RTX 3060 Ti 8GB, 32GB DDR4; this is **not** a machine for 10 simultaneously loaded large local models. Brain 2 status must be probed at runtime rather than assumed. A local model is not “less intelligent forever”: task-specific retrieval, verifier tools and domain-aware recipes can make the smaller model useful without magic weight gains.

## 10. UI requirements: one product with owner-quality visuals

**Don't bolt Rilo's Electron shell onto STAR.** Existing STAR has React+TypeScript; prioritize product design systems and real screenshot QA over rewriting framework.

- Main layout: 220px compact sidebar with projects/history; central conversation dominates; inspector is collapsible rather than a dense giant card wall.
- **Top of composer**: `STAR` / `Direct agent` / `Conductor`, plus `Free-first` / `Local-only` / `Quality` (actual measured selection, not fake rankings) and `Approve outside sharing` settings.
- **Provider drawer**: list by *agent harness*, *actual underlying model* and *tool capabilities*, with evidence states `Not installed`, `Login required`, `Quota unknown`, `Probed`, `No-charge verified`, `Metered`, `Disconnected`; account auth stays in provider app.
- **One chat**: STAR speaks as coordinator. Agent messages are collapsed into task steps; expanding shows actual model/probe/source, run time, error, diff, screenshots, citations and retries. Buttons only if backed by real host action.
- **Shared whiteboard**: zoomable dependency graph and inspector showing which team member owns what, exact file/engine locks, status and which models are waiting for approval. Not a wall of equally weighted cards.
- **Learning Inbox**: new lessons with original failure → host observed fix → before/after artifact → owner acceptance/rejection → trial/rollback; no deceptive “STAR got 9999x smarter” stats.
- Visual treatment: OLED black with restrained gold and off-white, impeccable spacing, no heavy glow, no decorative random circles, clear white icons, subtle borders, measured motion. Desktop screenshots at 1050×680, 1440×900, 4K and 100/125/150% DPI; WCAG contrast/focus/keyboard/reduced-motion review.
- **Metrics and state must be real:** display time-to-correct result and honest cost estimate/unknown, failed tests, queue wait and VM state. A model's written “done” never becomes a green UI pass.

## 11. Next build order (gated, not aspirational checkbox theater)

### P0 — this research / candidate
- [x] Curated source-linked agent taxonomy and honest free-vs-harness separation.
- [x] Review-only `star/agent_ecosystem.py` agent metadata and **safe** eligibility preview, no runtime/UI, with offline unit tests.
- [x] Owner's one-chat cross-agent learning + engine architecture documented.
- [ ] GitHub Python/Windows CI green and reviewer acceptance before merge.

### P1 — minimal real one-chat fleet
- [ ] First complete ACP adapter (prefer OpenCode) and Gemini CLI real headless session where official auth/quota permitted; connect approved local model separately.
- [ ] Typed event stream, native pause/cancel, verified resource budget, local-only defaults, provider/tool probe receipts.
- [ ] At least two heterogeneous workers genuinely solve independent subtasks of one chosen project and return inspectable artifacts.
- [ ] Existing `agent_runtime` determines dependency order, no second planner truth, no user-conversation provider-switch illusion.

### P2 — expanded ecosystem
- [ ] Goose (ACP), Pi (RPC), OpenHands (SDK) as distinct integration pilots; Continue, Aider, Kilo, Cline, Qwen as optional CLI adapters where scopes genuinely enforced.
- [ ] Browser Use/Playwright and read-only docs MCP; local ComfyUI/Blender renders within machine headroom.
- [ ] Official Codex app-server and Claude Agent SDK pathways as optional *alongside* free/local agents, not universal dependency.
- [ ] Live statuses and cross-provider cost/privacy allowance; no secrets in logs or public GitHub.

### P3 — game-engine bridges
- [ ] Take existing Godot/Unity/Unreal read-only project path; add approved CLI test/import commands, no shell-generated arbitrary instructions.
- [ ] Real editor-only owner-selected sandbox, screenshot + visual QA, undo rollback, unit tests and performance receipts.
- [ ] Engine-neutral scene/asset schema and explicit glTF/rig/material/platform conversion tests.
- [ ] Extend catalogs to curated other engines based on installed project version and accepted test coverage.

### P4 — proof-carrying shared skills
- [ ] Integrate #413 evidence contracts (after review) and existing STAR paired gate for agent lessons, sample IDs and sealed holdouts; provenance from host tool calls only.
- [ ] At least 50 rights-cleared source/project-disjoint tasks covering code/test, multi-engine imports, UI visual and no-answer/private data negatives.
- [ ] Compare STAR solo, Rilo-style simple fan-out, always-parallel agents, and **adaptive conductor**. Report p50/p95/cost/win rates with confidence. Never self-train on sealed evaluations.
- [ ] Owner opt-in to share approved skill cards with external providers, visible in run inspector; no third-party weight-training claims.

### P5 — STAR Forge engine research prototype
- [ ] Separate experimental, no auto-install project with user-selected Bevy/Rapier/wgpu pinned dependency versions and reviewed licenses.
- [ ] One playable 3D stylized demo under test; entity editor/runtime scene save/reload, screenshot, tests, actual FPS/VRAM report, UI/rig/physics benchmarks.
- [ ] Local tool protocol callable by STAR approved workers; undo/recovery and canary tests.
- [ ] Only evolve to full engine after validated accepted gameplay and unique editor/product value.

**Independent release acceptance:** fully packaged Windows machine, real installed CLI/provider accounts, explicit privacy and spend decisions, authenticated isolated editor bridges, parent/child task failure tests, source-hash and audit fixtures, screenshots the owner actually likes, and no regressions to current stable STAR. No merge to `main` or publishing from a research proposal.

## 12. Source register / freshness restrictions

Primary live sources reviewed 2026-10-15:
- Additional open-agent candidates: [Hermes](https://github.com/NousResearch/hermes-agent); [Plandex](https://github.com/plandex-ai/plandex); [OpenClaw](https://github.com/openclaw/openclaw). These are research candidates, not verified free-inference integrations.
- Open agent/CLI: [Gemini CLI](https://github.com/google-gemini/gemini-cli); [pricing](https://google-gemini.github.io/gemini-cli/docs/quota-and-pricing.html); [OpenCode ACP/serve](https://github.com/anomalyco/opencode/blob/dev/packages/web/src/content/docs/cli.mdx); [goose](https://block.github.io/goose/); [OpenHands](https://github.com/OpenHands/OpenHands); [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk); [Aider](https://github.com/Aider-AI/aider); [Cline](https://github.com/cline/cline); [Continue headless](https://github.com/continuedev/continue/blob/main/docs/cli/headless-mode.mdx); [Kilo](https://github.com/Kilo-Org/kilocode); [Pi RPC](https://github.com/badlogic/pi-mono); [Qwen Code](https://github.com/QwenLM/qwen-code); [Qwen billing withdrawal](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/model-providers/); [SWE-agent](https://github.com/SWE-agent/SWE-agent); [Browser Use](https://github.com/browser-use/browser-use).
- OpenAI: [Tools](https://developers.openai.com/api/docs/guides/tools), [Agents](https://developers.openai.com/api/docs/guides/agents), [tool search](https://developers.openai.com/api/docs/guides/tools-tool-search), [Codex app-server](https://openai.com/index/unlocking-the-codex-harness/), [Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/), [ChatGPT plugins](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt).
- Anthropic: [Tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference), [Agent SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/overview), [subagents](https://code.claude.com/docs/en/sub-agents), [hooks](https://code.claude.com/docs/en/hooks-guide), [managed threads](https://platform.claude.com/docs/en/managed-agents/session-threads).
- Orchestration: [Microsoft AF 1.0](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/); [AF patterns](https://learn.microsoft.com/agent-framework/workflows/orchestrations/); [LangGraph](https://langchain-ai.github.io/langgraph/concepts/durable_execution/); [Google ADK](https://github.com/google/adk-python); [ACP](https://agentclientprotocol.com/); [MCP tools spec](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx); [A2A](https://a2a-protocol.org/latest/specification/); [GEPA](https://dspy.ai/3.0.4/api/optimizers/GEPA/overview/).
- Engines: [Godot](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html), [Unity](https://docs.unity.com/en-us/engine/6000.5/manual/unity-editor/command-line-arguments/editor), [Unreal UAT](https://dev.epicgames.com/documentation/unreal-engine/unreal-automation-tool-overview-for-unreal-engine), [Bevy](https://bevy.org/), [wgpu](https://wgpu.rs/), [Rapier](https://rapier.rs/docs/), [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [Playwright MCP](https://github.com/microsoft/playwright-mcp).

**Source caution:** Provider quotas, agent features, open-source licensing and model catalogue names change rapidly. Links are **research evidence**, not installations or provider guarantees. Recheck entitlement/model/CLI version at connection time and record exact snapshots in a local receipt. Public GitHub must never contain user's API tokens, credentials, client project archives, training corpora or private screenshots.
