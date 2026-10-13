# STAR Tool Intelligence Scout — October 13, 2026

**Scope:** source-backed engineering research and a candidate-only research watcher expansion. No model is retrained, no new binary is downloaded, no arbitrary MCP connection is opened, and no code/tool permission is enabled by a documentation update.

## Finding: optimize STAR's real Roblox engineering loop, not its marketing claims

On the current \`star/next\` integration branch, STAR already has a local model/tool loop (\`star/agent.py\`), scoped Studio connection, lesson review (\`star/lessons.py\`), independent evaluation gate (\`star/eval_gate.py\`), measured comparison protocol (\`star/frontier_lab.py\`), and research ledger (\`star/evolution_research.py\`). The greatest near-term opportunity is to connect deterministic evidence to improvement proposals. Candidate notes, prompt changes, downloaded tools, model weights, and accepted capabilities are **different trust classes**.

The eight upstream sources added in this PR are **public official documentation**. We deliberately do not auto-install software or reuse arbitrary content from documentation as instructions. Each adoption decision must separately prove relevance, licensing, system compatibility, permission scope, and an advantage on STAR's own tasks.

## Prioritized tools and reproducible trials

| Target | Published capability (source) | Hypothesis for STAR | First measured experiment | Current decision |
|---|---|---|---|---|
| [MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) | Stateless core; per-request capabilities; optional Tasks, Skills over MCP, MCP Apps | Better discovery and lower integration friction | Run protocol-version, header, cancellation, timeout and malicious-result contract fixtures against STAR's existing bridge | **Research only**; no dynamic server registrations |
| [DSPy optimizers](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md) | Metric-driven prompt and pipeline optimization | Tune tool-choice prompts and skill routing from *development* cases without tuning on holdouts | Freeze 30-50 Roblox prompts; compare paired success/cost/latency and unseen holdouts vs unchanged baseline | **Top future experiment**; do not replace evaluation gate |
| [OpenHands Agent SDK](https://github.com/OpenHands/software-agent-sdk) | Composable coding agent, edit tools and optional disposable workspaces | Faster reproducible coding repairs on scripts; strong separation of execution environments | Compare one scoped repair-task replay: existing STAR vs SDK on the same fixtures, latency, diff size, and security violations | **Adapter evaluation** only, no shell privilege escalation |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | Agents/tools, handoffs, tracing, MCP filtering, guardrails | Structured traces and selective tool discovery | Build a trace-only adapter with sanitized event snapshots; measure overhead and token savings, including local-provider compatibility | **Compare**, don't replace local-first runtime blindly |
| [Agent Lightning v1](https://github.com/microsoft/agent-lightning) | Training from agent rollouts through a gateway and RL trainer | Eventually improve specialized model policies from verified outcome rewards | Before GPU training, simulate reward extraction from existing Studio test reports; reject missing evidence and reward-hacking cases | **Long-term**; reference setup uses CUDA/verl/vLLM/WSL or GPU clusters |
| [LangGraph persistence](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx) | Checkpoints plus durable stores; interrupt/resume execution | Eliminate duplicate side effects when STAR restarts during coding tasks | Injection-test cancelled/stale tasks, at-most-once writes and idempotency IDs; compare against STAR's existing journaling | **Compare** before migration |
| [Rojo 7](https://rojo.space/docs/v7/) | Filesystem-first Roblox source synchronization | Faster reviewable Studio-to-file workflows for Luau builds | Pin Rojo/Rokit; test a disposable test place only; verify script lineage, conflicts and round-trip parity | **High-value Roblox pilot**, permission-controlled |
| [StyLua](https://github.com/JohnnyMorganz/StyLua) | Deterministic Lua/Luau formatting; v2.6.0 released October 10, 2026 | Cleaner generated Luau and smaller diffs | Run pinned StyLua on Luau corpus, including the new \`if local\`/ \`if const\` syntax, then parse, format twice and compare output | **Continue existing opt-in #188**, do not duplicate |

Primary sources: [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28), [DSPy optimization](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md), [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk), [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/), [Agent Lightning](https://github.com/microsoft/agent-lightning), [LangGraph persistence](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx), [Rojo](https://rojo.space/docs/v7/), and [StyLua release](https://github.com/JohnnyMorganz/StyLua/releases/tag/v2.6.0). Vendor claims are not STAR benchmark results.

## Actual code shipped by this PR

1. The **fixed trusted URL catalog** grows from 5 documents to 13 (8 high-value tools above). Stable, first-party/project-owned documentation is preferred to arbitrary community posts and dynamic search results. URLs are compiled into reviewed Python; the model cannot select a new destination.
2. **Fair oldest-first scheduling:** background research (off by default) checks at most five due sources, each at most once in 24 hours. First-time sources precede previously checked ones. Failed requests receive a timestamp too; no hammering on an outage. Repeated manual checks rotate through the catalog without starving the new tools.
3. **Fail-closed retrieval remains:** HTTPS fixed URLs, no redirects, no proxy or credentials, 1 MB response limit, checked media types, URL equality, sequential network requests, and bounded plain-text candidate evidence. HTTP validators reduce unchanged downloads.
4. **No automatic learning or installation:** every observation is untrusted. Nomination only creates a reviewable candidate in the existing local Learning UI; human approval is required, and documentation cannot change settings, enable tools, execute code, or publish a release.
5. **Desktop UI** explains the bounded batch behavior instead of suggesting that one button fetches every source at once.

### What this does NOT establish

These are documentation-watch capabilities, not proof that adding a framework will improve STAR's answer quality. Running this PR in CI validates scheduling and safety with mocked HTTP only. It does not prove the upstream live docs are reachable from the owner's PC, nor that local GPU training is practical. Existing evaluation baselines and holdout files remain unchanged.

## Proposed experimental scorecard (follow-on PRs)

Use the same task prompts, Luau versions, Studio place snapshot, hardware budget, and test runner for each candidate. Record: (a) accepted Roblox features per task, (b) Luau errors and broken test assertions, (c) unintended file/place mutations, (d) time-to-first-token and end-to-end latency, (e) model tokens or local compute, (f) use of unapproved tools, and (g) regressions on protected holdouts. A proposal needs independent reviewer approval and a non-regression gate; if it loses on key measures, keep the baseline.

**Priority order:** first native Luau analyzer + opt-in StyLua + disposable Studio test execution; then DSPy prompt/skill experiments using real reward metrics; then tracing/checkpoint comparison with Agents SDK/LangGraph/OpenHands; finally consider costly RL training on compatible separate compute only if curated evaluation data justify it.

## Check plan

- \`tests/test_evolution_research.py\`: check a full 13-source cycle through three five-item batches, every source visited once; no request above the bound; repeated manual checks rotate.
- Simulate HTTP 503 for every source: no rapid retry and no trust promotion; due slots are re-eligible after a day.
- Malformed historical timestamps recover; source URLs are approved HTTPS hosts and do not carry credentials.
- Existing screenshot/UI and learning review tests remain unmodified.

**Source freshness:** October 13, 2026. Some upstream vendors report benchmark gains on non-Roblox tasks; STAR has not reproduced those claims.
