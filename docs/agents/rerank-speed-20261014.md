# rerank-speed-20261014 (Claude, board item #139)

Brief (coordinator, 2026-10-14 ~13:10Z): (1) put `cache-ram = 0` for star-rerank into the repo models.ini so apply.sh
cannot undo the live change; (2) find out why one 15-document rerank takes ~12 s, fix it under the quiet lock with
top-5 results identical (target under 1-2 s, or a clear explanation of the limit); check whether starkb could rerank
fewer candidates (e.g. 8) with no retrieval loss on `starkb eval`.
Branch star/rerank-speed-20261014, worktree worktrees/rerank-speed (from origin/star/next 8581091e).

## Status (14:20Z): DONE
- (1) `server/brain/models.ini`: `cache-ram = 0` under `[star-rerank]`; the repo file now equals the live
  /opt/star/config/models.ini (ignoring comments). PR into star/next (see below).
- (2) Root cause: **compute**. The 0.6 B Q8_0 reranker reads ~3,800 tokens per 15-document call (15 x ~255 tokens:
  template + query + a document of up to 1,000 chars) and this CPU processes ~350-430 tokens/s for this model.
  No server flag gets a 15-document call near 1-2 s; only less text does. **And rerank is not in any live search
  path**: the knowledge service offers only vector/bm25/hybrid (`serve.py`: "rerank costs about 14 s per query and is
  not offered", default `vector`), and the desktop app asks for `vector`. Rerank runs only in `starkb eval`,
  `starkb search/ask` on the command line and validate.py. So it is not a speed sink in users' knowledge searches.
- Fewer candidates: **8 loses retrieval** (r@5 75/95 vs 80/95 with 15). Vector-only search (what the service already
  uses) beats hybrid+rerank on all three question sets (85/95), at ~0.1-0.2 s.
- Nothing was changed on the live server in this item (the cache-ram change was made earlier in the RAMForge item).

## Measurements (server 1; quiet lock holder `rerank`; live slots idle)

### Raw prompt speed of the reranker model (llama-bench, live b11541 binary, pp256 / pp1024 tok/s), 13:09Z
| threads / placement | pp256 | pp1024 |
|---|---|---|
| 24, --numa distribute, interleave, flash-attn on (live) | 434 | 407 |
| same, flash-attn off | 358 | 293 |
| 12, distribute | 244 | 225 |
| 6, one node | 129 | 115 |
| 12, one node with SMT | 148 | 134 |
| 12, two nodes | 235 | 214 |
| 48, distribute | 481 | 442 |
Scaling is linear with cores (~21 tok/s per core): compute-bound, not memory, not NUMA. 0.6 B params x 2 FLOP x 434
tok/s = ~0.5 TFLOP/s, about half of this Zen 1 CPU's AVX2 peak; an LLM pass over every document token is the cost.

### Real starkb rerank requests (fixture = the exact 15-document inputs starkb sends for 10 eval questions, mean
document 677 chars; `rr2.py`, median per call)
| server config | median s / call | top-5 vs live | full order vs live |
|---|---|---|---|
| live star-rerank (t24/tb24, 4 slots, cache-ram 0), 13:15Z | 11.16 | (reference) | - |
| live again, 14:09Z | 11.26 | 10/10 | 10/10 |
| temp server, same flags | 11.30 | 10/10 | 9/10 |
| temp server -t 48 -tb 48 | **9.92 (-11%)** | 10/10 | 9/10 |
| temp server -np 16, -b/-ub 4096 (all docs in one batch) | 10.11 | 9/10 | 6/10 |
The server reaches ~340 tok/s of the 434 raw. Batching all documents together does not help (and changes rounding);
48 threads is the only identical-result gain (-11%, measured once).

### Less text per call (live server, 14:09Z, clean)
| documents x max chars | median s / call |
|---|---|
| 15 x 1000 (starkb today) | 11.26 |
| 8 x 1000 | 5.93 |
| 5 x 1000 | 3.69 |
| 15 x 400 | 7.70 |
| 8 x 400 | 4.11 |
About 0.75 s per full document and still ~0.5 s per 400-char document (the reranker template + query is ~80-100 tokens
per document, mostly not reusable across documents). 1-2 s means at most 2-3 documents on this CPU.
An earlier attempt (13:35Z) is discarded: the deployed `starkb eval` was running and ignored the lock (see findings).

