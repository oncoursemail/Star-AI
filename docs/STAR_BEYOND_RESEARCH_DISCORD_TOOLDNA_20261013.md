# STAR Beyond: Self-improving intelligence, ToolDNA, compute and Discord

**Research checkpoint:** 2026-10-13. **Status:** engineering proposal, not released capability. This extends the baseline roadmap in docs/STAR_INTELLIGENCE_ACCELERATOR_20261013.md. No new paid API, weight training, hidden system privilege, Discord publication, or automatic self-update is authorized by this document.

## What the STAR repository already provides

- The current star/next tree has local llama.cpp and authenticated LAN inference, and explicit Groq, OpenRouter, Gemini and Cerebras providers. Brave/Tavily research credentials exist. Recent draft #265 adds time, SearXNG and web fetching, and #267 connects real-time web context to Discord.
- Star has a project-scoped read-only ToolWorkshop (star/tool_workshop.py): propose, preview, list and run human-approved recipes from five existing sources. It does **not** synthesize arbitrary executable plugins or automatically change permissions.
- Discord code in star/discord_bot/ supports the owner-only DM channel, opt-in image vision, slash ask/research/status/help, privacy/permission checks, one-shot speech, verified Night School reports and reviewable correction candidates. PRs #226 (DM, images, learning), #264 (quick-model chat routing/streaming) and #267 (Discord clock/citations) are merged into star/next.
- PR #264 observed a 43-73 second owner Discord-chat delay previously dominated by inference-slot queueing. This is evidence to prioritize foreground resource admission over ever more model processes.
- In-progress #266 resource planner, #268 native Studio Lab, #270 Best-of-N coding, #271 creator inspection, #274 KV caching, #275 verified training/self-play, and #278 baseline roadmap must be verified/integrated before overlapping replacement implementations.
- The current Discord gateway source contains no active rotating presence or scheduled public MOTD feature at this checkpoint. A prior research document's future calendar labels are **not evidence that those features were deployed**.

## 1. How STAR can become measurably more intelligent

### PlanGraph: persistent plans with proofs

Represent the user's goal as a project-scoped directed acyclic graph: constraints, tasks, dependencies, authorized tools, expected outputs, native engine tests, result hashes and owner feedback. Plans are durable across sessions but don't invent completed tasks after a crash. A small model decomposes; a stronger reviewer flags missing dependencies; the resource planner admits ready tasks; every node advances only when its explicit proof exists. Replan on genuine errors or changed user constraints.

### MemoryTruth: correct and auditable long-term recall

Preserve existing source-digest conversation retention. Extract four kinds of memory: working context, episodic attempt history, semantic preferences/facts, and reviewed procedural skills. Each durable fact records source line/message ID, project, timestamp, unverified-vs-verified status, conflicting correction, and deletion/expiry. Use hybrid lexical exact retrieval and embeddings instead of reloading everything. A user correction can supersede a preference, but the original evidence remains reviewable under the user's retention settings. Never mix private projects or hallucinate a passed test from a failed chat turn. Test with long-range references, negative aesthetic constraints, pronouns, contradictions, deletion and poisoned quoted notes.

### Free-model intelligence market

Route between models only after a project-privacy gate. Compare live quota, vision/code/tool ability, model revision, rate-limit headers, p95 queue time, valid task completion and estimated full-work cost. Reserve the fastest local slot for chat; use larger reasoning models only when complexity justifies them. Re-test policies on held-out tasks, including counterfactual replay of different model/tool choices using approved, nonsecret fixture prompts.

As of research date, published official terms include OpenRouter Free 25+ free models and 50 requests/day; Groq organization- and model-specific RPM/RPD/token limits and Retry-After; Cloudflare Workers AI 10,000 free neurons/day (selected models require paid billing); Hugging Face Inference Providers $0.10 monthly free credits; Brave Search API $5 free monthly credits at $5/1000 search requests. Google Gemini free tiers vary and can use free-tier data to improve products. No vendor is unlimited. Account-specific limits take precedence; 429 should fall back to owner-approved local inference without automatically paying or rotating identities to evade limits.

