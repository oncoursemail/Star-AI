# STAR Universal Game Development: engine adapters, language intelligence, asset production, and reverse engineering

**Research verified: 2026-10-11.** This is an engineering research plan plus an implemented, offline-tested *read-only first step*. It does **not** claim STAR can already generate, run, or publish arbitrary games in Godot, Unity, or Unreal.

## 1. What exists in the working STAR branch

The working base is star/claude-integration-20261010, not the older main release. STAR already has the selected-workspace file tools in star/workspace.py, their model bindings in star/agent.py, Roblox Studio policy in star/policy.py and star/studio_loop.py, plus trusted bounded worker infrastructure in star/agent_runtime.py. The existing AGENTS.md requires tested, reviewable changes, rejects claims about unexecuted operations, and prevents generated scripts or MCP responses from granting themselves higher permissions.

The strongest next architecture is a set of **engine adapters** operating through these existing scopes. STAR should not gain an unrestricted local shell just because a model can generate commands. Opening a project in an editor can run untrusted plugins or editor scripts; the flags “headless” and “batchmode” control user interface presentation, not security isolation.

## 2. Verified engine APIs and project structures

| Engine | Project indicators | Automation that official sources establish | Constraints |
|---|---|---|---|
| **Godot** | project.godot, .gd scripts, .tscn scenes, export_presets.cfg | CLI headless import, editor startup, script parsing, release export | Export requires preset/templates and target directory; Godot engine-internal --test is not a universal game test runner; @tool scripts run inside the editor. |
| **Unity** | ProjectSettings/ProjectVersion.txt, Assets/, Packages/manifest.json | Editor -batchmode, -projectPath, Unity Test Framework -runTests, project-owned Editor C# static methods via -executeMethod | Must match installed editor version; test runs should not add -quit; opening/importing a project can execute Editor code. |
| **Unreal** | .uproject, Source/, Content/, .umap | Editor Python/Blueprint scripting, AutomationTool/RunUAT and BuildCookRun | Build targets, installed SDKs, engine association and packaging profiles vary by platform; do not invent a universal launch command. |
| **Roblox** | Luau source, Studio hierarchy and existing MCP | Retain STAR's approved local Studio tools and place ownership checks | Never weaken the existing Roblox permissions or run unrestricted Luau by default. |
| **Blender** | .blend scenes, armatures, meshes, materials | Python bpy scripting, background batch processing, glTF export | Export success must be followed by real target-engine material, rig and motion validation. |

Primary docs reviewed:

- Godot CLI: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
- Godot in-editor code warning: https://docs.godotengine.org/en/stable/tutorials/plugins/running_code_in_the_editor.html
- Godot supported 3D formats and glTF 2.0 recommendation: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html
- Unity editor CLI: https://docs.unity3d.com/Manual/EditorCommandLineArguments.html
- Unity Test Framework CLI: https://docs.unity3d.com/Packages/com.unity.test-framework@1.4/manual/reference-command-line.html
- Unreal editor automation: https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-and-automating-the-unreal-editor
- Unreal Automation Tool: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-automation-tool-overview-for-unreal-engine
- Unreal packaging: https://dev.epicgames.com/documentation/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine
- Blender Python module and background automation: https://docs.blender.org/api/current/info_advanced_blender_as_bpy.html

## 3. First executable STAR integration (this PR)

**star/game_projects.py** reads only limited approved files and scans a bounded number of project entries. It detects Godot, Unity and Unreal project folders; reads Godot project labels and named export presets, Unity editor version and package counts, and Unreal engine association; counts source-language extensions and samples scene paths. It does not trust project-provided instructions.

**star/workspace.py** adds three callable tools through STAR's existing selected-workspace permissions:

1. **workspace_game_discover** – locate up to 12 projects within the chosen workspace, without following symlinks, external directories or generated caches.
2. **workspace_game_inspect** – summarize the detected engine, manifest and limited code/scene inventory for one project.
3. **workspace_game_plan** – output a structured preview of engine-specific validation, import, test or export arguments. It never starts an editor or shell; result explicitly says executed=false. Unsupported operations are reported as unavailable rather than faked.

Examples: Godot import argv = [godot, --headless, --path, ., --import]. A Godot release-export preview requires a *matching named preset from export_presets.cfg* and a safe relative output filename inside the project. Unity EditMode test argv uses -batchmode, -nographics, -projectPath, -runTests and -testPlatform EditMode with an explicitly unresolved editor executable. No Unity test preview adds -quit because Unity documentation warns it can terminate active test runs.

**tests/test_game_projects.py** adds offline fixtures for project discovery, manifest parsing, supported/unsupported operations, malformed manifests, symlink and traversal boundaries, private directories, export preset/output validation, scan caps and rejected arbitrary operations. It needs no network, GPU, editor installation, license, credential or keyring. A local isolated harness passed 11 tests before committing; the full repository and native Windows editor acceptance remain separately unverified.

## 4. The universal adapter contract

STAR needs one narrow, engine-agnostic job envelope: workspace ID, project root, detected engine, requested capability, structured arguments, required permission, intended artifact, timeout, expected evidence and rollback token. The adapter supplies detection, inspection, planning, preflight, execution, artifact collection, verification and rollback.

