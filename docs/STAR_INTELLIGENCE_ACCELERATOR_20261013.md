# STAR Intelligence Accelerator: verified research and implementation program

**Research checkpoint:** October 13, 2026. **Target:** develop from current star/next. **Status:** design and evidence, not installed runtime features. **Primary measure:** independent, accepted tasks completed per hour without compromising privacy, spending caps, system responsiveness, or existing data.

This proposal is intentionally an **integration and measurement plan**, not a replacement for current draft pull requests #266 (live resource admission), #270 (Best-of-N code verification), #271 (creator inspections), #274 (knowledge/KV banks), #275 (self-play/skill evolution/training), or #268 (Studio Lab). Land and validate those in small reviewed stages instead of introducing a second competing implementation.

## 1. Verified present baseline

- Main repository: oncoursemail/Star-AI. Development target: star/next; main is not the release target for speculative changes.
- Existing star/providers.py supports LOCAL llama.cpp, authenticated STAR Server LAN, and owner-keyed hosted Groq, OpenRouter, Google Gemini and Cerebras. Brave and Tavily search credentials are already known. No new generic arbitrary URL provider should bypass existing private endpoint validation or OS-backed credential storage.
- Existing star/conversation_memory.py already retains scoped raw conversations and digest-verified compaction checkpoints. Improvements must use this substrate, never replace it with an unaudited memory vector store that silently changes historical facts.
- PR #112 merged first-party Blender MCP with bounded trusted editable scene recipes and GLB export, but not animation rigs/VFX, real Studio acceptance, or remote Brain2 installation.
- At this checkpoint, remote Brain1 (Linux starai) is online with 125 GiB physical RAM, about 62 GiB available, and no Blender executable found on PATH. Brain2 (Linux alexbuz1) is online with 15 GiB RAM, ~170 GiB free disk, and no Blender executable on PATH. Brain2 Ubuntu repository offers Blender 4.0.2 but no installation was performed. Desktop Commander rejects sudo; one attempt to reach an official Blender download endpoint returned HTTP 403. Do not work around the operator's command protections.
- These observations are snapshots, NOT evidence that the Windows desktop executable, real Godot/Unity imports, network Blender MCP or training jobs work end-to-end.

## 2. Optimize for validated outcomes, not impressive agent counts

**North-star metric:** independently accepted development/creation tasks per wall-clock hour, separately reporting CPU, RAM, VRAM, cost, privacy and reliability.

Capture p50/p95 time to first token, time to first correct answer, prefill and decode tokens/sec, verification coverage, end-to-end pass rate, Studio/engine native result, cold/warm retrieval speed, peak CPU/RAM/GPU/VRAM, and regression count. Do not trade away UI responsiveness to win an offline benchmark.

Use three distinct work queues:
- **Interactive:** human chat, code editing and preview. Reserve at least one rapid inference slot and protect Studio responsiveness.
- **Verified background work:** static checks, tests, renders, benchmark suites, retrieval, source indexing, approved web research. Yield immediately to foreground pressure.
- **Opt-in experiments:** LoRA/QLoRA trials, candidate skill evolution, longer test-time search and self-play. Run only with rights-verified data, owner-approved devices, quotas and separate immutable result evidence.

Explicitly differentiate **prefill latency** (prompt caching can help) from **decode speed** (needs model/backend optimizations); background batching may increase global throughput while making one user response slower.

## 3. Multi-model Free-API Intelligence Router (proposal, not active)

Provider candidate strategy:

| Route | Current status | Actual free allowance and limitations | Privacy/action |
| --- | --- | --- | --- |
| Local llama.cpp / STAR LAN | Already present | No hosted inference fee; electricity, disk, memory and CPU/GPU contention are real costs | Default for private/project data |
| OpenRouter | Already present | Official Free plan says 25+ free models and 50 requests/day (account limits can vary). Models/provider availability changes. | Strict opt-in for sending code; capability/privacy flags per routed destination |
| Groq | Already present | Free plan has model-specific request/token quotas and 429 responses. No unlimited pool. | Retry-After; per-model budget/cooldown |
| Google Gemini | Already present | Free tier depends on model/region/project; free-tier inputs can be used to improve products according to current pricing table. | Do not send private user projects without informed opt-in |
| Cerebras | Already present | Free usage exists subject to current account/model limits; fetch model catalog and live headers instead of assuming allowance. | Dashboard/account verification |
| Cloudflare Workers AI | **Not integrated** | 10,000 neurons/day free (official Oct 1, 2026 pricing); some latest models require paid billing method. | Add an explicit account-scoped adapter, not model-generated URL |
| Hugging Face Inference Providers | **Not integrated** | Free users get $0.10 monthly credits, subject to change; this is an experiment allowance, not general continuous inference. | Require account token, limits, provider-specific data practices |
| Brave Search | Existing API key slot | $5 free monthly credits, web search $5/1,000 requests (~1,000 covered if exclusively search); beyond free credit has billing implications. | Independent source citations, web prompt sanitization |
| GitHub public API | GitHub access possible through tools | Typical REST 60 unauthenticated / 5,000 authenticated requests per hour; actual secondary and per-endpoint limits apply. | Never scrape secrets; respect scopes and rate-limit responses |

