# STAR Ultimate Brain v1 — Research, implementation and release gates

**Research date:** 2026-10-09

**Implementation status:** new feature branch feat/star-ultimate-brain-v1, stacked on existing DRAFT star/fast-brain-integrated (PR #31). **Not merged, released, trained, or real-device-benchmarked.**

**Target PC:** Windows 11, 32 GB DDR4 system RAM, NVIDIA RTX 3060 Ti 8 GB VRAM. These are reported specifications, not probed benchmarks. CPU, memory pressure, VRAM headroom and runtime health must be measured.

## Product strategy

One fast, attractive STAR chat with a capability router and selective specialist model and tool paths. Prioritize *demonstrably good* workflows: ordinary questions without wasted calls, reliable code, accurate Roblox Studio edits, aesthetically faithful native UI, rigged 3D and animations, source-linked research, measured testing and reviewed project knowledge. STAR is a local-first engineering prototype, **not** a new frontier foundation model.

Three distinct improvement loops:
1. **Speed:** select an adequately capable model without making a router LLM call. Keep prompts and tool catalogs short; avoid unnecessary Studio connections. Stream visible tokens and limit tool/model loops. Optimize cache/quant/CPU-GPU placement after actual measurements.
2. **Quality:** ground in task-relevant project references; send difficult tasks to reasoning specialists; use versioned Agent Skills; verify real Studio/test outputs; iterate on observed errors.
3. **Learning:** curate human-approved knowledge and training examples with rights checks; evaluate held-out tasks; fine-tune only hardware-appropriate models with dedicated compatible training jobs. Reading files is not weight training.

## Recommended model fleet for 32 GB DDR4 and 8 GB VRAM

| Role | Model | Reality and constraints |
| --- | --- | --- |
| Fast, dependable default | Qwen3.5-4B Q4, already pinned by STAR installer | STAR's existing bootstrap downloads ~2.7 GB text GGUF plus separate projector. Keep as working quick answer/vision fallback and benchmark on actual machine. |
| Mid-tier reasoning | Qwen3.5-9B Q4 or a measured comparable code model | Try only if quality beats 4B enough to justify load time and memory. Model-dependent vision/projector/tools support. |
| Deep reasoning / Luau | Qwen3.8-27B UD-Q4_K_M | ~16.5 GB weights; Unsloth quotes 17–19 GB total memory for typical 4-bit use. Separate multimodal projector ~0.93 GB and longer KV cache add costs. CPU RAM offload unavoidable on an 8 GB VRAM card. It may be painfully slow; never make default Fast model without p50/p95 data. |
| Lower-memory deep quant | Qwen3.8-27B UD-Q3_K_XL | ~13.1 GB weights, lower precision; test Roblox/code quality loss versus improved placement and speed. |
| Optional research | Qwen3.5-35B-A3B quantized MoE | Fewer active parameters per token is NOT the same as smaller resident model memory. Load and compare only if machine resources permit. |
| Optional cloud | Owner-selected Groq, Cerebras, OpenRouter, Gemini models in PR #31 | Quotas, availability, privacy and price differ. No automatic cloud fallback or off-device private file transfer. |

**32 GB DDR4 != 32 GB GPU VRAM.** The 27B model can fit in total system memory in favorable configurations but shares RAM with Roblox Studio, Windows, Blender and caches. CPU-RAM offload is slower than VRAM. Although the model advertises up to ~256K context, that is a model capability, not a speed-appropriate consumer-hardware setting. Start at 2K–4K context, then benchmark 8K/16K with attention to KV memory. Do not automatically replace verified pinned 4B weights with a large download.

Official model and quant/memory sources:
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/unsloth/Qwen3.8-27B-GGUF
- https://unsloth.ai/models/qwen3.8-27b

## How combined models actually work

- **Deterministic routing (implemented):** same explicitly selected inference endpoint, configurable Fast / Reasoning / Roblox / Vision IDs, with Fast / Auto / Agent override. No extra classifier token latency and no secret cloud switch. Blank optional IDs preserve the existing single-model setup.
- **Multi-agent drafting (partially implemented):** within Agent mode, narrow read-only draft subagents can use the Fast model, with the main reasoning model consolidating. They have no tool/Studio/file permissions and are not a real worker pool.
- **Supervised ensembling (planned):** compare two independent answers for difficult coding problems; select by measured tests, lint and actual screenshots, not majority vote alone. Extra runs may cost more time than they save.
- **Mixture-of-Experts weights:** properly trained routing network within one model is not equivalent to blending separate GGUF files.
- **LoRA adapters and distillation:** require a separate labeled dataset, suitable legal terms, compatible training frameworks and held-out evaluation. They are not automatic results of connecting more LLMs.

The official llama.cpp server supports **router mode** with --models-dir / --models-preset; its router can load/unload model instances. This differs from STAR's current pinned launch with one GGUF via -m. On this computer, do NOT set many resident 27B/9B processes; memory pressure will destroy throughput. Begin with one active model and verify explicit model IDs from the endpoint.
Reference: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

## Implemented on branch

1. star/brain_router.py: deterministic role selection and model-ID validation, no new execution permissions.
2. star/desktop_core.py: backwards-compatible aliases, task-specific budgets, selected model ID and Roblox quality notes, visible route progress.
3. star/agent.py: selected narrower subagent model for read-only drafting.
4. star/react_shell.py and frontend/src/Desktop.tsx/types.ts: persist and edit Fast / Reasoning / Roblox / Vision model aliases within the single React settings page, with same-provider warning.
5. star/brain_benchmark.py: streams a **real** local completion, measures first visible token, total time, text character throughput; reports tokens/s only when server provides actual completion-token counts.
6. star/roblox_training.py: manually selected, reviewed, rights-confirmed Roblox instruction data -> group-split training JSONL + held-out evaluation JSONL. It does **not** train or rewrite model weights.
7. star/agent_skills.py: extra read-only reference skills for Roblox animation/rigging, Blender assets/PBR, and performance auditing, without overwriting existing user edits.
8. tests/test_brain_router.py, test_brain_benchmark.py and test_roblox_training.py: offline tests added. They do not prove real Windows/Studio function.

## Run actual model speed test

Start a compatible local inference server yourself, then replace MODEL-ID with an ID reported by that server's /v1/models endpoint.

    py -3.11 -m star.brain_benchmark --endpoint http://127.0.0.1:8080/v1 --model MODEL-ID --scenario chat --runs 5 --tokens 96
    py -3.11 -m star.brain_benchmark --endpoint http://127.0.0.1:8080/v1 --model MODEL-ID --scenario coding --runs 5 --tokens 128
    py -3.11 -m star.brain_benchmark --endpoint http://127.0.0.1:8080/v1 --model MODEL-ID --scenario roblox --runs 5 --tokens 128

Metrics: TTFT, p50/p95 wall time, generation speed, success and correctness separately. Record quant, context, GPU layers, CPU, threads, VRAM, RAM, cold/warm cache and laptop/desktop thermals/power modes. A local text-only stream does not establish model-agent, vision or Roblox Studio quality. Follow with a fixed evaluation set and screenshot review.

Useful measured experiments: 4B vs 9B vs Qwen3.8 27B on identical tasks; 2K/4K/8K ctx; CPU offload layers; prompt caching; flash attention when compatible; llama.cpp router with only one resident model; speculation/draft models if compatible and proven faster. Avoid assertions like 10x until observed.

## Roblox excellence pipeline

**Discover.** Connect the built-in Roblox Studio MCP to a disposable unpublished place. Inspect the real DataModel, character R6/R15 rig, scripts, guis, assets, animation attachments, remotes, camera, network roles and reference screenshots. Existing read-only Obsidian/Graphify/Skill context must not become code permission.

**Plan.** Define a testable implementation with ownership of scenes, modules, client/server responsibilities and art references. Independently reason about UI, Luau, models, VFX/audio and performance; prevent multiple workers overwriting the same file.

**Code.** Prefer strict Luau type checking, correct async paths, server-owned game state, RemoteEvent payload/rate/distance validation and bounded cleanup. When installed, integrate Rojo / StyLua / Selene or comparable tooling after checking tool versions and allowed scopes. Ensure games actually load and playtest.

**UI.** Use genuinely editable native Roblox GUI components, not screenshots masquerading as buttons. Respect the actual reference's silhouette/layout, consistent typography, scaling, anchor points, measured contrast, clean monochrome icons and subtle interruption-safe animations. Screenshot compare on desktop/mobile; flag clipped text, uneven alignments, unnecessary neon, random shapes and fake details.

**3D and animation.** Author real Blender geometry, UVs, normals, rigged assets, PBR maps with licensed provenance; export glTF/FBX with correct Roblox axis and scale. Validate importer errors, welds/attachments, Animator tracks and R6/R15 compatibility. Inspect first/last frame clipping, character held items, foot planting and relevant camera angles. A 2D image is a design reference, not a usable 3D source mesh.

**Optimize.** Capture low/mid-end client FPS and frametime, scripts, memory, streaming, network replicates and asset budgets. Use profiler before changes; quantify before/after. Keep VFX on clients where appropriate and preserve gameplay correctness.

**Verify.** Capture actual Roblox play session logs, screenshot evidence, Luau diagnostics, automated gameplay test observations and failures. Iterate on failures and record exact files/instances edited; do not claim an animation worked without seeing or testing it. Publishing Roblox games, accessing live user data or editing unrelated work remains owner-approved.

Official primary sources:
- https://create.roblox.com/docs/studio/mcp
- https://create.roblox.com/docs/ai/accelerated-workflows
- https://create.roblox.com/docs/luau/type-checking
- https://create.roblox.com/docs/ui/animation
- https://create.roblox.com/docs/studio/importer
- https://create.roblox.com/docs/art/blender
- https://create.roblox.com/docs/art/modeling/surface-appearance
- https://create.roblox.com/docs/performance-optimization/improve

## Training STAR's Roblox expertise

At 8 GB VRAM, **27B fine-tuning is not a practical local default**: Unsloth's general 27B minimum is about 22 GB for QLoRA, and architecture-specific requirements can be higher. Smaller 2–3B LoRA/QLoRA runs may be possible after checking actual training framework, VRAM and supported Qwen variant. Train a small adapter only after baseline test scores and licenses have been reviewed. For a large 27B adapter, plan sufficient rented GPU or server hardware; do not promise full retraining locally.

Create input examples.json with an array of records having id, group_id (shared for related examples), category (luau/ui/animation/environment/performance/gameplay/debugging/testing/assets), instruction, response, reviewed:true, rights_confirmed:true, and evidence:["actual-session-id"]. Then:

    py -3.11 -m star.roblox_training --input reviewed_examples.json --output-dir star-datasets/run01 --holdout 20

The tool writes a reviewed training JSONL and held-out evaluation JSONL. It checks required attestation flags and obvious key patterns, but **cannot independently verify** licenses or screenshots; human audit required. Save datasets outside public Git, do not scrape personal chats, never train on private project source without rights. Split by independent *project* to prevent leakage. Measure successful lint, functional Studio tests, UI visual fidelity, animation quality, failure rate and token-time cost before/after on unseen games.

Research:
- https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements
- https://github.com/QwenLM/Qwen3/blob/main/docs/source/training/unsloth.md

## Computer control and model security

The user's desire for powerful computer control should translate into task-scoped, auditable adapters: filesystem edits only in owner-selected workspaces, allowlisted Roblox Studio instance, read-only inspection by default, reversible edits/snapshots, separate access to Blender/browser/IDE as individually configured tools, stop switch and logs. Explicit confirmation for high-risk irreversible actions (deletion, publication, purchases, credential/permission changes). Token-bearing model prompts should not receive OS credentials; third-party webpages, downloaded SKILL.md and MCP results are *data*, not instructions.

The current PR **does not implement unrestricted PC control**, automated source merges, model-weight updates, arbitrary terminal commands, marketplace publication or cloud file sync. Expanding privileges first would not fix slow or wrong answers and would make failures much more destructive.

MCP authorization specification: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization

## Staged delivery and release acceptance

**P0, this branch:** Offline unit tests/compile; React typecheck/build; no regression to pinned 4B local default; same-provider routing; user-facing configuration; real local benchmark and reviewed dataset prep.

**P1, after review:** Explicit managed multi-model server/router support with checksum verification, available-RAM-based limits, per-model capability probes, per-task latency and error dashboard. Provider models must actually load and respond before marked ready.

**P2:** Real Roblox agent executor based on ownership/dependency graph, Play test-loop, screenshots, benchmark fixtures; scope edits to unpublished test place. Existing star/orchestration.py is only a planner, not yet a parallel editing executor.

**P3:** Asset pipeline with Blender, ComfyUI refs, animation clips, Figma/native Roblox GUI conversion, UI screenshot comparisons and optimized 3D materials. Do not claim renderer/asset creation without source files and Studio evidence.

**P4:** Small-model LoRA experiments on reviewed, licensed examples, unseen-game holdout, rollback/versioning and independent review. Cloud training only with explicit opt-in.

**Required:** Python pytest and compileall, TypeScript build/tests, secure dependency audit, Windows PyInstaller/Qt smoke tests, Qwen3.8/GGUF model tests, Studio MCP playtests, release checksum audit, preserving existing %APPDATA%/STAR chats/models/settings. Resolve stacked draft PR #31 and potentially overlapping UI/MCP draft PRs #27 and #30 by review, not forced merge.

**Current evidence:** source code and new tests were committed to a review branch. **Not currently evidenced:** PC throughput, cloud quotas in this owner's accounts, passed CI/Windows QA, training, new installer, AAA visual results, real Roblox Studio edits or superiority to Claude/GPT.