**Phase A — completed foundation:** safe project discovery, metadata understanding, command planning, bounded manifest parsing.

**Phase B — isolated reviewed execution:** owner-selected *installed* engine binary and matching version, fixed application-owned argv allowlist, no shell interpolation, sandbox/worktree, job timeout, CPU/disk caps, process-tree cleanup, bounded log size, project-specific owner approval and immutable before/after diff. Running an engine in a normal subprocess is *not* a security boundary for unknown downloaded projects. Use a VM/container or other OS confinement when handling untrusted projects.

**Phase C — true scene editing:** first-party adapters rather than raw binary-scene mutation. Godot EditorScript/EditorPlugin and scene tree; Unity Editor C#, prefabs and SerializedObject; Unreal Editor Python and Blueprint-authoring utilities. Every edit should journal object IDs and old/new state, support undo and preserve existing content.

**Phase D — testing:** run engine-specific compilers/importers/tests only in approved isolated environments; capture stdout, stderr, log exit code, scene inspection evidence, real screenshots/videos and target-device measurements. A positive textual answer or exit code alone is not visual proof.

**Phase E — packaging:** explicit platform matrix, reproducible build inputs, artifact checksums, asset licenses, localization/accessibility tests, SDK availability and owner-controlled signing/release. Console toolchains/access and platform distribution credentials cannot be assumed.

### Capability status matrix

| Capability | Current PR | Next scoped implementation |
|---|---|---|
| Recognize Godot/Unity/Unreal projects | Implemented | Add metadata depth, engine-version matching |
| Read approved scene/code files | Existing workspace read plus new inventory | Engine-specific parsers/semantic scene graphs |
| Edit project source | Existing opt-in workspace write | AST-aware transactional edits/rollback |
| Run Godot/Unity/Unreal | **Not implemented** | Trusted owner-approved runner |
| Live editor interaction | **Not implemented** | Dedicated engine plugins and authenticated local bridge |
| Test/build/package for users | Command *previews only* | Engine-installed isolated execution and logs |
| Multi-platform publishing | **Not implemented** | SDK/signing/compliance review |

## 5. Language intelligence: use the right parsers, language servers and compilers

A model being able to *produce* a code snippet does not mean it understands its semantics. STAR should use an extensible language-backend registry:

- **GDScript:** Godot Language Server Protocol (LSP), Godot scene resource references, editor parser checks, chosen GUT/GdUnit test extension when installed.
- **C#:** Roslyn/C# language server, project references and symbol index, Unity API tied to installed editor version, Unity Test Framework; ordinary .NET projects can use dotnet build/test.
- **C++:** clangd with compile_commands.json, clang-tidy and sanitizer results, CMake/Ninja or Unreal Build Tool depending on project.
- **Luau:** existing Roblox Studio tools, Luau analyzer/parser, Selene and StyLua when configured, explicit client/server contract checks.
- **Python:** AST, type checking, Ruff and pytest in a restricted process.
- **JavaScript/TypeScript:** TypeScript language service, ESLint and Vitest/Jest with Playwright for interface checks.
- **Rust:** rust-analyzer, cargo check, clippy and cargo test.
- **HLSL/GLSL/ShaderLab:** engine shader import/compile and visual comparison.
- **C, Java, Kotlin, Swift, Zig, Lua and future languages:** on-demand Tree-sitter grammars, official LSP services and language-native compilers/toolchains where available.

Tree-sitter is a general incremental parser suited to recovering syntax ranges even in files with errors; the LSP provides editor diagnostics and navigation. Neither replaces the real engine compiler or target-device tests.

References: https://tree-sitter.github.io/tree-sitter/ ; https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/ ; https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-test

## 6. To make high-quality games, STAR needs more than code

**Gameplay:** input maps, camera rigs, character locomotion, deterministic state machines, enemy behavior, authoritative networking, storage and recovery, latency and anti-exploit design.

**Architecture/environment art:** scale diagrams and floor plans, real architectural typologies, modular parts, structural plausibility, silhouettes, believable material breakup, props with semantic purpose, scene staging and lighting hierarchy. Reject random piles of cubes/circles masquerading as buildings.

**Animation:** editable skeleton, pivot and retarget maps, IK, root motion, authored curves, animation events, foot locking, interactions, cinematic timing and cross-engine clip playback checks.

**VFX:** layer timing, shaders, particles/trails/ribbons, meshes, lighting bloom discipline, overdraw, texture budgets, style consistency and motion readability. Unreal Niagara, Unity Particle/VFX Graph and Godot GPU/CPU Particles need separate expert adapters.

**UI:** actual native UI hierarchy, design tokens, component states, localization, responsive anchors, gamepad/mobile accessibility, text overflow, hover/focus motion and pixel-level reference review.

**Audio/cinematics:** spatial audio, transitions, attenuation, sound events, licensed sources, captions, cameras and motion-cut coherence.

**Performance:** draw-call/triangle and texture budgets, LOD and streaming, collisions, shader compile cost, p50/p95/p99 frame times, peak memory, thermals, target hardware and platform settings.

