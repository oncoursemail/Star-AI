# STAR 2.0 — Multi-model Workforce: October 15, 2026 field research and pilot

> **Status:** Research + a new **default-off, read-only Python pilot** on a review branch. No standalone Ruflo install, no AionUi bundling, no ACP/Claude Code adapter, no new desktop switch, no publication and **no paid model calls**. Passing unit tests will establish only the mocked transport/contract behavior, not end-to-end Windows provider functionality.

## The product STAR should build

One locally installed Windows application in which the owner chooses a project, asks for a deliverable and reviews an explicit work plan. One chosen **conductor** (eventually Claude Code or another agent using its *documented* interface) assigns subtasks to a small fleet of independently configured models. A trusted STAR controller, not any model, owns permission, provider selection, task dependencies, deadlines, budgets, evidence, git write isolation and human approval. The conductor may propose work; it never acquires permissions by telling STAR it needs them.

Separate concepts that are often mistakenly presented as one feature:

1. **Multiple chat windows:** independent conversations, not collaboration.
2. **Role prompts/subagents:** multiple roles do not guarantee different underlying models, accounts or bills.
3. **True provider fan-out:** independently authenticated requests to selected models, measured and labeled by host.
4. **Cooperative coding:** scoped code edits, isolated branches/worktrees, integration, reproducible tests and human review.
5. **Durable autonomy:** safe continuation after interrupts; read-only retries only unless work is idempotent and separately authorized.
6. **Learning:** validated project notes, retrieval and promoted examples, *not* autonomous foundation-model weight updates.

Current `star/next` already has `star/orchestration.py`, `agent_runtime.py`, `team_service.py`, `model_fleet.py`, `providers.py`, `mcp_connections.py`, `eval_gate.py` and the Windows React/Qt shell. Reuse them rather than installing a second permanent daemon, credential vault, vector store or permission policy.

## Primary-source competition review

