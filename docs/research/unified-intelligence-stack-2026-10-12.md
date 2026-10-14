# STAR Unified Intelligence Stack: 2026 Technical Design

**State:** Research-backed draft, non-executing resource-planner prototype only. No production installation, paid inference, permissions change, merge, release, or new Roblox edits. This report consolidates the prior STAR Frontier and Agent Skills investigations.

## 1. Optimize work completed correctly, not agent count

STAR is a local-first Roblox development assistant. Its quality and efficiency must be measured as verified features/hour, p95 foreground latency, Studio multiplayer test success, code regressions, energy/cost per correct feature and independently validated learning. Many concurrent agents sharing the same CPU memory bandwidth can make each other slower.

Observed server baseline, October 12-13, 2026: Dell PowerEdge R7415; EPYC 7451 24 physical cores/48 logical threads; 128 GiB nominal DDR4 across four NUMA regions; AVX2/FMA but no AVX-512/AMX; production Qwen3.6-35B-A3B Q4 on llama.cpp with two slots, NUMA placement, 24 decode threads and 48 prefill threads; approximately 9.7-9.8 output tokens/s and 67 prefill tokens/s in recent log samples. The Knowledge service historically measured 256 ms median documentation search and 54 ms Luau static check. These are *observations*, not promised throughput under different workloads.

Night School has been practicing Luau tasks with static/stand-in VM checks; it has not demonstrated real Studio simulation or model-weight retraining. Its lessons require independent holdouts and human review before promotion.

## 2. Existing architecture — extend rather than duplicate

The current STAR sources on star/next include:
- star/agent_skills.py, star/skill_packs: portable skills and topic-specific guides.
- star/orchestration.py: validated dependency DAG and resource read/write conflicts.
- star/agent_runtime.py: real asynchronous bounded execution of authorized worker callbacks.
- star/specialist_agents.py, star/team_service.py: actual read-only research specialists, at most two simultaneous model calls.
- star/brain_router.py and star/providers.py: deterministic fast/reasoning/Roblox/vision roles, prompt-cache affinity.
- star/knowledge.py, star/lessons.py, star/frontier_lab.py and star/promoter.py: reviewed project memory and candidate improvement gates.
- star/studio_loop.py, star/studio_remote.py: permission-gated Studio edit/playtest scaffolding.
- star/tool_workshop.py: human-approved declarative read-only custom tools.

Do not install another agent operating system over all of this. Prefer a narrow, replaceable improvement with measured acceptance tests. Source presence does not mean a published app feature has been live-tested.

## 3. Technologies worth adapting

