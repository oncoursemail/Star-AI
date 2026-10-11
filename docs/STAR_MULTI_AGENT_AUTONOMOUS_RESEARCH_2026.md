# STAR: multi-agent engineering and autonomous research — October 2026

**Status:** engineering blueprint plus a bounded implementation candidate in this branch.
This is not a trained new foundation model, an unattended coding swarm, an
automatic plugin installer, or proof of improved game quality. Neither unmerged
code nor passing offline unit tests establishes production acceptance.

## 1. Verified baseline and current gap

At the integration branch `star/claude-integration-20261010`, STAR already has:

- **Parallel inference:** `star/agent_runtime.py` executes DAGs with a
  measured concurrency cap, dependencies, task timeouts and read/write resource
  exclusions; `star/team_service.py` runs 3 specialist roles plus synthesis.
  Most local providers support at most two simultaneous slots; more model
  requests may slow a low-VRAM machine.
- **Tool-using chat and delegation:** `star/agent.py` exposes model-selected
  tools under Python permission checks. `star/specialist_agents.py` runs
  separate model calls without giving specialist models tool schemas.
- **Reviewed custom tools:** `star/tool_workshop.py` lets STAR propose/test
  narrow read-only recipes; separate owner approval is required.
- **MCP tools:** `star/mcp_connections.py` discovers read-only operations only
  from explicitly configured, reviewed connectors. Remote registry listings
  are **not** permissions to install or invoke a server.
- **Research:** `star/web_search.py` retrieves source-linked search snippets
  via configured Brave/Tavily credentials. Before this candidate, the explicit
  Research button ran only one search for the whole question.
- **Knowledge and self-improvement:** reviewed, project-scoped knowledge and
  candidate-only self-builder changes. Evals must own their holdouts and grader.

The actual gap is *workflow quality*: source diversification, uncertainty,
trusted tool discovery, safe parallel work, durable plans, and measured feedback.

## 2. Implemented in this candidate

### 2.1 Parent-managed parallel research

`star/deep_research.py` is called **only when Research mode is already
enabled**. The trusted application derives up to three query angles: the
original question, primary/documentation lookup, and limitations/comparison
lookup. It issues at most two searches concurrently through STAR's existing
Brave/Tavily adapter. The model cannot choose arbitrary URLs or run scripts.

Each search returns only bounded, re-sanitized HTTPS *snippets*. Results are
merged round-robin across query angles, with URL deduplication and preference
for distinct domains. The total is capped at eight sources, including
citations. Partial query failures are noted honestly. If all queries fail,
Research mode fails explicitly rather than fabricating evidence.

This is **parallel retrieval, not page-level verification**. It cannot prove
article text, establish a site's reliability, or validate code by itself.

### 2.2 Specialists with optional web evidence

In a normal chat, delegated specialists see only approved local sources.
With the user's **explicit Research mode**, a delegated spec may request
`web` evidence. The parent executes at most two web lookups across
the model task, sanitizes returned records, and places snippets inside the
worker's untrusted evidence block. Specialists **never receive** search tools,
MCP permissions, API credentials, HTTP clients, shell, workspace writes, or
Studio access. They can still work independently while the parent searches.

The app must never describe source snippets as browsed articles, or model
reports as tested claims. Search failure details are not passed to models
because HTTP exceptions can contain sensitive data.

### 2.3 Concrete tests

Offline tests cover query caps, two-call concurrency, source diversity,
deduplication, explicit failures, cancellation, opt-in web permission,
tool-less specialists, and secret redaction. These tests use synthetic search
providers, not live hosted credentials. The normal Python and frontend
suites, packaging, and hands-on Windows/Studio checks remain release gates.

## 3. Recommended next architecture: a verified autonomous research loop

Implement in small independently reviewed slices:

1. **Planner:** split a complex objective into 2–5 *non-overlapping research
   questions*, record assumptions, scope, required evidence and maximum cost.
   Simple chat stays single-agent. Model-proposed work units are validated by
   a trusted Python budget/permission planner before execution.
2. **Retriever:** each researcher can ask only a preapproved broker for exact
   source classes (project notes, official docs, checked-out source, MCP
   catalog metadata, optional public web search). Fan out independent queries.
3. **Evidence ledger:** store query, timestamp, provider, URL/revision,
   excerpt boundary, source type, inferred versus observed status and
   conflicting claims. An excerpt is never authority over a tool call.
4. **Gap/contradiction checker:** an independent critic identifies missing
   evidence and failed source coverage. Allow **at most one or two bounded
   follow-up rounds**. No infinite "research until confident" loop.
5. **Synthesizer:** produce a sourced answer, confidence/unknowns and the next
   concrete test. Mark unverified steps explicitly. No fabricated citations.
6. **Evaluator:** use held-out project tasks to compare task success,
   evidence recall, citation correctness, wall time, p95 latency, model tokens,
   search costs, fail-closed behavior and user approvals against the baseline.

Persist a resumable **task ledger** distinct from reviewed project memory,
using SQLite with durable statuses and cancellation. Replays of operations with
possible side effects must use idempotency checks and operator review, not
blind retries.

## 4. Multiple coding agents: give each a bounded workspace

