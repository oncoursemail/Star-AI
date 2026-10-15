# STAR Universal Intelligence — architecture, creation, REA and self-improvement research

**Research checkpoint:** 2026-10-13. **Status:** draft PR #271, not a release. This is a research-backed engineering program with three *implemented but not yet user-device-verified* inspection tools. It is not a claim that STAR can reverse-engineer any application, autonomously upgrade its own foundation model, render AAA character animation, or outperform frontier models.

## Executive decision: improve quality-adjusted time to a *verified* result

For STAR's local-first Windows desktop, the primary objective is **successful, independently verified tasks per hour at a given hardware budget**, not maximum tokens per second. Track simultaneously:

- Code: p50/p95 time to first *correct* patch, compiler/type-check pass rate, regression test pass rate, rework count, security regressions, user acceptance.
- Creation: elapsed seconds to an engine-importable mesh/scene, successful render/import rate, triangle/texture/VRAM budgets, animation integrity, reference-image similarity by independent review, editability, license provenance.
- Analysis: evidence coverage, reproducible provenance, exact target SHA-256, supported and unsupported structures, source-reference precision, explainable unknowns.
- Hardware: measured prefill and decode tokens/s separately, p95 interactive latency, peak GPU VRAM, RAM working set, CPU saturation, thermal-throttle periods, power and background job interference.
- Learning: **held-out improvement over a frozen baseline** and independent reviewer acceptance, rather than a growing count of notes, generated tests, or self-scored wins.

STAR already contains local model inference/routing, ResourcePool admission previews, real Blender background workers, game-project detection, tool permissions, code navigation, eval gates, and learning diaries. Merge quality gates and measured outcomes across them instead of building unrelated agent frameworks.

## What this PR adds *now*

Three offline/read-only workspace tools; schemas are attached through the existing STAR workspace tool registry and existing scoped permissions. Nothing installs, downloads, publishes, runs, edits, or executes outside those read-only functions.