Official references:
- https://openrouter.ai/pricing
- https://console.groq.com/docs/rate-limits
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://huggingface.co/docs/inference-providers/pricing
- https://brave.com/search/api/
- https://ai.google.dev/gemini-api/docs/pricing

### Verified self-learning: Experiment Ledger

Record a structured, immutable evidence chain: task -> code/model/tool versions -> input and source rights -> proposed hypothesis -> build artifacts -> static checks -> test runs -> native Studio/engine screenshot evidence -> owner acceptance -> learning candidate. The model cannot mark its own answer "passed." Keep training, validation and sealed holdouts disjoint by game/project/problem family and have a separate evaluator/permission process that the model cannot modify.

Prioritize improvements through instructions and skills first (GEPA, DSPy MIPROv2, GEPA), and separately prototype small LoRA adapters only from rights-verified reviewed datasets when GPU capacity and heldout evidence justify it. Count actual task success, not generated examples. Run self-play only in owner-approved sandbox Studio places; distinguish simulated checks and actual playtests. Train on confirmed corrections, not recursively generated guesses.

Research:
- https://arxiv.org/abs/2507.19457
- https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md
- https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- https://deepmind.google/blog/alphaevolve-impact/

## 2. ToolDNA: the next generation of self-created tools

STAR already proposes composition of read-only tools. Extend it with clear permission tiers, not an unrestricted tool-writing agent.

- **Tier 0, existing:** human-approved read-only source recipes.
- **Tier 1, proposed:** generate a *pure transform* tool using a limited declarative DSL or audited WASM module with typed JSON in/out, fixed CPU/memory/timeout/output budgets and **no network, filesystem, credentials, environment or subprocesses**. Examples: Luau API signatures checker, mesh triangle estimator, Roblox remote event payload critic, animation foot-lock validator, Discord report formatter, documentation freshness diff.
- **Tier 2, proposed:** if a tool needs a real filesystem/Blender/Studio/GitHub action, create a draft pull request with a manifest, restricted permission set, implementation, tests, input fuzzing, dependency pins and source-license evidence. Run isolated tests with fake credentials before independent code/security review. Only an operator may promote signed reviewed tools. Even after promotion, host-side permission checks control each action.
- **Never:** let an AI rewrite its own evaluator, billing guard, capability approvals, passwords, test oracle or deployed binary automatically.

**Tool creation lifecycle:** identify missing capability -> search existing tools and active PRs -> specify typed input/output + permissions -> propose several variants -> static policy scan -> test in sealed runner -> benchmark against baseline -> record artifacts and failed counterexamples -> draft PR -> owner approval -> canary, shadow metric and rollback. A model cannot expand an allowlist by adding a new string in its own code and claiming approval.

MCP tool descriptions and server replies must be treated as untrusted. Pin tool schemas, verify changes, bind OAuth tokens to audience, and do not pass upstream secrets through arbitrary MCP proxies. More MCP servers increase attack surface and context overhead.

Official security:
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/security-considerations.mdx
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/tutorials/security/local-server-security.mdx

**Acceptance:** a tool is useful only if it passes previously impossible, independently verified tasks at acceptable resource cost with zero policy escapes or leakage. Number of generated tools is not a goal.

## 3. RAMForge 2.0: use CPU/RAM wisely

Previous owner hardware reports and a current remote snapshot place Brain1 near 128 GiB RAM and Brain2 near 15 GiB; the Windows GPU was previously reported as RTX 3060Ti 8 GiB. Re-probe OS versions, installed runtime, CPU, GPU, NUMA topology, RAM/VRAM, current loads and inference backend before tuning. Do not claim one 30B model becomes fast just because RAM can hold it.

**Four different bottlenecks:** time-to-first-token; decode tokens/sec; model slot queue delay; first *correct* completed user task. Cache reuse helps prompt prefill but does not inherently accelerate decode. More threads or resident model copies can make CPU inference slower due to RAM bandwidth/NUMA contention. Tiny GPU VRAM cannot host a large coding model, text-to-3D and training concurrently.

