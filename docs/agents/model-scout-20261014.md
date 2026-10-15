# Model scout 2026-10-14: a better star-fast for brain 1? (Claude)

Brief: lead task "model scout" (research + test plan only), rules docs/agents/WAVE-20261013-BRIEF.md.
Board item #130, branch `star/model-scout-20261014`, worktree `worktrees/model-scout` (from origin/star/next a71f1dac).
**Nothing was downloaded to a server, no server was touched, no eval was run** (RAMForge is timing brain 1).

## 0. Answer in short

- **Bytes per token, not parameter count, set the speed on brain 1, and the current file is not the fastest packing of
  this model.** In the live file (ggml-org Q4_K_M) the always-read dense part (DeltaNet/attention projections,
  shared expert) is stored as Q8_0: 1.59 of the 2.57 GB read per token. The experts are only 0.57 GB. So:
  - higher-precision **experts** cost little: a Q6_K file with Q6_K dense layers reads *less* per token than today
    (lmstudio-community Q6_K: 2.49 GB, est. 10.7 tok/s), and even Q8_0 everywhere is only about 20% slower (est. 8.4);
  - a standard-recipe Q4_K_M (dense layers in Q4_K/Q6_K) reads 1.98 GB per token, so about **+30% generation speed
    (est. 13.5 tok/s)**. The cost is lower precision in the dense layers.
- **Same speed, possibly better answers:** Ornith-1.5-35B-A3B (MIT) is the same `qwen35moe` architecture (llama.cpp
  b11541 already runs it), fine-tuned. Its makers report SWE-bench Verified 79.0 vs 73.4, SWE-bench Pro 59.6 vs 49.5,
  Terminal-Bench 2.1 67.8 vs 52.5 against Qwen3.6-35B-A3B. The catch: all of those numbers come from Ornith, all were
  run with thinking on, and STAR runs with thinking off. The Ornith-1.5-9B sibling did worse on our Luau checks on 2026-10-10.
- **A bigger model is not a faster or clearly better star-fast.** The candidates that fit 60-80 GB with 6-8B active
  parameters (Laguna S 2.1, Qwen3.8-Flash-Next, Mistral Small 4) read 4-7 GB per token, about 4-6 tok/s. That is
  star-deep's speed class, not star-fast's. Qwen3.8-Flash-Next does not fit at all (72.5 GB at 1 bit, because of its
  51B n-gram table).
- **Speculative decoding is not a lever for this target on this CPU.** It was measured slower here (MTP and DFlash,
  -12% to -58% on prose, at best +3% on code). The router does support per-preset draft models (star-deep uses one).
  RAMForge's S6-S7 slices are the right place to re-check it. No new draft model is recommended.

**Shortlist** (section 3): cand1 Ornith-1.5-35B-A3B Q6_K (quality bet, same speed) · cand2 Qwen3.6-35B-A3B Q6_K
(lmstudio-community: better experts at the same speed) · cand3 Qwen3.6-35B-A3B Q4_K_M (lmstudio-community: about +30%
speed, quality must hold). Reserve: K2-Horizon-MoVA-36B-A4B (Apache-2.0, best third-party index score in class, but
no vision, built to think first, est. 20% slower).

## 1. Method

- **Bytes read per generated token**, from each GGUF's own tensor table. A small script read only the header of each
  remote file over HTTP Range (8-16 MB, held in memory, nothing saved). It sums the always-read tensors (dense layers,
  shared expert, output head), adds `used/total` of the routed-expert tensors, and counts one embedding row as zero.
  Check: for the live file it gives 2.569 GB, exactly RAMForge's own figure (docs/research/ramforge-expertflow.md on
  star/ramforge-20261013). For Ornith, the 20 tensors of the built-in MTP block (`blk.40.nextn`, not run without
  speculation) are taken out. For K2 Horizon, the value experts count as 4/64 instead of the script's 8/100.
- **Estimated tok/s = 10.4 × 2.569 / bytes-per-token.** 10.4 is today's measured single-stream speed (validate.py
  10.33-10.48, brain-performance-20261013). Generation is bandwidth-bound: about 87% of the box's STREAM figure is
  already used (RAMForge). These are **estimates, ±15%**:
  - proportional scaling overstates the gain for lighter files, because the fixed per-token sync overhead stays;
  - it overstates the loss for heavier ones;
  - 48-layer models (K2, Laguna) pay more per-token overhead than the 40-layer Qwen, so their estimates are optimistic.
  Stage A of the plan measures the real number in 10 minutes per candidate.
