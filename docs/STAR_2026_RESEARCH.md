# STAR Intelligence: Research, executable architecture, and open questions
**Research snapshot:** 2026-10-09. **Hardware target:** Windows 11 / GeForce RTX 3060 Ti 8 GB VRAM / 32 GB DDR4.

This is a new application-focused synthesis of STAR's earlier research volumes, with a separation between published capabilities, implemented source, and unvalidated hypotheses. It is not evidence that any system has beaten ChatGPT/Claude at general intelligence. Full earlier research and references are retained in `RESEARCH_ROADMAP.md`, `FRONTIER_RESEARCH_VOL2.md`, `FRONTIER_SOURCES.json`, and the 86 defined Arena tasks.

## 1. Defining what success means
“Best AI ever” cannot be verified from subjective demos. For STAR, define a practical target: **on the same Roblox project, reference, model budget, and device, produce more accepted development features with fewer corrections** than a baseline general assistant. This is a credible niche target because the evaluation can inspect *actual engine state*, exact Luau code, UI components, animation clips, navigation and effects. Build source-controlled fixtures (never test on unprotected production experiences) and repeat the comparison across models and prompt variants.

Measure: task-success fraction; time and cost per accepted task; compiler/type-check errors; gameplay correctness with adversarial inputs; unwanted scene changes; UI fidelity and accessibility; verified rig/animation constraints; fps/network traffic on target devices; reviewer override rate; reproducibility after compaction; and security policy violations. Publish failures as openly as successes. Never let model-generated explanations replace objective evidence from the runner.

## 2. Research-backed building blocks
| Foundation | Published/verified capability | STAR implementation | Missing integration |
|---|---|---|---|
| Qwen3.5-4B on Hugging Face | Apache-2.0 image-text model, open weights | Configurable local model endpoint in STAR GUI | User must download and load model; test image accuracy and tool calls |
| GGUF/quantization | Common efficient inference artifact format, backend/model-specific | Optional llama.cpp launcher and LM Studio/Ollama support | Automatic model-download validator and multimodal projector setup |
| Roblox Studio official MCP | Inspects DataModel, edits scripts, captures screenshots, tests sessions and other engine operations | Python MCP bridge and bounded tool loop | Actual Windows Studio smoke/playtest and screenshot regression runner |
| GitHub Apps | Short-lived installation credentials and permission scopes | Existing GitHub App CLI module, CI workflow in repo | Register/install STAR's own App separately; benchmark PR worker |
| PySide6 + PyInstaller | Native Qt desktop UI, Windows executable via Windows build process | Real desktop shell and Windows workflow | GitHub Actions Windows run + target-machine UX test |
| Whisper-family ASR | Local audio transcription | Optional faster-whisper audio file input | Live microphone capture, voice activity and low-latency streaming |
| ComfyUI | Local node-based image models/workflows | Restricted local core-node JSON workflow runner | UX for selecting checkpoint/models and image-to-image control |
| Video understanding | Local frame extraction and text transcription can ground tasks | FFmpeg samples four video frames | Temporal tracking, motion-event sampling, GPU budget, continuity validation |
| PEFT/QLoRA | Adapter training, quantized base model reduces memory | Training/evaluation protocols documented | Curated licensed dataset + real training and live regression scores |

References: https://create.roblox.com/docs/studio/mcp ; https://huggingface.co/Qwen/Qwen3.5-4B ; https://huggingface.co/docs/transformers/quantization/gguf ; https://github.com/ggml-org/llama.cpp ; https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx ; https://pyinstaller.org/en/stable/ ; https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation

## 3. Why the architecture uses verified local tools rather than “unlimited access”
A small model can request useful actions if grounded in exact tool schemas, but broad uncontrolled OS access creates a security hazard and makes outcomes hard to reproduce. STAR uses **capability-based tools**: explicit workspace roots for local text files; selected Studio instance ID for Roblox tools; separate GitHub App credentials for repository changes; bounded attempts and retained logs. Routine actions within approved scopes need not pop up an approval dialogue. Publishing, deleting repositories, accessing unrelated credentials and installing arbitrary tools are not granted by this scope. That policy is enforced in code, not left to model instructions.

