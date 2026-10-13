# STAR KV cache banks: first-stage CAG experiment

**2026-10-13. Draft feature — disabled by default.** This is a bounded prototype for saving and restoring an already-primed llama.cpp **prompt prefix**. It does not preload the entire Roblox corpus, reserve 80 GB of RAM, make model decoding faster, replace documentation retrieval, train model weights, or prove an improvement.

## Implemented scope

STAR already primes byte-stable conversational prefixes through star/context_layout.py, star/providers.py and star/warmup.py. This PR adds:

- star/cache_banks.py: strictly owner-opt-in, LAN-only, model-revision- and prompt-prefix-scoped KV save/restore helper.
- star/warmup.py: restore a matching fingerprint before the existing background model warm-up, and save only after a successful primed response. Unknown, unsupported, missing, busy, or cancelled slots fall back to existing warm-up.
- tests/test_cache_banks.py: offline HTTP mocks covering stale banks, scope separation, tools/template changes, cancellation, wrong receipts, idle checks and disabled state.
- An opaque local metadata index in STAR app-data under cache-banks/index.json. It does not contain prompt text, raw docs, keys, chats or tensors. The KV snapshot remains on the model server under its separately configured slot-save path.

This is a **warm-up accelerator**, not an automatic restore before every real chat. For changing history, the model must still verify the current prompt and process the divergent suffix. Warm-up plus native cache-ram may already outperform save/restore. A speed gain has not been measured.

## Owner-run setup and safety

1. Use an **owner-operated, access-restricted** llama.cpp LAN server with the slot API. Never expose the slot API on a public or shared inference service: its snapshots can include sensitive conversation context.
2. Explicitly configure the server with the official --slot-save-path flag, pointing to a *private and capacity-limited directory owned by the server operator*. A RAM-backed directory is optional and resides on **the server**, not on the desktop. STAR does not install a RAM disk, determine free RAM or monitor its cleanup.
3. Opt in to both environment variables on the STAR desktop process: STAR_KV_BANKS=on and STAR_KV_BANK_MODEL_REVISION=<your exact immutable model+template revision>. The revision must change when the GGUF, quantization, tokenizer, context handling, adapter or chat template changes.
4. STAR must be configured for its validated star_server LAN provider, and a model with at least two known, explicitly pinned slots. If the server cannot report an idle slot or rejects the API, the ordinary warm-up proceeds.
5. A successful warm-up may include a cache_bank result with restored/saved booleans and short failure reasons. This describes a validated slot API receipt, not proven cache equivalence or a benchmark improvement.

The slot API has an important **TOCTOU limitation**: a slot may become busy between the idle check and save/restore. This prototype cannot atomically coordinate multiple desktops or unrelated clients. **Do not enable it on shared production fleets.** A next step requires a server-side reservation/lease or owner-controlled exclusive slot scheduling.

Only one snapshot filename per project/chat/model/revision is reused to prevent unbounded snapshot names per turn, but the server operator must still monitor storage and remove older snapshots. Local receipts expire after 12 hours; server files do not necessarily expire. No credentials or raw prompts are written to the local metadata index.

## What cache-augmented generation still needs

True pre-read documentation requires a separate, verified integration: choose small, licensed, version-pinned Roblox docs, reviewed skills and user-approved project reference extracts; insert **clearly delimited untrusted data** in a byte-stable shared prefix; hash source revisions and scope; verify references and invalidate when they change. Preserve context for new user questions. Keep ordinary retrieval available for updated docs, rare topics and larger knowledge sets. Run the eval gate before any default enablement.

The cache is not universal transferable knowledge. Model weights, tokenizer, LoRA settings, prompt templates and actual preceding tokens must be compatible. Token-limited models cannot simply hold all Roblox documentation just because the machine has spare RAM.

## Measured A/B acceptance requirement

Use fixed prompts, model/GGUF, context budgets, concurrency and hardware with independent grading:

- A: ordinary native llama.cpp caching with STAR warm-up.
- B: the same workload with opt-in slot bank save/restore.
- Compare cold start; switching between chats; a chat after background jobs evicted its slot; documentation changes and explicit invalidation.
- Record p50/p95 first visible token and completion time, server prompt_n/cache_n, bank save/restore time and bytes, peak RAM/VRAM, timeouts, failed attempts and code acceptance on held-out Luau tests.
- Reject the feature on any cross-project data mixing, stale API guidance, unsafe slot overwrite, failing Studio checks, or significant p95 regression.

## Other requested intelligence upgrades

**#1 Best-of-N:** Draft PR #270 contains opt-in parallel candidate generation and static/mock Luau verification. It does not establish successful Studio Lab gameplay. Real Studio verification requires separately approved disposable places, evidence-based acceptance and integration with the in-flight Studio Lab branch.

**#3 Self-play:** isolate small games, deterministic goals, robot tester traces, bounded Studio resources, screenshots and human visual review. No unsupervised outside-place edits or publishing.

**#4 Skill evolution:** restrict candidate rewrites to approved skill documents, freeze held-out evals, disallow scorer manipulation, independent review and rollback.

**#5 Fine-tuning from wins:** a passed test does not prove originality, licensing, security or rights. Review source provenance, deduplicate, protect project/user content, maintain project-disjoint test data, and seek owner approval before training or deploying a LoRA. A quality gain must be independently measured.

## Primary sources

- https://arxiv.org/abs/2412.15605 (cache-augmented generation research)
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md (llama-server prompt cache, slots, save/restore)
- https://github.com/ggml-org/llama.cpp/discussions/13606 (slot persistence and endpoint security)
- https://github.com/oncoursemail/Star-AI/pull/270 (concurrent candidate testing, draft)

No release or activation is implied by this PR. Server-side setup and real benchmark results remain separate requirements.
