# apprentice-model: STAR trains its own fast apprentice (Claude, 2026-10-16, board item #157)

Owner-approved idea: night school's verified worked examples train a small model on the PC's RTX 3060 Ti (8 GB); the
apprentice answers common Roblox tasks fast and the big model checks it. Branch `star/apprentice-model-20261016`,
worktree `worktrees/apprentice` (from origin/star/next 48c21bc8). Code `server/training/apprentice/`, test
`tests/test_apprentice_dataset.py`. Local only (not in git): `work/apprentice/` (2.7 GB after clean-up: base GGUF
2.4 GB, adapters, data copies, answers, scores). Venv reused: `tools-portable/train-venv` (torch 2.11+cu128,
transformers 5.19, peft 0.21, bitsandbytes 0.50). Nothing is switched on anywhere.

## Verdict (short)
- **Too little data for a useful apprentice.** 219 verified examples exist (server 1: 206, server 2: 13) -> 154 train
  / 10 validation after dedupe and the held-out slice. A useful specialist needs roughly **1,000+ verified examples**
  spread over the hand-written task families (about 6-7x today; at night school's ~50 new examples per day that is
  ~2-3 weeks).
- Even so, the pilot apprentice (Qwen3-4B-Instruct-2507 + LoRA, 1 epoch) beat its own base on the held-out slice:
  **43/117 vs 35/117** (20 wins / 12 losses, sign test p=0.11, NOT significant). The gain is all on the generated
  "ledger" tasks (14 -> 26 of 57); on hand-written practice tasks it got WORSE (21 -> 17 of 60). It learned the
  ledger style, not Roblox in general.
- star-fast is still clearly better: on the 42 tasks all three answered, **star-fast 23/42, apprentice 18/42, base
  11/42** (apprentice vs star-fast 5 wins / 10 losses, p=0.30 two-sided).
- Speed: apprentice **62 tok/s** on the PC (base 4B model with the LoRA applied at run time; the plain base runs
  96-98 tok/s, a merged apprentice should run at that speed, NOT measured), median 7.8 s per answer, vs star-fast on
  server 1 at 6.5 tok/s median, 72 s per answer (contended; RAMForge measured 10.5-11.2 tok/s quiet).
- **Route "apprentice answers, big model checks": NOT justified, not built.** The only check the app has at answer
  time is the Luau compile/type check; 49 of the apprentice's 74 failing answers pass a compile-only gate (they fail
  unit tests or required-API checks), so a compile-gated cascade would ship ~1 wrong answer for each right one.
  Revisit when (a) 1,000+ examples exist and (b) the apprentice is significantly better than base on the
  hand-written tasks, and (c) a stronger answer-time check exists (e.g. generated unit tests run in the Luau VM).

## Data (step 1) - `build_dataset.py`
| | count |
|---|---|
| verified rows read (s1 examples.jsonl 206, s2 13) | 219 |
| golden / holdout | 0 (golden ids + prompt hashes and the pool guard applied; `holdout-v1.json` never opened, any path with "holdout" is refused) |
| duplicate task (s1/s2 overlap; newest kept) | 8 |
| duplicate answer | 2 |
| in the measuring slice (never trained) | 45 |
| **train / validation** | **154 / 10** (65 categories) |
| measuring slice (20 % of ALL 632 pool tasks by id hash, solved or not) | 117 |
- Target = the model's own text: STAR's footer (Luau-check note, sources list) is cut with `eval_checks.split_answer`.
- Token lengths (Qwen3 template): median 782, p90 1,456, max 1,841 (none truncated at 3,072).
- Provenance: answers by STAR's own models in night school (star-fast = Qwen3.6-35B-A3B, Apache-2.0; server 2 Gemma 4
  E2B); every answer passed the app's automatic checks; task prompts come from the practice pool (written by agents
  in this workspace, plus generated ledger tasks). The 2026-10-13 GPU pilot excluded these examples for that
  reason; this run uses them because the owner approved it (lead brief). Prompts are masked out of the loss.
- `manifest.json` (local) records counts, sha256 of the source files and the system prompt.

## Model choice (screening, by evidence)
Base Q4_K_M GGUFs, single shot, greedy, thinking off, 24 tasks from the TRAIN side (never the measuring slice),
scored with night school's checks on server 1:
| model (licence) | passed | gen tok/s (3060 Ti) |
|---|---|---|
| **Qwen3-4B-Instruct-2507 (Apache-2.0)** | **13/24** | 96 |
| Qwen3.5-4B (Apache-2.0) | 9/24 | 85 |
| Qwen2.5-Coder-1.5B-Instruct (Apache-2.0) | 5/24 | 183 |
| Qwen3.5-2B (Apache-2.0) | 1/24 (5 ran to the token limit) | 158 |
Qwen2.5-Coder-3B (research licence) and 7B class (15 GB weights, disk) were not tried. Downloads: 4 GGUFs 7.6 GB
(unsloth / Qwen repos, pinned revisions in the logs) + HF weights of Qwen3-4B-Instruct-2507 7.6 GB (rev cdbee75f);
all but the chosen Q4_K_M GGUF deleted again after the lead's disk warning.