Separate three types of output: (a) narration from the model, (b) changes recorded by the tool host, (c) verification of resulting state. A model response claiming “I built it” is not equivalent to (b) or (c). Preserve tool calls and observations; check current Git HEAD after repository mutations, use unique operation IDs for retries, and avoid assuming a timed-out write failed.

## 4. Multimodal perception research: evidence before guesses
**Images:** preserve original pixels, capture media hash, viewport size and expected role; distinguish observed shapes from inferred design intent; apply reference image as an input to the actual VLM, not just a filename. For UI, construct an editable `ScreenGui` hierarchy and StyleSheet instead of flattening the screenshot. Verify original vs rendered state at comparable viewports; use measured `AbsolutePosition` and `AbsoluteSize` for exact alignment rather than model-estimated pixels. For characters, match proper R6/R15 or custom rig skeleton and attachment transforms; do not treat a 2D picture as proof of unseen geometry.

**Video:** sampling one frame/second misses fast contact and animation transitions. Initial STAR Desktop samples four evenly spaced keyframes (explicitly **not** complete video understanding); future adaptive sampling should first compute optical flow/action peaks, identify contact windows, and sample dense windows around events. For reproducible animation verification, record joint transforms and held-object attachment error, evaluate transition and loop continuity, and render multiple camera views. Distinguish prerecorded motion from a rig animation asset.

**Voice:** faster-whisper via CTranslate2 supports local transcription; CPU int8 is the first reliable mode on a small GPU. CUDA installations have version dependencies (cublas/cuDNN) that should be tested separately. A future voice pipeline needs microphone input, VAD, wake/stop controls, streaming segmentation, local TTS and interruption handling. The current file-transcription button is deliberately simpler and can require a one-time download of Whisper weights.

Sources: https://create.roblox.com/docs/animation ; https://create.roblox.com/docs/studio/testing-modes ; https://github.com/SYSTRAN/faster-whisper ; https://huggingface.co/docs/diffusers/optimization/memory

## 5. Roblox research: architecture before generation
Deep Roblox engineering spans far beyond Luau syntax. Before coding a feature, STAR must inspect: execution context (ServerScriptService/ReplicatedStorage/StarterPlayer/StarterGui), authority and RemoteEvents, concurrency, race conditions, memory cleanup, networking budgets, save/data migration, UI input modes, world scale and materials, rig topology and Animator, Studio tools, environment lighting and LOD, device/performance constraints, and testing capabilities. Roblox Studio's official MCP server already exposes foundational read/edit/test operations, but **each live installed tool schema is authoritative**, not a hardcoded assumed shape.

For reliable animation: inspect Motor6D chains/rig attachments, animations by authored keyframes, IK constraints, marker timing, blend trees, client prediction/server authority, layering, loop continuity, collisions, and actual camera presentation. A proper final feature requires usable native assets and runtime proof. See earlier STAR research volume II for extended rig/animation evaluation and source mapping.

For UI: use appropriate containers, UIGridLayout/UIListLayout, UISizeConstraint, safe areas and scale considerations, Roblox StyleSheets and accessible contrast/touch targets; test controller and mobile states. Recent Roblox `ProceduralModel` can represent parameterized architecture/assets, useful for reusable building modules; it is not a substitute for authored visual QA. See https://create.roblox.com/docs/parts/procedural-models and https://create.roblox.com/docs/production/publishing/adaptive-design .

For assets: choose Blender for hand-authored mesh topology and rigging; validate exports, textures/mesh count, normals, material/texture licenses, pivots, sockets, and actual Roblox import result. Roblox's generated mesh and procedural tools help produce candidates but may have quotas, variable quality, and distribution conditions. No model can guarantee “perfect” assets from one prompt.

