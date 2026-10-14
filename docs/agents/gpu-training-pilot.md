# gpu-training-pilot: W10 training pilot on the owner's RTX 3060 Ti (Claude, wave 2026-10-13, board item #69)

- Branch `star/gpu-training-pilot-20261013`, worktree `worktrees/gpu-training-pilot` (from origin/star/next 10cd008).
- Code: `server/training/gpu/` (common, eval_retrieval, gen_queries, build_pairs, train_embed, qlora_feasibility,
  deploy_embed_ft.sh), results `server/training/gpu/results/`, tests `tests/test_gpu_training_pilot.py`.
- Local only (not in git): `work/gpu/train/` = index copy, generated queries, pair sets, checkpoints, GGUF files,
  venv `tools-portable/train-venv` (uv, Python 3.12, torch 2.11+cu128, sentence-transformers 5.x, transformers 5.19).
- Owner authorised this PC's GPU for training today. Every run is interruptible (STOP files) and stops itself below
  6 GB free RAM. The 35B model is not loaded on this PC (see the honest note in the status log).

## Verdict (short)
- **Step 1 (embedding fine-tune): WIN on the PC, meets the W10a acceptance, ready for a guarded server A/B; not
  deployed.** Chosen model (A1, picked on dev as pre-registered), Q8_0 GGUF exactly as it would run in the brain:
  dev 27->30/30, held-out 36->37/40, golden prompts 14->18/25 (vector recall@5, vs the base GGUF that matches the
  server's own numbers). MRR golden 0.397->0.504, held-out 0.775->0.822. Caveat: n is small (sign test golden
  p=0.14, held-out p=0.5) and the strict variants show part of the held-out gain comes from the evaluation pages
  being covered by training queries (see table).
- **Step 2 (generator QLoRA): quality run NOT done, by the brief's own gate.** W3 has no result yet, and there is
  no rights-clean set of verified worked examples: night school's 136 examples answer practice-pool prompts that
  agents (Claude/Codex) wrote in this workspace, so they are excluded (provider terms). Done instead: a feasibility
  run that answers "does QLoRA fit on 8 GB": Qwen/Qwen3.5-2B yes (3.5 GB VRAM, 6.6 s per 8 examples); Gemma 4 E2B
  decoder fits in VRAM (6.9 GB) but needs ~11 GB host RAM for its per-layer embedding table and hits the 6 GB floor.

## Data provenance (rights-clean only; no Claude or ChatGPT output anywhere in training data)
| Origin | Rows (A2 set) | Written by | Licence |
|---|---|---|---|
| Passages (positives) | 3,805 chunks / 1,397 pages | Roblox Creator Docs (commit in index), Luau site | CC-BY-4.0 prose + MIT code; MIT |
| synthetic-question + synthetic-task | 7,252 queries (3,626 chunks) | Qwen3.5-9B Q4_K_M (unsloth/Qwen3.5-9B-GGUF of Qwen/Qwen3.5-9B) on the PC GPU; 12 rows by STAR star-fast (Qwen3.6-35B-A3B) | Apache-2.0 |
| doc2query-index | 821 | STAR star-quick on server 1 (JetBrains/Mellum2.1-12B-A2.5B-Thinking), study job, 2026-10-11 | Apache-2.0 |
- The generator prompt (gen_queries.py, version q-task-v1) shows the model ONLY the passage. The evaluation
  questions are used only as a filter: 31 generated queries too similar to an evaluation question (word Jaccard
  >= 0.5 or a shared 6-gram) were dropped. Every row carries provenance (generator, prompt hash, doc commit and
  licence, time). Manifests: `results/pairs-*.manifest.json`; data hashes: `results/data-sha256.txt`.
- The prompt templates are code (written by Claude); no Claude-written TEXT is a training input or target.
- Evaluation sets (not training): `server/knowledge/eval/{questions,heldout,golden-task-queries}.jsonl`.

