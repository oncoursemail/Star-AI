# STAR open Roblox benchmark

20 Roblox/Luau tasks (5 easy, 8 medium, 7 hard). Every task is checked by running it in a real Roblox Studio
playtest, not by reading the code: the answer goes into a throwaway test place, a check Script exercises it, and
the playtest output says which checks passed.

| level | tasks | points each |
|---|---|---|
| easy | E01-E05: formatting, Part properties, leaderstats, kill brick, countdown values | 1 |
| medium | M01-M08: CollectionService spinner, weighted random, TweenService fade, Signal class, inventory, raycast, data reconcile, spatial query | 2 |
| hard | H01-H07: grid pathfinding, binary heap (speed checked), JSON-safe serialization of Roblox types, shop and damage validation of client input, round state machine, collectable coins | 3 |

A task passes when every check passed and the answer's own scripts printed no error. Results per run:
`results/<date>/results.md` (scores) and `results.json` (every check, error lines, answer time); the models'
answers are kept next to them.

## Files
- `tasks/<id>.json`: `id`, `level`, `kind` (`module`: one ModuleScript named Solution; `script`: server Scripts in
  a Folder, `script.Parent`), `title`, `prompt` (exactly what the model is asked), `playSeconds`.
- `tasks/<id>.check.luau`: the check body. It runs after `harness.luau`, which gives `check(name, fn)`,
  `expect(cond, msg)`, `near`, `waitFor`, `solution()`, `testPlayer()`, `testPart(props)` and `stopwatch()`.
- `tasks/<id>.reference.luau`: a known-good answer. The pseudo-model `reference` runs these; all 20 must pass,
  which is how the benchmark checks its own checks.

## Add a task
Write the three files, then `python -m star.roblox_benchmark check` (offline) and run the reference for it in
Studio (`--models reference --only <id>`). Timing checks: game time and the wall clock disagree on a busy Studio
server; use `stopwatch()` and accept any of its clocks.

## Run
1. Answers (brain only, any machine with the brain endpoint; each answer is asked once and saved):
   `STAR_BRAIN_URL=<brain> python -m star.roblox_benchmark answers --answers <dir> --models star-fast,star-deep,star-quick`
   (key file `~/.star/server_api_key`, or `STAR_PLAYTEST_KEY_FILE`).
2. Studio (the Studio machine, user `star`, STAR Test Place open in the primary Studio):
   `bash server/studio_lab/roblox-bench.sh <answers dir> <out dir> reference,star-fast,star-deep,star-quick`
   It waits for the quiet lock, never overlaps the Studio Lab nightly or playtest learning, and stops the connector
   host afterwards. Edits go through the Studio Lab's guarded path (STAR Test Place only, one undo step each); other
   scripts of the place are paused during a playtest and switched back on afterwards.