## 6. A structured agent economy
Do not spawn many agents merely to appear intelligent. Tasks should form a **dependency DAG** with explicit ownership and a coordinator. A researcher can work in parallel with a coding worker when their outputs don't conflict; an animator needs rig information before writing clips; independent visual reviewers inspect original image and actual results, not the author's description. Queue GPU-heavy model work on an 8GB GPU and reserve the shared Studio mutation lease so workers cannot simultaneously move the camera, enter play mode and overwrite the same object.

Per subtask record: goal; baseline Git SHA/place revision; allowed original references; allowed tool names and write roots; expected output; required tests; max model/tool calls; execution results; owner; resume token. Return a proposed patch, not unchecked main-branch mutations. A Git worktree separates edits but **is not a security sandbox**.

## 7. Compaction, knowledge and training are different
Context compaction reduces active prompt size while preserving a structured checkpoint. It does not guarantee perfect memory; discarded context has to remain retrievable from raw logs. Maintain (1) immutable source artifacts, (2) reviewed project decisions, (3) codebase graph, (4) verified errors/repairs, (5) tool/SDK version provenance. Separate project memories and honor changed preferences. Avoid training on unverified AI output, and distinguish revised system instructions from actual weight updates.

Later memory milestones: SQLite FTS5/BM25 indexes, embeddings, hybrid search, per-source revision/timestamps, causal graph of requirements-to-implementation-to-tests, exact rollback, provenance UI, and integration with issue/commit IDs.

## 8. Self-improvement beyond marketing
A robust self-improvement loop resembles algorithmic search with an evaluator: propose multiple candidates, execute in isolated environments, search counterexamples, compare against baseline, promote only reproducible improvements, and keep rollback. STAR's existing `frontier_lab.py` is an offline comparator and does **not** execute Roblox tests by itself. Future experiments need a trusted runner that controls play sessions, inputs, screenshots, deterministic fixture scripts, network emulation, and independent rubric checks. Make held-out failures unavailable to the candidate author; otherwise STAR can game its tests.

Candidate learning modes:
1. **Tool/prompt improvements:** change the context/routing/tool strategy, evaluate, deploy when improved.
2. **Source-code/skill evolution:** create a development branch, test, present diff, and merge only after required checks.
3. **Model fine-tuning:** train adapters on licensed, verified examples, with separate held-out evaluation before switch.
4. **Model routing:** benchmark alternate local and hosted models at identical task budgets; make local inference default with no unannounced paid fallback.

AlphaEvolve-style search is applicable to measurable algorithms and local code optimizations; it does not prove automatic creation of a superintelligent general model. Study: https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ and https://huggingface.co/docs/peft/index .

## 9. Technical design for STAR Desktop v0.4

```
Windows STAR.exe (PySide6)
    ├── Chat / Projects / Tools / Image Lab / Settings
    ├── durable local histories + knowledge + compacted checkpoints (AppData)
    ├── task worker thread → local inference endpoint (LM Studio / Ollama / llama.cpp)
    ├── bounded OpenAI-compatible tool calls
    │     ├── workspace list/read/search/write (selected root)
    │     └── official Roblox Studio MCP (selected sandbox instance)
    ├── media adapters: actual images, FFmpeg sampled video, faster-whisper, pyttsx3
    ├── local ComfyUI workflow adapter (restricted core nodes)
    ├── evaluation comparator and source-controlled 86-test Arena specification
    └── GitHub App CLI / PR automation + GitHub Windows build workflow
```

Crucial implementation choices: host inference endpoint restricted to loopback; no hardcoded provider secrets; background worker for UI responsiveness; bounded tool/model calls; max file sizes; no unbounded computer shell; no uploading private source as third-party research without permission; no direct production publishing; binary generated by a Windows runner instead of deceptively claiming a Linux file is a Windows executable. The next engineering task is a **live Windows smoke test** of compiled STAR.exe, image handling and Roblox MCP.