Experiments, in order:
1. Integrate and test #266: spare fast chat slot, background Night School yield/preemption, native Studio memory reserve; stale telemetry forces safe fallback.
2. Record before/after p50 and p95 chat/model latency, separate queue/prefill/decode, response quality, time to correct patch, power/CPU/RAM, model revision, context and quantization.
3. Stable model prompt/template and permission-scoped knowledge prefixes; content-hash cache invalidation; #274's optional KV checkpoints require exclusive slot ownership.
4. Experiment with llama.cpp n-gram and small-model speculative decoding, acceptance rates, quantization, context, flash attention, batch size, threading/NUMA affinity; one A/B change at a time. https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
5. Content-addressed retrieval index, hot memory cache for approved docs, cold SSD for huge datasets; do not flood model context with all stored docs.
6. Test dedicated low-cost classifiers/embedding workers on spare Brain2 cycles only if Studio jobs have priority.
7. Run Blender renders and optional weight tuning under explicit GPU/CPU leases, never concurrently with games at the owner's expense. LMCache CPU offload may matter for a suitable vLLM GPU backend but shouldn't be imported blindly into CPU-only llama.cpp. https://docs.lmcache.ai/kv_cache/cpu_ram.html

Benchmark each on paired real Roblox/Discord prompts, idle/busy, cold/warm, multiple concurrency levels and tool-outage cases. Revert on any quality, security or p95 latency regression.

## 4. Discord: an actual STAR command center

This section incorporates prior user-approved direction: Star mascot across bot avatar/embeds and website, appealing but restrained dark design, clear icons and spacing; actual Playing/Watching/Listening bot-account activity and message-of-the-day; multimodal owner DMs and evidence-linked learning. Do not replace existing access restrictions or claim text/status is the same as a native Rich Presence application.

### Presence vs profile vs MOTD

**Bot account profile:** avatar, description/bio and approved app identity set through the Developer Portal. **Presence:** runtime Gateway activity on the bot account, online only while connected. **MOTD:** a scheduled post in a selected channel, not a profile message.

For presence, support a safe opt-in list whose text does not falsely claim it is currently training: "Watching /star help", "Playing STAR Intelligence", "Watching for /ask". Use discord.py constructor activity for initial presence. Avoid changing presence in on_ready, which can run repeatedly on reconnect. Rotate slowly (e.g. 15 minutes), only when online/ready, and recover from HTTP rate limits. Never include user names, private projects, secret counts or model-written uncontrolled text.
Official discord.py FAQ: https://discordpy.readthedocs.io/en/stable/faq.html

For MOTD, require explicit guild/channel, local timezone and opt-in, send at most once per approved channel and local date. Persist a SQLite ledger with (guild,channel,date,template revision) and pending/sent/unknown state. A lost acknowledgement must not trigger blind duplicates; reconnection should check receipts. Draft content from reviewed Roblox tip, verified source update or real nightly test result, and label the evidence level. Keep quiet hours and a preview/pause command. No everyone/here pings, private screenshot broadcasting, unsolicited DMs or auto-guild-wide distribution.

### Discord Components V2 experience

Use discord.py 2.6+ LayoutView, Container, Section, TextDisplay, MediaGallery, buttons, select menus and modals to build a clean interactive help/control center. A Components V2 message uses the IS_COMPONENTS_V2 flag and cannot be combined with legacy message embed/content on the same message; preserve a classic embed fallback. Present a consistent mascot thumbnail/branding and actual enabled commands, not an imaginary catalogue. Categories: Chat; Research; Roblox; Game Assets/VFX; Brain Health; Training Results; Help and Permissions.

Buttons must reauthorize the owner on **each click**, validate nonce and expiration, and return private results for private topics. Any remote operation is a separately approved typed job; a Discord DM cannot run host shell, GitHub or Studio because text says "I approve".

Official component reference: https://docs.discord.com/developers/components/reference
discord.py docs: https://discordpy.readthedocs.io/en/stable/interactions/api.html

### Evidence cards, voice, proactive updates and reliability

A STAR research card should display short answer, source URLs, retrieval freshness, model route and limitations. A Learning card distinguishes unit test vs simulated Luau vs native Studio result vs actual gradient training. A Creation card links owner-approved Blender/Studio screenshots and export provenance, not just "asset generated".

