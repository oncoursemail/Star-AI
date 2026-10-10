# STAR Intelligence — Parallel Agents, Verified Learning & High-Performance Local Context

**Engineering research and implemented prototype, October 2026.** This document connects primary documentation to code, tests, threat models and honest acceptance criteria. It does not claim STAR has trained a better foundation model, reached frontier scores or gained unrestricted computer access.

## Executive engineering decision

STAR should become an **evidence-driven AI development workspace**, not a UI with 50 competing model loops. The highest-leverage improvements are: (1) dynamically choose simple chat versus a team, (2) retrieve the **right** project facts rather than repeating entire histories, (3) use tool outputs with provenance, (4) delegate independent bounded analysis in parallel, (5) verify outcomes with independent tests before trusting them as memory, (6) measure real latency and task success before optimization, (7) grant only the minimum permissions needed.

The working local model remains an OpenAI-compatible `llama.cpp`/Qwen-style engine. An external model/provider is optional and must respect the explicit provider permissions introduced in a separate review branch. Neither hosted nor local model prompts should be allowed to silently promote their own answers to reviewed facts, authorize tool writes, or edit internal policy/tests.

## Research questions and primary frameworks

| Project / protocol | Evidence-based strength | Constraints / STAR choice |
|---|---|---|
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | Specialization, handoffs, guardrails, session state, tracing and humans in the loop | Useful architecture reference. Adding an entire SDK to STAR's small local loop now would duplicate the existing tool-security boundary and may complicate provider routing. |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Thread checkpoints, durable execution, long-term stores, human approvals and resumable runs | Separate **thread state** from **long-term verified knowledge**. STAR currently has persistent SQLite records; preserve them and migrate incrementally. |
| [Microsoft AutoGen GraphFlow](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.teams.html) | DAG fan-out, conditional execution, joins, role ownership and group orchestration | STAR already has a static DAG validator (`TaskPlan`). Build an executable local runtime instead of importing a second huge group-chat runtime just for parallel fan-out. |
| [Magentic-One](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html) | Task and progress ledgers, plan adaptation under stalls, specialist management | Useful for future durable tasks; unbounded replanning can cause exponential token, cost and latency blowups. Require global caps first. |
| [A2A protocol](https://a2a-protocol.org/v1.0.0/) | Interoperability and asynchronous task semantics for *different* agent services | Do not expose a remote agent server by default. A2A is a future opt-in provider integration; it is not necessary for multiple local tasks inside one STAR process. |
| [MCP specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) | Standardized tool interface and HTTP authorization rules | Tools have narrow schemas, independent host enforcement and least privilege. A model requesting an MCP tool is not authorization to run it. |
| [SQLite FTS5](https://www.sqlite.org/fts5.html) | On-device full-text index, BM25 ranking, query engine, mature SQLite storage | Best immediate low-dependency upgrade for reviewed notes. It is lexical, not semantic understanding; do not market FTS as embeddings or a knowledge graph. |
| [LangMem](https://github.com/langchain-ai/langmem) | Semantic, episodic and procedural memory distinctions; extracted memory consolidation | Promote only reviewed facts, user decisions and acceptance evidence. Model-only extraction can be stored as candidate material, never ground truth without validation. |
| [Mem0 memory benchmarks](https://github.com/mem0ai/memory-benchmarks) | LoCoMo, LongMemEval and BEAM cover recall, temporal reasoning and multi-session retrieval | Do not copy vendor benchmark percentages. Use the *method*: retrieval quality, answer correctness, token overhead, p95 latency, updating and contradiction tests. |
| [DSPy optimizers](https://dspy.ai/3.1.0/learn/optimization/optimizers/) | Evaluation-driven instruction/demo optimization, controlled examples | A future separate offline experiment; candidate prompts must beat baselines on held-out, labeled user-specific fixtures before human acceptance. No spontaneous live weight training. |
| [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | Continuous batching, parallel slots, prompt caching, token streaming and speculative draft approaches | Actual speed depends on GPU VRAM and model size. More concurrent requests can **increase p95 latency** and memory use on a modest card. Benchmark 1 vs 2 slots instead of promising 10x. |
| [OWASP Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) | Privilege escalation / prompt injection via extensions and untrusted peer output | Agents remain read-only by default; allowed actions are checked by Python, never by persuasive prompt text. |

These references are architectural and security grounding. They do not imply the entire third-party framework was installed in STAR.


## What the repository already had

The v0.8.1 baseline contains a React/TypeScript desktop embedded in Qt WebEngine, local model inference, persistent SQLite conversations, a small context checkpoint, a Studio MCP connection, scoped workspace tools, read-only Graphify and Obsidian connectors, Agent Skills as references, verified updater and real local analytics. The task planner (`star/orchestration.py`) already validates paths, dependencies and resource conflicts, but deliberately **does not run subagents**.

Two other draft PRs were active when this work started: [#27 unified conversation and image UI](https://github.com/oncoursemail/Star-AI/pull/27), and [#28 fast brain, cloud providers, web research and early subagents](https://github.com/oncoursemail/Star-AI/pull/28). This candidate was developed on its own isolated branch to avoid overwriting those proposals. Their source, UI layouts, database migrations and user-data contracts need deliberate reconciliation, not blind merging.

### The key distinction: execution model versus reasoning model

More independent specialist calls do not modify the base model's weights. STAR becomes more **effective** by selecting better context, tools, workflow, verification and structured delegation. Getting generally smarter via pretraining, fine-tuning or reinforcement learning is an entirely different expensive, data-driven project with privacy, evaluation, safety and compute requirements.

Never tell a user their AI "learned automatically" because a model response was inserted into a database. A response is evidence only when independently verified. Never claim a feature is released because its branch has passing Python tests.


## Implemented now: real bounded parallel orchestration

### 1. The runtime

`star/agent_runtime.py` is an actual asyncio executor for existing `TaskPlan` DAGs. It launches ready tasks as concurrent awaitables, respects max_parallel, then awaits first-completed results. A completion produces an immutable `TaskResult` with status, bounded answer, explicit evidence IDs and elapsed time. A `TeamResult` reports ordered outcomes, total wall time and **measured peak concurrency**.

Task admission is not LLM discretion:

- It checks all prerequisites before start.
- `TaskPlan.ready` holds overlapping read/write scopes; a writer cannot race against another writer or a reader of the same resource.
- The default allows **no task that declares writes**. An explicitly approved trusted worker can opt in with `allow_writes=True`; this does not itself grant any filesystem or Studio permission.
- A failed task blocks descendants but does not needlessly stop unrelated work.
- Per-task and global timeouts cancel unfinished coroutines; mutation retries are never automatic because a timeout may occur after a side effect.
- A hard 32-task limit and a plan-owned concurrency limit prevent unbounded delegation. The user-facing local Teams preset uses only two simultaneous model requests.
- Worker outputs are capped to 12,000 characters with up to 20 evidence strings. The UI receives role/status progress, **not** raw peer output or local secrets.
- Observability callback failures cannot corrupt the core result ledger.
- Input tasks, model IDs, endpoint, branches and scopes remain trusted application contracts—not arbitrary instructions returned by a peer model.

### 2. A usable STAR Teams mode

`star/team_service.py` composes four roles: evidence analysis, execution design, independent critique, then synthesis. The first three can overlap subject to the local concurrency cap. The synthesizer depends on all three and never starts before their successful results.

Every specialist receives its own short prompt, the relevant **reviewed** project context, a single first system turn (Qwen compatible), a bounded output-token budget and **zero tools**. The synthesizer receives the three bounded findings as *untrusted data*, not privileged instructions. It must label unverified claims, explain contradictions and propose testable next steps.

The command is opt-in through the React chat composer, with `STAR Teams` clearly showing four stages / max two concurrent calls. Native `runTeam` is an allowlisted Qt action, mutually exclusive with a normal running chat task; a pending task cannot silently start another. Team errors are reported, never converted to successful-looking answers. Successful synthesizer output is stored in the existing local project conversation.

**Current limitations:** this preset supports text-only local inference. It is not a browser agent, Studio editing swarm, self-training system or 24/7 autonomous service. On weak GPUs it can be **slower**, especially while loading several contexts or when `llama-server` uses one slot. A normal simple question should stay in ordinary single-model mode.


## Implemented now: reviewed, relevant long-term memory

### 1. Three memory classes worth distinguishing

- **Working / episodic:** recent user and assistant turns, tool logs, task outcome events and compacted current-session checkpoints. These are evidence of interactions, not guarantees that every answer was correct.
- **Semantic / project knowledge:** explicit design decisions, requirements, reviewed fixes, source artifacts and revision references, isolated by project. These should be fetched by relevance rather than always replaying the latest entries.
- **Procedural / skills:** non-executing `SKILL.md` guidance, code-review checklists and explicit high-level workflows. A skill's text cannot grant OS, Studio, network or credential privileges.

### 2. Full-text retrieval

`star/knowledge.py` now initializes a local SQLite FTS5 `notes_fts` index with insert/update/delete triggers. Existing `notes` data remains in the same database; a one-time rebuild indexes historical notes without deleting them. Relevant tokens are quoted and parameterized to block FTS operator injection. FTS5's `rank` (BM25 order) ranks relevant *older* facts ahead of unrelated recent notes.

The original project and reviewed filters are applied in the SQLite join. If FTS5 is unavailable, retrieval falls back to bounded, parameterized LIKE. Underscored identifiers such as `hello_world` use escaped LIKE because the FTS tokenizer may split underscores and incorrectly match `hello world`. Empty queries preserve the original recent-note behavior.

FTS5 is particularly efficient for large numbers of small reviewed notes and does not require an embedding API or paid vector service. It is **not** perfect semantic recall: synonyms, visual concepts and implicit links may require a future locally benchmarked embedding or graph retriever. Add such a system only after establishing retrieval baseline metrics.

### 3. Explicit approved learning, not silent false memories

`star/learning.py` adds `approve_learning()` and `learned_context()`. A native user action must carry a positive approval flag. Only decisions, requirements and fixes may become reviewed facts. Each fact has a kind, note ID, source marker, revision and project scope. The UI lists previously approved items.

A later user correction may **supersede** a specific reviewed note. The older row and its review evidence remain in the database for audit, but `reviewed=0` prevents its old claim from being trusted for new prompts. Attempting to supersede a note belonging to a different project is rejected.

Unapproved model responses, wiki pages, prompt injections, Graphify exports and Obsidian notes remain *untrusted* inputs. Tool outputs may suggest candidate notes for human consideration but cannot call the `rememberDecision` bridge action on the user's behalf.

The React Projects section now includes a bounded approval/correction editor. Saved facts are local under the existing STAR profile, not published to GitHub or sent for model weight training. Subsequent chats already use `KnowledgeStore.find(reviewed_only=True)`, so the upgraded relevance ranking and approved notes become part of actual conversation context without replacing the persistent chat store.


## Performance research: faster means less wasted work

### Baseline bottlenecks in an agentic local model

1. Every extra system schema or large copied conversation spends tokens on **prompt prefill**.
2. Each tool roundtrip adds at least one model-generation latency.
3. A 4B vision-capable model and projector can consume significant GPU memory. Four simultaneous contexts are not four free workers.
4. Full Markdown re-render per token and expensive UI filters add frontend overhead.
5. Repeated long-term memory queries using full-table keyword scans can be slow on large knowledge stores.
6. Infinite planning/retry loops can amplify cost without increasing correctness.

### Concrete optimization levers and where they belong

| Lever | Implementation or planned experiment | Measuring truth |
|---|---|---|
| Default Fast chat | Existing single-agent path with concise prompt and no irrelevant tool schemas; PR #28 is building stronger routing | Time-to-first-token, wall latency, actual answer accuracy |
| Bounded Teams mode | Four focused role calls, max 2 simultaneous local calls; isolated DAG | Wall time vs single model, verified user satisfaction; use only on harder tasks |
| Reviewed retrieval | SQLite FTS5 rank, project filter, <=8 notes and bounded context | Recall@k on user-verified questions, query p50/p95 |
| Backend event throttling | Existing streaming batches model deltas before React updates | Frames and text consistency in Qt WebEngine |
| Prompt caching | llama.cpp offers server prompt-cache and slot features, but requires tests per model/template | Measured prefill rate and GPU memory |
| Continuous batching | llama.cpp supports `--cont-batching` by default; not a magic free speedup | Requests/sec with 1 and 2 concurrent slots |
| Speculative decoding | llama.cpp draft/EAGLE mechanisms may help with compatible draft models | Tokens/sec, acceptance rate, VRAM cost, quality retention |
| Quality filtering | Prioritize verified facts rather than auto-append entire web results | Hallucination rate, correctness on held-out tasks |
| Async IO instead of threads | `run_plan` overlaps actual awaitables and provides event outcomes | Peak concurrency and time across real requests |
| Provider routing | Separate draft PR #28 supports approved optional hosted endpoints; maintain local default | Per-provider latency, privacy, cost and error frequency |

### Real benchmark tool

`star/inference_benchmark.py` and `scripts/benchmark_star.py` send small, harmless requests to a **validated localhost** OpenAI-compatible server. They measure actual request success/failure, wall time, median/p95 latency, requests/sec and output tokens/sec *when the model provides token usage*. They deliberately do **not** fabricate GPU throughput, hardware information or fake downloaded statistics.

Example:

```powershell
python -m scripts.benchmark_star --endpoint http://127.0.0.1:8080/v1 --model YOUR_LOCAL_MODEL --parallel 1 --requests 4
python -m scripts.benchmark_star --endpoint http://127.0.0.1:8080/v1 --model YOUR_LOCAL_MODEL --parallel 2 --requests 4
```

Benchmark runs are opt-in, local-only, use no project/user text and do no Studio operations. For a modest 8GB GPU, **start at one slot**. More concurrent agents may improve total throughput while making each single answer slower. Only device measurements can determine the right setting.

A useful performance comparison should always include model ID, quantization, GPU/CPU, context size, prompt length, concurrency, number of completed requests, failure count and the warm/cold distinction. Comparing unrelated hardware or using synthetic `asyncio.sleep` as though it were real model speed is invalid.


## Tool ecosystem: what should actually be added next?

**Already connected or in review:**

- **Roblox Studio MCP:** inspect the actual open test place; scoped edits require the existing permission layer, with a separate reproducible test and rollback plan.
- **Graphify:** read validated source-grounded `graphify-out/graph.json`. Graph snapshots are a useful navigation/index layer, not automatic truth.
- **Obsidian:** explicit read-only vault folder; user must enable, and note writes remain outside the present bridge. Never recursively expose unrelated home directories.
- **Agent Skills:** starter skill catalog and bounded `SKILL.md` reads for task-relevant instructions; scripts are not auto-executed.
- **Fast/provider/web subagents:** PR #28 is separate draft work. Review provider keyring security, web citation provenance, tool budgets, retries, cost controls and interaction with the Teams runtime before integration.
- **Unified React conversations:** PR #27 is separate draft work. Persist thread IDs and migrate old SQLite data without losing conversation history; verify each agent uses the right thread/project context.

**Strong next integration candidates, subject to evaluation:**

| Candidate | Concrete use | Risk / prerequisite |
|---|---|---|
| [ripgrep](https://github.com/BurntSushi/ripgrep) | Fast repository exact-text discovery | User-selected workspace, read-only and bounded outputs |
| [tree-sitter](https://tree-sitter.github.io/tree-sitter/) | AST-aware symbol/chunk indexing for code RAG | Correct grammar for Luau; never infer source symbols without references |
| [Rojo](https://rojo.space/) | Roblox source syncing for reproducible test projects | Studio editing requires explicit controlled transport |
| [StyLua](https://github.com/JohnnyMorganz/StyLua), [Selene](https://kampfkarren.github.io/selene/) | Formatting and static checks for reviewed Luau files | Invoke through trusted host steps only on approved files |
| [Wally](https://wally.run/) | Roblox package dependencies and repeatable builds | Pin dependencies, scan licenses and lockfiles; no autonomous downloads |
| [Playwright](https://playwright.dev/docs/intro) | Browser UI snapshots / interactive acceptance checks | Allowlist local preview URLs and sandbox browser credentials |
| [Whisper.cpp](https://github.com/ggml-org/whisper.cpp) | Local audio transcription alternative | Compare speed and quality with existing implementation first |
| [Qdrant](https://qdrant.tech/documentation/), [LanceDB](https://lancedb.github.io/lancedb/), [FAISS](https://github.com/facebookresearch/faiss) | Optional local embedding search on large artifact corpora | Adds model, index storage, version migration; benchmark before adopting |
| [DSPy](https://dspy.ai/) | Offline prompt/recipe optimization on verified evaluation cases | Separate bench run; human review before applying candidate changes |
| [OpenTelemetry](https://opentelemetry.io/docs/) | Structured trace spans and latency analysis | Local opt-in collection; avoid prompts, keys and media in traces |
| [A2A](https://a2a-protocol.org/v1.0.0/) | Federated external specialist services | Requires explicit server trust, authenticated transport and consent; unnecessary for local Teams |

Installing everything indiscriminately increases startup time, dependencies, security vulnerabilities and UX clutter. Prefer one good tool with real evidence over twenty unused icons.


## Evaluation-driven growth instead of unchecked self-training

The trustworthy feedback loop is:

1. **Observe** a real task, source code revision, tool response and/or user-reported bug. Preserve non-sensitive reference IDs.
2. **Propose** a candidate fix, instruction, skill or project decision. Candidate status is not trusted status.
3. **Verify** via independent assertions, compile/tests, live Studio evidence or explicit human review. Never accept self-reported pass claims as execution proof.
4. **Promote** only the reviewed evidence into project-scoped retrieval or a reviewed source change. Never modify fixtures to manufacture a pass.
5. **Compare** on an unchanged held-out evaluation set across latency, accuracy, memory recall, tool rejection and risky write constraints.
6. **Roll back** on regressions, preserve prior knowledge for auditing, and do not silently rewrite user projects.

Useful measures, aligned with memory and agent research:

- Task completion rate **with external evidence**, not generated confidence percentages.
- Source attribution precision: links/paths actually exist and refer to the claimed revision.
- Memory retrieval Recall@5 / MRR on verified questions; contradictory old decisions not resurfacing.
- Tokens supplied from memory per correct answer; latency per retrieval.
- Number of model turns and tool calls for equivalent tasks.
- Mean and p95 wall time at one/two agents, actual VRAM use when available.
- Safe refusal of unauthorized tool invocations and prompt-injection attacks.
- Preservation of user files, original images, and approved Roblox UI layouts.

STAR's existing `evals/roblox_cases.json` includes user-visible design, Luau, memory, publishing, tool and security cases. Many are **definitions**, not executed Studio tests. Extend fixtures and publish honest `not_run` counts instead of invented passing percentages. The `star/evals.py` verdicts must remain externally supplied.

[OWASP guidance](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) specifically cautions that malicious tool output and peer-agent material can trick over-privileged agents. In STAR, a peer's generated text is not an authorization credential and cannot instruct the native host to write a file. This is enforced by tool scopes and the read-only Teams design, not by a comforting instruction string alone.


## Security and isolation details

1. **Endpoint:** STAR Teams and the benchmark accept only the pre-existing validated loopback OpenAI-compatible endpoint. No client-provided arbitrary URL or API key is accepted.
2. **Secrets:** Provider keys remain OS keyring/env only in a separately reviewed integration. They must never enter React bootstrap JSON, session transcripts, test fixtures, Git commits or prompts.
3. **Files and Studio:** Team workers call only `chat.completions.create` without tools. No filesystem, Studio, HTTP browser, arbitrary process or network search tool is available in this path.
4. **Memory scope:** Queries join `notes.project=?` and `reviewed=1` in SQL. Appointments, unrelated games, other projects and user secrets do not cross this boundary.
5. **Permissions:** `human_approved` is required to promote facts through a dedicated native method. A model tool cannot call the approval method; React's bundled WebChannel is allowed only on local app pages. Untrusted Obsidian, Graphify, web and Skill text cannot escalate permissions.
6. **Concurrent conflicts:** A task that reads `src/UI` cannot run alongside one writing the parent `src` scope. Normal Teams tasks declare no writes.
7. **Timeouts:** Workers stop within global/per-worker asyncio budgets when cooperative, with failed dependencies blocked. Never automatically retry partially completed side-effectful operations.
8. **Logging:** Events expose roles, task ID, status and timings. Never log full model transcripts, bearer tokens, local user paths or untrusted tool text as analytics details.
9. **Upgrades:** Existing conversations/checkpoints/models remain under `%APPDATA%/STAR`; reviewed-note FTS migration is additive and can fall back to original LIKE.
10. **Provenance:** Reviewed facts have note IDs, revision and source. A superseded fact loses trusted status but remains auditable in SQLite.

Security tests must include poisoned "ignore prior instructions" notes, a fabricated peer-agent claiming system authority, cross-project memory reads, path traversal, malicious FTS syntax, huge tool outputs, simultaneous conflicting writes and cancellation during a task.


## Exact implementation and handoff matrix

| File | Changed behavior | Status in this candidate |
|---|---|---|
| `star/agent_runtime.py` | Real async DAG executor, conflicts, failure propagation, task evidence and time caps | Implemented; offline tests |
| `star/team_service.py` | Four specialist local inference stages, dependency-gated synthesis, read-only policy | Implemented; mocked-completion tests |
| `star/knowledge.py` | SQLite FTS5 BM25, migration triggers, project/review filters, safe fallback | Implemented; migration tests |
| `star/learning.py` | Human-approved project decisions, correction/supersession, bounded trusted context | Implemented; isolation tests |
| `star/react_shell.py` | Allowlisted `runTeam`, `rememberDecision`, `listLearning`, status events | Implemented; requires Windows Qt acceptance |
| `frontend/src/Desktop.tsx` | STAR Teams composer toggle and approved knowledge editor | Implemented; requires real UI visual review |
| `frontend/src/agents-learning.css` | Responsive quiet team/learning controls | Implemented; reduced-motion CSS |
| `star/inference_benchmark.py` | Actual localhost latency/throughput measurement and statistics | Implemented; unit-tested statistics |
| `scripts/benchmark_star.py` | User-run measured benchmark CLI | Implemented; not run on user's GPU |
| `tests/test_agent_runtime.py` | Concurrency, read/write conflict, failure, cancellation, budgets | Added |
| `tests/test_team_service.py` | Four model requests, two-way overlap, Qwen message order, knowledge isolation | Added |
| `tests/test_verified_learning.py` | Reviewed provenance, corrected facts, FTS indexing/migration, injection rejection | Added |
| `tests/test_inference_benchmark.py` | Measured-output summaries and localhost-only constraints | Added |

### Integration with existing drafts

PR #27 changes the very same chat/Qt service files for real chat threads. Before merging both, the team action should pass the selected thread ID through the same approved conversation store and avoid resurrecting a single-stream project history. The accepted decision journal should stay project-scoped and should **not** treat an unrelated thread as cross-project authorization.

PR #28 introduces fast/cloud model routing and its own `star/subagents.py`. The reviewed coordination should choose a single task-mode router: simple prompts use the fast path; research/analysis can use STAR Teams; tool-edit tasks route to the existing authorized Studio tool agent. Two implementations must not race to update the same conversation. Hosted parallelism requires its own quotas and provider privacy settings.

Avoid forcing merges while those drafts are being revised. Green Python tests and a bundled Windows EXE test do not prove the provider keyring, GPU throughput, real Roblox tools or visual design have been tested on the user's PC.


## Release and QA gates

**Automated:** full `pytest` and Python compileall; React `tsc`, Vitest and Vite build; live async overlap fixture; conflicting writer lock test; global timeout/cancellation test; reviewed-only project isolation; migration from an old notes database; malicious FTS text; local benchmark provider security; packaging UI-doctor on Windows; no new repository secrets.

**Required real Windows acceptance:** open a clean local STAR Brain and ensure normal single-agent chat still answers; open Teams mode, request a multi-step design brief, and observe each specialist status plus final synthesis; compare real measured latency of Teams with the same question in normal chat; save a design choice, restart STAR, ask a relevant question and verify source-grounded recall; correct it and ensure the old contradictory note disappears from trusted context; restart/upgrade without losing chats/models; verify new UI at 1050×680 / 1440×900 and 125/150% DPI; ensure no text overlaps icons; test reduced motion and keyboard-only use.

**Future evaluation projects:** graph/embedding retrieval only when FTS recall is insufficient, verified per-project semantic note sets, offline controlled prompt optimization, hardware-aware model slot tuning and genuine A2A agent interop. These should each have a reproducible benchmark, permission review and rollback plan.

**Nonclaims:** No foundation model has been retrained. No promise that four model calls are faster than one. No new unrestricted PC control, autonomous Roblox publishing, indefinite background learning, or guaranteed AAA game generation. STAR's demonstrated value is a better-organized, evidence-grounded local agent application with measurable capabilities.


## Curated primary source index

**Agent runtimes:** [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) · [OpenAI Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/) · [AutoGen team API](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.teams.html) · [Magentic-One](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html) · [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [Agent2Agent](https://a2a-protocol.org/v1.0.0/).

**Memory/optimization:** [SQLite FTS5](https://www.sqlite.org/fts5.html) · [SQLite WAL](https://www.sqlite.org/wal.html) · [LangMem](https://github.com/langchain-ai/langmem) · [Mem0 benchmarks](https://github.com/mem0ai/memory-benchmarks) · [DSPy optimizers](https://dspy.ai/3.1.0/learn/optimization/optimizers/) · [DSPy GEPA](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/getting-started/gepa-optimization.md).

**Local inference:** [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [llama.cpp speculative decoding](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md) · [OpenAI-compatible model-client interface](https://github.com/openai/openai-python).

**Safety/integration:** [OWASP Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) · [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) · [Agent Skills](https://agentskills.io/home) · [Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp) · [Qt WebChannel](https://doc.qt.io/qt-6/qtwebchannel-javascript.html).

**Research caution:** These references are upstream documentation; they do not substitute for source-specific tests or measured STAR performance. Recheck changed APIs before adding optional dependencies.
