# STAR blind holdout suite (holdout-v1)

**Status: frozen 2026-10-11; any later edit makes earlier results incomparable; never use for training data or for tuning.**

The two suites in `docs/evals.md` (v2 and creation-v1) were also used to calibrate graders, write skill packs and decide
which packs ship, so a gain measured on them is optimistic. This suite is the one that nobody tuned against: it was written
once, without looking at any stored STAR answer or score, and without running STAR on it. It exists to confirm a change
(a skill pack, a routing rule, a prompt edit, a trained adapter) on tasks that the change was not shaped by.

## What exists

| Piece | Where |
|---|---|
| The suite: 24 automated tasks, all `split: holdout` | `evals/roblox/holdout-v1.json` |
| Harness-owned unit-test bodies (22 of the 24 tasks) | `evals/roblox/tests/HO-*.luau` |
| Reference answer (must pass) and realistic wrong answer (must fail) per task | `evals/roblox/reference/HO-*.md`, `HO-*.bad.md` |
| SHA-256 of all of the above (line endings normalised to LF) | `evals/roblox/holdout-v1.sha256` |
| Structure, no-duplicate and freeze checks | `tests/test_eval_holdout.py` |
| How it was built, weak spots, exact run commands | `docs/agents/eval-holdout.md` (project notes) |

The shared `evals/roblox/prelude.luau` is used as it is (the harness supports one prelude per suite folder, and it is not
edited). Everything else a test needs (Vector3 and CFrame maths, an Instance with Parent bookkeeping, Enum, UDim2, a
virtual-time `task` library, a TweenService that finishes tweens in virtual time, DataStore and CollectionService fakes) is
written inside the test body of the task that needs it, so each file stands alone.

## Coverage

| Area | Tasks | What they check |
|---|---|---|
| Networking and security | HO-NET-01 to 05 | speed/teleport check on position samples, token-bucket limiter with strikes, replay-proof input batches, server-owned crafting, a RemoteEvent that receives an Instance |
| Data | HO-DAT-01 to 04 | session lock through UpdateAsync, save-format migration, OrderedDataStore leaderboard with paging, a codec that makes sparse/mixed/NaN data storable and reversible |
| UI | HO-UI-01 to 04 | hotbar from layout objects in Scale only, queued toast with tweens, health bar with one cancelling tween, tab bar state |
| Animation and VFX | HO-ANI-01, HO-VFX-01, HO-VFX-02 | an Animator-based controller (load once, fade, speed), a Beam chain with Debris clean-up, throttled ParticleEmitter bursts |
| Building and world | HO-BLD-01 to 03 | CFrame ring in the center's own space, line of sight with a raycast, CollectionService binder |
| Pure Luau engineering | HO-ENG-01 to 03 | stable generic heap with a type-checker probe, shortest route with defined ties, number abbreviation with rounding carry |
| Documentation questions | HO-DOC-01, HO-DOC-02 | attribute types and replication, MessagingService limits; both need a cited official page |

## How the checks are used

- 22 tasks are judged mainly by a unit-test body that runs the returned module in the standalone Luau VM on the server, through
  stand-ins. Each test checks only behaviour the prompt states; where an implementation can legitimately differ (a callback
  chain or a worker thread, `track:Play(fade, 1, speed)` or `AdjustSpeed`) the test accepts both.
- `luau_check` (compile and type analysis) runs on every code task. The ENG tasks are checked as written (`compile_mode: exact`,
  `--!strict` required, the mode may not be relaxed); HO-ENG-01 also has a `typecheck_probe`: pushing a string on a
  `Heap<number>` must be rejected by the type checker.
- Required/forbidden API patterns are used sparingly, where correctness depends on the call itself: `UpdateAsync` and `pcall`
  for the session lock, `GetSortedAsync` for the leaderboard. The documentation tasks use prose patterns for the facts the
  cited page states (types, signal name, replication; 1,024 and 80 characters, 600 + 240 per player) and the citation check.
- Pattern checks never decide style. Deprecated APIs are caught by behaviour (the Animator controller must load tracks once;
  the mock Humanoid has no `LoadAnimation`).

## Rules for using it

1. Decide the change first, run it afterwards. Do not read a failing task and then adjust the change to it.
2. One baseline arm and one candidate arm per change, from the same suite file, the same server build and the same model. A
   baseline must be re-made when any of those changes; the gate refuses to compare different suite files.
3. Never copy a task, a test or a reference into training data, a skill pack, a prompt, a routing trigger or an example.
4. Do not edit the suite. If a task is found to be unfair, write a new suite (`holdout-v2`) and re-run both arms; do not patch
   this one. `tests/test_eval_holdout.py` fails when a frozen file changes.
5. Stored result files keep the answers (so a result can be re-scored); treat them like the suite: look at them only after
   the verdict, never to tune.

## Commands

```text
set STAR_EVAL_SERVER=http://<server-address>:8080/v1
set STAR_EVAL_SSH=<user>@<host-address>
python -m star.evals selftest --suite evals/roblox/holdout-v1.json          # no model calls; references pass, bad and empty answers fail
python -m star.evals list     --suite evals/roblox/holdout-v1.json
python -m star.evals run      --suite evals/roblox/holdout-v1.json --out evals/results/holdout-v1-baseline.json --packs off
python -m star.evals run      --suite evals/roblox/holdout-v1.json --out evals/results/holdout-v1-<change>.json --packs <names>
python -m star.evals gate     --baseline evals/results/holdout-v1-baseline.json --candidate evals/results/holdout-v1-<change>.json
```

Run each arm from a frozen copy of the code (a `git archive` of the head under test), as described in `docs/agents/skills-eval.md`,
so later edits cannot change a running job. One task takes about 1 to 4 minutes, so one arm takes about an hour of server time.
Same-prompt reruns flip about one task in six (see `docs/evals.md`): when the gate blocks on one task, re-run only that task
once before deciding.

## What it cannot tell us

- 24 tasks: one task moves the rate by about 4 points, and the same task asked again flips in roughly one run in six.
- The tests run in the plain Luau VM with stand-ins. They cannot see an engine behaviour the stand-in does not model (replication,
  physics, the real rendering of a UI or an effect).
- The author is an AI assistant that also helped write STAR's skill packs. The tasks avoid scenarios, names and values from the
  earlier suites and were not shaped by any STAR answer, but the same habits of thought remain. A review by someone else
  (without STAR's answers) is the remedy, not a claim that the suite is neutral.
- A few prompts fix many details (names, numbers, colors) so that the tests are fair; that measures careful reading of a
  specification as much as Roblox skill.