### Retrieval quality (`starkb eval`, star-embed-ft1, 13:24-14:05Z; recall@5 hits / n, MRR@10)
| set (n) | vector | hybrid | hybrid+rerank 15 | rerank 8 | rerank 5 |
|---|---|---|---|---|---|
| questions (30) | **30**, 0.867 | 25, 0.735 | 28, 0.800 | 26, 0.754 | 25, 0.722 |
| heldout (40) | **37**, 0.822 | 34, 0.747 | 35, 0.743 | 33, 0.725 | 34, 0.735 |
| golden-task-queries (25) | **18**, 0.502 | 16, 0.516 | 17, 0.396 | 16, 0.422 | 16, 0.466 |
| total r@5 (95) | **85** | 75 | 80 | 75 | 75 |
Rerank median latency per query in these runs: 11.9-17.4 s (15), 6.4-8.9 s (8), 4.0-5.6 s (5).

## Verdict / recommendations
1. Keep the knowledge service and the app on `vector` (already the default): best recall on every set, no rerank.
2. Do not cut rerank to 8 candidates: -5 of 95 at recall@5. If rerank is used (evals), keep 15.
3. If a fast rerank is ever wanted live, it needs other hardware (e.g. the PC GPU) or a different design; on brain 1
   the floor is ~0.5-0.75 s per document. `threads = 48` would give -11% with identical results (not applied: rerank is
   not live, and 48 threads would take every hardware thread during evals).
4. RAM: star-rerank stays loaded (5.8 GB RSS) only for evals/CLI. `load-on-startup = false` for it would free that
   memory; the router loads it on first use. Not changed (owner/lead decision; measure first-use load time).

## Findings for others
- The deployed knowledge app on server 1 is older than the repo: /opt/star/knowledge/app/starkb/evaluate.py has no
  quiet-lock wait (repo version calls wait_while_locked). My eval run at 13:24-14:05Z therefore kept running through
  one of my lock windows (that timing was discarded). No live chat requests happened in that window (journal checked).
  Redeploy server/knowledge (owner of the knowledge deploy) so evals honour the lock.

## Status log
- 13:05Z claimed #139, worktree from origin/star/next.
- 13:09Z llama-bench sweep (RS1); 13:15Z flag variants on real fixture (RS2); 13:24-14:05Z starkb eval x9 (unit rf-kbeval);
  14:09Z clean fewer/shorter runs (RS4). Locks released each time; server left clean (no temp servers, unit finished).
- Commit 6498bbcd models.ini; pytest 7679 passed, 256 skipped, 1 failed before the commit
  (test_brain_models_ini_is_checked_out_with_lf compares the working copy with the index; passes after the commit).

## Lead decisions applied (2026-10-14 14:2xZ, item #140)
1. star-rerank `load-on-startup = false`, live and in the repo (PR #389). Applied WITHOUT a brain restart: backup
   /opt/star/config/backups/20261014-rerank-ondemand/models.ini, edited /opt/star/config/models.ini, then
   `POST /models/unload {"model":"star-rerank"}`. All other models stayed loaded (star-fast, star-voice, star-embed,
   star-embed-ft1). **RAM freed: 5.8 GB** (container used 37,571 -> 31,778 MiB). First rerank call after that loads it
   on demand: 8.9 s, then 0.5 s for a 2-document call; unloaded again afterwards. The router applies the file's
   `load-on-startup = false` at its next restart (until then it simply stays unloaded unless used).
   Rollback: copy the backup models.ini back (and load it with any rerank call, or restart star-brain).
2. Knowledge app redeployed from star/next d287e67c with `server/knowledge/deploy.sh --install` (clean detached
   worktree; LF files checked). Backups: /opt/star/knowledge/backups/app-20261014-1419.tgz and units-20261014-1419/.
   star-knowledge restarted 14:19:48Z (~3 s gap); drop-ins embed-ft1.conf kept (STAR_EMBED_MODEL=star-embed-ft1 on both
   units); the refresh unit now also has STAR_PLANNER_URL (planner not running = old behaviour).
   Checks: the same live search returns the same 3 passages (vector, 45 ms); evaluate.py now waits for the quiet lock
   (seen: "quiet: server lock present, pausing" / "continuing after 20s" with a test lock); `starkb eval`
   recall@5 vector 30/30, 37/40, 18/25 and MRR 0.8667 / 0.8217 / 0.5017 = identical to before.
   Rollback: `tar xzf /opt/star/knowledge/backups/app-20261014-1419.tgz -C /opt/star/knowledge`, copy the three units
   back to /etc/systemd/system, `systemctl daemon-reload && systemctl restart star-knowledge`.
