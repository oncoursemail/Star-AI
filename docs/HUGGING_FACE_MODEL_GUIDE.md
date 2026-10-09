# Hugging Face research: STAR's local model strategy (October 2026)

## 1. Read model cards before downloading
The Hugging Face Hub holds model repositories (weights/configuration), dataset repositories, and Spaces. A model's card should be evaluated for **license**, modality (text/vision/audio), architecture/runtime compatibility, quantization, context length, tokenizer/processor dependencies, known failure modes, and intended usage. A model named “coder” does not necessarily support image input; a vision model does not necessarily produce high-quality Luau. Inspect exact model revisions and provenance.

Primary sources:
- https://huggingface.co/docs/hub/model-cards
- https://huggingface.co/docs/hub/datasets-cards
- https://huggingface.co/docs/transformers/quantization/gguf
- https://huggingface.co/Qwen/Qwen3.5-4B

## 2. Models to evaluate on an RTX 3060 Ti 8 GB

| Candidate | Purpose | Practical tradeoff |
|---|---|---|
| Qwen3.5-4B 4-bit | Primary multimodal language/vision agent | Small enough for a meaningful local prototype, but image and tool accuracy require testing; cache and projector overhead matter |
| Qwen3.5-9B 4-bit | Quality experiment / CPU-offload option | Often close to VRAM limits; image context and GPU offload can greatly reduce speed |
| Qwen2.5-Coder-7B 4-bit | Dedicated code-repair comparison | Useful for coding tests but not a vision model |
| Lightweight image-embedding models | Semantic retrieval / similarity | Separate retrieval engines, not replacements for an LLM |
| faster-whisper tiny/base/small | Offline audio transcription | Use CPU int8 by default to avoid competing for GPU memory |
| Diffusion image model through ComfyUI | Render assets and concept art | Run sequentially with LLM unloading; license/checkpoint/tool chain differ |

**Quantized file size is NOT peak VRAM usage.** Context KV cache, vision projection, graph buffers, CUDA memory and Windows display use additional memory. Start at 4K context and increase only after measuring throughput and peak usage.

Qwen3.5-4B's card lists image-text modality and Apache-2.0 license for original weights at time of research. Quantized derivatives can have their own provenance and required projector files. GGUF is a format for quantized inference and does not magically make an unsupported model compatible with a runtime.

## 3. Safetensors vs pickle vs GGUF
Safetensors reduces arbitrary-code execution risk from serialized weight files. Other bundled model code, tokenizers, custom operators, training scripts, installers, and workflow nodes must still be reviewed. Avoid `trust_remote_code=True` unless absolutely necessary and the repository/revision has been inspected. Verify file hashes for critical artifacts.

GGUF files can be used by llama.cpp, Ollama, and some LM Studio workflows, subject to architecture support; `Transformers` may handle GGUF differently depending on backend. For small GPUs, 4-bit quantization is a useful first benchmark but check regressions on UI screenshots and Luau coding before standardizing.

Sources:
- https://huggingface.co/docs/safetensors/index
- https://huggingface.co/docs/transformers/quantization/gguf
- https://github.com/ggml-org/llama.cpp

## 4. RAG + memory before fine-tuning
Build a searchable corpus from official Roblox Creator Hub docs, Engine API names, Luau language reference, selected project source, real errors, approved reference images, and verified repairs. Keep project scope, license, source URL, revision, timestamp, and confidence separate. Preserve exact images/code as artifacts. Retrieval and context compaction improve operational context, **not base model weights**.

The immediate memory stack uses SQLite checkpoints + project-scoped reference knowledge; a future version should add FTS5/BM25, semantic index, source versioning, and revocation when user intent changes.

## 5. Fine-tuning using PEFT/QLoRA
Hugging Face `PEFT` supports adapter-based training, and `TRL` supports training/evaluation workflows. An 8 GB card can experiment with small quantized models and carefully chosen sequence lengths, but there is no guaranteed stable recipe for every multimodal model on Windows; Linux/WSL2 training may be necessary.

Recommended experimental protocol:
1. Build at least 100 independently graded Roblox tasks before tuning.
2. Hold out real reference-to-UI, code repair, rig animation, and gameplay edge-case tests.
3. Collect verified (prompt, context, action, execution evidence, final diff) records. Check licenses and private-data consent.
4. Baseline current model with same inference hardware and budget.
5. Use LoRA/QLoRA only with a supported model and validated training configuration. Track GPU RAM, wall time, regression metrics and seed.
6. Reject checkpoint updates that regress hard safety or correctness tests. Keep original weights and reversible adapter versions.

Research:
- https://huggingface.co/docs/peft/index
- https://huggingface.co/docs/trl/index
- https://huggingface.co/docs/diffusers/optimization/memory
- https://github.com/huggingface/peft/tree/main/examples/sft

## 6. Running local models
STAR currently accepts an OpenAI-compatible local endpoint. Ollama documents local chat completions with images and tools (`http://localhost:11434/v1`) and LM Studio provides a similar localhost interface. STAR also has a `llama-server.exe` launcher but its initial arguments don't cover every multimodal GGUF/projector architecture; use a compatible loader for your chosen model. Keep endpoints bound to loopback by default. Avoid automatic unreviewed remote API fallback.

Source: https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx

## 7. How STAR can become measurably better
Specialize in testable Roblox subdomains and verification, not an unmeasured claim of universal intelligence. Compare completion rate, time-to-verified-merge, GPU cost, code regressions, UI fidelity judged against approved references, animation attachment drift, test escapes, and reproducibility. A multi-agent system should be compared with one agent under equal compute and budgets; more workers are not evidence of improved ability.