## Configs, VRAM, time
- Base: unsloth/embeddinggemma-300m (ungated mirror of google/embeddinggemma-300m, Gemma licence; the brain runs
  ggml-org/embeddinggemma-300M-GGUF Q8_0). Our base conversion: 333,590,912 bytes vs deployed 333,590,944.
- Training (train_embed.py): CachedMultipleNegativesRankingLoss, batch 64 (mini-batch 8), NO_DUPLICATES sampler,
  1 epoch, lr 2e-5, linear schedule, 10 % warm-up, bf16 autocast, 8-bit AdamW, token-embedding table frozen
  (106.3M of 308M trainable), max_len 320. Peak VRAM 5.25 GB; ~6 s/step; A1 331 s, A2 444 s (127 steps).
  First attempt (full fp32 AdamW, all weights) peaked at 8.77 GB -> spilled into shared memory, 30 s/step: fixed.
- Interruption tested for real: A2 was killed at step 55 and resumed from checkpoint-50 to completion.
- Query generation: Qwen3.5-9B Q4_K_M, llama.cpp b11538, `-ngl 99 -np 6 -c 12288 --cache-ram 0 --ctx-checkpoints 0`,
  ~0.9 chunks/s (~6 GB VRAM). Without `--cache-ram 0` the server grew to 16.5 GB RAM and slowed to 0.55 chunks/s.
- Export: llama.cpp b11538 `convert_hf_to_gguf.py --sentence-transformers-dense-modules` + `llama-quantize Q8_0`.
  Two traps: transformers 5 saves no `tokenizer.model` (copy the base tokenizer files) and rewrites the rope keys in
  config.json (copy the base config.json; the architecture is unchanged). Exported file
  `work/gpu/train/gguf/embeddinggemma-300m-star-ft1-Q8_0.gguf`, 333,591,200 bytes,
  sha256 87794a6becd6b536a44ca49e7900149318834be775fdc2312b1434706b58e31e. GGUF vs fp32 vectors: cosine 0.9999.

## Metrics (vector recall@5; MRR@10 in brackets). PC, the service's own eval code with a local embedder.
| Model | dev 30 | held-out 40 | golden 25 | Notes |
|---|---|---|---|---|
| server (Q8, 2026-10-11 record) | 27 (0.770) | 35 (0.775) | 14 (0.382) | knowledge-study.md |
| base, Q8 GGUF on PC | 27 (0.770) | 36 (0.775) | 14 (0.397) | reference for the A/B |
| base, fp32 | 27 (0.753) | 35 (0.774) | 15 (0.398) | |
| **A1** 3,537 pairs, all pages | **30 (0.867)** | **37 (0.822)** | **18 (0.502)** | chosen on dev |
| A1, Q8 GGUF (deployable) | 30 (0.867) | 37 (0.822) | 18 (0.504) | vs base GGUF: held-out +2 -1, golden +6 -2 (p=0.14) |
| A2 8,073 pairs, all pages | 29 (0.839) | 36 (0.777) | 17 (0.424) | more steps, not better |
| B1 strict, 2,897 pairs | 29 (0.933) | 34 (0.794) | 18 (0.496) | no eval-answer page in training |
| B2 strict, 6,809 pairs | 29 (0.869) | 35 (0.788) | 15 (0.451) | |
- Hybrid mode (BM25 + vector RRF) gains less: A1 GGUF golden 13->16/25, held-out 34->34, dev 26->25.
- Reading: all four variants improve dev and MRR; golden r@5 rises in 3 of 4 (18, 17, 18, 15 vs 15 fp32 base);
  held-out stays within -1..+2. Differences between variants are 1-3 questions: noise-sized. A1 is the dev choice.
- Paired detail per question: `results/eval-*.json`; `python eval_retrieval.py --compare A.json B.json`.