**3D pipeline:** Blender → glTF/FBX/other target import must check units, transforms, bone hierarchy, skin weights, UVs, tangents, normals, PBR and gamma, mesh collision, animations, LOD and license provenance. A successful import is not proof of visual quality. Godot recommends glTF 2.0 for 3D scene imports.

## 7. Reverse engineering: useful research, with provenance and rights

Reverse engineering should improve STAR's understanding of software architecture, interoperability, save data, rendering, performance and editor APIs **for projects it is entitled to analyze**. It should not copy proprietary code, commercial models, textures, audio, DRM-protected assets or shipped games into STAR-generated products. Respect license conditions, access terms and applicable law; when unclear, prefer public interfaces/open source and independent clean-room implementation.

**Tools worth learning:**

| Project | Value to STAR | Boundary |
|---|---|---|
| Ghidra — https://github.com/NationalSecurityAgency/ghidra | Open-source disassembly, decompilation, control flow and scripted binary analysis | Only authorized binaries; decompiled output is not verified source |
| Rizin/Cutter — https://github.com/rizinorg/rizin | Scriptable file-format/ABI analysis and reverse-engineering UI | Approved research targets only |
| ILSpy — https://github.com/icsharpcode/ILSpy | Managed .NET assembly inspection and API compatibility | Does not grant license to redistribute closed-source implementations |
| Frida — https://frida.re/docs/home/ | Runtime instrumentation, owned test-app tracing and diagnostics | No general STAR access to unrelated processes or third-party protected software |
| AssetStudio — https://github.com/Perfare/AssetStudio | Unity asset-bundle format research on authorized content | Extraction does not confer reuse rights; version compatibility varies |

**Open-source engineering case studies:**

- OpenMW: https://github.com/OpenMW/openmw — scene/data compatibility, modding boundaries, RPG systems; original proprietary game content still requires separate rights.
- OpenRA: https://github.com/OpenRA/OpenRA — real-time strategy architecture, C# game loops, mod content separation and multiplayer.
- OpenRCT2: https://github.com/OpenRCT2/OpenRCT2 — mature simulation and compatibility engineering, UI/state ownership, backwards-compatible saves and regression tests.
- Luanti: https://github.com/luanti-org/luanti — procedurally streamed voxels, Lua mod APIs and multiplayer infrastructure.
- Godot core and demos: https://github.com/godotengine/godot and https://github.com/godotengine/godot-demo-projects — architecture, import pipeline, API examples and testable sample game patterns.

**Approved analysis workflow:** identify owner authorization, precise question, hashes and versions; read docs/source/tests before considering binary analysis; gather observable inputs/outputs; record evidence and uncertainty; independently implement a capability; run comparison tests and performance benchmarks; submit for human review. Neither a scraped file nor a decompiler listing is authoritative on its own.

## 8. Verification, evaluation and learning without self-deception

Multi-engine acceptance cases must cover playable 2D Godot movement, Unity prefab/script tests, Unreal lighting and level builds, Blender export/rig playback, and Roblox network/server safety. For every case, collect: modified file paths and diffs, compiler results, tests truly executed, images/videos actually inspected, p95 target-device frame time, asset/provenance records, failed attempts, and rollback evidence.

Measure **correctness, art-direction fidelity, gameplay quality, code maintainability, security, and performance** separately. The model should improve via reviewed failure cases, retrieval updates and skill packs, not by unverified claims that it secretly retrained its weights. Evaluation fixtures and scoring must remain outside the model/self-builder's writable scope. Compare to a held-out baseline in the existing evaluation gate, with independent reviewer approval.

Do not inflate “fastest AI” claims: measure time to first token, successful game tasks per hour, compiled clean outputs, and quality-adjusted time-to-completion. Use a small model and cached parsed source for routine inspection; route complex reasoning, visual reference comparisons and debugging to capable specialist models only when measured benefit justifies their latency. Concurrent read-only jobs should be capped and independent, not an uncontrolled agent swarm.

## 9. Next priorities

1. **Now, in this draft PR:** read-only project detection/inspection/command previews plus offline tests and this research document.
2. **Next PR:** version-matched installed-editor discovery, approved binary paths, owner approval UX, non-privileged isolated test worktrees and evidence-backed runner.
3. **After security review:** Godot editor adapter, GDScript diagnostics and deterministic fixture-based scene tests; Unity Editor C# adapter, prefab/scene operations and EditMode/PlayMode tests.
4. **Then:** Unreal asset/level automation with UAT, Blender modeling/rigging/UV and glTF automation; screenshot, animation, VFX and frame-budget evaluation.
5. **Longer term:** signed multi-platform build pipeline, accessible UI, games-as-modular-skills, reference-quality metrics, reusable visual style libraries, real user-approved publication and evidence-driven continual refinement.

**Definition of done for future abilities:** a runnable engine installed on the owner's supported machine, explicit authorization and workspace scope, validated executable/configuration, reproducible test logs, successfully opened output in the target runtime, and visually reviewed results. No part of that is implied merely by this documentation or its draft PR.
