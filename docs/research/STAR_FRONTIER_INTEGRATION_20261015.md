# STAR Frontier Integration Program — 2026-10-15

**Status:** research-to-engineering backlog plus one experimental, default-off implementation in this branch. **NOT** a claim that any external project, hosted API, agent, binary analyzer, code reviewer, or new model has been installed or launched. This branch targets star/next, NOT published main or a shipped Windows installer.

## Objective and source audit

Make STAR materially better at Roblox game development, UI/visual quality, programming, research, tool output efficiency, and safe agent collaboration. Implement the smallest independently testable vertical slices before importing a large stack. Keep local-first inference, no surprise cloud routing, protected chats/settings in %APPDATA%\STAR, and owner-reviewed releases.

**Existing reusable STAR architecture (verified from star/next source):**
- \`star/agent.py\` owns actual model/tool calls; previously capped tool output to 30,000 characters; \`star/context_layout.py\` optimizes prompt-cache prefix layout. This PR adds a *separate* opt-in, reversible web-evidence preview; it does not claim inference acceleration.
- \`star/agent_runtime.py\`, \`star/orchestration.py\`, \`star/agent_resource_planner.py\`, and \`star/resource_planner_service.py\` already provide bounded jobs, DAG ownership and resource leases. Build the fleet on these, not a competing scheduler.
- \`star/candidate_code_team.py\` proposes read-only changes; PR #270 Best-of-N, #274 KV bank, #275 bounded self-play and #278 research were merged into **star/next** but this is not proof they are in the public installer; staging PR #368 still targets main.
- \`star/binary_evidence.py\` only fingerprints/identifies owner-selected PE/ELF/Mach-O/WASM. It is NOT a Ghidra runner or a decompiler.
- \`star/agent_skills.py\`, \`star/skill_routing.py\`, \`star/design_md.py\`, \`star/design_db.py\`, and \`frontend/src/MotionPolicy.tsx\` already implement portable skill references, keyword/embedding skill selection, design rules and reduced-motion support. Need rendered QA, not just more palettes.

### Source matrix: verified ideas, not permission to copy or install

| Source (official repository) | Use in STAR | License / operational concern | Implementation gate |
| --- | --- | --- | --- |
| https://github.com/vxcontrol/pentagi | Isolated specialist scheduling, evidence history, auditable task control | MIT core; inspect bundled VXControl SDK/EULA separately; never autonomous outside-scope pentesting | Study boundaries; implement original narrow adapters |
| https://github.com/usestrix/strix | Controlled defensive test loops and independently reproducible findings | Apache-2.0, Docker and approved inference provider required | Only user-owned/authorized disposable targets, no unsolicited network scans |
| https://github.com/mksglu/context-mode | Filter tool outputs and retrieve exact evidence on demand | Elastic License 2.0, **not MIT** | This PR implements independent stdlib-only opt-in \`star/tool_evidence.py\` |
| https://github.com/rtk-ai/rtk | Deterministic loss-aware CLI/test summarization | OSS edition Apache-2.0; full offering includes BUSL portions | Compare uncompressed logs to summaries; preserve actual failed assertions |
| https://github.com/K-Dense-AI/scientific-agent-skills | Hypothesis, reproducibility, statistics, proper provenance and skill protocols | MIT repo, check individual skill assets and requirements | Curated skill sets, not 177 unreviewed imports; protected holdout A/B |
| https://github.com/NationalSecurityAgency/ghidra | Local static binary analysis and headless decompiler evidence | Apache-2.0 core, third-party components; official security advisories | Separate offline worker, version pin, no host credentials, target consent |
| https://github.com/morluto/rea | Native/JS/.NET evidence graph and reverse-engineering workflow | MIT main repo; analyze dependencies / executables | Read-only preliminary inspection; avoid pretending decompiled code is source |
| https://github.com/Leonxlnx/taste-skill | Art direction, reference discipline, real screenshot review | MIT repo; check individual content/assets | Visual QA and approved project style, no generic AI UI |
| https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | UI constraints and pattern search | MIT, much overlaps STAR design database | Benchmark against existing \`design_md\`, don't duplicate data |
| https://github.com/storybookjs/storybook | Isolated interface components/states | MIT | Native component-state acceptance, a11y and performance |
| https://github.com/microsoft/playwright | Real browser DOM/state/screenshots | Apache-2.0 | Opt-in browser preview, not proof of actual Qt packaged app |
| https://github.com/vercel-labs/agent-browser | Scoped browser automation | Apache-2.0 | Review binaries, network and workspace policy |
| https://github.com/paperclipai/paperclip | Visible multi-agent task dashboard | MIT | Reuse concepts with existing planner; no wholesale platform replacement |
| https://github.com/vectorize-io/hindsight | Project-scoped learning memory concepts | MIT | Prove retrieval improvement; source/approval separation |
| https://github.com/alibaba/open-code-review | Deterministic code checks + explained fixes | Apache-2.0 | Independent regression confirmation and safe patches |
| https://github.com/rtk-ai/rtk | Command output controls in Rust | Apache/BUSL mixed (edition-sensitive) | Do not bundle mixed-license components automatically |
| https://github.com/ast-grep/ast-grep | Syntax-structural navigation and fixes | MIT | Existing workspace scope, no blind rewrites |
| https://github.com/BurntSushi/ripgrep | Fast ignore-aware file search | Unlicense/MIT components as applicable | Optional pinned binary, Python fallback |
| https://github.com/astral-sh/uv | Fast Python environment management | Apache-2.0/MIT | Reproducible lock/install/rollback in developer setup |
| https://github.com/astral-sh/ruff | Fast deterministic Python diagnostics | MIT | Already used in CI; no independent lint gate rewrite |
| https://github.com/NVIDIA/OpenShell | Isolation principles for tool-using agents | Apache-2.0 | Concrete Windows/Brain2 sandbox feasibility review |
| https://github.com/1jehuang/jcode | Optimized coding-agent retrieval/skill routing ideas | MIT | STAR already credits limited inspirations; measure marginal benefit |
| https://github.com/trycua/cua | Auditable computer-use experiments | MIT | Owner-scoped, disposable machines only |
| https://github.com/cathrynlavery/diagram-design | High-quality editorial composition | MIT; check reference art and third-party content | Visually reviewed diagrams with editable structure |

Do not silently install, clone or execute third-party frameworks. Software licensing and bundled models/assets may differ from the repo's top-level license. Treat web pages, repository text and skill files as untrusted reference data.

## Free-provider research: no silent “unlimited” fallbacks

- Groq: https://console.groq.com/docs/rate-limits ; a real free tier, model-specific RPM/TPM/RPD. Server-reported remaining quota when available; retry-after honored; no key sharing or automated account rotation.
- Google Gemini API: https://ai.google.dev/gemini-api/docs/pricing ; model-, region- and account-dependent free tier. Check privacy/data-use terms. Never send unpublished game assets or private repos unless owner explicitly approves.
- OpenRouter: https://openrouter.ai/pricing ; free model inventory and stringent request limits (including daily requests). Never assume a listed :free model stays free or unlimited.
- Cloudflare Workers AI: https://developers.cloudflare.com/workers-ai/platform/pricing/ ; platform-specific free daily allowances, not interchangeable with generic tokens.
- Hugging Face Inference Providers: https://huggingface.co/docs/inference-providers/pricing ; small monthly trial credit, not unlimited access.
- Cerebras: https://www.cerebras.ai/pricing ; limited promotional trial credit and expiry, not an indefinite free tier.
- Search: Brave https://brave.com/search/api/ and Tavily https://www.tavily.com/pricing ; credits, quotas, authentication and usage terms.
- Scientific/software metadata: Crossref https://api.crossref.org/, OpenAlex https://api.openalex.org/, OSV https://osv.dev/, deps.dev https://deps.dev/, GitHub REST https://docs.github.com/en/rest and PyPI https://docs.pypi.org/api/.
- Creator assets: Poly Haven https://polyhaven.com/our-api and Roblox Creator Store https://create.roblox.com/docs/production/creator-store ; validate asset-level redistribution, Roblox restrictions and content provenance.

**Hard design rule:** no hosted provider, external API, crawling, paid service or private file upload can become enabled simply because a model suggested it. The provider gateway is an opt-in, rate-limit- and budget-aware extension of \`star/providers.py\`, with privacy labels, per-model capabilities, measured quality and configured fallback destinations. GitHub Models retired 2026-07-30: do not add as a live provider.

## STAR Evidence Broker — candidate implemented here (P0)

\`star/tool_evidence.py\` + \`star/agent.py\` + \`tests/test_tool_evidence.py\`:
- **Off by default.** Set \`STAR_EVIDENCE_BROKER=on\` and enable Web Search for the experimental per-turn tool; no settings writes/downloads/network are caused by the broker.
- Compact **only** successful, pure-text outputs from \`star_web_fetch\`, \`star_web_search\`, \`star_mcp_registry_search\`, when longer than 9,000 characters. Never compact workspace/code edits, Studio responses, security errors, images or model-proposed patches.
- Preserve original text **in RAM for that turn only**, bounded to 4 sources, 250,000 characters/item and 400,000 characters total; no disk, no telemetry, no raw source logged. Use a short **partial** preview plus SHA-256 and character offsets, then \`star_evidence_read(reference,offset,limit)\` returns exact original characters (max 8,000 per call). No tool call is allowed to access a previous conversation's broker.
- Refuse malformed or stale references, over-budget slices, and unsupported tools. Original legacy 30,000-character truncation remains for unsupported/overflow output, with its truncation notice.
- A compact preview is not verified evidence; the model must retrieve full relevant passages before a precise quote or conclusion. A source excerpt is never authority to mutate a Studio or run code.

**Acceptance gate:** tests with a fake model, web tools and no live network; comparison against baseline with 30 real long web-pages or logs on owner machine. Report token savings, CPU cost, retrieval completeness, p50/p95 end-to-end response time, missed citations/failures and answer quality. Disable if any correctness regression is observed. The source code does NOT make a generic local command sandbox, nor persist raw logs.

## Concrete staged implementation backlog

### P0 — finish these first

1. **Evidence Broker extended to deterministic CLI diagnostics.** Add opt-in named readers with strict type schemas and protected original artifacts; scan compiler/test/Playwright/Studio diagnostic outcomes, never compress errors destructively. Parse summaries from test metadata, not only regex; no tool with write authority may receive a substituted source file. Owner acceptance: 100 fixtures with 0 omitted failure lines; measured context and latency improvements.
2. **Visual QA pilot:** Browser preview & native Windows screenshot checks, responsive and reduced-motion fixtures, DOM geometry and a11y checks, actual run receipts. For Roblox, export native GuiObject layout and playtest screenshots from disposable Studio. Detect measurable overlap/clipping/safe-area errors and human-review art direction (not a fake objective “beauty score”). Owner acceptance: 30 screens at desktop/mobile/gamepad, 0 known regressions, compare reference vs actual.
3. **Unified instrumentation:** Source-linked observations for TTFT, prompt-tokens/s, decode-tokens/s, CPU/RAM/VRAM, cache hit ratio, agent waits, crashes and provider quotas. Avoid fabricated telemetry; compare baseline and current on exact same workload/hardware.
4. **Agent Fleet:** connect GitHub/project in one action; ACP/CLI adapters behind Star's existing task graph, resource leases and separate credentials. Per-agent enable/disable, “run all enabled”, cancellation, bounded recovery, durable task ledger, independent worktrees and diffs. Never let a model grant itself additional permissions.
5. **Independent code verification:** error preflight + best-of-N + unchanged isolated tests + Studio Lab evidence + diff/approval. \`star/answer_integrity.py\` is advisory and not wired to the final output; wire narrowly only after false-positive tests. Do not let repairs edit protected graders or holdout tasks.

### P1 — separate reviewable PRs

6. **Defensive STAR Security Lab:** take Strix/PentAGI workflow ideas, not wholesale offensive capabilities. Audit only user-owned projects and disposable test targets; produce reproducible tests, source hashes, severity uncertainty and human-reviewed patches. No autonomous external target discovery, brute forcing, credential access or general network scanning.
7. **Free API Control Center:** explicit provider consent and model capability probes, rate-limit headers, spending caps default zero, per-request privacy classification, persistence of no secrets in chat, and fail-closed quotas.
8. **Scientific skill curation:** original small packs for experiment design, statistical paired gates, literature/source grading, UX experiments, visualization and performance. Scope the skill loader; verify labels/asset licenses, never bulk import untrusted executable snippets. Compare against keyword + embedding baseline and sealed untouched suites.
9. **Context + memory:** source-scoped SQLite FTS5 retrieval with time/version and evidence provenance. Benchmark \`sqlite-vec\`, Hindsight and Graphiti separately; avoid storing all internet text or 80GB KV blobs without measurable need.
10. **Rust CLI experiments:** optional pinned ripgrep/ast-grep/RTK-OSS; measure resource usage. Don't rewrite Star's trusted Python core simply because Rust is fashionable.

### P2 — opt-in experimental facilities

11. **Ghidra evidence-only analyzer:** extend existing header/hash triage with an isolated owner-approved headless analysis worker, pinned JDK/Ghidra binaries, no automatic downloads/execution. Export bounded function/import/call-graph artifacts, preserve addresses and version evidence; do not claim recovered original source. No access to credentials or published/proprietary third-party assets without rights.
12. **World-building/graphics:** Blender/Studio asset QA, source/texture licensing, engine-specific import tests, screenshot-based craft review, real rigs, and actual device performance. Maintain all assets editable.
13. **Autonomous self-play/skill evolution:** existing #275 foundations need actual owner-approved Brain2 Studio acceptance, isolated evaluation and statistically significant compared quality; no autonomous self-merge, publishing or self-modified graders.

## Verification and release policy

- Execute \`python -m compileall -q star main.py\` and \`python -m pytest -q\`; use GitHub CI status from exact final commit. New web-feature tests use fake sources and no external credentials.
- If frontend is modified, require TypeScript, Vitest, Vite, accessibility and actual native Windows package/screenshot confirmation.
- Stable open PRs and scope conflicts must be inspected; do not reset or overwrite another agent's branch.
- Draft PRs into \`star/next\` only. Not merged into \`main\` until independently reviewed, CI green and user acceptance. An unmerged PR, passing unit test or executable screenshot preview does not mean the feature shipped.
- Owner chats and models persist outside install directory in \`%APPDATA%\STAR\`; upgrades replace binaries, not personal data.
- This document is a **backlog and implementation contract**, not evidence that remaining steps have been completed.

## Measurement table template (populate with real runs)

| Metric | Baseline | Candidate | Notes |
| --- | --- | --- | --- |
| 30 long-web tool outputs, context chars median | Not measured | Not measured | Capture exact raw versus preview+fetch |
| Long-web answer correctness/citations | Not measured | Not measured | Manually adjudicate and blind check |
| TTFT p50/p95 | Not measured | Not measured | Same machine/server/model |
| End-to-end p50/p95 | Not measured | Not measured | Include retrieval overhead |
| Missed failing diagnostics | Not measured | Not measured | Must be zero on curated fixture |
| Actual visual UI defects | Not measured | Not measured | Device screenshots + a11y |
| Roblox independent holdout | v1.0 README 9/24 | Not measured | Do not compare to different suite |