- **llama.cpp support** was checked against the live build b11541 (published 2026-10-10, commit f2918cab). The
  GitHub compare API shows b11541 "ahead" of each support PR's merge commit, so each architecture is in the live build.
- **Licences, benchmarks, sizes and checksums** come from the Hugging Face model cards and the `/api/models/.../tree`
  listings (LFS sha256), read 2026-10-14. Revisions are pinned in section 5.

## 2. Ranked table

Speed column: estimate unless marked measured. "Vendor" = the maker's own numbers. Qwen3.6 reference scores (vendor
card): SWE-bench Verified 73.4, SWE-bench Pro 49.5, SWE-bench Multilingual 67.2, Terminal-Bench 2.0 51.5.

| # | Model, quant (repo) | File GB | Active | GB read / token | Est. tok/s | Quality evidence | Licence | llama.cpp b11541 |
|---|---|---|---|---|---|---|---|---|
| 1 | **Ornith-1.5-35B-A3B Q6_K** (ornith-ai) | 29.2 | 3B | 2.49 | **10.7** | Vendor, thinking on, avg of 5: SWE-V 79.0, SWE-Pro 59.6, SWE-ML 71.4, TB2.1 67.8/68.5 (Qwen3.6 on the same card: 73.4/49.5/67.2/52.5). No third-party confirmation (BenchLM: "not enough sourced coverage"). Ornith-1.5-9B failed our Luau compile checks (server-inference.md 4.2.3). | MIT | yes (`qwen35moe`, same as live) |
| 2 | **Qwen3.6-35B-A3B Q6_K** (lmstudio-community) | 28.5 | 3B | 2.49 | **10.7** | Same model. Experts Q4_K → Q6_K, dense Q8_0 → Q6_K. Published KL vs BF16 (mudler, wikitext): Q8_0 0.0059, UD-Q5_K_XL 0.0083, UD-Q4_K_M 0.0138; PPL 6.720 / 6.725 / 6.736 (BF16 6.722). localbench: tool calling is this model's most quant-sensitive category. | Apache-2.0 | yes |
| 3 | **Qwen3.6-35B-A3B Q4_K_M** (lmstudio-community) | 21.2 | 3B | 1.98 | **13.5** (+30%) | Same model. Experts like today (Q4_K, some Q6_K), dense Q8_0 → Q4_K/Q6_K: lower precision exactly where most of the per-token traffic is. localbench: lmstudio-community quants never on the KL Pareto frontier. Quality must be shown, not assumed. | Apache-2.0 | yes |
| 4 | Ornith-1.5-35B-A3B Q4_K_M (ornith-ai) | 21.7 | 3B | 1.98 | 13.5 | As #1, with the #3 trade-off (Q4_K dense). The obvious follow-up if #1 and #3 both pass. | MIT | yes |
| 5 | Qwen3.6-35B-A3B Q4_K_M (ggml-org, **live**) | 20.4 | 3B | 2.57 | **10.4 measured** | reference | Apache-2.0 | live |
| 6 | Qwen3.6-35B-A3B Q5_K_M (bartowski) | 25.9 | 3B | 2.58 | 10.4 | Q5_K experts, mixed dense (Q8_0/BF16/Q5_K). An alternative to #2. | Apache-2.0 | yes |
| 7 | Qwen3.6-35B-A3B UD-Q5_K_XL (unsloth) | 26.6 | 3B | 2.89 | 9.3 | KL 0.0083 (above). Dense kept Q8_0, so slower than #2. | Apache-2.0 | yes |
| 8 | Qwen3.6-35B-A3B UD-Q6_K (unsloth) | 29.3 | 3B | 2.97 | 9.0 | Near-lossless; dense Q8_0. | Apache-2.0 | yes |
| 9 | Qwen3.6-35B-A3B Q8_0 (ggml-org) | 36.9 | 3B | 3.20 | 8.4 | KL 0.0059 (mudler), 0.069 (localbench, other method). Best precision, -20% speed. | Apache-2.0 | yes |
| 10 | K2-Horizon-MoVA-36B-A4B Q4_K_M (IFM) | 22.4 | ~4B (5.95B incl. embeddings) | ~3.30 | 8.1 (likely lower: 48 layers) | Artificial Analysis Intelligence Index **25 vs 18** for Qwen3.6-35B-A3B (both reasoning mode). IFM card, AA-run: TB2.1 58.6 vs 44.9, tau3-Banking 26.8 vs 9.3, GPQA 80.8 vs 84.1. Text only. Thinking-first (vendor recommends high effort). Non-thinking works (empty think block in its template) but is untested. | Apache-2.0 | yes (PR #29535, merged 2026-10-06). Open: reasoning parser at low/medium effort (#30246, fix PR #30335 unmerged) |
| 11 | K2-Horizon-MoVA-36B-A4B Q6_K (IFM) | 30.8 | ~4B | ~4.4 | ~6.0 | as #10 | Apache-2.0 | yes |
| 12 | Laguna S 2.1 UD-IQ4_XS (unsloth) | 57.6 | 8B | 6.05 | 4.4 | Vendor: TB2.1 70.2, SWE-ML 78.5, SWE-Pro 59.4. Thinking recommended. star-deep class (Qwen3.8-27B: SWE-Pro 61.7, TB2.1 73.0, 4-5.5 tok/s with MTP), not star-fast. | OpenMDW-1.1 | yes (PR #25165, merged 2026-07-22). Prompt reuse needs `--swa-full` (thread report) |
| 13 | Laguna S 2.1 UD-Q4_K_XL (unsloth) | 73.4 | 8B | 6.74 | 4.0 | as #12 | OpenMDW-1.1 | yes |
| 14 | Qwen3.8-Flash-Next UD-IQ1_S … UD-Q4_K_XL (unsloth) | 72.5-111 | 6B (+51B n-gram table, +4B MTP) | not read (est. 3.5-4) | ~6-7 | Card: SWE-Pro 62.5, LiveCodeBench v6 91.9, SWE-ML 81.0. **Does not fit** the 60-80 GB budget except at 1-2 bit. | qwen-community-1.0 | yes (PR #27742, merged 2026-08-27). MTP PR #28243 closed unmerged |
| 15 | Qwen3-Coder-Next 80B-A3B (Q4_K_M ~48 GB, est.) | ~48 | 3B | not read | ~9-10 | Card: SWE-V 70.6, SWE-Pro 44.3, TB2.0 36.2: below Qwen3.6. No vision, no thinking. | Apache-2.0 | yes (qwen3next) |
| - | Others checked, not pursued | | | | | Laguna XS 2.1 33B-A3B (SWE-ML 63.1 < 67.2), Nemotron 3.5 Lightning 31.6B-A3.6B (SWE-V 51.6), gpt-oss-120b (older, lower SWE-V), Mistral Small 4 119B-A6.5B and Nemotron 3 Super 120B-A12B (star-deep speed class, no coding edge shown), Gemma 4 26B-A4B (SWE-V 17.4 on the Qwen card). No Luau/Roblox benchmark exists for any of these; our own eval is the only Luau evidence. | | |

**What the table supports, and no more:**
- Only #1-#4 are realistic star-fast replacements: same architecture, same 248K-token tokenizer, same router
  config, and at least today's speed.
- #2 and #3 are packing choices for the same weights. Their quality difference from today is small in published
  KL terms. It is very likely below what our eval can resolve: 57 tasks × k=2 needs about +9 tasks (section 4.4).
- #1 is the only candidate with a large claimed quality gain at no speed cost. Every gain claim comes from its
  maker, measured with thinking on.

## 3. Shortlist (2-3) and expected gains

1. **cand1: Ornith-1.5-35B-A3B Q6_K.** Speed same as today (est. 10.7 tok/s, ±15%). Quality: maybe better on
   agentic/repo coding if the vendor numbers carry over to thinking-off Luau answers. Two reasons for doubt: they come
   from the maker only, and the 9B sibling was worse on Luau. Vision via its own mmproj (BF16, 0.9 GB). RAM +9 GB
   over today's star-fast file.
2. **cand2: Qwen3.6-35B-A3B Q6_K (lmstudio-community).** Speed same (est. 10.7). Quality: a small, real precision
   gain on the experts. Expect the gate to say INCONCLUSIVE, which means "not worse" at our resolution. Lowest risk.
   It isolates the quant effect from the fine-tune effect in cand1. RAM +8 GB.
3. **cand3: Qwen3.6-35B-A3B Q4_K_M (lmstudio-community).** Speed est. **13.5 tok/s (+30%)**. This is the speed
   bet, and it fits the owner's current speed focus. It compounds with RAMForge's NUMA placement if that lands. Risk:
   Q4_K in the DeltaNet/attention projections. Our gate can only rule out a large loss (section 4.4). RAM -1 GB.

Reserve: K2-Horizon-MoVA-36B-A4B Q4_K_M. Test only if cand1 fails and the lead accepts a text-only, thinking-first
model at about 8 tok/s or less. If cand1 and cand3 both pass, try Ornith Q4_K_M (#4).

## 4. Test plan (STAR's eval gate)

Preconditions: RAMForge finished and its quiet lock released. Lead OK for one router restart, which adds the presets
(1-3 min of brain downtime). star-deep stays unloaded. Test one candidate at a time. RAM: the router uses about 46 GB
today plus up to 24 GB of star-fast prompt cache. A 30 GB candidate plus 4 GB of cache fits in the rest. Two
candidates at once do not fit safely.

### 4.0 Disk and space check, then download (inside the starai container, as user `star`)

From the PC: `ssh <user>@<brain1-host>`, then `lxc exec starai -- su - star`. The real host is in CLAUDE.md, never in git.

```bash
set -u
df -h /opt/star/models; free -g; test -e /opt/star/lock && echo "QUIET LOCK HELD: do not download now"
command -v hf >/dev/null || python3 -m pip install --user --upgrade "huggingface_hub[cli]>=0.34"   # gives `hf`
# dl <repo> <revision> <file> <dir under /opt/star/models> <sha256> <bytes>
dl() {
  local repo=$1 rev=$2 file=$3 dir=/opt/star/models/$4 sum=$5 bytes=$6
  local need=$(( bytes / 1000000000 + 25 ))                     # file + 25 GB margin
  local free=$(df --output=avail -BG /opt/star/models | tail -1 | tr -dc 0-9)
  [ "$free" -ge "$need" ] || { echo "STOP: ${free}G free, need ${need}G for $file"; return 1; }
  mkdir -p "$dir"
  if command -v hf >/dev/null; then
    nice -n 10 ionice -c3 hf download "$repo" "$file" --revision "$rev" --local-dir "$dir" || return 1
  else  # fallback = the pattern of server/setup/05-download-models.sh, pinned to the revision
    nice -n 10 ionice -c3 curl -sS -fL --retry 5 -C - -o "$dir/$file.part" \
      "https://huggingface.co/$repo/resolve/$rev/$file" && mv "$dir/$file.part" "$dir/$file" || return 1
  fi
  echo "$sum  $dir/$file" | sha256sum -c - || { echo "CHECKSUM MISMATCH: deleting"; rm -f "$dir/$file"; return 1; }
  # drop the file from the page cache: a 30 GB cached copy fills NUMA nodes and spoils the next model's interleave
  python3 -c 'import os,sys; fd=os.open(sys.argv[1],os.O_RDONLY); os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)' "$dir/$file"
}
# cand1 (29.2 GB + 0.9 GB mmproj)
dl ornith-ai/Ornith-1.5-35B-A3B-GGUF 12393612fd4f730ff5aadc23e9b8f9648aa49ceb Ornith-1.5-35B-Q6_K.gguf \
   ornith-1.5-35b-a3b 15d4658bbfc9c6034621729c15bbb50662c82b32a7ddd9624a1e545a74bdbb4b 29208731392
dl ornith-ai/Ornith-1.5-35B-A3B-GGUF 12393612fd4f730ff5aadc23e9b8f9648aa49ceb mmproj-Ornith-1.5-35B-BF16.gguf \
   ornith-1.5-35b-a3b 1921a36a85aee56cd2abd27f46701802c9d85a33474792e600df6c3b282a135d 902822240
# cand2 (28.5 GB)
dl lmstudio-community/Qwen3.6-35B-A3B-GGUF 68a34855558af61cbef0324d31f411be8a506b08 Qwen3.6-35B-A3B-Q6_K.gguf \
   qwen3.6-35b-a3b-lms a9708027db6e4f1ea44790e4e650068935384b71f2af46dbee213da3e060e0f3 28514152288
# cand3 (21.2 GB)
dl lmstudio-community/Qwen3.6-35B-A3B-GGUF 68a34855558af61cbef0324d31f411be8a506b08 Qwen3.6-35B-A3B-Q4_K_M.gguf \
   qwen3.6-35b-a3b-lms 4ac6a06bce551257267f49ad2226f8671a22519ccc1a4dde9d5b433d1f2a410d 21166757728
# reserve (22.4 GB): IFM/K2-Horizon-MoVA-36B-A4B-GGUF b318d1343a9460b05b0e04984fdd268cc5ef647c
#   K2-Horizon-MoVA-36B-A4B-Q4_K_M.gguf k2-horizon-36b-a4b 513dd78590ac29135a7cea5a99865d57d65291b1f857a8904fb9b1878d4f4cbd 22368011616
df -h /opt/star/models
```

All three candidates together need about 80 GB. If `df` shows less than that plus 25 GB, download and test one at a
time and delete each rejected file before the next download. cand2 and cand3 reuse the live
`mmproj-Qwen3.6-35B-A3B-Q8_0.gguf` (same base weights).

### 4.1 models.ini presets (new sections; star-fast is not touched)

Put these on a branch (from star/next, so the rest of the file matches the live one). Apply them with the existing
`server/brain/apply.sh`: it takes the lock, backs up, restarts and rolls back by itself if a startup model fails. The
router reads presets only at start, so add every preset whose file is already downloaded in one restart. Never add a
preset whose file is missing. Do not merge these into star/next unless one is adopted.

```ini
; TEST ONLY (model-scout-20261014). Loaded on first request, never at start; unload after each test.
[star-fast-cand1]
; Ornith-1.5-35B-A3B Q6_K (MIT), qwen35moe fine-tune: same speed class as star-fast, vendor-claimed better coding.
model = /opt/star/models/ornith-1.5-35b-a3b/Ornith-1.5-35B-Q6_K.gguf
mmproj = /opt/star/models/ornith-1.5-35b-a3b/mmproj-Ornith-1.5-35B-BF16.gguf
ctx-size = 32768
parallel = 1
reasoning = off
cache-ram = 4096
load-on-startup = false

[star-fast-cand2]
; Qwen3.6-35B-A3B Q6_K (lmstudio-community): Q6_K experts and dense, 2.49 GB read per token (live file 2.57).
model = /opt/star/models/qwen3.6-35b-a3b-lms/Qwen3.6-35B-A3B-Q6_K.gguf
mmproj = /opt/star/models/qwen3.6-35b-a3b/mmproj-Qwen3.6-35B-A3B-Q8_0.gguf
ctx-size = 32768
parallel = 1
reasoning = off
cache-ram = 4096
load-on-startup = false

[star-fast-cand3]
; Qwen3.6-35B-A3B Q4_K_M (lmstudio-community): Q4_K/Q6_K dense layers, 1.98 GB per token (speed candidate).
model = /opt/star/models/qwen3.6-35b-a3b-lms/Qwen3.6-35B-A3B-Q4_K_M.gguf
mmproj = /opt/star/models/qwen3.6-35b-a3b/mmproj-Qwen3.6-35B-A3B-Q8_0.gguf
ctx-size = 32768
parallel = 1
reasoning = off
cache-ram = 4096
load-on-startup = false
```

Apply from the PC worktree: `STAR_SSH_HOST=<user@brain1> STAR_BRAIN_URL=http://<brain1-container>:8080 bash server/brain/apply.sh check`,
then the same without `check`. Note the backup stamp it prints.

### 4.2 Stage A: load, template, speed (10 minutes per candidate, quiet lock)

1. `./star.cmd lock take --owner claude --holder model-scout --server 1`. Check the live slots are idle
   (`/opt/star/bench/busylog.sh`). Never poll `/slots` or `/props` for a model you do not mean to load: on the router
   that LOADS it (brain-performance-20261013 mistake).
2. Template check (as for Mellum): POST `/apply-template` with `{"model":"star-fast-candN", ...}` must show the
   thinking-off form. Qwen/Ornith: `enable_thinking` false, no open `<think>`. The Ornith template has an
   `enable_thinking is false` branch.
3. Speed: `STAR_BRAIN_URL=... python server/brain/bench/validate.py --models star-fast,star-fast-candN --reps 3 --tag candN`
   (gen tok/s, first token, cold 1,438-token prompt, next turn).
4. Unload: `curl -X POST $BRAIN/models/unload -d '{"model":"star-fast-candN"}'` (with the API key header). Release the lock.

Stop the candidate here if any of these hold:
- it does not load;
- the reasoning-off template is wrong;
- generation is below 9.0 tok/s (cand1, cand2) or below 12.0 tok/s (cand3, whose only reason to exist is speed);
- prompt processing is below 55 tok/s.

Quick Luau spot checks: the server-inference.md 4.2.3 harness in `/opt/star/bench`. Confirm the exact s06 command
there before running it. Use `luau_exec`, `luau_roblox`, `luau_strict`, `roblox_api`, `tool_call`. A check that
star-fast passes and the candidate fails is a stop: this is the trap Ornith-1.5-9B fell into.

### 4.3 Stage B-D: the eval gate

The runner sends every request to `--model`: run_task never runs the server-role discovery, which only happens in
the app's warm-up, Discord and voice paths. So `--model star-fast-candN` measures the candidate alone, and
`--model star-fast` reproduces the v1.0 release configuration (`mode auto`, `packs off`). Confirm on the first task
from the router journal that the candidate preset answered.

**Gate tooling caveat:** `python -m star.evals gate --paired-session` returns UNUSABLE when `run.model` differs
("model differs: not a like-for-like comparison"), and eval_gate is a protected path. Use the script below. It applies
the gate's own `eval_stats.paired_decision` and checks the rest the gate checks (suite identity, grader, mode,
36-hour session). It was tested on v090 vs v100 creation and reproduced the release verdict: INCONCLUSIVE, 10/23 vs 11/23.
Proper fix: an owner-approved `--allow-model-change` flag in eval_gate (protected-closure label).

```python
# compare_models.py: run from a Star-AI worktree with PYTHONPATH=.   usage: compare_models.py b1.json[,b2.json] c1.json[,c2.json]
import json, sys
from datetime import datetime
from star import eval_stats
def load(arg): return sorted((json.load(open(p, encoding="utf-8")) for p in arg.split(",")), key=lambda r: r["run"]["started_at"])
B, C = load(sys.argv[1]), load(sys.argv[2]); first = B[0]
for r in B + C:
    for k in ("sha256", "identity_sha256", "tasks_total", "automated"): assert r["suite"].get(k) == first["suite"].get(k), k
    for k in ("mode", "grader_sha256"): assert r["run"].get(k) == first["run"].get(k), k
when = datetime.fromisoformat
span = (max(when(r["run"].get("finished_at") or r["run"]["started_at"]) for r in B + C) - min(when(r["run"]["started_at"]) for r in B + C)).total_seconds() / 3600
print(f"baseline {first['run']['model']} vs candidate {C[0]['run']['model']}, span {span:.1f} h" + ("  NOT ONE SESSION (>36 h)" if span > 36 else ""))
ids = sorted({t for r in B for t, row in r["tasks"].items() if isinstance(row, dict) and row.get("status") in ("pass", "fail")})
s = {"pass": True, "fail": False}
arm = lambda runs: {t: [s.get((r["tasks"].get(t) or {}).get("status")) for r in runs] for t in ids}
print(eval_stats.paired_decision(arm(B), arm(C)).text())
```

Runs (Git Bash, from a detached worktree of the commit under test). Same pattern as the release script: separate
APPDATA per arm. **Start both arms of a sample at the same time** so drift cancels. Never use `--tasks` into an
existing result file (#359 overwrite bug).

```bash
export STAR_EVAL_SERVER="http://<brain1-container>:8080/v1" STAR_EVAL_SSH="<user>@<brain1-host>"
PY=/c/Users/alexi/Documents/starai/worktrees/pr39/.venv-audit/Scripts/python.exe; OUT=/c/Users/alexi/Documents/starai/work/model-scout
run() { # arm model suite sample
  APPDATA="$OUT/appdata-$1-$4" "$PY" -u -m star.evals run --suite "evals/roblox/$3" \
    --out "$OUT/$1-${3%.json}-s$4.json" --model "$2" --mode auto --packs off > "$OUT/$1-${3%.json}-s$4.log" 2>&1
}
for suite in golden-tasks-v2.json golden-tasks-creation-v1.json; do      # Stage B = sample 1, Stage C = sample 2
  run base star-fast "$suite" 1 & run cand1 star-fast-cand1 "$suite" 1 & wait
done
```

| Stage | What | Wall time (from the v1.0 runs: v2 2.2 h, creation 4.4 h for one arm) | Rule |
|---|---|---|---|
| B screen | dev v2 (34) + creation (23), k=1, both arms in parallel | ~6-8 h | stop if REJECT or any confirmed regression |
| C confirm | the same, sample 2 → `compare_models.py b-s1,b-s2 c-s1,c-s2` per suite and pooled | ~6-8 h | cand1/cand2: **PROMOTE** needed. cand3: **not REJECT, no confirmed regression** (a speed change, judged as non-inferiority; lead to confirm this rule) |
| D holdout | holdout-v1 (24), once, k=1, both arms in parallel | ~6-10 h | not REJECT. Used once, never tuned on |

### 4.4 What the gate can and cannot show (be honest in the result)

- MDE: 57 tasks × k=2 ≈ +9 tasks (about 16 points); 24×2 ≈ +6 (docs/agents/eval-gate-v2.md).
- A pure quant change (cand2) will almost surely come out INCONCLUSIVE. INCONCLUSIVE never promotes. Adopting cand2
  anyway, on "equal speed + lower published KL + not REJECT", is a lead/owner policy call. Write it up as that, not
  as a measured win.
- For cand3, "not REJECT" only rules out a loss of about 9 tasks or more. A smaller loss would pass. Add the Stage A
  spot checks and a few real chats before adopting it.
- Thinking stays off in all arms (STAR's config). The vendor numbers for cand1 do not apply to that mode.

### 4.5 Adoption (separate change, only after a pass)

A separate PR changes `[star-fast]`'s `model`/`mmproj` lines, after validate.py and a vision smoke test (one image
chat, because star-fast also serves `star-vision`). Apply with apply.sh. Keep the old file in place for a week.

### 4.6 Rollback

- During tests: unload the preset (above). If anything misbehaves, `bash server/brain/apply.sh rollback` restores
  the latest backup (check it is the stamp printed by the candidate apply), or copy
  `/opt/star/config/backups/<stamp>/models.ini` back and `systemctl restart star-brain`.
- After tests: remove the `[star-fast-candN]` sections in one more apply (or leave them: with
  `load-on-startup = false` they cost no RAM). Then `rm -r /opt/star/models/ornith-1.5-35b-a3b /opt/star/models/qwen3.6-35b-a3b-lms`
  for rejected candidates, and check `df -h`.
- After an adoption: put the old `model =` line back and apply again. The ggml-org file stays in
  `/opt/star/models/qwen3.6-35b-a3b/` until the lead removes it.

## 5. Speculative decoding and draft models (question 3)

- Measured on this box (server-inference.md 2.3): MTP (Qwen's own head) and DFlash on star-fast are slower: -12% to
  -58% on prose, at best +3% on code. Unsloth's own claim for MoE + MTP is only 1.15-1.25×, and that is on GPU.
- The router supports speculative decoding per preset (`spec-type`, `model-draft`, `spec-draft-n-max`): star-deep
  runs with an MTP draft through the router today (4.1-5.5 vs 2.3 tok/s, dense target).
- Tokenizer-compatible drafts:
  - cand1-cand3 share the Qwen3.5/3.6 248K vocabulary: the Qwen3.5 small models, the ggml-org `mtp-` and `dflash-`
    files, and Ornith's built-in `blk.40.nextn` MTP block.
  - K2 Horizon has its own 250,624-token vocabulary. The K2 Horizon dense family (0.9B/3.7B) probably shares it;
    not checked.
- Open question for RAMForge S6-S7 (not a promise): by bandwidth alone, verifying 3 draft tokens should cost about
  1.6 GB of dense reads once plus about 1.8 GB of experts, against 7.7 GB for 3 sequential tokens. That should be a
  win, yet the measurement says no. The likely costs are the DeltaNet state rollback on rejection and per-token thread
  sync on 4 dies.
- A draft on the PC's RTX 3060 Ti would need llama.cpp's RPC backend across the LAN for every draft step. Not
  recommended. The GPU is better kept for embeddings.

## 6. Status log

- 10:40Z started. Read CLAUDE.md, STATE.md, wave brief, standing rules, brain-performance-20261013,
  server-research, ramforge-20261013 (+ worktree draft ramforge-expertflow.md), models.ini on star/next, eval docs.
  `star status`: quiet lock held by claude-ramforge, so no server work at all.
- Research (web): HF model cards and file trees, llama.cpp PR status via the GitHub API, KL sources, AA pages.
- Ran: remote GGUF header reads, in memory, for 22 files (script in the session scratchpad, `gguf_bytes.py`; the
  live-file check matched RAMForge's 2.569 GB). compare_models.py tested on stored v090/v100 results (PC only, no model).
- Not run: any download, any server command, any eval or speed test. Every tok/s in this file except the live
  reference is an estimate.
- NEXT (lead): when RAMForge is done, Stage A for cand3 then cand2 then cand1 (cheap, 10 min each). Then Stage B-D
  for whichever passes, in that order of value: cand1 (quality) and cand3 (speed).

## Sources (read 2026-10-14)

- Files and checksums (HF API trees): [ggml-org/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/ggml-org/Qwen3.6-35B-A3B-GGUF),
  [unsloth/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF),
  [lmstudio-community/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/lmstudio-community/Qwen3.6-35B-A3B-GGUF),
  [bartowski/Qwen_Qwen3.6-35B-A3B-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3.6-35B-A3B-GGUF),
  [ornith-ai/Ornith-1.5-35B-A3B-GGUF](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF),
  [IFM/K2-Horizon-MoVA-36B-A4B-GGUF](https://huggingface.co/IFM/K2-Horizon-MoVA-36B-A4B-GGUF),
  [unsloth/Laguna-S-2.1-GGUF](https://huggingface.co/unsloth/Laguna-S-2.1-GGUF),
  [poolside/Laguna-S-2.1-GGUF](https://huggingface.co/poolside/Laguna-S-2.1-GGUF),
  [unsloth/Qwen3.8-Flash-Next-GGUF](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF).
- Model cards: [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B),
  [ornith-ai/Ornith-1.5-35B](https://huggingface.co/ornith-ai/Ornith-1.5-35B),
  [IFM/K2-Horizon-MoVA-36B-A4B](https://huggingface.co/IFM/K2-Horizon-MoVA-36B-A4B),
  [poolside/Laguna-S-2.1](https://huggingface.co/poolside/Laguna-S-2.1),
  [Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next),
  [Qwen/Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next),
  [poolside blog: Laguna XS 2.1](https://poolside.ai/blog/introducing-laguna-xs-2-1).
- Quant quality: [mudler/Qwen3.6-35B-A3B-APEX-GGUF](https://huggingface.co/mudler/Qwen3.6-35B-A3B-APEX-GGUF) (KL/PPL table),
  [localbench Qwen 3.6 35B A3B GGUF benchmark](https://localbench.substack.com/p/qwen-36-35b-a3b-gguf-quality-benchmark),
  [Unsloth Qwen3.6 docs](https://unsloth.ai/docs/models/qwen3.6).
- Third-party index: [Artificial Analysis: K2 Horizon MoVA 36B A4B](https://artificialanalysis.ai/models/k2-horizon-mova-36b-a4b),
  [Artificial Analysis: Qwen3.6 35B A3B](https://artificialanalysis.ai/models/qwen3-6-35b-a3b).
- llama.cpp: [PR #25165 Laguna](https://github.com/ggml-org/llama.cpp/pull/25165),
  [PR #27742 Qwen3.8-Flash-Next](https://github.com/ggml-org/llama.cpp/pull/27742),
  [PR #28243 Flash-Next MTP](https://github.com/ggml-org/llama.cpp/pull/28243),
  [PR #29535 K2 Horizon](https://github.com/ggml-org/llama.cpp/pull/29535),
  [issue #30246](https://github.com/ggml-org/llama.cpp/issues/30246), [PR #30335](https://github.com/ggml-org/llama.cpp/pull/30335),
  [release b11541](https://github.com/ggml-org/llama.cpp/releases/tag/b11541).
- Model landscape lists (secondary, used only to find names): [Pinggy, Oct 2026](https://pinggy.io/blog/best_open_source_self_hosted_llms_for_coding/),
  [Thunder Compute, Oct 2026](https://www.thundercompute.com/blog/best-open-source-llms).
- Local: docs/research/server-inference.md (2.3, 4.2.3), docs/agents/brain-performance-20261013.md,
  docs/research/ramforge-expertflow.md (branch star/ramforge-20261013), docs/evals.md, star/eval_gate.py, star/eval_stats.py,
  star/eval_runner.py, star/server_roles.py (star/next a71f1dac).