| Capability | Working API | Evidence actually available | Limitation |
|---|---|---|---|
| Game asset audit | \`workspace_asset_audit(path, target, triangle_budget)\` | glTF 2.0 JSON/GLB-JSON header, node hierarchy/cycles, accessor references, primitive topology/estimated triangles, skin joints, animation sampler targets, materials, unverified external resources | A **preliminary static inspector**, not the Khronos Validator or a renderer. No reading vertex/index buffers; animations and visual quality are not certified. |
| Engine dependency graph | \`workspace_game_graph(path)\` | Godot textual \`res://\` references and missing local paths, Unity scene/prefab YAML GUID links into locally scanned .meta mappings, Unreal declared plugins | Bounded scan. Unity external GUIDs may be package assets. Godot UID references and Unreal .uasset/.umap binary dependencies need engine adapters. |
| REA preparation | \`workspace_binary_triage(path)\` | PE/ELF/Mach-O/WASM header fields, whole-file SHA-256, byte size | **Not REA integration or decompilation**. Does not execute, decrypt, inspect process memory, or claim original source. |

The module names are \`star/artifact_intelligence.py\`, \`star/engine_evidence.py\`, and \`star/binary_evidence.py\`. The tool host is \`star/workspace.py\`, and offline tests are in \`tests/test_creator_intelligence.py\` and \`tests/test_binary_evidence.py\`. The local workspace resolver prevents escaping the selected user project. Limits cap JSON, file size, graph edges and file scans; credentials and private folders remain denied by the existing workspace policy.

**Important quality gate:** The glTF tool is designed for fast, safe first-pass advice. For specification validation use the [Khronos glTF-Validator](https://github.com/KhronosGroup/glTF-Validator), which checks JSON, binary buffers, references, accessors and more. A successful structure audit is **not** a successful import, texture bake, animated playback, rendering review or license clearance.

## 1. REA — Reverse Engineer Anything: verified discovery

The likely requested repository is **[morluto/rea](https://github.com/morluto/rea)**, not one of its numerous forks. Its official readme calls it an MCP + CLI toolkit for investigating applications and binaries. As of this research checkpoint:

- Official entry points: [rea.tools](https://rea.tools/), [original repository](https://github.com/morluto/rea), and [npm package](https://www.npmjs.com/package/rea-agents). Inspect releases and package publishers; do not install similarly named repositories from search results.
- Setup is **owner-run**, not something STAR should execute on untrusted model instructions: \`npx rea-agents setup\` after checking the current supported Node.js versions and reviewing changes. The 2026 README lists Node 22.x >=22.19, 24.x >=24.11, or 26+.
- **Native binary analysis** uses a configured Hopper, Ghidra or IDA provider. Outputs may include procedures, pseudocode, assembly, calls, xrefs and strings with evidence. Decompiled pseudocode does not recover original source or prove runtime behavior.
- Supported investigations described in current REA docs also include JavaScript/Electron application relationships, website observations, .NET managed assemblies, WASM artifact analysis with a caller-supplied tool, saved network captures, Android artifacts/devices with separate prerequisites, and more; availability depends on the platform and provider.
- The documented CLI \`rea analyze-javascript-application <approved-path> --json\` can produce very large Evidence records. The official docs recommend saved evidence and bounded summaries, rather than passing hundreds of MB directly to a model context.

STAR's existing generic remote MCP Hub does **not** automatically register or authorize REA's local stdio agent server. Do not pretend \`workspace_binary_triage\` equals \`rea analyze\`, and do not silently run \`npx\` or expose an arbitrary stdio subprocess.

**Next REA adapter (separate reviewed PR):** installer-free, explicit owner-controlled local executable discovery; pinned official binary/package version and checksum; Windows support verification; scoped project target and SHA-256 receipt; read-only MCP capability allowlist; time/memory/output caps; no unrestricted shell or external URL; consent for each analysis target; no arbitrary attach to third-party processes; sanitized structured findings with links to offsets/functions and confidence; versioned evidence records; tests against STAR-owned open-source fixture binaries. Start with existing public-source/test analysis before decompilation. Preserve API/asset licenses and clean-room boundaries.

A small but useful investigation cycle is **question → target hash → authorized source/binary → REA evidence → hypothesis → independently written implementation → original-vs-new behavior tests → review**. For native Ghidra automated analysis see [Ghidra headless scripting](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md). Other applications' copy-protection, secrets or proprietary game assets are not a license to clone them.

## 2. True multi-engine creation: one semantic scene, different adapters

STAR already has read-only Godot/Unity/Unreal detection and Roblox Studio tools. Next, maintain a typed **Creator Scene Intermediate Representation (Creator-IR)**:

- Objects: persistent IDs, bounds, transforms, hierarchy, semantically named materials and assets, references, units, local coordinate frames.
- Animations: skeleton and joint paths, bind transforms, animation tracks, IK goals, interpolation, root motion, events, fps/sample times.
- Gameplay: components, tags, interaction contracts, replication/authority ownership, save schemas, camera inputs, level transitions.
- Evidence: source files and line numbers, owner-provided visual refs, geometry generation recipe, tool/version/license provenance and safety scope.
- Quality: style constraints, screenshot reference points, geometry/material/texture budgets, GPU/audio/VFX targets, target platform and test cases.

**Never translate everything to generic cube meshes or pre-rendered screenshots.** A Roblox R6 character, Unity humanoid rig, Unreal Control Rig, Godot Skeleton3D and Blender armature have different rig conventions. Adapters must state what semantics survived each export and verify retargeting instead of claiming generic parity.

Phase-specific adapters:
- **Roblox:** Rojo/Luau LSP/StyLua, existing Studio MCP + ownership guard; server/client tests, real R6/R15 rigs, replicated gameplay and mobile UI.
- **Godot:** \`.tscn\` and typed GDScript semantic references; project manifest; headless import and a deliberately chosen installed test runner; \`@tool\` scripts need confinement.
- **Unity:** AssetDatabase GUID mappings, MonoBehaviour fields, .unity/.prefab object graphs, C# diagnostics with the project's installed editor version, EditMode/PlayMode runners; importing may run editor scripts.
- **Unreal:** C++ module and Blueprint graph understanding, Asset Registry and engine Python/editor adapters; platform-specific BuildCookRun and actual map/device tests.
- **Blender:** trusted \`bpy\` job recipes, editable .blend master, glTF/FBX export, render and validation. No model-written \`bpy\` REPL or arbitrary addons.

An advanced Blender character pipeline should add **mesh topology and edge-flow checks**, non-overlapping UVs/texture atlas validation, PBR texture channels, skeleton and binding-pose checks, skin weights/normalization, pose library, keyframe curves with foot-lock and root-motion checks, cyclic animation continuity and multiple camera renders. The default existing STAR worker produces authored primitives/architecture and .glb; it **does not** yet implement these character/animation upgrades. High-quality visuals require art direction and *reviewed renders*, not a declarative name like "AAA".

**Hardware-aware image-to-3D research:** [Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) currently documents around **6 GB VRAM** for shape generation, but substantially more for complete shape + texture generation (its README gives **16 GB**). On STAR's reported **8 GB GPU + 32 GB DDR4** machine, test low-VRAM shape-only generation separately, use nonconcurrent texture jobs or approved external/cloud processing, and report failures and model-license conditions; do not promise that every Hunyuan checkpoint and Blender rendering job fits together in 8 GB.

## 3. RAMForge: engineering speed on limited CPU, RAM and VRAM

Do **not** confuse a proposed optimization with one actually installed and benchmarked in STAR. Existing \`star/agent_resource_planner.py\` is only a non-executing admission preview; integration of live resource pools is separately under review.

Candidate optimizations, ordered by realistic payoff and complexity:

1. **Foreground-first admission:** preserve fast chat responsiveness; when working set and GPU VRAM are near limits, queue 3D/render/large-specialist jobs rather than load several heavyweight models. Use *measured* OOM thresholds and host-level telemetry.
2. **Stable prompt-prefix + evidence caching:** cache pinned system/tool/schema prefixes, source graph snapshots keyed by file content hash, and unchanged source retrievals. Invalidate a dependent symbol/scene when its source changes; never allow stale cache to override current permissions.
3. **Task-specific model cascade:** small local model for scan/format/triage; capable specialist for semantic code repair, deep architecture and visual reasoning; verify each step with compilation/tests. A cheap incorrect answer has high rework cost.
4. **llama.cpp benchmark tournament:** measure appropriate quantization, GPU-layer offload, flash attention, KV cache formats, batching, n-gram/speculative decoding, context size, threading and RAM use on **the actual owner's hardware**. Upstream [speculative decoding docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md) describe draft-model and n-gram variants; gains depend on workload and acceptance rate.
5. **CPU architecture-aware experimentation:** profile AVX2/AVX-512, NUMA affinity and CPU RAM bandwidth *only after hardware detection*. Simpler kernels can win if transfers/branching dominate. Pin baseline executable/model versions to compare fairly.
6. **Optional BitNet CPU specialist:** [microsoft/BitNet](https://github.com/microsoft/BitNet) publishes optimized ternary-model inference and updates, but gains quoted by the project are relative to particular baselines and models; do not extrapolate them to STAR's current GGUF model without compatible weights and matched tests.

Before any runtime optimization, record CPU/GPU model, RAM/VRAM, drivers, inference backend, exact model GGUF and quantization, input context length, concurrency, warmup, first-token time, decode throughput, solution acceptance and power. One A/B change at a time; revert on quality regression.

## 4. Self-improvement without "self-learning" illusions

STAR's approved evolution loop should be:

1. Observe a *real* task, tool results, files/tests/run IDs, and independent acceptance. Separate observed facts from guesses and model-authored postmortems.
2. Classify failure precisely: wrong API, missed context, bad tool selection, invalid syntax, geometry, animation, render fidelity, test mistake, latency/VRAM or unsafe access.
3. Produce a **candidate patch or skill** only inside a branch/job scope. Protect eval fixtures, grader, tool allowlists, secrets, installers and release controls outside the self-builder's writable boundary.
4. Compare to frozen baselines with matched tasks and *unseen* held-out cases; run relevant compiled/tests, security checks, static 3D auditing, actual engine render/player tests when available. Measure latency and resource cost at the same time.
5. Independent review approves or rejects promotion. Roll back instantly if user experience, safety, or quality declines. A model cannot self-certify success or rewrite the acceptance threshold.
6. Store accepted learned strategies as sourced, project-scoped skill/recipe retrieval. Model-weight fine-tuning (LoRA, etc.) is a **separate**, owner-approved, rights-cleared training pipeline—not an automatic consequence of writing memory entries.

**New research hypotheses** (not claims of inventions or proven breakthroughs):
- **Evidence Hypergraph:** unify code symbols, game scenes, bone tracks, glTF primitives, Blender recipes, REA xrefs and real test receipts as typed entities with source provenance. Hypothesis: cross-domain retrieval reduces hallucinated dependencies and accelerates fixes.
- **Semantic Delta Cache:** invalidate only affected graph subtrees and targeted tests when a file, engine setting, mesh or animation clip changes. Hypothesis: lower prefill/context and tool-call costs without missed regressions. Challenge: dynamic dependencies require periodic full-run audits.
- **Quality-adjusted scheduler:** optimize \`verified successes / second\` subject to VRAM, queue fairness and human review rather than \`tokens / second\`. Hypothesis: a cheap scout + expensive reviewer wins on mixed programming/art workloads.
- **Counterexample Forge:** deliberately generate small negative tests for changed code, shader behaviors and animation edge cases, then evaluate them *with a separate trusted grader*. Never let the candidate mutate the scoring cases.
- **Retargetable Creator-IR:** compile an approved semantic world/rig graph into engine-native objects, preserve source links and round-trip check imports. Hypothesis: higher art/editability fidelity than writing every engine script from scratch.
- **Hardware autotuning with a quality gate:** offline microbenchmarks propose measured cache/quant/kernel/thread changes, evaluated on held-out coding tasks with automatic rollback. No unreviewed source or permission mutation.

The learning engine should *propose* its own architectural changes, but a separate reviewer/tester must accept them. It must never independently lower its own test threshold, bypass the user-approved Studio boundary, exfiltrate private context or self-deploy.

## 5. Milestones and acceptance matrix

| Priority | Deliverable | Objective acceptance |
|---|---|---|
| P0: this draft | Asset audit + Godot/Unity dependency graph + binary receipt | Tests pass; no network/process/editor launch; bounded resources/safe workspace; evidence and gaps explicit |
| P1 | Khronos full validator integration + import/clip/playback audit in disposable Blender scenes | Multiple malformed glTF fixtures rejected; validated scenes survive Blender→engine round trip; image/rig evidence captured |
| P1 | REA official local connector prototype, opt-in | Approved test binary hash matched, read-only procedure/xref evidence, 0 unapproved processes/network writes, clear abort/rollback |
| P1 | Resource telemetry & quality-adjusted routing | Reduced p95 successful task latency on frozen 60+ tasks, no output-quality or foreground regressions, no OOM |
| P2 | Engine scene adapters for Godot and Unity | Built/imported user-selected sample projects, automated compile and gameplay fixtures, transactional undo and log evidence |
| P2 | Blender asset/animation studio | Genuine skinned rig, UV/PBR validation, named clips, multi-view renders, engine playback and independent visual review |
| P3 | Unreal and other engine deep adapters + content-scale evaluation | Real editor version matches, reproducible map/build tests, frame budgets and license review |
| P3 | Self-architecture candidate lab | Several independent held-out runs per candidate, explicit improvement confidence intervals, safe reversible promotion only |

**Non-goals for this PR:** installing REA/Blender, bypassing rights or anti-tamper systems, running arbitrary game executables, unrestricted OS command execution, automatic publication, training model weights, autonomous architecture rewrites or claiming 100% correct AAA content.

## Primary-source reference index (verify future version changes)

- Official REA repository: https://github.com/morluto/rea
- Official REA CLI and evidence guide: https://github.com/morluto/rea/blob/main/docs/cli.md
- REA installation and MCP: https://github.com/morluto/rea/blob/main/docs/installation.md
- Ghidra headless analysis: https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md
- Khronos glTF 2.0 specification: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
- Khronos glTF-Validator: https://github.com/KhronosGroup/glTF-Validator
- Blender Python API: https://docs.blender.org/api/current/
- Godot editor CLI: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
- Unity Editor CLI and tests: https://docs.unity3d.com/Manual/EditorCommandLineArguments.html
- Unreal Asset Registry: https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-registry-in-unreal-engine
- llama.cpp speculative decoding: https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
- BitNet inference: https://github.com/microsoft/BitNet
- Hunyuan3D-2 3D generation: https://github.com/Tencent-Hunyuan/Hunyuan3D-2

All third-party feature claims are subject to pinned versions and independent tests. As of this PR, *only* the three read-only inspectors above are newly coded here.
