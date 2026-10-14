# RAMForge ExpertFlow: measured CPU/RAM inference research for STAR (2026-10-13)

Status: measured 2026-10-14 (S1-S5 of the run plan). Every number below is labelled "measured" (with time and
command) or "estimate". Nothing here changed the live `star-brain` service.

## Result (measured 2026-10-14 09:12-11:26Z, quiet lock held per slice, live slots idle; details in section 4)

**NUMA-local placement wins: +6.4% generation in llama-bench and +6.6% in server chat runs, beyond the ~1.5% noise,
with bit-identical greedy text and unchanged prompt speed and first token.** Variant A1 = `GGML_NUMA_BLOCK=1`
(thread k on node k*4/n instead of k mod 4) + `LLAMA_RAMFORGE_PLACE=1` (after loading, each node's row block of every
weight matrix, per expert slice, is bound to that node with `mbind`). It is below the 10% bar this document first set
for deployment, so it is shipped **opt-in** (`server/ramforge/switch.sh`), not switched on. The two-level barrier adds
nothing on top. Keeping a node free for background jobs only works with the 3-node layout (model on nodes 0-2 with
placement: llama-bench equal to today's 4-node baseline, server chat -3%, prompt -9%; a heavy job on node 3 then costs
the model only 1.7%); pinning a heavy job to node 3 while the model spans all four nodes costs **71%**.


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
  covers ExpertFlow (NUMA/MoE execution), SpecDecode, and a design for an AI-driven kernel search loop.

## 2. Hardware and model facts (verified today)

| Fact | Value | How |
|---|---|---|
| CPU | AMD EPYC 7451 (Zen 1), 24 cores / 48 threads, AVX2+FMA, no AVX-512 | `lscpu`, earlier `server-inference.md` 1 |
| NUMA | 4 nodes, 6 cores + 6 SMT siblings each, distance 10 local / 16 remote | `numactl -H` |
| Memory | one dual-rank 32 GB DDR4 DIMM per die: each memory controller mc0-mc3 has exactly one populated channel (csrow 2+3) | `/sys/devices/system/edac/mc/mc*/rank*/dimm_location` |
| Theoretical bandwidth | 21.3 GB/s per channel at DDR4-2666 = 85 GB/s for 4 channels (DIMM speed not readable from the container) | AMD EPYC 7451 spec; estimate |
| Model | Qwen3.6-35B-A3B Q4_K_M (`qwen35moe`): 40 layers (30 Gated DeltaNet + 10 attention), 256 experts, 8 used per token | GGUF metadata |

Bytes the model must read per generated token (from the GGUF tensor table, `server/ramforge` script output):

| Part | Type | Size in file | Read per token |
|---|---|---|---|
| routed experts (`ffn_{gate,up,down}_exps`) | Q4_K | 18.12 GB | 8/256 = 0.57 GB |
| attention / DeltaNet projections, shared expert | Q8_0 | 1.50 GB | 1.50 GB (all) |
| output head (vocab 248,320) | Q6_K | 0.42 GB | 0.42 GB (all) |
| router, norms, conv | F32 | 0.09 GB | 0.09 GB |
| token embedding | Q4_K | 0.29 GB | one row |
| **total** | | 20.4 GB | **~2.57 GB** |

So **the dense part is 78% of the decode traffic and the experts only 22%**. "Hot-expert caching" can touch at most a
fifth of the bytes; the lever is where *all* weights sit relative to the cores that read them.

## 3. Prior art (what exists, what applies to this box)

- **llama.cpp mainline** (`--numa distribute|isolate|numactl`): pins threads evenly over nodes but does nothing about
  where weights live; mirror mode was planned in PR #5377 and removed before merge. `-ot/--override-tensor` places
  tensors on *devices* (CPU vs GPU buffer types), not on NUMA nodes, so it cannot express node placement.
  Sources: llama.cpp PR #5377; discussion #12289; issue #1437; `--numa` help.
