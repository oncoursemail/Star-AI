# STAR 2.0 — Conductor Intelligence: Rilo integration, portable AI agents, and verified learning

**Research date:** 2026-10-15. **Status:** research architecture + separately proposed default-off evidence contracts, NOT a shipped conductor or a model upgrade. **Target:** `star/next` via a draft PR; do not modify `main`, release, merge, install software, authenticate providers, run paid calls, or grant permissions.

## Executive decision

Build **STAR as the host-controlled intelligence/conductor**. Import Rilo's best user interaction patterns and local coding-agent adapters **as concepts and selectively reviewed implementations**, not by copying its entire Electron application into STAR. Allow STAR or a user-selected Claude/Codex/other model to *propose* task plans; only trusted STAR code validates scope, admission, tool permissions, costs, execution, receipts, review, and memory promotion.

The proposed differentiator is a **cross-agent proof-carrying handoff + verified lesson exchange**: candidate agents supply artifacts; independent host-owned tools supply execution/test evidence; one project-scoped evaluation and owner-feedback pipeline converts demonstrably useful outcomes into reviewed skills, prompts, examples, and routing improvements. No provider is asked for its private reasoning. Merely talking to Claude, Codex, or Grok does not automatically retrain STAR or those vendors' weights.

Optimize the measurable objective **accepted correct work per owner hour and dollar under resource and privacy budgets**, not simultaneous token count, model count, empty "AI power" claims, or unconstrained background activity.

## 1. Primary-source audit: what Rilo actually is

**Repository:** https://github.com/oncoursemail/Rilo