Slash interactions must defer within **3 seconds**; interaction tokens remain valid **15 minutes**. For lengthy builds/training use a durable job ID, an owner-accessible status command and a separate consented completion message path rather than trying to edit a stale interaction token. Honor Discord Retry-After headers and bot/Gateway rules. DAVE/voice-receive dependencies must be verified before promising always-on conversational voice; default is explicit recordings/one-off transcriptions, no silent ambient recording.

Official timing: https://docs.discord.com/developers/interactions/receiving-and-responding
Official rate limits: https://docs.discord.com/developers/topics/rate-limits

The existing owner-only access model and disabled guild MESSAGE_CONTENT/MEMBERS/PRESENCES intents remain unchanged. No self-bots and no public automation of users' accounts. Track p95 defer/first-text/model-queue durations, 429s, duplicate scheduled messages, user-visible errors and corrections without logging message bodies or credentials. A future OAuth website can expose an authorized, read-only dashboard but is a separate project and threat surface.

## 5. Original hypotheses to test, not "proven breakthroughs"

**H1: Proof-linked memory promotion.** A fact "STAR fixed collision" cannot become verified until a specific code hash, test run, native result and owner review exist. Maintain attempted and successful history separately; reduces confident fabricated memories.

**H2: Counterfactual route ledger.** Re-execute failed approved test prompts on alternative free/local models overnight to estimate which model *would* have done better, subject to resource and cost ceilings. Update route policy only after independent holdout gain.

**H3: Tool-DNA composition evolution.** Evolve graphs of typed, human-approved pure tools; test subgraphs and reuse successful modules instead of writing unbounded plugins. Tool permissions never evolve automatically.

**H4: Multi-fidelity creator critic.** Cheap static asset/rig/VFX checks -> headless Blender preview -> full Studio/Godot/Unity import/gameplay test -> human art review. Reject bad candidates early to save CPU/GPU; cheap passes aren't proof of good animation/art.

**H5: Failure fingerprint school.** Every independently confirmed Luau/network/rig/UI bug becomes a rights-cleared task family with new examples and frozen external tests. Detect duplicates and leakage across project families before training or practice.

**H6: Hardware admission twin.** A calibrated simulator predicts each job's RAM/CPU/VRAM/slot/latency cost from real metrics and recommends queue placement. Predictions may not override actual runtime safety budgets.

**H7: Research novelty radar.** Read new papers/docs, find an actionable hypothesis, search STAR's own issues/PRs/code to avoid duplicate effort, and provide a falsifiable experiment rather than an invented "breakthrough".

**H8: Nightly evolutionary optimization tournament.** Use spare resources after live chat constraints to propose algorithm tweaks, evaluate independently and open draft PRs with paired benchmark tables. No changes are auto-deployed and every candidate has a rollback flag.

## 6. Phased delivery and quality gates

**First:** frozen baseline and CI review of active #266/#268/#270/#274/#275 and source-only bot tests. Avoid duplicate overlapping PRs.

**Next quick wins:** one opt-in, independently tested rotating bot presence; separately consented/deduplicated MOTD; Components V2 help preview with fallback. Live Discord smoke only using the owner's local bot token and explicit chosen server.

**Then:** measured multi-provider failover and account-specific free quotas, provenance memory and plan graph; build Tier 1 ToolDNA declarative pure tools with hard no-network/no-disk tests.

**Then:** native Roblox/Blender/Godot/Unity creation validation and evidence cards; optimization tournament behind resource leases; carefully reviewed training pilots. Publish verified success comparisons, not subjective "smarter" scores.

**Acceptance examples (targets, not observed claims):** 30% lower p95 owner-chat first text under fixed load, no cloud call after denied privacy/budget checks, no Discord unsolicited posting, zero cross-project memory leakage on heldout tests, 100% tool promotion requires independent tests and human approval, improved Studio-accepted Roblox features/hour with no >5% p95 live-chat regression.

**Absolute constraints:** no uncontrolled self-modifying executable; no auto-enabling privileged API tools; no editing the scoring oracle; no provider charge without owner consent; no automatic local secrets sent to free model APIs; no training on unlicensed or private Discord content; no claim of native engine correctness without engine-native evidence.