Official current reference URLs:
- https://openrouter.ai/pricing
- https://openrouter.ai/docs/api/reference/limits
- https://console.groq.com/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/pricing
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://huggingface.co/docs/inference-providers/pricing
- https://brave.com/search/api/
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

A **quota-safe router** must keep, per provider/model: task and modality capabilities (vision, tool calls, streaming, code, context), owner opt-in, project privacy level, token cost or free-tier terms, account-specific recent 429 information, model revision, latency, valid-output rate, and last verified metadata time. Each call checks hard daily/monthly budgets, then ranks quality-adjusted p95 wall time. A call to a free vendor may fail: show the failure and switch to an authorized local model, not silently make a paid call. Never ship auto top-up or automatic API-key discovery. A provider cannot be treated as free merely because a model display name includes free.

Start with **measurement and failover for already implemented providers**, not ten additional vendor connections. Add Cloudflare and Hugging Face behind owner-entered credentials only if their security, terms, and actual value meet explicit acceptance criteria. Source permissions must be evaluated **before** selecting hosted inference. Persist only redacted usage/quality receipts; keys stay in OS credential store, never training logs.

## 4. Task-specific models and practical hardware placement

Bench candidate local families, one hardware-resident GGUF/version at a time. Candidates (not default deployment decisions): Qwen3-Coder-30B-A3B-Instruct for coding on high-RAM CPU, quantized Qwen3.5-9B multimodal for images/UI with VRAM/context caps, OpenAI gpt-oss-20b for coding/reasoning if host quantization makes sense, and Microsoft BitNet-compatible smaller specialist for CPU experiments. Compare with STAR's current pinned model fleet; count VRAM for KV cache and vision as well as weight size. A 30B MoE still stores tens of billions of weights even if active parameters per token are lower. Specific named checkpoints and licenses must be verified before auto-download or redistribution.

