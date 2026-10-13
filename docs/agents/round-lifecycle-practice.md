# Round lifecycle practice — 12 independent Roblox exercises

This **opt-in practice suite** is at `evals/roblox/practice-tasks-round-lifecycle-v1.json`. It is **not** added to the default night-school or evaluation task pools, and it does not change any runtime grader, API rules, or frozen benchmark. Each prompt requests a server-side or pure-Luau lifecycle contract rather than an isolated beginner repair or trust-boundary exploit.

## Exercise map

| ID | Category | Contract / edge to inspect |
| --- | --- | --- |
| RND-01 | state-transitions | Reject illegal round-phase jumps; Results -> Playing must be rejected even if the requested phase is otherwise valid. |
| RND-02 | state-transitions | Start each round exactly once and preserve increasing identifiers; Calling begin() twice before finish() must increment the ID only once. |
| RND-03 | state-transitions | Emit ordered notifications only for accepted phase changes; A callback registered while Playing receives no event until the next accepted transition. |
| RND-04 | time-cancellation | Drive a round countdown from a deadline and stop its frame listener; A single Heartbeat delayed past the deadline must expire once, without negative remaining time. |
| RND-05 | time-cancellation | Invalidate delayed round callbacks when a match is cancelled; Schedule A, cancel it, then schedule B; A's delayed callback must never affect B. |
| RND-06 | time-cancellation | Pause and resume a round timer without losing remaining time; Pause for 100 seconds when 3 remain, then resume; remaining should still be about 3. |
| RND-07 | joins-leaves | Keep late joiners spectators until the next participant snapshot; A player joining immediately after start() is ineligible until start() is called again. |
| RND-08 | joins-leaves | Cancel intermission when a departing player breaks the minimum; Exactly two players in intermission: one leaves; the countdown must cancel immediately. |
| RND-09 | joins-leaves | Resolve departures without rewarding disconnected players; Two players disconnect in quick succession; no winner may be a disconnected player. |
| RND-10 | results-cleanup | Select a deterministic round winner from scores; Two players with the same score must give the smaller UserId even if table order flips. |
| RND-11 | results-cleanup | Award a round winner at most once despite duplicate completions; The award callback itself calls finish() again; it must not trigger a second award. |
| RND-12 | results-cleanup | Disconnect event listeners and destroy temporary arena objects after each round; After two rounds with repeated cleanup, the prior round's Touched listeners must not fire. |

Three exercises each cover phase transitions, time and cancellation, joins and leaves, and results and cleanup. Each has a task prompt, learning note, observable edge case, documented expected behavior, allowed engine symbols, required code markers, and forbidden code markers. **Reference-like positive and negative snippets live only in `tests/test_round_lifecycle_practice.py`**; the task suite contains no solutions.

## Deterministic scoring: what is proved and what is not

The production `load_suite` validates the JSON schema and regexes. The production `score_answer` extracts fenced Luau, asks the normal Luau checker to check the block, and evaluates the required/forbidden patterns against **code with comments removed**. The Python regression test exercises these real paths with a **stubbed successful compiler response** for **12 positive and 12 negative structural probes**. It also checks that comments containing code markers cannot pass and that a reported syntax error cannot be ignored. This proves that **the scoring contracts discriminate those probes**, not that the positive fragments pass an actual Luau compiler or reproduce complete Roblox behavior.

All 12 tasks use **static-only** scoring; no Luau VM, actual server, Studio playtest, live model response, wall-clock timer, or multiplayer join/leave simulation is executed by these new tests. Regex structure can be satisfied by logically incorrect code; conversely a perfectly correct alternative design can fail a narrow structural criterion. In particular, event callbacks, cancellation races, timing accuracy, tie-breaking, idempotent awards, and resource cleanup require adversarial **deterministic sandbox or Studio integration tests before promotion to a trusted behavioral benchmark**. Never report a practice static pass as a verified secure or correct game.

## Overlap policy

The regression test compares normalized goals/prompts and rejects Jaccard word-set similarity ≥ 0.50 against `golden-tasks-v1.json`, `golden-tasks-v2.json`, `golden-tasks-creation-v1.json`, `holdout-v1.json`, and—when present in the current base—earlier security/debugging practice suites from PRs #197 and #198. The creation-time comparison also reads their live draft branches; they are not required to be merged for this PR's CI. Existing benchmark and holdout files remain unchanged. Each lifecycle prompt is independently authored and scopes its checks to one contract.

## Source verification — official Roblox Creator Hub

The API and behavior checks use these current references, not guessed identifiers:

- [module](https://create.roblox.com/docs/scripting/module)
- [luau](https://create.roblox.com/docs/luau)
- [players](https://create.roblox.com/docs/reference/engine/classes/Players)
- [player](https://create.roblox.com/docs/reference/engine/classes/Player)
- [run](https://create.roblox.com/docs/reference/engine/classes/RunService)
- [task](https://create.roblox.com/docs/reference/engine/libraries/task)
- [connection](https://create.roblox.com/docs/reference/engine/datatypes/RBXScriptConnection)
- [basepart](https://create.roblox.com/docs/reference/engine/classes/BasePart)
- [instance](https://create.roblox.com/docs/reference/engine/classes/Instance)
- [table](https://create.roblox.com/docs/reference/engine/libraries/table)

Specifically: `Players.PlayerRemoving` occurs **before** the player is removed, so RND-08 excludes the departing player during counting. `Players:GetPlayers()` enumerates connected players for RND-07. `RunService.Heartbeat` fires each frame with elapsed delta; RND-04 instead anchors remaining time to an injected deadline, so hitches cannot extend it. `task.delay` can schedule delayed work, but a generation token still rejects stale completions in RND-05. `RBXScriptConnection:Disconnect`, `Instance:Destroy`, and `table.clear` are documented lifecycle cleanup operations.

## Assessment approaches (licence, upkeep, cost)

| Option | Licence / availability | Upkeep and execution cost | Decision |
| --- | --- | --- | --- |
| **Existing STAR pattern grader** | First-party code already in this repository; no new dependency fee | Lowest upkeep; inexpensive deterministic offline checks, but cannot demonstrate behavior | **Chosen for initial practice gating**, with limitations stated |
| Standalone Luau VM fixtures | [Upstream Luau](https://github.com/luau-lang/luau) is MIT; local binaries require maintenance | Additional sandbox/fake-service fixtures, time budget and platform portability concerns | Next phase for strong behavioral scoring, not introduced here |
| Roblox Studio multiplayer playtests | Roblox Studio is free to use under Roblox terms; not redistributable as an MIT test library | Requires Studio infrastructure, engine execution and multi-client orchestration; higher maintenance | Essential pre-release validation, out of scope |

## Verification commands for a future checkout

```text
python -m pytest -q tests/test_round_lifecycle_practice.py
python -m pytest -q
```

These commands are documentation only in the PR until GitHub Actions reports executing them. Do not claim Studio or a local test run from this document.
