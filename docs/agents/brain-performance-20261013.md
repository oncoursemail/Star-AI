# Brain performance 2026-10-13 (Claude, board item #68)

Task: baseline + tune both brain servers (llama.cpp router on server 1, second brain on server 2).
Brief: docs/agents/WAVE-20261013-BRIEF.md. Branch star/brain-performance-20261013 (worktree worktrees/wt-brainperf).

## Result (state 12:25Z)

**No engine or flag change beat the live configuration on brain 1; the live service was not changed.** The 2026-10-11
tuning (numactl --interleave=all, --numa distribute, -t 24 -tb 48, dio load, f16 KV, 2 slots) is still the best
measured setup. One capacity change (bigger prompt cache) is staged, pre-flight checked, and waits for a restart window.
Brain 2 stays the Studio-testing machine (lead direction); its Studio connector was checked and works.

### Brain 1 (EPYC 7451, 4 NUMA nodes x 1 DDR4 channel, 125 GB): star-fast = Qwen3.6-35B-A3B Q4_K_M

All rows: temp llama-server on 127.0.0.1:8094 with the live flags unless noted, `validate.py --reps 3` + `par.py`,
quiet lock held, live slots idle at the start. "2 par" = two simultaneous 150-token answers, tok/s per stream.

| Run (UTC) | gen tok/s | first token, short | cold 1,438-token prompt | next turn | 2 par | verdict |
|---|---|---|---|---|---|---|
| live router, 11:24 (baseline, from the PC) | 10.33 | 1.31 s | 70.0 tok/s (20.8 s) | 0.99 s | - | baseline |
| b11541 (live build), 11:29 | 10.48 | 1.22 s | 70.9 tok/s (20.5 s) | 0.82 s | 7.35 | reference |
| b11583 (newest mainline, 13 Oct), 11:32 | 10.51 | 1.24 s | 69.0 tok/s (21.1 s) | 0.86 s | 7.38 | same: not worth a rebuild |
| ik_llama.cpp 9c3b2417, -rtr, fused MoE, 11:44 | 11.43 | 4.39 s | 57.8 tok/s (25.2 s) | 27.4 s (no reuse) | 0.50 | rejected |
| b11541 built without OpenMP, 11:58 | 7.45* | 3.02 s* | 35.8 tok/s* | 2.88 s* | 2.2* | worse (*contaminated) |
| -np 4 -c 131072, 12:10 | 6.26* | 7.65 s* | 34.1 tok/s* | 10.2 s* | - | discarded (*contaminated) |

\* another agent's star-fast answers ran during these runs (see log 12:06Z); treat as not measured.

- star-voice (Mellum2.1-12B) baseline 25.41 tok/s, first token 0.90 s, prompt 107 tok/s; embed 570 tok/s; rerank
  8 docs 4.72 s; star-fast under an embedding job 9.95 tok/s. Not changed.
- Utilisation: star-fast generation uses 24 cores (about 2,400% CPU, one thread per physical core, 6 per node);
  prompt reading uses all 48 hardware threads. RAM: router 45-46 GB resident (star-fast 29.7 GB), about 80 GB
  available. Generation is limited by memory bandwidth plus cross-die thread sync (4 single-channel nodes), not by
  cores or RAM size: spare RAM cannot make tokens faster.
- Research summary (sources below): mainline release notes b11542-b11583 contain only two CPU changes (F16C fix
  for AVX2 builds that were not `-march=native`, vectorised fp32->fp16); this build is native, so no gain, as measured.
  ik_llama.cpp has fused delta-net and Qwen3.5/3.6 MTP, but no router mode and, on this CPU, slower prompt reading,
  no prompt reuse for this hybrid model and very slow parallel decoding. Speculative decoding (MTP/DFlash) on
  star-fast was already measured slower on this CPU (server-inference.md 2.3). KV q8_0 was measured slower (2.5).
  Per-node instances: one channel gives about 3.9 tok/s, two 7.3, four 9.5 (server-inference.md 2.0), so splitting
  star-fast per node lowers single-user speed; not pursued. Bigger tier (e.g. a 122B-A10B MoE, ~74 GB): bandwidth
  says about 3 tok/s, the same as star-deep with MTP, and star-deep did not beat star-fast in spot checks: not pursued.

### Staged, not applied: star-fast prompt cache 8 GB -> 24 GB

