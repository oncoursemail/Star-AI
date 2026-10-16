# STAR Roblox benchmark results (2026-10-16T09:04:00Z)

Each task's checks ran in a real Roblox Studio playtest. Score: easy 1, medium 2, hard 3 points.

| model | tasks passed | score | easy | medium | hard | checks | median answer s |
|---|---|---|---|---|---|---|---|
| reference | 20/20 | 42/42 | 5/5 | 8/8 | 7/7 | 79/79 | - |
| star-fast | 14/20 | 26/42 | 5/5 | 6/8 | 3/7 | 63/73 | 188.1 |
| star-deep | 17/20 | 34/42 | 5/5 | 7/8 | 5/7 | 70/79 | 134.1 |
| star-quick | 7/20 | 12/42 | 4/5 | 1/8 | 2/7 | 42/73 | 34.4 |

| task | reference | star-fast | star-deep | star-quick |
|---|---|---|---|---|
| E01-format-time | pass | pass | pass | pass |
| E02-make-part | pass | pass | pass | pass |
| E03-leaderstats | pass | pass | pass | pass |
| E04-kill-brick | pass | pass | pass | pass |
| E05-countdown | pass | pass | pass | fail 3/4 |
| H01-grid-path | pass | fail 2/4 | pass | fail 0/4 |
| H02-priority-queue | pass | pass | pass | fail 1/3 |
| H03-serialize | pass | fail 0/6 | fail 0/6 | fail 0/6 |
| H04-shop-validation | pass | pass | pass | pass |
| H05-round-machine | pass | pass | pass | fail 3/5 |
| H06-coin-collect | pass | fail 2/3 | fail 2/3 | pass |
| H07-damage-guard | pass | fail 5/6 | pass | fail 0/1 |
| M01-spinner-tags | pass | pass | fail 1/3 | fail 1/3 |
| M02-weighted-pick | pass | pass | pass | pass |
| M03-fade-tween | pass | pass | pass | fail 0/3 |
| M04-signal | pass | fail 4/4 | pass | fail 3/4 |
| M05-inventory | pass | fail 0/0 | pass | fail 3/5 |
| M06-ground-raycast | pass | pass | pass | fail 0/3 |
| M07-reconcile | pass | pass | pass | fail 2/3 |
| M08-parts-in-radius | pass | pass | pass | fail 0/3 |

## Conditions (2026-10-16)
- One answer per model and task (temperature 0.3), thinking off for all three (star-fast has reasoning off on the
  server; star-deep asked with `--no-think`; star-quick showed no thinking). Answers are in `answers/<model>/`.
- Answer seconds are not a speed benchmark: brain 1 was shared with night school, and star-fast's first answers ran
  while an orphaned star-deep request used the CPU.
- Studio: the primary Studio on brain 2 (STAR Test Place), one playtest per task. It was slow (game time down to
  ~0.15x wall time at moments), so timing checks accept the wall clock, game time or Heartbeat time. Five play
  starts needed a reconnect; each task was then played again (no result lost).
- star-fast M05: the answer ran to the 6,000-token cap (repeating) and has no closed code block.