A practical STAR engineering team is an orchestrator plus separately scoped
roles for architecture, source retrieval, Luau/Python/TypeScript implementation,
UI/visual review, testing, security review and integration.

Start on **two** concurrent read-only agents; add more only if device/provider
benchmarks demonstrate lower end-to-end time. For write-capable coding workers,
the owner must explicitly enable a verified coding sandbox. Use independent
Git worktrees or isolated containers and assign disjoint file ownership. The
planner reserves conflicting writes/readers; changes undergo typechecking,
syntax checks, deterministic tests and diff review. Integration alone may
propose a draft PR against a chosen non-main work branch. No silent merge,
force-push, evaluation-fixture edits, policy changes or game publication.

For Roblox, use the official Studio MCP/open-cloud boundaries and existing
`star/policy.py` permission gate. Real quality checks must cover
playability, visuals, Luau warnings, server/client authority, streaming and
mobile performance. A local model's design description is not a screenshot.

## 5. Tool discovery and self-created tools

**Tool discovery** should read the official MCP Registry and approved vendors'
tool manifests **as metadata**. Rank candidates by task capability,
maintainer provenance, pinned version/digest, license, permissions, telemetry,
installation surface, schema size, maintenance and sandbox reproducibility.
Flag risky descriptions and verify schema hashes. Present candidates to the
owner; installing or connecting new software remains an explicit approval.

**Tool creation** should evolve from declarative, previewed read-only recipes
toward candidate code *only inside an isolated build worktree*. Require a
minimal schema, test fixture, import review, allowlisted dependencies,
filesystem/network sandbox, per-tool timeout, output cap, secret scans,
signature/provenance review and a diff of changed permissions. STAR must never
authorize a candidate tool using only its own endorsement. Auto-enable only
after independent tests and owner approval.

Start with tools that directly raise Roblox creation quality: Luau syntax/
type validation; source graph/dependency navigation; Rojo sync previews;
geometry/PBR asset validation; animation rig checks; style-reference checks;
UI overlap and contrast checks; automated Studio test-scene screenshots.
Treat Blender and external engine automation as separate, optional capabilities.

## 6. Faster without quality collapse

Measure first: median and p95 first-token latency, full-task time, tokens/s,
VRAM usage, parallel slot occupancy, context bytes, cache hits, research API
calls and objective task success. Benchmark **one vs two** concurrent model
slots on the target Windows device. STAR already routes different tasks; next
optimizations should avoid redundant tools/context, preserve prefix cache
keys, compact with citations, and let small models handle narrow extraction
while stronger models critique or integrate. Cache only immutable,
revision-scoped read evidence. Never share private project evidence across
users or projects.

llama.cpp documents parallel slots, continuous batching, and speculative
decoding, but these features are **hardware-dependent hypotheses**, not
promised speedups. Resist 10-agent configurations until metrics establish
benefit on the owner's GPU.

## 7. Research references and what to borrow

| Primary reference | Applicable capability | STAR decision |
|---|---|---|
| [Anthropic: multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Orchestrator, parallel research, evaluation and token-cost tradeoffs | Borrow fan-out/merge, cap real workload |
| [OpenAI Agents SDK orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration) | Manager/specialist ownership, tools and handoffs | Preserve existing guarded STAR Python runtime instead of immediately importing a second orchestrator |
| [OpenAI Agents SDK tracing](https://openai.github.io/openai-agents-python/tracing/) | Run and tool-call observability | Implement local privacy-aware event ledger before external telemetry |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/durable_execution/) | Checkpointed tasks versus durable knowledge | Adapt existing SQLite rather than migrate user memories blindly |
| [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk) | Coding agents in isolated workspaces | Compare isolated-worktree design in a gated sandbox experiment |
| [MCP Registry](https://github.com/modelcontextprotocol/registry) | Server discovery metadata | Discovery yes; no unreviewed auto-install or auto-permission |
| [MCP local security](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/tutorials/security/local-server-security.mdx) | Tool-description injection and server trust | Pin and audit tool definitions after connection |
| [OWASP excessive agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) | Risks from excessive permissions, tools and autonomy | Host-enforced least privilege and independent approvals |
| [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | Parallel slots, batching, speculative decode | Benchmark per model/device, never promise gains without measurements |
| [Anthropic: agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Multi-turn, tool-dependent behavior evaluation | Use reliable holdouts, failure taxonomy and trace-based regression tests |
| [OpenAI: coding benchmark issues](https://openai.com/index/separating-signal-from-noise-coding-evaluations/) | Benchmark task/grade failures | Audit task correctness; prioritize private project-realistic acceptance over leaderboard claims |

## 8. Acceptance criteria for future increments

A feature is not "smarter" because the UI displays more agents. Require
repeatable evidence that it improves **at least one** of: verified task
success, precision of citations, the number of high-quality Roblox artifacts
approved by a human, bounded latency at equal quality, or safe recovery under
failure — with **no regressions** in private-project isolation or security.

Current candidate only establishes *bounded workflow mechanics* under offline
tests. Live search quality, public article correctness, Windows provider keys,
real concurrent local-model performance, Blender, Roblox Studio, and release
packaging require separate acceptance evidence.