## QLoRA feasibility (step 2 groundwork; NOT a quality result)
| Model (Apache-2.0) | Fits 8 GB? | Peak VRAM | Step (8 ex x 1024 tok) | Host RAM | Held-out loss |
|---|---|---|---|---|---|
| Qwen/Qwen3.5-2B, 4-bit NF4, LoRA r16 (10.9M) | yes, 30 steps | 3.53 GB | 6.6 s (no fla kernels) | ok (>= 12 GB free) | 2.69 -> 1.97 |
| google/gemma-4-E2B-it, decoder 4-bit, PLE/towers on CPU | VRAM yes | 6.93 GB | 15.7 s | stopped: free RAM 5.9 GB | 4.03 -> 3.78 (1 step) |
- Task was passage-recall SFT (synthetic question -> doc passage), only to measure fit/speed. No GGUF export or
  dev-suite evaluation was done for a generator. Gemma 4 E2B fix path: keep the 2.35B-parameter per-layer
  embedding table in bf16 on CPU (bitsandbytes offloads in fp32 = 9.4 GB), or train Qwen3.5-2B/4B instead.

## What it would take to deploy step 1 (prepared, NOT run)
`server/training/gpu/deploy_embed_ft.sh stage|embed|switch|rollback`: new router alias `star-embed-ft1` next to
`star-embed`; vectors stored under the new model name next to the old ones (embeddings PK = (text_sha, model)); the
knowledge service and the refresh job pick it via `STAR_EMBED_MODEL` (systemd drop-in). Rollback = remove the
drop-in + restart star-knowledge (old vectors untouched). Needs one star-brain restart (models.ini + --models-max)
in a quiet window and ~80 min of server CPU to embed 18,133 chunks (duty 0.5). Before switching, rerun
`python -m starkb eval` on the server with the new vectors; expect dev 30/30.

## Next steps (for whoever resumes)
1. Owner/lead decision on the server A/B (stage -> embed -> eval -> switch). Also run night school's retrieval on it.
2. More golden-style prompts (25 is small) before claiming significance; the eval-gate-v2 paired method applies.
3. Step 2 needs rights-clean verified examples first: tasks written by STAR's own models (e.g. the 3,600 synthetic
   "task" queries here) + answers by STAR + tests/Luau checks as the verifier, then QLoRA Qwen3.5-2B/4B vs base+RAG.

## Status log
- 11:20Z started; brief read; claim + worktree created.
- 11:25Z facts: brain embedding model = EmbeddingGemma-300M Q8_0 (ggml-org/embeddinggemma-300M-GGUF), models.ini
  [star-embed]. Base weights for training: unsloth/embeddinggemma-300m (ungated mirror, Gemma licence; google/ is gated).
  Index copied from server 1 (kb.sqlite3, 18,133 chunks) to work/gpu/train/data/ (read-only copy via sqlite backup).
- 11:30Z PC eval path reproduces the server (base model, fp32, local): dev vector 27/30, held-out 35/40, golden 15/25
  (server Q8 had 14/25). Scripts: server/training/gpu/{common,eval_retrieval,gen_queries,build_pairs,train_embed}.py.
- 11:35Z star-fast (35B-A3B) on the PC generates only ~0.05 chunks/s -> switched the query generator to
  Qwen3.5-9B Q4_K_M (unsloth/Qwen3.5-9B-GGUF, Apache-2.0) fully on GPU, -np 6: ~0.5 chunks/s.
  Running in background: work/gpu/train/gen-q9.log -> data/queries-q9.jsonl (3600 chunks, stop: work/gpu/train/STOP-GEN).
- Provenance note: practice-pool task prompts (and so night school's 136 worked examples' PROMPTS) were written in
  this workspace by Claude/Codex agents -> NOT used for training here (provider terms). Answers are STAR's own.
- 11:55Z GGUF path checked: llama.cpp b11538 source (same build as work/gpu/engine) convert_hf_to_gguf.py
  --sentence-transformers-dense-modules + llama-quantize Q8_0 on the BASE model -> 333,590,912 bytes (deployed file
  333,590,944); its vectors vs sentence-transformers fp32: cosine 0.99985. So a fine-tuned model can be exported the same way.
- 12:00Z generator parser fixed (Qwen3.5-9B sometimes drops the closing brace: 22 % of rows were lost); resume retries
  failed rows. tests/test_gpu_training_pilot.py (4 tests) passes. deploy_embed_ft.sh written (NOT run).