- Evidence: the star-fast RAM prompt cache is at its 8192 MiB default and evicts all day (320 "removing oldest
  entry" lines in 24 h, entries 200-360 MiB, so only ~25-40 prompts are kept). An evicted conversation is re-read
  (cold 1,438 tokens = 20.8 s today) instead of restored (1.3-1.6 s measured in first-token.md). Night school and
  agent evals add a new 200-360 MiB entry every few minutes, so a user's conversation falls out within ~2 hours.
- Change: `cache-ram = 24576` in `[star-fast]` (repo `server/brain/models.ini`; the rest is identical to the live file).
  `bash server/brain/apply.sh check` passed (12:21Z). Not applied because the router reads presets only at start
  (checked in tools/server/server-models.cpp: reload happens only after a download), so it needs a 1-3 minute
  star-brain restart, and the W3 worked-example A/B (another agent) was using star-fast continuously.
- Apply (Git Bash on the PC, from the worktree; takes the server lock, backs up, restarts, rolls back by itself if a
  model does not come up, measures before/after):
  `STAR_SSH_HOST=<user@brain1> STAR_BRAIN_URL=http://<brain1-container>:8080 bash server/brain/apply.sh`
- Rollback: `bash server/brain/apply.sh rollback` (restores /opt/star/config/backups/<LATEST>/), or by hand: copy
  `/opt/star/config/backups/<stamp>/models.ini` over `/opt/star/config/models.ini`, `systemctl restart star-brain`.
- Check after apply: `journalctl -u star-brain | grep "removing oldest entry"` should become rare; validate.py numbers
  must stay at baseline (the change does not touch the compute path).

### Brain 2 (i7-9700 8c/8t, 16 GB, container 6 CPU / 12 GB, Intel UHD 630)

- Role per the owner/lead plan: real Roblox Studio testing, not a model host. Checked read-only 12:20Z:
  `studioctl status` all units active, `studio-probe.py` -> ok, 30 tools, 1 Studio attached in 0.04 s, Edit mode,
  STAR Test Place 128074805767678. (The "zero attached Studio" note in the ChatGPT plans is out of date.)
- Memory: about 5 GB available in the container with Studio open (Studio + WebView about 4.8 GB). Earlier benchmark
  (server2-studio.md 6): Mellum 11 tok/s (half of brain 1) and 10.4 GB, which does not fit beside Studio; Gemma 4 E2B
  4.4 GB at 10 tok/s would fit but is slower than star-voice on brain 1 and the app has no fallback route to a second
  brain. Nothing installed. Nothing changed on brain 2.

### Sources
- llama.cpp releases b11572-b11583 (github.com/ggml-org/llama.cpp/releases) and `git log b11541..b11583`.
- ik_llama.cpp README and docs/parameters.md at 9c3b2417 (qwen35moe PR 1288, fused delta-net PRs 1315/1333/1362/1373,
  Qwen 3.5/3.6 MTP PRs 1698/1745, -rtr PR 147, -fmoe PR 229); ik discussion #164 (older CPU comparison).
- llama.cpp discussions #11733 and #11765 (multi-socket/NUMA generation scales poorly; per-node placement), issue #1437
  (numactl --interleave), `--numa` help text; `--cache-ram` PR 16391 (server help text).
- Earlier measurements on this box: docs/research/server-inference.md (2.0-2.5, 4.2), docs/agents/first-token.md.

## Status log
- 11:20Z claimed; read first-token.md, server-research.md, server2-studio.md (6), ledger brain section.
  Prior state: tuning applied 2026-10-11 00:39Z (interleave, thread counts) gave star-fast 5.05 -> 10.43 tok/s.
- 11:24Z baseline (lock held, live router, validate.py from PC, reps 3): star-fast gen 10.33 tok/s, first token 1.31 s,
  cold 1438-token prompt 70.0 tok/s (20.8 s), next turn 0.99 s, under embed 9.95; star-voice 25.41 tok/s, 0.90 s,
  107 tok/s prompt; embed 570 tok/s; rerank 8 docs 4.72 s. File: work/brainperf/validate-before-20261013.json.
- Server 1 RAM: 125 GB, 45 GB used by the router (star-fast RSS 29.7 GB), ~82 GB available. star-fast uses 24 cores
  (~2400% CPU) while generating; night school keeps it busy most of the time.
- 11:29-11:37Z A/B temp server :8094 (same flags as live, interleave, dio, -t 24 -tb 48, -np 2), lock held:
  b11541: gen 10.48, prompt 70.9, next turn 0.82 s, 2 parallel 7.35+7.34 (13.3 agg)
  b11583: gen 10.51, prompt 69.0, next turn 0.86 s, 2 parallel 7.38+7.38 (13.3 agg)  => no gain, keep b11541.
  Scripts on server: /opt/star/bench/{ab.sh,par.py,waitidle.sh,validate.py}; results /opt/star/bench/ab-20261013/.
- 11:38Z ik_llama.cpp (9c3b2417, supports qwen35moe + Mellum2, fused delta-net) building in /opt/star/src/ik_llama.cpp.
- Server 2: i7-9700 8c/8t, 15 GB (container 6 cpu / 12 GB), Intel UHD 630 only, 1 NUMA node. Studio open
  (place 128074805767678), ~5 GB available in the container. Same b11541 build + Mellum + Gemma E2B files, no service.
- 11:43-11:52Z ik_llama.cpp 9c3b2417 (-fa on --no-mmap -rtr, fused MoE on, same placement/threads): gen 11.43 tok/s
  (+9%), but short-prompt first token 4.39 s (vs 1.22), cold prompt 57.8 tok/s (-18%), NO prompt reuse (next turn
  re-read 1,496 tokens = 27.4 s), 2 parallel 0.50 tok/s each. Rejected. Also: no router mode in ik (single model only).
  (This run overran the 10-min lock by ~1 min because the 2-parallel test took 311 s; aborted the next run, released.)
- 11:53-12:02Z no-OpenMP build of b11541: gen 7.45, prompt 35.8, 2-par 2.2 - but CONTAMINATED (live star-fast busy).
- 12:06-12:15Z -np 4 -c 131072 test: CONTAMINATED (live star-fast busy 158 of 160 samples), numbers discarded.
  Cause: work/worked-examples-ab/ab.py (W3 A/B, another Claude agent) takes the quiet lock as owner claude per answer;
  `star lock take` says "already yours" to any claude session, so both of us ran inside each other's lock. Messages
  #179-#181 posted. Lesson: before a timing run check the live slots with /opt/star/bench/busylog.sh.
- MISTAKE 12:03Z: polling `/slots?model=star-deep` made the router LOAD star-deep (23 GB, ~100 s). Unloaded at 12:07Z
  with POST /models/unload (memory back to 46 GB used). Never query /slots for an unloaded model.
  Correction 12:24Z: the same polling had queued a SECOND star-deep load (spawned 12:05:33, port 39713) that stayed
  loaded (23 GB) after the first unload; found at 12:23Z, unloaded again, verified 0 star-deep processes, 45 GB used.
- 12:20Z brain 2 read-only check (studioctl status + studio-probe.py): ok, 30 tools, 1 Studio attached in 0.04 s, Edit
  mode, STAR Test Place 128074805767678, watchdog active. Lead direction 12:16Z: brain 2 = Studio testing only, no
  big model there. Nothing changed on brain 2.
- Finding: star-fast RAM prompt cache is at its 8192 MiB default limit and evicts all day (320 "removing oldest entry"
  in 24 h, entries 200-360 MiB, so ~25-40 prompts fit). Planned change: `cache-ram = 24576` for star-fast (repo copy
  server/brain/models.ini). Needs a star-brain restart (router re-reads presets only at start); waiting for a window
  because W3 A/B uses the brain continuously (~56 answers left at 12:18Z).
- Repo: worktree has server/brain/{models.ini, star-brain.service, star-brain-prestart.sh, apply.sh, apply-remote.sh}
  and server/brain/bench/{validate.py, ab.sh, par.py, waitidle.sh, busylog.sh} (addresses removed; apply.sh needs
  STAR_SSH_HOST and STAR_BRAIN_URL from the environment). Not committed yet.
- 12:22Z PR #225 (star/brain-performance-20261013 -> star/next, head 8d15158): server/brain config + bench scripts +
  this file. pytest 4673 passed / 223 skipped. `apply.sh check` passed (12:21Z, stages files only).
- 12:24Z server left clean: no temp server, busylog stopped, lock free, star-brain active/health ok, star-deep
  unloaded (as before), 45 GB used. Build trees left in /opt/star/src (llama.cpp-b11583 292M, llama.cpp-b11541-noomp
  292M, ik_llama.cpp 377M); results /opt/star/bench/ab-20261013/. Live config unchanged.
- NEXT (lead): apply the staged cache-ram change when the W3 A/B is finished or paused (command in "Result"), then run
  validate.py and check the eviction count. Optional: make star-deep resident (load-on-startup = true) - it costs
  23 GB of the ~80 GB spare and removes its ~100 s first-use load (seen today), at +~100 s per router restart.