## 10. Priority research experiments for the next six releases

| ID | Experiment | Success requirement |
|---|---|---|
| EXP-01 | Local model truthfulness | No false edits reported in 100 forced tool-failure trials |
| EXP-02 | Project/reference memory | Preserve approved layout instructions after 8 compaction cycles; original image retrievable |
| EXP-03 | Vision-to-native UI | Build working menu from screenshot; no unexpected clipping at three viewport sizes |
| EXP-04 | Luau static + runtime validation | Pass typed Luau/test suite while preserving existing code |
| EXP-05 | Multiplayer inventory | Reject forged/duplicate client requests; no data race on reconnect |
| EXP-06 | Animation rig fidelity | Attachment drift and transitions within action-specific tolerances |
| EXP-07 | Procedural environment | Consistent scale and navigation; bounded part/triangle counts |
| EXP-08 | Adversarial verifier | Find more real bugs than static tests under same inference budget |
| EXP-09 | Multi-agent vs one agent | Higher accepted-task rate without regression or uncontrolled token overhead |
| EXP-10 | Fine-tuning ablation | Improved held-out Luau bug fix rate, no lost tool safety |
| EXP-11 | VRAM scheduling | No OOM after repeated vision ↔ image-generation switches |
| EXP-12 | Installer reproducibility | GitHub Windows artifact passes --doctor and runs on clean Windows 11 VM |

Priority order: **Windows EXE build → local model response → image input → Studio read test → Studio edit test → reliable test runner → benchmark competition → agent delegation → adapter training**. Any report that substitutes 86 unexecuted case definitions for real test results fails the integrity requirement.

## 11. Limitations / things not established
- No evidence currently shows STAR beating OpenAI/Anthropic frontier models on general reasoning.
- Small local models may call tools incorrectly, hallucinate APIs, misread small fonts, or fail complex animation tasks.
- A source-code package alone does not prove a Windows GUI renders correctly. GitHub Actions will build/smoke-test, but human visual and Roblox playtesting still matter.
- ComfyUI / llama.cpp / FFmpeg / Whisper model weights are separate installs and can require hundreds of MB or GB.
- Windows model-runtime GPU behavior depends on drivers, quantization, CPU offload, and context; exact performance must be measured on the user's computer.
- GitHub integration authenticated as ChatGPT is distinct from a STAR-named GitHub App identity. The latter needs separate registration and installation.

## Primary source register

Roblox official: https://create.roblox.com/docs/studio/mcp ; https://create.roblox.com/docs/reference/engine ; https://create.roblox.com/docs/parts/procedural-models ; https://create.roblox.com/docs/animation ; https://create.roblox.com/docs/studio/testing-modes ; https://create.roblox.com/docs/production/publishing/adaptive-design

Hugging Face: https://huggingface.co/Qwen/Qwen3.5-4B ; https://huggingface.co/docs/hub/model-cards ; https://huggingface.co/docs/hub/datasets-cards ; https://huggingface.co/docs/safetensors/index ; https://huggingface.co/docs/transformers/quantization/gguf ; https://huggingface.co/docs/peft/index ; https://huggingface.co/docs/trl/index ; https://huggingface.co/docs/diffusers/optimization/memory

Local inference & media: https://github.com/ggml-org/llama.cpp ; https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx ; https://lmstudio.ai/docs ; https://github.com/SYSTRAN/faster-whisper ; https://docs.comfy.org/ ; https://modelcontextprotocol.io/docs/getting-started/intro

Desktop & GitHub: https://doc.qt.io/qtforpython-6/ ; https://pyinstaller.org/en/stable/ ; https://docs.github.com/en/actions ; https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation ; https://docs.github.com/en/repositories/working-with-files/using-files/creating-new-files

Research: https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ ; https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents ; https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