- PRE-REGISTERED (12:05Z, before any fine-tuned result): configs are chosen on the 30 dev questions only (vector
  r@5, then MRR@10; tie -> less training). Held-out 40 + golden 25 are reported for every config tried, but the
  verdict uses the dev-chosen one. W10a acceptance (design doc): held-out vector r@5 >= 35/40 AND golden vector
  r@5 >= 17/25 (PC baseline 35/40, 15/25; server 35/40, 14/25). Paired view: wins/losses at rank 5 + exact
  one-sided sign test. Generalisation check: strict variant B trained WITHOUT any page that is an expected answer
  of an evaluation question (140 pages).
- 12:40Z RAM incident (lead's 6 GB floor message): the Qwen3.5-9B llama-server grew to 16.5 GB private RAM (llama.cpp
  host prompt cache --cache-ram default 8 GB + context checkpoints); free RAM was 3.3 GB. Stopped it (free RAM back to
  18 GB). Restart flags now: --cache-ram 0 --ctx-checkpoints 0. gen_queries.py and train_embed.py stop cleanly below
  6 GB free (STAR_TRAIN_RAM_FLOOR_GB). Honest note: before the lead's rule arrived, star-fast (35B) was loaded on the
  PC once for ~3 minutes (6-chunk speed test, 11:33Z), then stopped. It will not be loaded again.
- Trainer: full fp32 + AdamW spilled past 8 GB (8.77 GB peak, 30 s/step). Fixed: 8-bit AdamW + frozen token-embedding
  table (106.3M of 308M trainable), max_len 320 -> peak 5.25 GB, ~6 s/step.
- 12:55Z RESULT A1 (3,537 pairs / 1,600 chunks, 1 epoch, lr 2e-5, batch 64, 331 s): vector r@5 dev 27->30/30,
  held-out 35->37/40 (+3 -1), golden 15->18/25 (+5 -2, sign p=0.23); MRR held-out 0.774->0.822, golden 0.398->0.502.
  Meets W10a (>=35/40 and >=17/25) on the PC. Strict B1 (2,897 pairs, no eval-answer pages): dev 29/30, held-out
  34/40 (+1 -2), golden 18/25 (+5 -2): the golden gain generalises to unseen pages; the held-out gain does not.
- 13:45Z A2/B2 (full 3,626-chunk generation) trained + evaluated: not better than A1 (table). A1 exported to GGUF,
  end-to-end GGUF eval on the PC GPU equals the fp32 result; base GGUF reproduces the server's dev/golden numbers.
- 14:30Z QLoRA feasibility: Gemma 4 E2B (two failed attempts: LoRA hit vision-tower layers; fp32 upcast spilled,
  RAM floor stopped it; third: VRAM ok, host RAM floor stopped it at step 1). Qwen3.5-2B: 30 steps OK.
- 14:45Z writing this doc; next: full pytest, star commit, push, draft PR to star/next, claim done, message.


## Post-pilot pair integrity checks (future builds; not a reproduction of W10)

New calls to `build_pairs.py` validate every indexed alias of a passage hash,
rather than trusting one arbitrary `GROUP BY` row. In strict mode, an eval
expected-answer page excludes the entire shared content hash, including aliases
under non-evaluation paths. Query sampling with `--exclude-paths` also excludes
every matching hash. A passage is rejected if any indexed source for its hash
lacks a declared repository, commit or explicitly supported documentation
licence (MIT or CC-BY-4.0). Synthetic and indexed questions require a declared
local-model generator and an explicit false third-party-generation flag;
contradictory declarations are dropped and counted in the generated manifest.
These declarations are **not independent proof** of source identity, licences,
model origin or rights. Unknown documents and models require review before
expanding the allowlists.

The previously committed W10 pair manifests, model runs, evaluation JSON and
reported measurements remain unchanged. This regression fixture demonstrates
forward fail-closed decisions on synthetic SQLite indexes; it does **not**
recreate or authenticate the original GPU training, and the historical W10
numbers have not been rerun under these stricter rules.
