# RAMForge ExpertFlow: measured CPU/RAM inference research for STAR (2026-10-13)

Status: DRAFT, being filled in as runs complete. Every number below is labelled "measured" (with time and
command) or "estimate". Nothing here changed the live `star-brain` service.

<!-- RESULTS -->

## 1. What RAMForge was, and what was found of it

- ChatGPT's lab: server 1, container `starai`, `/home/star/ramforge-lab/` (RESEARCH.md, `ramforge_probe.py`,
  `baseline.json`, 2026-10-13 00:35Z). It is a Phase-0 read-only probe: CPU topology, EDAC memory entries, the
  router's own decode/prefill timings from the journal (p50 9.80 / 67.3 tok/s), and an older STREAM-style figure
  copied from `/opt/star/bench/s01.log` (31.2 GB/s at 24 threads). It made no model request and measured nothing new.
  Its hypotheses (A-I: profile experts, adaptive layout, Zen 1 kernels, prefetch, scheduling, speculation,
  prompt reuse, precision, KV) are the starting list for this document.
- Roadmap: `docs/research/unified-intelligence-stack-2026-10-12.md` section 6 ("profile Qwen3.6 sparse expert
  activation ... compare four-node NUMA locality, selective hot-expert caching and AVX2 fused quant kernels against
  the installed ggml baseline ... Only ship repeatable end-to-end gains") and section 8, Phase 6.
- Scope split in this wave: ContextVault (prompt/KV reuse) = chat-speed agent (24 GB RAM prompt cache is live);
  Resource-Aware Scheduler = resource-planner agent; Model Router = llama.cpp router mode (live). This document
  covers ExpertFlow (NUMA/MoE execution) and SpecDecode.