- **Arm's cross-NUMA patch, llama.cpp PR #14232 (open, unmerged)**: splits each matmul's src0/dst into per-node
  segments moved with `move_pages()`, makes threads compute only their node's segment, adds a NUMA-aware two-level
  barrier; +32.7% tg / +50.8% pp (llama3-8B Q4_0, 2 nodes x 64 Neoverse N2 cores) and node bandwidth going from
  70.6+0.2 GB/s to 74.4+72.2 GB/s. Dense models only; this document's prototype applies the same idea to MoE expert
  slices and to the kernels this CPU actually uses.
  Sources: github.com/ggml-org/llama.cpp/pull/14232; Arm community blog "cross NUMA problem and optimization in
  llama.cpp ... Neoverse N2".
- **ik_llama.cpp** (fused MoE `-fmoe`, runtime repack `-rtr`, Qwen3.5/3.6 MTP): measured here earlier today on this
  box: +9% generation but -18% prompt, no prompt reuse for this hybrid model, 0.5 tok/s with 2 parallel streams, no
  router mode: rejected (docs/agents/brain-performance-20261013.md). A community `--numa mirror` fork of ik_llama.cpp
  duplicates all weights per socket (would need 4 x 20 GB here).
- **KTransformers** (SOSP'25): NUMA-aware CPU MoE: experts' GEMVs sliced along the output dimension and spread
  over the cores of each node, per-expert barriers instead of global ones. Its fast kernels are AMX/AVX-512; the AVX2
  path takes BF16/FP8/GPTQ-INT4/RAWINT4 (not GGUF Q4_K) and documents an NVIDIA GPU as a requirement: not runnable
  here, but its slicing scheme is the one prototyped below.
  Sources: madsys.cs.tsinghua.edu.cn KTransformers SOSP25 paper; lmsys.org/blog/2025-10-22-KTransformers;
  github.com/kvcache-ai/ktransformers doc/en/kt-kernel/AVX2-Tutorial.md.
- **AMD ZenDNN backend**: prompt processing (BF16/Q8, large batch, Zen 3+); token generation tracks the CPU backend:
  not relevant to Zen 1 decode. Source: amd.com "llama.cpp on AMD EPYC" (2026).
- **llama.cpp issue #19480**: DeltaNet (Qwen3-Next / Qwen3.5 family) CPU decode was slower than bandwidth math
  predicts; dedicated delta-net ops followed. Relevant because 30 of 40 layers here are DeltaNet: the op profile below
  checks how much of each token is not matmul.

## 4. Measurements (2026-10-14, server 1, container `starai`)

Method: `server/ramforge/run_lab.sh` (as user star), RAMForge build of b11541 (`build.sh`; behaves like the live
binary when no variable is set), same model file and live flags (`numactl --interleave=all`, `--numa distribute`,
`-t 24`, `-fa 1`, `-lm dio`). Every slice: live slots idle and <=2 busy cores for 40 s (`run_lab.sh quiet`), quiet lock
held (<=9.5 min), released, >=3 min gap. Afterwards the router journal was checked for live star-fast/star-voice tasks
inside each lock window: only one (a 34-s chat at 09:38Z, during A3-1's prompt phase); every other run is clean.

### 4.1 Bandwidth suite (`numa_bw`, 6 threads per node, 3 s each)

| Pattern | GB/s |
|---|---|
| one node reading its own memory (nodes 0-3) | 17.2-17.5 |
| one node reading another node's memory | 14.5-15.3 |
| all 24 cores, each reading its own node | 68.9-69.6 |
| all 24 cores, page-interleaved (what the live brain does) | 62.4 |
| all 24 cores, memory on one node | 16.1 |

### 4.2 llama-bench (pp512 / tg128, 3 repeats each; 3-node rows 2 repeats)

| Variant | runs | tg128 tok/s | vs A0 | pp512 tok/s |
|---|---|---|---|---|
| A0 baseline (live layout) | 3 | 9.58, 9.58, 9.65 (mean 9.60) | - | 63.7, 64.5, 64.6 |
| A2 BLOCK thread mapping only | 2 | 9.98, 9.92 | +3.6% | 65.9, 63.3 |
| **A1 BLOCK + PLACE** | 2 | **10.24, 10.19** | **+6.4%** | 65.0, 65.1 |
| A3 BLOCK + PLACE + two-level barrier | 1 | 10.22 | +6.5% (= A1) | 65.4 |
| A1 with dense weights only placed (first build, experts skipped by a bug) | 1 | 10.14 | +5.6% | 64.3 |
| N3 model on nodes 0-2, 18 threads, interleave | 2 | 8.89, 8.91 | -7.3% | 53.8, 53.6 |
| N3P nodes 0-2 + BLOCK + PLACE | 2 | 9.61, 9.51 | -0.4% | 54.5, 52.8 |
| N3P + heavy job on node 3 (6 threads streaming node 3) | 1 | 9.44 | -1.7% | 52.7 |
| A0 + the same heavy job on node 3 | 1 | **2.75** | **-71%** | 5.9 (pp64) |

Placement moves 18.73 GiB (4,804 MiB per node; every probed page on its intended node) in ~21.6 s at load.
The first A1 build skipped the expert tensors because CPU_REPACK buffers do not report `is_host`; fixed (the experts
are 22% of the per-token bytes, which matches the small extra gain from 10.14 to 10.22).

### 4.3 Server runs (`specbench.py`, temp llama-server on 127.0.0.1:8094, -np 1, ctx 32k, -tb 48, greedy, 8 prompts = 2,764 tokens)

| Variant | runs | gen tok/s | prompt tok/s | first token, median of 8 | greedy text = baseline |
|---|---|---|---|---|---|
| A0 baseline | 2 | 10.48, 10.52 | 61.1, 59.6 | 1.60, 1.70 s | 8/8 (reference) |
| **A1 BLOCK + PLACE** | 2 | **11.25, 11.13 (+6.6%)** | 60.9, 60.5 | 1.70, 1.63 s | **8/8, 8/8** |
| N3P (nodes 0-2, -t 18 -tb 36) | 2 | 10.15, 10.16 (-3.3%) | 54.1, 55.5 (-9%) | 1.79, 1.76 s | 3/8 (fewer threads changes rounding) |

### 4.4 Reading

- Decode is bandwidth-bound per node: local reads are 11% faster than interleaved ones in the raw suite, and placement
  turns that into +6.4-6.6% tokens/s (the rest of each token is non-matmul ops and barriers).
- The block mapping alone gives about half of the gain (threads that share a node's L3 and memory controller work on
  neighbouring rows); placement adds the rest.
- A heavy CPU job pinned to one node steals that node's cores from the model's 24 threads; every barrier then waits for
  the slowest thread, so the whole model slows by 71%. Background work belongs either off brain 1, at low priority
  without pinning (today's behaviour), or on node 3 only together with the 3-node model layout.


## 5. Later phase: an AlphaEvolve-style kernel search loop (design + step-0 prototype)

Prompted by AlphaEvolve (an LLM proposer + automatic evaluators found a 23% faster matmul kernel in Gemini, ~1%
of its training time), AlphaTensor, KernelBench, and the Sakana "AI CUDA Engineer" retraction (its kernels passed
the checker by reusing the reference's output buffer and other loopholes; independent replication dropped its
reported speedups from up to 100x to ~1x). Sources: deepmind.google blog "AlphaEvolve" (2025-05-14); METR
"Recent frontier models are reward hacking" (2025-06-05); EvoEngineer (arXiv 2510.03760); Kernel Contracts
(arXiv 2604.22032); TechCrunch / Sakana's own update on the walk-back.

**When it is worth it here.** Only where a kernel, not memory, is the limit. Measured with kernel_lab (step-0 table below): the shipped
AVX2 Q4_K gemv does 5.4-6.5 GB/s per core and six cores of one node already saturate that node's single DDR4
channel (16 GB/s; compute capacity ~35 GB/s). So today, and even more after NUMA-local placement, decode is
memory-bound per node and a faster dot product buys almost nothing for `star-fast` generation. Kernel search
becomes worth running for: prompt processing (compute-bound: 48 threads, 60-70 tok/s), the non-matmul DeltaNet
ops if the op profile shows they are a large share, a smaller-footprint quant format (fewer bytes per token
at equal quality, e.g. a Q8_0 replacement for the 1.5 GB dense part that decodes as fast as Q8_0), and on
brain 2 / other machines where cores, not channels, are scarce.

**Loop (all local, under the quiet lock, nothing ships without a human-reviewed PR):**
1. *Target*: one kernel signature from the live path (e.g. `ggml_gemv_q4_K_8x8_q8_K`, `ggml_vec_dot_q8_0_q8_0`,
   the repack `forward_mul_mat_id` tiling, the delta-net op, thread-to-node mapping).
2. *Propose*: a generator writes a variant from the shipped source (today `server/ramforge/cand_gen.py` applies
   hand-written mutations: software prefetch distance, next-row prefetch; an LLM proposer would edit the same
   extracted function). The proposer sees source and scores only, never the reference outputs or the harness.
3. *Compile* in an isolated directory (`-O3 -march=native`, same flags as ggml), reject on any warning about
   undefined behaviour.
4. *Check against frozen references* (`server/ramforge/kernel_lab.c`): inputs are generated from a fixed seed in
   the exact live formats (repacked `block_q4_Kx8`, `block_q8_K` activations); the reference is computed by ggml's
   portable `*_generic` C kernel *before* the candidate runs, kept in memory the candidate is never given, and the
   inputs are compared byte-for-byte after the candidate ran (catches in-place tricks). Tolerance = 4x the shipped
   AVX2 kernel's own deviation from the generic one (measured 4.8e-7 relative), floor 1e-5. Anti-cheat additions
   for the LLM phase: random shapes from the same shape class that the proposer never saw (Kernel Contracts'
   lesson), shuffled run order, fresh processes per candidate (no shared buffers with the reference), and a final
   end-to-end check: greedy decode of fixed prompts must give identical text to the unpatched binary.
5. *Benchmark*: hot (in cache, compute ceiling), cold (DRAM local to the core), node (all cores of one node
   streaming): the node number is what decode sees. Compare against the extracted-but-unmodified "copy" variant,
   not against the shipped binary (a separately compiled copy measured ~3% slower than the shipped kernel).
6. *Keep only measured wins*: >= 5% on the node benchmark in 3 alternating repeats, then an end-to-end llama-bench
   A/B under the lock, then the normal >10% / same-quality gate before any deployment.

**Step-0 prototype, measured 20:05-20:25Z while the release eval was running (contended):**

| Variant (q4_K_8x8 gemv, 2048-wide rows) | correct | hot GB/s/core | cold GB/s/core | one node, 6 cores |
|---|---|---|---|---|
| generic C (reference) | (ref) | 0.52 | 0.52 | 3.10 |
| shipped AVX2 | yes (4.8e-7) | 6.46-6.54 | 5.67-5.92 | 16.2-16.3 |
| copy (extracted, unmodified) | yes | 6.31 | 5.39 | 15.97 |
| + prefetch block b+1 | yes | 6.32 | 5.86 | 16.59 |
| + prefetch block b+2 | yes | 6.24 | 5.59 | 15.94 |
| + prefetch block b+4 | yes | 6.34 | 5.05 | 16.07 |
| + prefetch next 8-row group | yes | 6.38 | 5.72 | 16.80 |
| shipped Q8_0 vec_dot (dense layers) | - | 9.0-9.8 | 8.7-8.9 | - |

Reading: the harness works end to end (generate, compile, check, time), and as expected for a memory-bound
streaming kernel on Zen 1 none of the prefetch variants is a real win: all within run-to-run noise. Not deployed.

## 6. Not run (optional S6-S8 of the plan)

Speculative decoding on star-fast (S6-S7) and imatrix expert-routing statistics (S8) were not run in this round;
earlier measurements on this CPU already found speculative decoding slower for star-fast (server-inference.md 2.3).