## Training (step 2) - `train_qlora.py`
- QLoRA: NF4 4-bit base, LoRA r16/alpha 32 on q/k/v/o/gate/up/down (33.0M trainable), lr 1e-4 cosine, batch 1 x
  accum 8, loss on answer tokens only, chat template with thinking off. Owner guard: refuses to start when the GPU is
  busy, stops (saving the adapter) when a game uses CPU, free RAM is below `--ram-floor`, or STOP-TRAIN exists.
- Run a2 epoch 1: val loss 1.302 -> **0.796**, train loss 0.978, 1,062 s, peak 6.46 GB VRAM. Epoch 2 stopped twice:
  RAM floor (the full 8 GB card spills into shared system memory under WDDM; `torch.cuda.empty_cache()` per step
  added) and then CUDA out of memory on resume while the owner was using the PC. The HF weights were then deleted
  (disk), so no further epochs. Evaluated adapter = epoch 1 (best and only full epoch).
- Export: llama.cpp `convert_lora_to_gguf.py` (b11538 source) -> `work/apprentice/lora/apprentice-a2-e1.gguf`
  (f16, 66 MB); served by the CUDA build in work/gpu-test/cuda: `llama-server -m Qwen3-4B-Instruct-2507-Q4_K_M.gguf
  --lora apprentice-a2-e1.gguf -ngl 99 -c 8192 -fa on --jinja --reasoning off`. Outputs differ from the base on
  117/117 tasks (adapter confirmed active). 11/117 apprentice answers ran to the 2,048-token limit (base 0).

## Measurement (step 3) - `gen_answers.py`, `score_answers.py`, `compare.py`
Same system prompt, greedy, thinking off, single shot for every arm (no STAR pipeline, no docs search, no repair).
Scored inside the server 1 container with night school's own `RealModel.score` (pool loader + unit tests +
knowledge-service Luau check + sandboxed Luau VM); sanity: 5 known-good examples passed, an empty answer failed.
| arm | 117-task slice | 42 common tasks | gen tok/s (median) | s/answer |
|---|---|---|---|---|
| apprentice (4B + LoRA, PC) | 43 (36.8 %, CI 29-46 %) | 18 | 62 | 7.8 |
| base Qwen3-4B-2507 Q4_K_M (PC) | 35 (29.9 %, CI 22-39 %) | 11 | 96-98 | 3.8-4.0 |
| star-fast (server 1) | - | 23 | 6.5 (contended) | 72 |
- star-fast answered only the first 42 of 60 planned tasks: it shares server 1 with other sessions' quiet locks.
  MISTAKE: from ~02:15Z to 03:25Z my star-fast requests ran without checking /opt/star/lock while another session
  held it (message #320 posted); after that a lock-aware loop (`star_fast_resume.sh`, local) waited for every lock.
- First failing check, apprentice / base: unit tests 27 / 36, required API 22 / 33, Luau compile 15 / 13, no code
  block 10 / 0.

## Re-run (commands, from work/apprentice)
`python build_dataset.py --examples raw/s1/data/examples.jsonl raw/s2/data/examples.jsonl --pool raw/s1/pool --out data`;
`train_qlora.py --model <hf dir> --data data --out runs/X --epochs 3`; `convert_lora_to_gguf.py --base <hf dir>
--outtype f16 --outfile lora/X.gguf runs/X/epoch-N`; `run_arm.sh <gguf> <arm> data/measure.json answers/X.jsonl
[--lora ...]`; `score_remote.sh score/X.jsonl answers/X.jsonl` (check the quiet lock first); `compare.py`.

## Status log
- 02:10Z claimed; data copied read-only from server 1 (`/opt/star/learning/{data,outbox,pool}`) and server 2 (data).
- 02:20-02:40Z screening; 02:45-03:15Z base slice; 02:46Z training a1 stopped at the 6 GB RAM floor; 02:47-03:05Z
  a2 epoch 1; 03:15-03:35Z apprentice slice; 03:38Z resume of epochs 2-3 failed (CUDA OOM); 04:08Z star-fast stopped
  at 42 tasks. Lead disk warning: deleted my screening GGUFs, HF shards, partial adapters; work/apprentice = 2.7 GB.
- Scorer files left on server 1 in /opt/star/learning/apprentice/ (scripts + answer copies, < 2 MB).