| System | Worth adopting | Do not assume |
|---|---|---|
| [Ruflo](https://github.com/ruvnet/ruflo) | Hierarchical swarms, task/memory conventions, diagnostic CLI/TUI, provider adapters, plugin ecosystem | Agent count is not free-model count; initializing the CLI modifies a workspace and may add hooks. CLI, MCP tools and plugin console are distinct installation paths. Not a native Windows desktop installer. Provider/model identity must be checked from the transport, not from its config. |
| [AionUi](https://github.com/iOfficeAI/AionUi) | Native Windows frontend; leader/teammate user journeys, shared task board, ACP-managed agents, per-agent approvals | Shared folder is not isolation. Custom ACP Team Mode compatibility has been questioned in [#3525](https://github.com/iOfficeAI/AionUi/issues/3525) and [#4177](https://github.com/iOfficeAI/AionUi/issues/4177); Windows model-selection concerns in [#3747](https://github.com/iOfficeAI/AionUi/issues/3747). Test a real teammate, not only a configured slot. |
| [Maestro](https://github.com/RunMaestro/Maestro) | Desktop moderator group chat, reusable Auto Run plans, git worktree isolation, audit-friendly cross-agent requests | Worktrees prevent edit collisions only when the integrations actually create and honor them; group-chat synthesis alone does not compile or test the result. [CLI docs](https://github.com/RunMaestro/Maestro/blob/main/docs/cli.md). |
| [OpenCode](https://opencode.ai/docs/providers/) | Configurable provider/model per agent, local-compatible API, direct use as coding-worker bridge | An OpenCode subagent is not automatically a separate free account; provider access and quota are independent. |
| [ACP](https://github.com/agentclientprotocol/agent-client-protocol) | Agent-to-desktop client protocol: initialize/auth, sessions, prompts, updates, cancellation, permission requests | Protocol version negotiation matters; the published v2 changes client-owned filesystem/terminal methods. No unvalidated private ACP extension should be required. |
| [MCP](https://modelcontextprotocol.io/) | Narrow **tools** for Roblox Studio, Blender, research and approved local resources | MCP is not a universal multi-agent scheduler, nor does a tool description authorize code execution. [Security guidance](https://modelcontextprotocol.io/docs/tutorials/security/local-server-security). |

### Security and limits

- AionUi, Ruflo and Maestro show useful UI and orchestration patterns, but do not copy their implicit privileges or assume that all open issues are resolved.
- [OWASP MCP Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html) recommends least privilege and reviewing/pinning tool definitions. Tool outputs and model-written text are untrusted even from apparently friendly team members.
- [Claude Code non-interactive CLI](https://docs.anthropic.com/en/docs/claude-code/cli-usage) supports `--print`, JSON/stream-json and permission settings. A real Claude lead adapter must safely bind session, filesystem scope, permission prompts, costs and cancellation, and must use *authorized* user authentication. **Not implemented in this pilot.**
- [OpenRouter pricing](https://openrouter.ai/pricing): free tier includes free models with **50 requests/day** before qualifying credits; free access is not limitless throughput or a promise of a specific model.
- [Google's June 18, 2026 announcement](https://github.com/google-gemini/gemini-cli/discussions/28017): consumer/free Gemini CLI requests moved to Antigravity CLI. Do not hard-code the retired login flow. [Antigravity pricing](https://antigravity.google/pricing) is plan/region/quota dependent.
- [Qwen Code authentication](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/): its prior OAuth free tier ended April 15, 2026. Open-weight Qwen models remain a separate local/provider route.
- For the owner's Windows desktop, use existing STAR-managed local inference first. The RTX 3060 Ti's 8 GB VRAM cannot host many large models simultaneously. On the second machine use measured CPU/RAM/model-slot availability, not invented speedups or indiscriminate swarms.
- Subscription access to Claude/other interactive apps is **not automatically** API access for arbitrary agents. Obtain consent, follow provider terms, expose actual usage/quotas, and never rotate accounts to circumvent limits.

## Implementation delivered by this review branch: bounded fleet pilot

File: `star/conductor_fleet.py`. It extends—not replaces—STAR's existing task planner and runner.

**Trusted inputs:** 1–8 existing `Task` nodes; 1–4 `FleetMember` slots; an exact application-selected task-to-member map; snapshots of STAR's existing validated `Settings`. STAR's `open_client` and `background_client` authenticate through the existing approved provider catalog/keyring. No model-generated URLs or keys can be inserted.

**Execution:** actual `client.chat.completions.create` calls in parallel only when the dependency graph and per-origin semaphores permit it. Two logical local agents pointed at the same GPU endpoint serialize their requests. One worker can have a finite request budget; no implicit rerouting on timeout. Cloud requests require **two separate owner booleans**: allow cloud workers and consent to sending task/project context. Workers have no tools or write access.

**Receipts:** selected provider, selected model, **model returned by the response when present**, task status, observed token counts when returned, request and completed-answer SHA-256. Responses that report a different explicit model fail; for the dynamic `openrouter/free` alias, record the actual returned model without pretending the alias matched. Receipts mark `verified=False`: SHA-256 proves which content the host saw, **not that code works**. No raw credentials or prompts are persisted to disk.

**What is NOT delivered:** Claude Code ACP adapter, per-account credentials, cloud-cost estimates, full token metering when providers omit usage, write-agent isolation, artifact packaging, GUI, persistent job recovery, operating-system sandbox, proof that a provider truly ran particular weights, or a finished Windows release. These need separate reviews.

### Recommended test command on a checkout

```powershell
python -m pytest -q tests/test_conductor_fleet.py
python -m pytest -q tests/test_agent_runtime.py tests/test_team_service.py
python -m compileall -q star
```

The PR's GitHub Actions are the authoritative review tests for this branch. Native Windows provider logins, CPU load, local model identity, editor automation and installation must also be tested on the owner's machines before exposing the feature as ready.

## STAR's target architecture

```text
User request / selected project
   ↓
Conductor proposal (Claude Code / eligible other ACP leader; later phase)
   ↓
STAR trusted policy + route compiler (existing TaskPlan)
   ↓
Local/remote model catalog  ──→ quota / price / privacy / hardware limits
   ↓
Workforce run (real calls, bounded parallelism, deadline, cancellation)
   ├── Research worker → cited evidence
   ├── UI worker       → editable React/Figma proposal
   ├── Roblox worker   → Luau proposal / Studio Lab tests
   ├── Art worker      → Blender / image draft in sandbox
   └── Reviewer        → independent rejection and repair prompts
   ↓
Integrator + host-owned verification → result manifest / diffs / screenshots
   ↓
Owner review (Approve, Request fixes, Reject) → gated repo PR or export
   ↓
Only *verified + accepted* corrections → project-scoped lessons
```

Future coding workers get one task-owned worktree or isolated scratch folder each. No shared writable folder with concurrent uncontrolled workers. The existing STAR GitHub App may open draft PRs only inside its approved repository scope; no auto-merges or live Roblox publication.

### Runtime invariants

1. Task owner, provider, model, tool permissions, project and dependency set are immutable for each running task.
2. Agent output is always data, never a policy/approval instruction. Model summaries cannot upgrade `verified` flags.
3. Abort if provider identity unexpectedly differs, if a dependency failed, if context is about to go to an unapproved cloud route, or if a task requests writes in read-only mode.
4. Reserve memory and per-endpoint compute slots; allow at most a few *useful* parallel models rather than thousands of queued chatbots.
5. Final output names failures, unverified claims, missing citations, skipped tests and actionable next checks.
6. Never pretend a cloud fallback is the owner's local model. Every provider switch needs consent and an observable event.
7. Structured event logs are bounded, host-authored and redacted. A model can't write its own PASS verdict into a test ledger.
8. Persistent retry of **side-effectful** actions is forbidden without an idempotency design and explicit authorization.

## Desktop UI — build a genuinely designed workforce workspace

Use STAR's existing React/TypeScript + Qt WebEngine shell, not a competing Electron app. Avoid touching the active UI PR's `Desktop.tsx` until it merges or its integration points are reviewed. Keep the user's approved Star mascot and OLED/gold visual identity.

### Information architecture (not a stock neon dashboard)

- **Left rail**: Chat, Projects, Workforce, Library, Connections; small clear labels, project switcher; no duplicated navigation.
- **Main header**: project breadcrumb, mission title, active model and privacy mode; accessible keyboard focus.
- **Center workspace**: vertically grouped task lanes showing actual dependencies and named model owners; concise status, time and evidence, not a sea of generic cards/circles. Show Pending, Running, Waiting for approval, Blocked, Failed, Done.
- **Right inspector**: selected worker's provider+model, quota, granted scope, sources used, structured artifacts, reviewer disagreements and exact reason for any failure.
- **Bottom review surface**: actual diff, screenshot comparison, Luau output, tests and Retry / Approve / Reject actions. Never label a generated proposal as installed, published or verified.
- **Settings**: native-feeling searchable list of eligible provider integrations, each with Authenticated / Needs setup / Unsupported / Offline status, independent credential management and privacy consent.
- **Accessibility**: keyboard-only operation, visible focus, WCAG-tested contrast, screen reader names, useful empty/error/loading states, 200–400% scaling, reduced-motion path.
- **Visual acceptance**: capture actual Windows screenshots at 100/125/150/200% DPI, 1280×720 through ultra-wide, responsive browser sizes, long task names, running/failure/cancellation. Check typography baseline, panel alignment, scroll ownership, truncation, no icon-label collisions, no placeholder model metrics. Compare against a reference editorial/motion system selected by the owner; iterate until approved.

No fake graph nodes, invented star counts, fabricated activity, “10 agents connected” claims or glowing gradients just because an AI generated the interface. The task graph must be derived from host events.

## Research-to-product phases (gated, not promises of completed features)

| Phase | Deliverable | Gate |
|---|---|---|
| **P0 (this PR)** | Read-only provider-aware team runner, quota/concurrency/cancellation, honest receipts + fake-transport tests | CI and manual review; not exposed to ordinary users |
| **P1** | Opt-in Workforce view wired to real backend task events; accessible consent/auth setup and model identity status | Rendered screenshot review, Windows DPI/a11y, privacy test |
| **P2** | Version-negotiated ACP client with Claude Code leader, OpenCode worker, and Antigravity when provider legitimately supports integration | Spawn/auth/session/prompt/cancel smoke tests with *actual* CLIs; independent provider logs |
| **P3** | Coding in isolated per-task worktrees, patch application and 3-way integration, independently run unit/build/Luau/Studio Lab checks | No edits outside approved scopes, deterministic CI, forced-conflict replay |
| **P4** | Durable read-only mission checkpoints + evidence-grounded lessons + hardware-aware workload planner | Interrupted-run replay, context revision invalidation, memory safety, benchmark before/after |
| **P5** | Curated Ruflo-compatible skills/adapters and bounded specialist marketplaces | Audited versions, reviewed MCP tool schema hashes, prompt-injection and rollback tests |
| **P6** | Causal failure prediction and self-improving playtest loop based on *actual* failure data | Calibration on withheld failures; measure precision/false positives and verified repairs |

### Original product research direction: “Proof-Carrying Work Cells”

Each worker's result is packaged with **host-generated lineage**: which model was requested, what was actually observed, which task it received, input/output hashes, the controlled workspace diff, runtime checks and the owner's acceptance decision. A conductor can propose parallel experiments, but only evidence-backed artifacts become reusable memory. Add a “Failure Forecast” trained on **recorded** prior verification failures, tested on holdout tasks; show confidence intervals and false positives instead of pretending omniscience.

This combination may be a useful STAR differentiator. It is **not** a claim that nobody has ever explored provenance, process mining, predictive testing or multi-agent orchestration.

## What to benchmark rather than market as already solved

Record setup time, authenticated workers that actually respond, model identity match rate, per-provider errors/quotas, p50/p95 first-token and completion latency, peak GPU/RAM/CPU, number of real parallel calls, successful compiled outputs, regression-free merge rate, test coverage of changed lines, rollback outcomes, and owner-rated UI quality. Include single-model Claude, local-only and mixed-provider baselines at comparable cost. Report **zero/unknown** until measured.

## Repository concurrency notes

On October 15, 2026, several open STAR PRs are already relevant:

- [#413](https://github.com/oncoursemail/Star-AI/pull/413): conductor research + evidence contracts.
- [#421](https://github.com/oncoursemail/Star-AI/pull/421): open-agent catalog.
- [#402](https://github.com/oncoursemail/Star-AI/pull/402): read-only checkpoint recovery.
- [#418](https://github.com/oncoursemail/Star-AI/pull/418): STAR's genuine desktop workbench redesign.

Do not rewrite their files from this PR. Later integrate their contracts into this provider runner when reviewed and merged. Keep `star/next`/main policy and auth modules unchanged; request an independent review before connecting tool-writing agents.

## Evidence references

Primary documentation as retrieved on October 15, 2026: [Ruflo README](https://github.com/ruvnet/ruflo), [Ruflo changelog](https://github.com/ruvnet/ruflo/blob/main/CHANGELOG.md), [AionUi Team Mode README](https://github.com/iOfficeAI/AionUi/blob/main/readme.md), [Maestro overview](https://github.com/RunMaestro/Maestro/blob/main/docs/about/overview.md), [OpenCode provider docs](https://opencode.ai/docs/providers/), [ACP](https://github.com/agentclientprotocol/agent-client-protocol/blob/main/docs/protocol/v1/overview.mdx), [OWASP MCP security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html), [OpenRouter pricing](https://openrouter.ai/pricing), [Google Gemini CLI transition](https://developers.google.com/gemini-code-assist/docs/deprecations/code-assist-individuals), [Qwen Code discontinued OAuth](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/).