### High-priority native capabilities
- Agent Skills specification (https://agentskills.io/specification): hash-pinned source/rights metadata, lazy load and human-reviewed imports.
- Superpowers (https://github.com/obra/superpowers): design specification -> test -> implementation -> independent review -> proof.
- GSD Core (https://github.com/open-gsd/gsd-core): persistent phases, fresh-context execution and dependency-aware parallel waves. The old gsd-build/get-shit-done repository is archived.
- ECC (https://github.com/affaan-m/ECC): focused quality/security checks; not its entire large prompt/agent catalog by default.
- Ruflo (https://github.com/ruvnet/ruflo): trace/cost/task orchestration ideas, not a guarantee that 100 agents outperform two.
- Playwright CLI (https://github.com/microsoft/playwright-cli): real browser regressions for the React app and site; use Playwright MCP only where persistent UI state merits its extra schemas.
- Roblox-dev (https://github.com/ivar-anon/roblox-dev): severe RemoteEvent/DataStore/typing defects and TestEZ conventions.
- ShiroKSH Roblox Studio (https://github.com/ShiroKSH/skills): SceneSpec, map readiness, geometry validation, MCP/Studio tests; compare code and sandbox rules against STAR's existing integration before enabling.

### Design and image-to-code research
- Taste Skill (https://github.com/Leonxlnx/taste-skill): adjustable density/motion/layout and image-to-code; experimental design-taste-frontend v2 remains opt-in.
- Emil Kowalski (https://github.com/emilkowalski/skills): animation timing, motion quality, reduced-motion, mobile responsiveness and anti-jank rules.
- Impeccable (https://github.com/pbakaus/impeccable): UI inspection and deterministic style defect detectors; don't blindly install executable hooks.
- Awesome Design Skills (https://github.com/bergside/awesome-design-skills): curated style reference pairs, not 67 always-on skills.
- Web Design Guidelines (https://github.com/vercel-labs/agent-skills): accessibility, interaction, React performance; pin downloaded guideline version and audit rather than obey remote text as instruction.
- UI UX Pro Max (https://github.com/nextlevelbuilder/ui-ux-pro-max-skill): concept guides; translate website aesthetics into native Roblox GUI where applicable.
- Figma MCP (https://developers.figma.com/docs/figma-mcp-server/): native token/component hierarchy and editable design data, seat/rate-limit constraints apply.
- React Three Fiber (https://github.com/pmndrs/react-three-fiber), ShaderGradient, liquid-glass-js and liquid-logo: optional web presentation layers, never Roblox-native graphics or unbounded GPU effects.
- Netlify and Vercel: preview deployment requires explicit authorization, no main branch/release publishing automatically.

### Learning, memory, orchestration and security
- Headroom (https://github.com/headroomlabs-ai/headroom): test reversible compression of noisy logs/JSON/tool results. Preserve errors exactly.
- Claude-Mem (https://github.com/thedotmack/claude-mem): observation summaries and cross-session relevance, but optional hosted-memory behavior needs a privacy check.
- Karpathy-inspired guidelines (https://github.com/multica-ai/andrej-karpathy-skills): surgical edits, admit uncertainty, simple code, tests as goal.
- Council reviewers: use only for complex architecture/security reviews, and account for added latency/token cost.
- REA (https://github.com/morluto/rea): evidence-backed reverse engineering only of software the owner is authorized to examine. Proprietary assets and license restrictions still apply.
- Stop Slop: prose editing, not an automatic 3D/UI/gameplay improvement.
- Task Observer, Agent Self Awareness and Arenas: treat as requested capabilities (trace ledger, capability accuracy, object-placement/level/playtest evaluation) until a canonical authoritative project URL is verified. No anthropomorphic self-awareness claims.

### Models and free resources
- Evaluate the community Jackrong Qwen3.5-9B Opus-style reasoning distillation (https://huggingface.co/Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2) only after verifying provenance/license and unseen Roblox coding tests; a model card's HumanEval results are not an independent STAR benchmark.
- Try Gemma 4 variants (https://deepmind.google/models/gemma/) as alternate quick/multimodal model candidates, no default replacement without measurement.
- GLM-5.2 (https://z.ai/blog/glm-5.2) is a heavyweight long-horizon open model, not an inference target for STAR's 128 GiB CPU machine; any cloud use needs separate consent.
- Whisper.cpp (https://github.com/ggml-org/whisper.cpp) is a useful local speech option.
- TRELLIS.2 (https://github.com/microsoft/TRELLIS.2) is a 4B image-to-3D/PBR generator whose upstream documentation asks for Linux and 24GB+ CUDA GPU, not a viable new local task on the existing 8GB desktop GPU without a differently tested setup.
- DeepGEMM (https://github.com/deepseek-ai/DeepGEMM) targets supported modern NVIDIA architectures, not Zen1 CPU/AVX2 inference.
- free-for-dev (https://github.com/ripienaar/free-for-dev) is a frequently updated *directory* of offers, not proof of provider availability.
- Official quotas change: Cloudflare Workers AI currently advertises 10,000 free neurons/day for eligible models; Groq has per-model request/token caps; Google Colab free GPU is not guaranteed and may terminate; Hugging Face ZeroGPU free quota is very limited. No account farming or unauthorized data uploads.
- Perchance is a website, not assumed to be a supported stable free machine-to-machine API; OpenClaw's broad tool authority requires a separately approved security design.

## 4. The proposed STAR architecture

Trusted user and policy host
 -> deterministic intent/capability planner and consent boundary
 -> dependency-checked task graph
 -> pinned skill registry, source hashes and review records
 -> shared physical CPU/RAM/GPU/Studio resource pools and queue admission
 -> parallel independent read-only specialist research
 -> authorized scoped writer(s), one integrator per resource
 -> Luau static/unit/security checks, real Studio TestService, Playwright screenshots
 -> immutable outcomes and provenance (no raw prompts stored by default)
 -> compare skill/routing/repair/memory improvements on frozen unseen holdouts
 -> review and opt-in promotion with rollback

A task observer should emit only task IDs, role, phase, hashes, durations, verified outcomes, resource cost and error class. Model-written notes and outside SKILL.md contents remain untrusted data, not permission grants.

## 5. Multiple parallel agents, without overwhelming the server

The current EPYC and its main 2-slot model share physical CPU bandwidth. Parallel GPU render, browser QA, static compile and documentation work can be truly useful, but four simultaneous giant CPU inference jobs may worsen response time.

Initial planner prototype: star/agent_resource_planner.py defines ResourcePool, ModelWorker, TaskDemand and preview_assignments. It models a shared machine pool, two-sided cloud opt-in, exact capabilities, DAG dependencies, owner-interactive priority, bounded slots/CPU/RAM, and a strict ban on agent write delegation. Tests exercise synthetic cases only. It NEVER executes agents or provisions devices.

Next integrate as an optional preview alongside TaskPlan.ready; do not enable live assignment until measured. The backend must also preserve fairness, cancellation receipts, cache affinity, outstanding task deadlines, and human-approved source scope.

## 6. Technical frontier research program

- **RAMForge ExpertFlow**: profile Qwen3.6 sparse expert activation on synthetic prompts; compare four-node NUMA locality, selective hot-expert caching and AVX2 fused quant kernels against the installed ggml baseline. Earlier tests have already optimized interleaving, threading and loading. Only ship repeatable end-to-end gains.
- **ContextVault**: content-address stable prompt prefixes, documentation digests and project-scoped runtime state; validate cache invalidation and cross-project privacy. Avoid ungrounded "instant" claims on uncached prompts.
- **Verified Model Cascade**: deterministic lookup/exact patches, quick model with verifier, strong model on uncertainty/failure. Measure accepted-invalid answers and user latency, not just routing cost.
- **Studio Evidence Loop**: disposable unpublished place, 2-8 simulated clients, object placement, server authority, replication, persistence failures, UI accessibility, animation and framerate checks. Never report mocked Luau test as native Studio playtest.
- **Skill Academy**: treat every skill as an experiment. Baseline vs candidate vs grouped skill, frozen holdouts, token-budget accounting, content safety, relevance and optional approval.
- **EvoForge**: constrained self-improvement of one routing/repair/skill configuration at a time; independently reproduce positive results, rollback failures and track rejected candidates.
- **Design Native Bridge**: screenshot/Figma/source reference -> component constraints -> editable native Roblox GUI/asset or React code -> multi-viewport Playwright/Studio comparison -> review.
- **Task Observer / capability honesty**: host-controlled capability inventory; classify actions as proposed, mocked, tool-confirmed, independently verified. Autonomous agents cannot upgrade their own permission levels.

## 7. Acceptance gates, not marketing numbers

Each experiment records benchmark commit/model/weights digest, prompt+fixture hash, exact environment, p50/p95 TTFT, inter-token latency, total verification time, CPU/RAM/VRAM, electricity/cost where measurable, regression score, and task outcome.

To promote:
1. No unauthorized writes, cloud data leaks, account actions or Roblox publishing.
2. No proven regressions on a new holdout of at least 50 functional Luau/security cases; evaluate visual and Studio tests separately.
3. For major CPU inference claims, reproduce at least 15% median or 25% p95 latency improvement using identical model weights and task distribution, with quality unchanged.
4. For new agents, compare total correct tasks/hour and absolute resource/token use against single-agent baseline. Peak concurrency is not proof of intelligence.
5. Positive results must survive fresh repeat runs, error/timeout handling and restart/rollback tests.

## 8. Next separate draft PRs and work ownership

1. **Phase 0 (this draft):** pure read-only resource admission + offline tests and this source-backed design. No production binding.
2. **Phase 1:** skill provenance catalog + prompt-injection/lint gate; opt-in imported reference text only.
3. **Phase 2:** task-observer telemetry with privacy-safe replay and viewer-visible status.
4. **Phase 3:** optional resource-aware dispatcher wiring into existing agent runtime, with resource fairness and no permission escalation.
5. **Phase 4:** actual Playwright QA for React frontend and verified Studio sandbox playtests.
6. **Phase 5:** A/B Skill Academy and controlled model cascade, including Jackrong/Gemma 4 candidates.
7. **Phase 6:** isolate RAMForge AVX2/NUMA/quant experiments and optional dedicated GPU worker.
8. **Phase 7:** autonomous proposal-review learning with frozen holdouts, rejection memory and rollback.

Work separately on current star/next-based branches. Use DRAFT PRs, CI and explicit owner review; never merge into main, publish games, download unreviewed binaries to production, or touch live STAR settings without specific authorization.

## 9. Source inventory

Official resources and upstream project references appear inline above. Additional essential references:

- Roblox StudioTestService: https://create.roblox.com/docs/reference/engine/classes/StudioTestService
- llama.cpp: https://github.com/ggml-org/llama.cpp
- AMD EPYC 7451 spec: https://www.amd.com/en/products/processors/server/epyc/7001-series.html
- Microsoft Playwright testing: https://playwright.dev/docs/intro
- Cloudflare Workers AI pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Colab FAQ: https://research.google.com/colaboratory/faq.html
- Hugging Face ZeroGPU: https://huggingface.co/docs/hub/spaces-zerogpu
- Agent skill security: https://agentskills.io/specification
- Google Gemma: https://deepmind.google/models/gemma/

A separate, longer Frontier Research Dossier and Ecosystem Research report contain expanded literature notes. Every unproven mechanism here is a **hypothesis**, not an accomplished STAR performance increase.