- **Brain1: EPYC/125Gi Linux:** large resident quantized models that are too large for the GPU, docs retrieval and embeddings, artifact indexing, background eval and prompt-cache experiments; watch RAM bandwidth/NUMA pressure.
- **Brain2: i7/15Gi Linux:** actual Roblox Studio Lab, low-resource verification workers and, if authorized and installed, small Blender/Godot headless build jobs; preserve Studio's memory floor in #266.
- **Windows PC RTX 3060Ti 8Gi:** interactive multimodal small model or GPU-assisted rendering; 8Gi VRAM cannot simultaneously hold every 3D foundation model, a large chatbot, texture synthesis, and training; owner activity priority. QLoRA only on explicitly scheduled safe snapshots.
- Run benchmark tournament of llama.cpp stable prompt cache, flash attention, appropriate threading/quantization, small draft model or n-gram speculative decoding and model-dependent offload. Record exact versions and back out regressions. Experimental KV checkpoints (#274) must be isolated per project/chat/model, never shared across users without slot exclusivity and leases.

Reference: https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md ; https://github.com/QwenLM/Qwen3-Coder ; https://huggingface.co/Qwen/Qwen3.5-9B ; https://openai.com/open-models/ ; https://github.com/microsoft/BitNet .

## 5. Better conversation memory, comprehension and planning

Implement around existing scoped checkpointed raw history, not over it. New indexed **facts** should carry project/chat IDs, message IDs, timestamps, extraction model revision, source excerpt checksum, stated vs inferred flag, privacy, TTL and correction/superseded pointer. Distinguish:
- Working memory: current turn, last relevant turns, explicitly selected project and active files.
- Episodic memory: what user asked, which implementation was tried, tests, screenshots, acceptance and outstanding work.
- Semantic memory: stable preferences and source-grounded facts, conflict and timestamp resolution, user-editable review.
- Procedural memory: reviewed skills/workflows and tested scripts, not blindly promoted AI-generated instructions.

At each turn: resolve project, retrieve by lexical exact identifiers plus optional embeddings, rank freshness/consent/source authority, check contradictions, include a small evidence budget, cite message/file provenance internally, and allow the user to correct or opt out. No cross-project leakage. Failed/incomplete turns must never be reconstructed as completed answers. Eval with pronoun follow-ups, changed design constraints, contradicting earlier instructions, long-range recall, deleted data, exact numbers, and adversarial tool output. Optimize **correct recall per 1,000 prompt tokens** rather than number of vectors stored.

For complex creation and research, use a persistent **plan graph**: objective, constraints, ordered subtasks, dependencies, tools, verification evidence, blockers, next action, and an explicit owner approval boundary. Planning can survive chat resumes without inventing results. A separate creative generator produces competing style/gameplay ideas; an evaluator checks playability, originality, coherence and measurable compliance with human visual references, never substituting its own taste for user acceptance.

## 6. Learn faster, but only from reliable outcomes

Combine techniques with verifiable feedback, not uncontrolled self-rewriting:
1. **Best-of-N (#270):** branch code candidates; static-compile, Luau type-check, run isolated behavior tests, and rank by independent execution evidence; reserve chat slots. Only tests that ran count as passes.
2. **Curriculum/self-play (#275/#268):** generate small legal owner-controlled Roblox exercises with deterministic target behavior, run actual Studio Lab sessions, screenshots, bot interactions, regression checks, and failure classification. Simulated tests must say simulated.
3. **Reflective instruction evolution (#275):** freeze candidate prompts/skills; evaluate against sealed, contamination-controlled held-outs; keep only versions with statistically meaningful improvement and no safety regressions.
4. **Reinforcement-by-feedback data curation:** correct only source-rights-cleared problems with independently verified tests or user acceptance, annotate provenance and duplicate hashes; separate train, validation and test by project/family.
5. **Small local adapter fine-tuning (#275):** export only approved datasets, pin code/dataset/checkpoint, benchmark memory and learning before an opt-in QLoRA job, evaluate blindly, deploy only after approval and explicit rollback.
6. **Research-grade novelty experiments:** copy the methodological idea of AlphaEvolve—generate algorithms, objectively evaluate them, mutate survivors—but apply it to narrow verifiable objectives: Luau network bandwidth, generated map draw calls, asset triangle budgeting, test scheduling, and pathfinding runtime. Claims of discovered breakthroughs require independent reproduction and controlled baselines.

Research: https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ ; https://arxiv.org/abs/2506.13131 ; https://arxiv.org/abs/2507.19457 (GEPA) ; https://arxiv.org/abs/2207.10397 (CodeT generated tests); https://arxiv.org/abs/2207.14502 (verified self-generated code problems). Beware repeatedly training on unverified synthetic outputs; model collapse and benchmark contamination are real risks.

## 7. Creator Studio: real assets, animation, VFX and engine tests

Adopt an editable **Creator IR** carrying unit conventions, transforms, meshes, materials/textures, rig skeleton, skin weights, animation tracks/events, VFX emitter/particle graphs, shaders, LOD, gameplay components, target export constraints, license provenance, and reference image camera/light conventions. Keep native-specific semantics, do not falsely present Unity humanoid as Roblox R6 parity.

| Engine | Adapter builds and tests (future owner-approved tasks) | Minimum proof |
| --- | --- | --- |
| Roblox Studio | Luau/Rojo verified scripts, real R6/R15 rigs, particles/trails/beams, TweenService, animation tracks, server/client replication and physics | Luau analyzer + owner-controlled Studio runtime + visual screenshots + latency/fps checks |
| Blender | Extend first-party bounded recipes to topology/UV/PBR/armatures/actions/IK/bakes/materials, import/export GLB and .blend, camera previews | Native Blender headless render, glTF Validator, topology/skin checks, editable source and manual character review |
| Godot | .tscn/.tres/GDScript, AnimationPlayer/Skeleton3D/GPUParticles3D, headless project import and tests | installed-version headless import + script diagnostics + target-engine screenshots/playtests |
| Unity | C# tests, GUID/prefab/scene graph, Animator/humanoid retarget, VFX Graph/Particle System, editor Test Runner | installed Unity project version + EditMode/PlayMode passes and executable scene captures |
| Unreal (later) | Asset Registry, Niagara, Blueprints/control rig verified through operator-installed editor | native editor cook/play tests; no false claims from static file scans |

The open-source CoplayDev Unity MCP and Godot community MCPs are **candidate third-party integrations**, not verified STAR installations. Inspect their permissions, license, update mechanism and arbitrary scripting surfaces before adoption. Third-party Blender MCPs may expose arbitrary bpy and telemetry; keep STAR's limited first-party Blender MCP as the default. Human-reviewed reference comparisons and genuine native game renders are mandatory for the desired high-quality art direction.

Asset pipeline: style brief -> multiple concept options -> chosen design language -> rough geometry -> topology/UV/rig -> authored animation and foot-lock/cycle tests -> authored VFX with frame/budget caps -> native import -> screenshot and performance comparison -> iterative repair. Use licensed assets and do not assume high-quality character creation from procedural primitives or proof solely from a .glb file being present.

Official/related resources: https://docs.blender.org/api/current/ ; https://github.com/KhronosGroup/glTF-Validator ; https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html ; https://docs.unity3d.com/Manual/ ; https://create.roblox.com/docs/art/blender ; https://github.com/CoplayDev/unity-mcp ; https://github.com/ahujasid/mcp-for-blender .

### Blender installation and Brain2 access constraint

Current STAR Blender connector defaults to a local in-process memory MCP; having Blender installed on Brain2 **does not automatically attach the Windows STAR desktop to a remote Blender process**. Implementation of a network bridge would require a new mutually authenticated private endpoint and strict tool allowlists rather than opening a Blender Python shell. Brain2 currently lacks a Blender executable and elevated installation via Desktop Commander is blocked. An authorized operator may install the Ubuntu repository Blender 4.0.2 with administrator rights, or an official verified user-scope portable release after a successful approved download/checksum. Then validate headless Blender version, editable blend, GLB, preview, real Windows application routing to Blender MCP, and destination Studio import. Do not report it installed or connected until those tests run.

## 8. Independent tests and go/no-go gates

Benchmark suites should contain: (a) held-out Roblox Luau implementation, debugging and exploit resistance; (b) long conversation instruction/fact recall and correction; (c) engine-specific real gameplay/VFX/art import; (d) cross-model failover under injected 429s/timeouts/cost caps; (e) private data not sent to unapproved cloud; (f) memory/project scope isolation; (g) resource pressure and foreground cancellation; (h) repeatable human creative review. Use **paired A/B tasks with pinned prompts/datasets/models**. Keep hard failure/unknown distinct from success, and record CI run IDs/screenshots/videos.

Proposed targets to test, NOT measured claims: p95 time to first useful response 30% lower on warm repeat tasks, at least 15% better accepted Luau tasks/hour with Best-of-N under a fixed cost/hardware budget, 95% exact project-fact recall on held-out multi-session tests with zero cross-project leaks, 95% native import success for owner-reviewed asset fixtures, zero cloud calls after budget/permission refusal, and no surprise paid calls.

## 9. Sequencing and protected boundaries

**P0: verify and integrate existing work.** Finish CI, review, merge independently and owner-native test #266/#268/#270/#274/#275/#271 in dependency-aware order. Don't force-merge conflicts. Capture baseline resource/performance/evals first. Validate true Blender binary + first-party connector + Roblox import before claiming creator power.

**P1: router observability and safe API expansion.** Instrument already-supported provider success/time/cost/privacy, account-specific quotas and consented failover; then optional Cloudflare and HF adapter proposal with unit tests, secret redaction and $0-spend default.

**P2: durable memory and project planner.** Index source-linked facts with contradiction handling, typed plan graph/checkpoint evidence, cross-session UX and end-to-end regression tests. Promote only after multi-session hold-out pass.

**P3: Creator VFX and animation adapters.** Land Blender rig/UV/animation integrity tests, Godot headless build/test, Unity editor integration under explicit permissions and independent native smoke suites. Roblox rig and particle budgets reviewed in Studio.

**P4: learning and frontier research.** Continue self-play and sealed skill evolution under resource admission, only then trial narrow adapter fine-tunes and independent evaluation. No model self-promotion, raw secret training, unrestricted admin privileges, autonomous paid usage, source-license guessing or uncontrolled recursive synthetic data ingestion.

### Security requirements throughout
- Local-first default for private project files and chat memory, explicit opt-in for each external provider and permission escalation.
- Never accept arbitrary endpoint URLs, shell commands, downloaded addons, scripts or tool schemas solely from an AI response or web result.
- Source attribution, rights/robots/ToS compliance and audit logs for externally retrieved knowledge; no unapproved private/paywalled content.
- No blanket “free APIs”: implement failure on exhausted quotas with owner-visible budget diagnostics, never spend automatically.
- No automatic shipping of model weights, code changes, Blender scene edits, Roblox publication, Unity asset writes or memory promotion without isolated test evidence and owner review.

**Definition of success:** STAR beats its own pinned baseline on reproducible user-relevant coding, art, gameplay and planning tasks with transparent evidence, while staying responsive and private. Claiming STAR universally outruns ChatGPT or Claude requires an independently valid head-to-head evaluation; it cannot be established from architecture, API count or an internal leaderboard.