| Evidence | What exists in the draft branch | What is not yet proved |
|---|---|---|
| [Rilo #1](https://github.com/oncoursemail/Rilo/pull/1) | Electron app prototype with headless Kilo, Antigravity, OpenCode, Ollama; isolated Git worktrees, streamed process logs, cancellation; test/packaging files | Real cloud-provider login, installed Windows GUI, independent code verification |
| [Rilo #7](https://github.com/oncoursemail/Rilo/pull/7) | Team Studio agent toggles, project picker, role prompts, per-provider models, fan-out to separate branches; documented four-process cap for this stage | Genuine task DAG, agent-to-agent communication, reconciliation, shared evidence, secure OS sandbox |
| [Rilo #9](https://github.com/oncoursemail/Rilo/pull/9) | Persistent local transcripts and settings; Windows update implementation with explicit install consent | Finished real-device updater rollback acceptance |
| [Rilo #10](https://github.com/oncoursemail/Rilo/pull/10) | New unified console, Claude Code headless provider, selectable model aliases, opt-in MCP registration, six-process ceiling, first-output timings | Connected live MCP introspection, genuine synthesis, durable multi-step missions, self-learning, empirically best provider routing |

**Important:** These are *stacked DRAFT PRs*. Rilo `main` currently contains a small project README, not all those pending features. Its team dispatch gives separate agents related prompts, but there is no verified shared plan or trustworthy automatic integration. A worktree is an editing boundary, **not** a security sandbox. Rilo #10's solo Claude permission bypass is unsuitable for unattended team execution; STAR should not inherit it automatically.

The most transferable Rilo components are (1) per-agent on/off/role/model selection; (2) CLI readiness/error display; (3) human-readable run timeline and cancellation; (4) scoped Git worktrees; (5) persistent sessions and updater-safe state; (6) responsive command-center interaction. The most valuable *missing* component is true orchestration and feedback.

## 2. Existing STAR baseline: extend, do not duplicate

**Repository:** https://github.com/oncoursemail/Star-AI ; staging [PR #368](https://github.com/oncoursemail/Star-AI/pull/368) contains `star/next`, and is not the published `main` release.

- `star/orchestration.py`: validated role/task DAG and path read/write exclusions; it itself does not spawn agents.
- `star/agent_runtime.py`: bounded real asynchronous worker runtime, failed-dependency blocking, cancellations, event callbacks, timeouts; tool permissions stay with trusted worker implementations.
- `star/team_service.py`: existing **local/LAN-only** three specialists plus one synthesis for read-only answers, not a mixed-vendor coding workforce. It explicitly rejects cloud providers in this mode.
- `star/providers.py`: direct API-key cloud routing currently includes **GroqCloud (not Grok)**, OpenRouter, Gemini, Cerebras, alongside private local/LAN routes. Never mislabel one provider as another.
- `star/resource_planner_service.py`, `star/agent_resource_planner.py`: CPU/RAM/VRAM admission and lease ideas; preserve the existing machinery.
- `star/knowledge.py`, `star/conversation_memory.py`, `star/learning.py`, `star/learned_week.py`: project-scoped memory, owner-approved corrections, night-school reviewed lessons, temporary trials.
- `star/eval_gate.py`, `star/eval_stats.py`: paired independent evaluation gate. A generated test report or passing CI by itself does NOT justify broad model superiority.
- Existing drafts: [#401 evidence broker](https://github.com/oncoursemail/Star-AI/pull/401) and [#402 read-only mission checkpoints](https://github.com/oncoursemail/Star-AI/pull/402). Rebase/adapt their reviewed APIs after upstream integration, not overlapping rewrites.
- Open backlogs: [#406 Agent Fleet](https://github.com/oncoursemail/Star-AI/issues/406), [#407 free API Control Center](https://github.com/oncoursemail/Star-AI/issues/407), [#307 knowledge fabric](https://github.com/oncoursemail/Star-AI/issues/307). These remain implementation backlogs; don't mark them shipped.

**Gap:** STAR currently lacks an integrated mixed-vendor agent session with unified, trustworthy result receipts, provider-native subscription/CLI authentication, cross-agent artifact handoffs, isolated code-writing concurrency, tool-specific cost/permission views, and measured learning from those sessions.

## 3. Crucial access model: a subscription is not a generic API key

Use **five distinct transport types**. Do not present a single deceptive "any subscription means unlimited API" login.

| Transport | Examples | Authentication and terms | STAR design |
|---|---|---|---|
| **Local inference** | llama.cpp, Ollama, selected GGUF models | Local model files, owner-selected licensing; CPU/RAM/VRAM | Already supported; use existing routers, no compulsory key |
| **External coding-agent harness** | Claude Code, Codex, OpenCode, Kilo, Antigravity, Copilot CLI, where official support exists | Each CLI/SDK owns sign-in, tool permissions, model rights and quota | Prefer Agent Client Protocol (ACP) and official app-server/SDK; bounded headless CLI only as vetted fallback |
| **Direct hosted model API** | xAI Grok API, Anthropic API, Gemini, OpenRouter, GroqCloud, Cerebras | Per-provider keys, billing, data-retention/privacy policies | Owner opt-in, native vendor endpoints, OS keyring, hard spend caps and no silent cloud fallback |
| **Agent-to-agent service** | Authorized remote A2A agents and owner-hosted worker on Brain 2 | Endpoint-specific authentication, trust, billing and role | Phase-later A2A client, explicitly approved endpoints, no broad internet agent discovery auto-run |
| **Tool/connector** | Roblox Studio, Blender, Playwright, Figma, GitHub through MCP | Tools are capabilities, NOT inference subscriptions | Review tool/schema digest, scoped project access, exec/network controls, audit trail, per-tool approval |

**Claude Code.** Official Claude documentation says Pro/Max users can authenticate the CLI with their Claude subscription, subject to shared usage limits. On 2026-10-07, Anthropic documented continued subscription-limit use for the Agent SDK and third-party apps and new Max/Team monthly API credits. **Crucial billing caveat:** `ANTHROPIC_API_KEY` in the environment can switch Claude Code to metered API billing. Show the effective authentication *path* without reading/displaying secrets. Detect quota failure/plan prompts and pause rather than silently buying credits. See:
- https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan

**Codex / ChatGPT.** Official OpenAI Codex supports `codex exec` (bounded tasks), an SDK, and app-server for threads, streaming, approvals and resumability. The September 28, 2026 **Sign in with ChatGPT** open-source integration documents optional consented ChatGPT-plan usage for eligible Plus/Pro users; it is not access to their ChatGPT history. Integrate with the official open-source sign-in client and Codex app-server only after consent, eligibility, token renewal, branding, secure keyring and preview limits are verified. A model catalog is **not** an entitlement check; run a permitted real test call. No credential scraping/browser-cookie hacks or entitlement claims based solely on plan names.
- https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt
- https://developers.openai.com/siwc/quickstart
- https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
- https://developers.openai.com/blog/codex-as-a-platform

**Grok (xAI) vs Groq (inference).** A newly announced X Subscription pools Grok and Cursor features in those products, but **xAI states Grok consumer and xAI developer API billing are separate**. Do not promise an X/SuperGrok plan can make arbitrary xAI API calls. Start with official xAI API as an explicitly metered, separately configured provider; explore an officially supported Grok Bot/Cursor agent integration only when vendor terms and documented transport permit it. STAR already has a *GroqCloud* adapter; that is not a Grok model adapter.
- https://x.ai/news/x-subscription
- https://docs.x.ai/developers/faq/accounts
- https://docs.x.ai/developers/rest-api-reference/inference
- https://docs.x.ai/developers/cost-tracking

**Free models.** Include owner-selected, actually available local models and legitimate time/region/account-limited free API plans (e.g. eligible Gemini/OpenRouter/Groq tiers) with live quotas, availability and privacy labels. No guarantee of perpetual free model IDs. Never rotate accounts to circumvent limits, silently spend, or send private Roblox project sources to a public service without consent.

## 4. Technical architecture: separate the planner, conductor, and executor

```text
STAR Desktop (existing React/TypeScript shell)
  ├─ Direct: STAR | Claude Code | Codex | OpenCode | other supported agent
  ├─ Conductor: STAR leads | Claude proposes plan | Codex proposes plan
  └─ Mission: goal + project + quality/time/cost/privacy + enabled agents/tools
            │
            ▼
TRUSTED STAR CONTROL PLANE (Python)
  mission contract + repo revision + provenance + rights + approval policy
  durable DAG / read-write claims / budgets / priority / cancellation
  capability catalog + health probes + model/agent selection
            │
   ┌────────┴────────────┐
   │ adapters/agent loop │  local model | official CLI/SDK/ACP | direct API | later A2A
   └────────┬────────────┘
            │
  scoped tasks in isolated worktrees AND appropriate OS isolation
            │
  evidence broker: source digests, diffs, raw test receipts, Studio renders,
  tool-specific verification, errors, costs, timestamps, reviewer identity
            │
  independent verifier / source-aware synthesis / owner diff & visual approval
            │
  only then → reviewed code proposal / candidate learning / project memory
            │
  sealed paired eval + rollback → revised skills/router/prompt/tool candidates
```

**A model chosen as conductor is a *planning/synthesis peer*, never the authority that grants itself new credentials, raises spend caps, disables checks, selects private projects, changes protected tests, or deploys.** STAR as host validates the same plan regardless of whether STAR, Claude, or Codex proposed it. Avoid running two full orchestrators simultaneously as competing authorities.

### Core typed contracts

1. `MissionRequest`: `mission_id`, project/repository ID, user intent, frozen source revision, output target, acceptance tests, authorized read/write paths, tool grants, privacy classification, time/token/dollar caps, permitted provider list, cancel token.
2. `AgentDescriptor`: provider transport/CLI version, model ID or alias, capabilities (code/tools/vision/MCP/long-running), auth state (connected/unknown/denied; NO token), region/privacy, estimated marginal cost, observed health, machine and concurrency slots, last verified date.
3. `WorkOrder`: task ID, dependencies, bounded inputs/source refs, outputs required, tool grants subset, resource lease, task-owner identity and retry/idempotency policy; typed `TaskPlan` remains the scheduler source of truth.
4. `AgentEvent`: started/progress/tool request/approval request/artifact proposal/tool error/cancelled/failed/finished, with sequence number and immutable run IDs. Never substitute a natural-language agent claim for a host event.
5. `EvidenceEnvelope`: project+task+run+agent+model ID, source revision, artifact SHA-256, exact test/verifier receipt hashes, timings, cost provenance and uncertainty labels. No private prompts, secrets, raw personal memory or unapproved screenshots in public GitHub.
6. `LearningCandidate`: scoped fix/pattern, preceding failure, verified result hash, task-family tags, source rights, reviewer state, negative constraints, expiry and rollback ID. Auto-accepting model-written lessons is prohibited; use STAR's existing review/eval gate.
7. `IntegrationProposal`: cross-worktree patch/PR against owner-selected non-main branch, test evidence, diff and risk summary, with an explicit owner review point. No automatic merge or game publication.

**State machine:** `queued → admitted → running → awaiting_review → verified | failed | cancelled | incomplete`; a process exit code of zero is NOT `verified`. A blocked dependency does not count as pass. Every retry with side effects requires an idempotency key or new approval.

## 5. Interoperability choices and their tradeoffs

| Standard/framework | Appropriate use | Decision |
|---|---|---|
| **Agent Client Protocol (ACP)** | Host ↔ local interactive coding agents with streams, threads, approvals | Primary agent adapter where actually supported; feature-probe, do not assume uniform tool permissions |
| **Codex app-server/SDK** | Codex threads/events/approvals and sanctioned ChatGPT-plan consent | First-class adapter; keep Codex-specific protocol behind a common interface |
| **Claude Code/Agent SDK** | Headless or persistent Claude coding sessions; native session, permission hooks | First-class optional adapter, no unattended permission-bypass |
| **OpenCode** | Broad provider catalog/local models and agent runtime | Optional adapter; reuse its provider config rather than pretending all its models are native STAR |
| **GitHub Copilot SDK** | Supported subscription-backed coding tool and parallel subagent features | Optional adapter after license/entitlement verification |
| **MCP 2026-07-28** | Tool and data capability access, auth and task extensions | STAR broker owns user permission & scope; cache lists by version/TTL; reject unreviewed servers |
| **A2A 1.0** | Remote autonomous agents with Agent Cards, async tasks, artifacts | Future cross-host bridge after local execution works; not needed to run two local CLIs |
| **LangGraph** | Durable graph/checkpoint and human-approval patterns | Study contracts, preserve STAR's existing Python DAG; do NOT replace runtime without proven advantage |
| **OpenHands SDK** | Sandboxed software-agent reference, typed events, workspace separation | Compare as optional backend, not second always-on assistant |
| **Microsoft Conductor** | Versioned, deterministic YAML agent workflows | Borrow declarative workflow replay and deterministic routing, not a duplicate scheduler |
| **RouteLLM** | Learn when cheaper models suffice | Borrow quality/cost controlled evaluation; do not import ancient router weights as universal truths |
| **DSPy (MIPROv2/GEPA)** | Candidate prompt/skill improvements scored by frozen metrics | Offline, opt-in optimization after dataset and independent evaluator are secured |

Primary sources:
- https://agentclientprotocol.com/ and https://zed.dev/docs/ai/external-agents
- https://github.com/openai/codex
- https://github.com/github/copilot-sdk
- https://github.com/anomalyco/opencode
- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://a2a-protocol.org/latest/specification/
- https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph
- https://github.com/OpenHands/software-agent-sdk
- https://github.com/microsoft/conductor
- https://github.com/lm-sys/RouteLLM
- https://github.com/stanfordnlp/dspy

## 6. The cross-model learning engine (central STAR 2.0 feature)

### A. Capture observations without equating logs with truth

Only with consent for the selected project, store bounded **host-generated** metadata for each run: model/provider/version, task family, tool versions, source revision, timed actions, exact artifact/test receipt digests, classification of failures, human accept/reject, corrections and final accepted patch. Preserve original sensitive logs *locally and under retention controls*, not in public GitHub, provider prompt history or another cloud AI by default.

Separate confidence classes:
- **agent-reported**: agent says it finished/ran tests; no trusted proof.
- **tool-observed**: STAR actually saw an allowlisted tool/test run return evidence tied to source/artifact.
- **independently reviewed**: separate verifier/CI and, where visual quality is subjective, explicit owner acceptance.
- **promoted skill**: review + sealed eval and rollback record; still NOT model weight training.

This branch's proposed `star/conductor_evidence.py` is **pure, default-off admission logic** for cross-provider learning *candidates only*. It does not create identities, run tests, connect CLIs, persist private logs, or promote lessons. Input construction must occur inside a trusted host after verifiable tool events, never by deserializing a model's self-reported `host` flag.

### B. Convert observed wins/failures into transferable lessons

1. **Detection:** match a failed task to exact Luau error, UI overlap, animation grip issue, failed Blender export, broken test or user-design rejection.
2. **Counterfactual repair:** offer 2–4 alternative edits/approaches inside scoped task workers; stop if budget insufficient. Preserve a control baseline and record which change actually caused improvement.
3. **Independent verification:** rerun same targeted tests and untouched sealed holdouts; native Studio evidence for Roblox; side-by-side owner review for visual taste.
4. **Extract a narrow skill card:** `when task signals X, check Y; prefer action Z; avoid error W`, tied to result/source hashes and bounded negative examples. Do not store secret/restricted data or provider-internal deliberation.
5. **Apply selectively:** the relevant STAR local model can retrieve the approved skill via existing project memory; participating external agents can receive a compatible brief *only with consent* and provider rights. Their vendor weights do not change.
6. **Measure actual gain:** paired same-hardware/model and task-family trials, time to verified correct artifact, test recall, success, cost; reject if regression or inconclusive.
7. **Optional actual fine-tuning:** only rights-cleared, owner-authorized samples and capable hardware/service; compare a frozen base vs trained candidate. STAR's existing GGUF running a context document is NOT training. No automatic private-data training.

### C. Learn who should work on what

First collect a **task-specific model scorecard**; do not guess that "highest tier" means "always best." For each provider/model/version/task family track true independent pass rate with uncertainty, time-to-first-output, time-to-correct-artifact, cancellation/error rate, p95 load, API charge (actual if available), and local resource pressure.

Start with a **deterministic capability filter**, then route to an affordable, available model; use one strong independent reviewer only when the expected correctness gain exceeds cost/latency. After sufficient independent outcomes, experiment with a conservative contextual-bandit selection policy in shadow mode. No training on the sealed benchmark labels. Always permit manual model/conductor override, local-only/zero-spend mode and explicit privacy exemptions.

### D. Proposed experimental differentiator: Proof-Carrying Handoffs

A lightweight shareable `proof packet` = input/source hash + task contract + output artifact hash + *independently obtained* checker reports + reviewer notes + bounded summarized context. Handoffs omit chain-of-thought, credentials and unrestricted filesystem references. Agents can continue from these packets without each re-reading the entire repository. STAR can compare which route got to a **correct** artifact fastest and which checker prevented failures.

**Hypothesis, not proven novelty/superiority:** these packets plus revision-scoped caching and adaptive scheduling can reduce wasteful repeated agent research while making learning more reliable. Validate against a simple single-model baseline, Rilo fan-out and STAR local Teams. Preserve source excerpts only with their permissions and revocation hooks.

## 7. Hardware, scheduling and actual speed

- **Brain 1 known target:** Windows 11, RTX 3060 Ti 8 GB VRAM, 32 GB RAM. Heavy simultaneous local LLMs will compete for memory bandwidth and often get slower. Benchmark 1 vs 2 concurrent resident-model slots and sequential 4B/9B/large quantized models; do not promise an all-in-VRAM 27B.
- **Brain 2:** allocate Roblox Studio/Blender/GPU rendering and physical-device verification only after explicit host setup. Its current capacity, GPU and active headroom must be measured rather than invented. Agent orchestration must not starve Studio.
- Keep low-latency interactive chat high priority. Admit CPU-only retrieval, static checks and document searches in parallel; GPU image/vision/Studio heavy tasks get exclusive or bounded leases.
- Cache versioned, authorized source snippets, project AST/dependency maps and reusable tool results by exact source/permissions hash. Never cache whole private projects across unauthorized runs; invalidate on source deletion/revocation.
- Deduplicate the same tool lookup across cooperating agents. Stream first useful progress, but do not label elapsed UI activity as proof of completion.
- Benchmark p50/p95 **time to correct accepted result** as primary, plus TTFT, tokens/s, provider retries/rate-limit wait, worktree conflicts, memory peak, input tokens and cost. More agents may improve throughput while making one task slower.

## 8. UI and experience: one command center, not a gimmicky multi-chat wall

Keep STAR's existing React/TypeScript desktop shell for now. Do not replatform to Tauri, rebuild the updater, or fork Rilo's Electron shell before user-visible benchmarks. Rilo's own draft wisely keeps its existing Electron bridge for this stage.

**Three prominent user modes:**
1. **STAR Chat** — STAR's local/private answer path; specialist tools selectively applied.
2. **Direct Agent** — pick one provider (Claude Code / Codex / OpenCode / others) and converse with its real agent through provider-owned authentication. A visible toggle offers **"Share verified results with STAR learning"**; off means no training/lesson extraction from that direct session.
3. **Conductor** — choose **STAR leads**, **Claude plans**, **Codex plans**, or **Auto (measured)**; STAR remains the runtime authority; select enabled agents, per-model budget, project, tool trust, write permission and review requirements.

**Mission Control** (one main screen): left narrow project/history navigation; central conversation + task DAG with dependable live task states; right collapsible selected-worker inspector showing model, repo/worktree, actual tools granted, consumption/credits, artifacts, tester output, diff, review and cancellation. Add a compact **Provider Connections** settings screen with separate statuses "installed / signed in / access verified / rate limited / paid metered / disconnected"; no raw credentials displayed. Show exact cost or explicitly `unknown`.

**Learning Inbox:** `candidate → proof attached → owner accepted/rejected → trial → kept/rolled back` with before/after checks, date, source, affected project and undo. Give users a one-click method to say "this UI is wrong because labels overlap icons" and bind it to screenshot/reference hashes.

**Visual language:** OLED black (#000 baseline), restrained warm gold/accent and cream/white text; crisp hierarchy, narrow outlined panels, deliberate spacing, no neon, glow, floating decorative circles, busy agent icons, overlapping text, synthetic statistics, or inert actions. Responsive at 1050×680/1440×900 and 100/125/150% Windows scaling. Respect reduced motion, focus visibility, legible contrast, long transcript virtualization and cancellation; screenshot-test with real renderer, not only DOM snapshots.

## 9. Safety, autonomy and honest "uncensored" operation

Provide **user-selected permissible local models and configurable content/style preferences** where licenses allow. "Uncensored" must NOT mean blanket filesystem/network/credential/publication privileges or silent tool permission bypass. A model can propose tasks; trusted STAR code enforces grant scopes. Never copy Rilo's solo `--dangerously-skip-permissions` option into background or mixed-agent mode.

- Default local/private and read-only for unknown agents/tools; approve each cloud transfer with sensitivity and retention shown.
- Owner-initiated settings/CLI authentication; validate vendor entitlement and TOS, stop on unavailable models or quota.
- OS-level sandbox/container or carefully scoped isolated worker for executing untrusted code; Git worktrees alone are not containment.
- Network and filesystem allowlists, secret isolation, artifact path canonicalization, subprocess argument arrays and input limits; pinned MCP server hashes.
- No account cycling, paid top-up, unattended posting/purchasing, Roblox live-place publishing, protected-path edit, test-suite self-edit, or autonomous release.
- Ask approval before high-impact writes; issue short-lived scoped grants to verifiable tasks, log immutable receipts, support kill/pause/rollback.
- Do not retain provider-proprietary hidden reasoning or assume permission to train on third-party outputs; require explicit data rights and documented retention.

## 10. Staged engineering plan and acceptance tests

### P0 — Conductor groundwork (now)

- Land isolated default-off `conductor_evidence` validation + tests. This is a research-backed reusable proof data contract, **not** live conductor wiring.
- Freeze user-facing requirements, route schemas and provider taxonomy in this doc; compare Rilo #10 and STAR #406 to prevent competing implementations.
- Add a dedicated umbrella issue referencing #406/#407 and each required acceptance gate.
- Acceptance: hash/project/source isolation, self-attestation refusal, failed/missing checks, bounded content, no credential/raw prompt storage; Python CI green.

### P1 — One true mixed coding-agent session

- Add **one** legitimate, official coding-agent adapter (Claude Code *or* Codex app-server) behind opt-in settings, then the second. ACP when feature-complete; official SDK/app-server fallback.
- Include user authentication and signed-in status without acquiring tokens from agents, streaming, interrupt, cancellation, actual CLI exit semantics, and a shared run ID.
- Run two independent read-only tasks and combine with source-linked evidence. Prove denial/timeout/401/429/CLI-missing handling and provider credits.
- Acceptance: real Windows device tests with authorized signed-in account; zero silent API usage; quality and latency comparison vs STAR local Team.

### P2 — Real DAG and isolated coding teamwork

- Extend existing `TaskPlan` and resource lease machinery to worker adapters, typed outputs, shared revision-scoped research and crash recovery. Reuse the checkpoint draft #402 if reviewed.
- Two agents in separate sandboxed worktrees tackle disjoint edits; third independent reviewer checks. On conflict, pause, do not auto merge.
- Acceptance: 3 overlapping edit cases, revocation midrun, stale source digest, permission denial, forced crash, repeated task replay, one Windows complete PR flow with author review.

### P3 — Verified learning across agents

- Store host-receipt evidence locally with project scope; propose skills/lessons via existing STAR `learning` and `eval_gate`, never direct auto-promotion.
- Run at least 50 right-cleared *project-disjoint* coding/Roblox/UI cases plus no-answer/privacy negatives; blinded owner quality judgments for visual tasks.
- Accept only a statistically supported gain on sealed heldouts with no privacy regression and no higher false-pass rate. Measure memory recall, wrong-project exposure, mean/p95 response and accepted quality.

### P4 — Adaptive model router, expanded tools, multi-host

- Benchmark local models + permitted free APIs + optional metered Grok/Claude/OpenAI direct APIs. Record source of each quota/charge; hard zero-dollar mode.
- Add MCP capabilities as separately reviewed and pinned connections, first Roblox Studio, Blender and Playwright, not unvetted massive registry installs.
- Add A2A bridge to permitted remote agents and Brain 2 only after secure authentication, health, permissions and end-to-end task receipt tests.
- Router rolls forward only on task-disjoint measured wins; rollback and manual override for regressions.

### P5 — STAR 2.0 release readiness (not a date promise)

- 20+ real owner-relevant end-to-end tasks across Luau, UI, meshes, animations, VFX, research and Windows app engineering; independent approval/benchmark receipts.
- No false claims of "merged" or "learned"; actual tested correctness, human acceptance, reproducible setup, common error recovery, offline/private-default and zero unauthorized spend.
- Windows packaged exe + upgrade preservation, accessibility, perf/resource/recovery, security and AI-provider acceptance. Publish only through owner-controlled release workflow.

**Primary decision:** Do **not** merge Rilo source directly or build a new second frontend. Treat Rilo as a tested design/adapter reference, keep STAR's working auth, policy, runtime, memory and CI as the trust root. Use small, independently reviewable changes rather than a single untestable "all providers everywhere" PR.

## 11. Research and evaluation evidence register

Project primary sources:
- Rilo drafts [#1](https://github.com/oncoursemail/Rilo/pull/1), [#7](https://github.com/oncoursemail/Rilo/pull/7), [#9](https://github.com/oncoursemail/Rilo/pull/9), [#10](https://github.com/oncoursemail/Rilo/pull/10)
- STAR [staging #368](https://github.com/oncoursemail/Star-AI/pull/368), [Agent Fleet #406](https://github.com/oncoursemail/Star-AI/issues/406), [Free API #407](https://github.com/oncoursemail/Star-AI/issues/407), [Evidence Broker #401](https://github.com/oncoursemail/Star-AI/pull/401), [Durable Missions #402](https://github.com/oncoursemail/Star-AI/pull/402)

Official provider and protocol sources:
- Anthropic [Claude Code Pro/Max](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan) and [Agent SDK subscription update](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
- OpenAI [Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform), [SIWC open-source guide](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt), [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server), [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- xAI [2026 X Subscription](https://x.ai/news/x-subscription), [consumer/API billing separation](https://docs.x.ai/developers/faq/accounts), [API authentication](https://docs.x.ai/developers/rest-api-reference/inference)
- [ACP / Zed adapters](https://zed.dev/docs/ai/external-agents); [2026 MCP specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/); [A2A spec](https://a2a-protocol.org/latest/specification/); [Copilot SDK](https://github.com/github/copilot-sdk); [OpenCode](https://dev.opencode.ai/docs/providers)
- [LangGraph state/interrupts](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph); [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk); [Microsoft Conductor](https://github.com/microsoft/conductor)
- [RouteLLM](https://github.com/lm-sys/RouteLLM); [DSPy optimizers](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md); [Reflexion](https://arxiv.org/abs/2303.11366); [OpenTelemetry GenAI metrics](https://opentelemetry.io/docs/specs/semconv/); [SWE-bench Verified contamination warning](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)

**Research limitations:** This review read existing GitHub source/PRs and official online documentation. It did not execute Rilo or STAR on the owner's Windows machines, connect paid accounts, verify live model IDs/entitlements, run real Studio playtests, or benchmark the proposed conductor. The proposal must earn performance claims through the above gates.
