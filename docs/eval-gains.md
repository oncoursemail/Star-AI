# eval-gains: progress (agent: eval-driven gains)

Worktree `worktrees\wt-eval-gains`, branch `star/eval-gains-20261011`.
Base: local integration commit 10ea90c (= integration 77f7e4e + the integrator's merge of skills-eval 1de6c38 + 10ea90c).
`origin/star/claude-integration-20261010` was still 77f7e4e (no eval harness, no skill packs) when this started, so the branch was
cut from the integrator's committed local head instead. Nothing was changed in `worktrees\wt-integration`.

## Final state (read this first)

Branch head: see `git -C worktrees/wt-eval-gains log --oneline -1` (code is final at ba18ea3; later commits only add result files
and this report). Full pytest at ba18ea3: 1494 passed, 12 skipped. Nothing is merged.

**Measured against the stored baselines** (real server, `star-fast`, mode auto, default packs given by name, training generator
stopped during the runs, one run at a time; the server's load average still stayed at 21 to 25 from other work):

| Suite | Baseline | This branch | Gate | Flips | Each flip run once more |
|---|---|---|---|---|---|
| v2 (34) | 18 / 34 = 52.9 % (`baseline-v2.json`) | **16 / 34 = 47.1 %** (`gains-v2.json`, code of 2e87304) | **BLOCKED** (exit 1) | regressions LUA-03, NET-01, NET-14, PERF-01, UI-10; improvements LUA-05, NET-07, NET-10 | `gains-v2-rerun.json` (ba18ea3): LUA-03, NET-01, PERF-01, UI-10 fail again; NET-14 passes; LUA-05, NET-07, NET-10 pass again. Counting NET-14's rerun: 17 / 34 |
| creation-v1 (23) | 11 / 23 = 47.8 % (`baseline-creation-v1.json`) | **15 / 23 = 65.2 %** (`gains-creation-v1.json`, ba18ea3) | **ALLOWED** (exit 0) | improvements ANI-10, BLD-01, ENG-07, VFX-05; no regression | `gains-creation-v1-rerun.json`: all four pass again |

What those numbers do and do not show:
- **Creation, +4:** these are exactly the four tasks the default skill packs fixed when they were measured one pack at a time
  (docs/evals.md). This is the first run with all default packs together, and it confirms 15 / 23; it is **not** a gain of this
  branch. This branch changed no creation task from fail to pass on its own, and broke none.
- **v2, minus 2 (minus 1 with NET-14's rerun):** the four regressions that reproduce (LUA-03, NET-01, PERF-01, UI-10) also fail
  at the base commit 10ea90c with the default packs and none of my changes (`gains-control-base-v2-a.json`,
  `gains-control-base-v2-b.json`: 0 of 4 pass). STAR's check passed all four answers unchanged (no repair, no continuation), so
  this branch did not touch them. The stored v2 baseline (packs off, an older commit, yesterday) is no longer reproduced by the
  integration code with default packs; a gate against it blocks whatever is tested. **A fresh baseline at the integration head
  is needed before any v2 verdict means something.** NET-14's first failure was an answer cut inside its code whose continuation
  came back with another conversation's text in it (the server's slot was shared with another client at that time; the lead
  restarted the brain for that reason); the join was hardened in ba18ea3 and the task passes on the rerun.
- **What this branch itself moved on v2:** LUA-05 and NET-07 pass because the repair now succeeds and is kept (both "repaired"
  in the events, both pass again on the rerun). NET-10 is the secure-remotes pack's known gain.
- **So: no measured net gain in pass count from this branch.** Two tasks moved by its repairs on v2, none on creation, on sets
  where one task is 3 to 4 points and the same request asked twice returns the same answer (a rerun shows reproducibility, not
  an independent sample). The suites were also used to find the fixes. The blind holdout is the real test.

Added time (from the `luau_check_finished` events of the two full runs): v2: 7 of 34 answers had a repair call, 542 s in
total (median 70 s per repaired answer, 16 s averaged over all answers); creation: 6 of 23 answers, 748 s (median 131 s, 33 s
averaged). The API lookups cost under a second per answer. A continuation ran only for answers cut inside code (89 s in the
one clean example). Five answers were cut in their closing prose and carry the one-line note instead of a model call.
Median task time 155 s on v2 (baseline 149 s) and 171 s on creation (167 s), measured under different server load.

What did not work:
- **The answer-shape rule** (code first, short comments, five bullets): answers a quarter shorter and a median turn of 109 s,
  but 16 / 34 and two regressions it reproducibly causes (`gains-v2-shape-on.json`, `gains-v2-ab-shape-off.json`,
  `gains-v2-ab-shape-on.json`). Off by default; `STAR_ANSWER_SHAPE=on` switches it on.
- **Repairs are slow and not always right**: each one writes the whole block again (median 70 to 131 s). UI-12's invented
  member was replaced by another wrong name twice; SYS-01, NET-13 and ENG-02 still fail their Luau check after a repair.
- **Continuation**: ANI-04 was continued and still ended with unfinished code (the model closed the block early).
- **Non-strict analysis of engine code** removes the false alarms but differs from the grader, which analyses some of these
  blocks strict (NET-13; any block with a comment above `--!strict`).

What is left, in order of expected value:
1. A fresh v2 baseline at the integration head with the default packs (see above), then this branch against it.
2. Repairs as search-and-replace edits instead of a rewritten block: about ten times less output, and the model has to name the
   line it changes (twice it returned the broken line unchanged).
3. The largest failure class is untouched: logic that fails the unit test (12 of 28). Static checks cannot see it; it needs a
   way to run model-written tests in the server's sandbox.
4. Tool route: with "roblox" plus an action verb a turn carries 15 tools. Seen there: the final answer leaves the code out
   because it was only sent to a tool (ENG-03, both runs), a `CompactionLimitError` (NET-04, once), unparseable tool calls
   (handled now).
5. Retrieval: at least one expected page in the top four for only 23 of 57 prompts.

Merging later (not done, as instructed): against `origin/star/claude-integration-20261010` at 9d5f04c (70 commits past my base)
`git merge-tree` reports one textual conflict, the import line in `star/desktop_core.py` (keep both sides:
`answer_shape` plus the new `studio_loop` / `studio_connections` imports). `star/agent.py` and `star/react_shell.py` merge
automatically. Not textual but to be checked by whoever merges: the new `star/luau_lint.py` overlaps with the bug-lint handling
in `doc_grounding.review_luau`; `star/doc_knowledge.py` changed (this branch calls `api_lookup` and `luau_check` as they were at
10ea90c); `star/eval_gate.py` and `star/eval_runner.py` were hardened, so the result files here (made with the runner of
10ea90c) may need a re-score or may be refused by the new gate.

## How to resume if cut off
1. `git -C worktrees/wt-eval-gains status` and `git -C worktrees/wt-eval-gains log --oneline -5` show what exists.
2. Environment for runs (addresses are never written into the repo): `STAR_EVAL_SERVER` = the container's own address, port 8080,
   path /v1; `STAR_EVAL_SSH` = the LXD host (see `docs/agents/skills-eval.md`, "Address note"). This session kept them in a scratch
   file `evalenv.sh` (session scratchpad), which also sets `PY` and `WT`.
3. Full runs (Git Bash, from `worktrees/wt-eval-gains`, one at a time, never with the quiet lock; a rerun of the same command resumes):
   `APPDATA=<temp> $PY -u -m star.evals run --suite evals/roblox/golden-tasks-v2.json --out evals/results/gains-v2.json`
   `APPDATA=<temp> $PY -u -m star.evals run --suite evals/roblox/golden-tasks-creation-v1.json --out evals/results/gains-creation-v1.json`
   plus `--packs roblox-secure-remotes,roblox-animation-craft,roblox-vfx,roblox-building-layout,eng-verify-before-done` (the
   runner's own default is `off`; these five are the app's default). Stop the training generator in the server container
   first (`systemctl stop star-training-gen`) and start it again afterwards. Then
   `$PY -m star.evals gate --baseline evals/results/baseline-v2.json --candidate evals/results/gains-v2.json` and the same for creation.
4. Tests: `APPDATA=<temp> $PY -m pytest -q -p no:cacheprovider` in the worktree (1478 passed, 12 skipped at commit 6993e56).

## Step 1: root causes of the 28 failing baseline tasks (read from the stored answers, no model calls)

Result files: `evals/results/baseline-v2.json` (16 failures of 34) and `evals/results/baseline-creation-v1.json` (12 of 23).

| Task | Failing check | Root cause | Evidence (one line) |
|---|---|---|---|
| LUA-05 | unit 2/4, strict header | logic + directive typo | trims with `string.find(s, "%S", #s, true)` (plain search for the two characters `%S`); first line is `---!strict`, a comment |
| NET-03 | unit 3/4 | logic | `trackedCount` returns `#lastUseTime` of a table keyed by Player (always 0); block 2 "failed" STAR's check only on strict-mode noise |
| NET-04 | required API | knowledge not retrieved | never uses UnreliableRemoteEvent; the four passages were RemoteEvent pages and a tutorial |
| NET-05 | Luau check, unit 4/5 | invalid types not repaired + logic; cut at the length limit | `player: Players.Player`, `: void`; STAR's check found them, the repair "did not pass either"; answer is exactly 1600 tokens |
| SYS-01 | unit 0/6 | interface | functions declared with `:` (`InventoryService:Give`) where the request gives plain signatures; cut at 1600 tokens |
| SYS-03 | unit 3/4, numbers not quoted | logic; cut at the length limit | wrong loop; the hand trace is cut off at 1600 tokens before any result |
| UI-09 | required API | requirement described in words not met; retrieval miss | no aspect-ratio constraint although "a constraint that keeps the slots square" was asked; 0 of 4 expected pages retrieved; cut at 1600 tokens |
| UI-12 | required API | explicit instruction ignored + invented API | asked for a UIScale, resizes by hand; `GuiService.ViewportSize` and a `VirtualInputManager` property do not exist |
| UI-13 | required API | requirement not met; retrieval miss | no SelectionGained/SelectionLost for the gamepad; 0 of 4 expected pages |
| UI-14 | required API | requirement not met; retrieval miss | manual loop over GetTextSize, no bound object; passages were about player display names |
| NET-07 | Luau check | type error found, repair returned the same code | `math.isfinite(x)` after `type(x) ~= "number"` on an unannotated parameter |
| NET-10 | unit 5/7 | logic | reads `Stamina` from the Humanoid, the request says the player's attribute; rate limit off |
| NET-13 | Luau check, unit | syntax error; the repair that fixed it was thrown away | `type DataStore = DataStoreService:GetDataStore | ...`; replay: repair fixes line 2, the re-check then shows `math.isFinite`, the old rule discards the repair |
| ANI-04 | required API (2) | requirements not met; cut at the length limit | no Grip property, no `Tool.Activated` handler; 1600 tokens |
| PERF-02 | required API (2) | requirement not met, wrong fact | says parts "cannot be forced" to stream; never sets ModelStreamingMode, no ChildAdded |
| PERF-03 | unit 5/6 | logic | `release` logic; STAR's check failed only on strict-mode noise (5 errors, 0 in non-strict) |
| ANI-07 | no answer | STAR failure | the server rejected the model's own tool call ("Failed to parse tool call arguments as JSON"); the turn failed |
| ANI-08 | Luau check, unit 12/14 | type errors not repaired + logic | `Unknown type 'Combo'`; buffered press handled a frame early |
| ANI-09 | no code block | cut at the length limit | the answer stops inside its first code block at exactly 1600 tokens |
| ANI-10 | required API | explicit instruction ignored | asked "give it a SmoothTime"; the code never sets it; 1600 tokens |
| ANI-11 | required API | explicit instruction ignored | asked for Action priority; the track's Priority is never set |
| VFX-03 | unit 6/10 | logic | active/total counters wrong |
| VFX-05 | required fact | fact not in the retrieved passages | documentation question; the 20 s lifetime limit is not in the answer |
| BLD-01 | unit 9/12 | logic | layout algorithm (STAR's check repaired a type error; the logic stayed wrong) |
| ENG-02 | Luau check, unit 0/9, tests | logic; cut at the length limit; repair failed | its own first test fails ("45s" gives nil); the second block is cut off at 1600 tokens |
| ENG-03 | honesty | wording | explains a fix but never says it was not run |
| ENG-05 | unit 0/8 | block not self-contained; repair cut off | tests block calls `chunk` defined only in the next block; replay: the repair hit its 875-token budget before the closing fence |
| ENG-07 | honesty | wording | as ENG-03 |

Counts (a task can have several):

| Root cause | Tasks | Which |
|---|---|---|
| Logic fails the unit test (static checks cannot see it) | 12 | LUA-05, NET-03, NET-05, SYS-01, SYS-03, NET-10, PERF-03, ANI-08, VFX-03, BLD-01, ENG-02, ENG-05 |
| A required API or behaviour is missing | 9 | named outright in the request: UI-12, ANI-10; described in words: NET-04, UI-09, UI-13, UI-14, ANI-04, PERF-02, ANI-11 |
| STAR's own check found errors, the answer shipped unrepaired | 9 | NET-03, NET-05, SYS-01, NET-07, NET-13, PERF-03, ANI-08, ENG-02, ENG-05 (the grader's Luau check failed in 5 of them) |
| Answer cut off at the 1600-token limit | 8 failing + 4 passing = 12 of 57 | decisive for ANI-09, partly ENG-02 and SYS-03 |
| Invented API name | 3 failing | UI-12, NET-13, UI-09 (also in passing answers: BLD-03 `Atmosphere.SunInfluence`) |
| Honesty wording | 2 | ENG-03, ENG-07 |
| Fact not retrieved (documentation question) | 1 | VFX-05 |
| STAR failure (unparseable tool call) | 1 | ANI-07 |

Retrieval, measured offline against each task's `expected_sources` (used for diagnosis only, nothing is keyed on it): with today's
query builder at least one expected page is in the top 4 for 23 of 57 prompts (vector, the default), 25 (hybrid), 27 (bm25). No
search mode is clearly better, so retrieval was left alone.

## Step 2: why the safeguards did not prevent them (traced in code and confirmed by replaying the repair call on the server)

1. **Length limit.** `brain_router.select_route` gives a full answer 1600 tokens; `agent.execute` never looked at `finish_reason`,
   so a cut answer was returned as finished. The eval runner asks again when an answer stops inside a code block; the app did not.
2. **Repair all-or-nothing, one round, tight budget.** `doc_grounding.review_luau` kept a repair only if the re-check was clean.
   Replays of the old repair call on stored blocks: NET-13 repaired the syntax error, the re-check then reported the errors that
   error had hidden, repair discarded (37 s wasted); NET-07 returned the code unchanged (83 s); ENG-05 was cut off by
   `max_tokens = len(code)/3 + 220` = 875 before the closing fence (101 s); PERF-03 went from 5 errors to 3, discarded.
3. **Strict-mode noise.** The checker has no Roblox type definitions (`roblox_api_types: false`); in `--!strict` every engine value is
   `unknown`, so `player.Name .. "!"` "fails". Of the 9 failed self-checks, 4 are clean in non-strict mode (NET-03 block 2, SYS-01,
   PERF-03, ENG-02 is pure Luau and stays strict). Each triggered a repair turn that could not succeed.
4. **Nothing checked API names.** The note said so ("Roblox API names and types were not verified"), although the knowledge service
   answers exact-name lookups in milliseconds (154 names in 0.2 s; inheritance, enum items, libraries, deprecation all covered).
5. **Nothing compared the answer with what the request named.**
6. **Tool route.** `needs_project_tools` is true for 51 of the 57 suite prompts ("roblox" plus an action verb, or "roblox" plus
   "game"), so those turns carry 15 tool definitions (about 1,650 prompt tokens) and the long rule set. That is by design and was
   not changed; but when the model writes a tool call the server cannot parse, `execute` let the turn fail (ANI-07).

## Step 3: the fixes (all general; nothing is keyed on a task, a prompt's wording, a test body or a grader)

| Fix | Where | What it does | Extra model time |
|---|---|---|---|
| A. Answers cut at the length limit | `star/answer_shape.py`, `agent.execute` (`complete_cut_answer`), `desktop_core.run_task` | (1) when the final answer ends inside a code block (`finish_reason == "length"` or an open fence) STAR asks for the missing lines only, at most twice with 900 tokens each, and joins them on (handles a re-opened fence, repeated lines, a block started again, text written before the fenced continuation); (2) a cut in the closing prose costs no call and gets one honest line; (3) **off by default** (`STAR_ANSWER_SHAPE=on`): a 130-token per-turn rule for requests that ask for code (complete code first, short comments, at most five bullets), switched off because it reproduced two regressions | only when the code was cut: one request of at most 900 tokens |
| B. Self-check that repairs instead of giving up | `star/doc_grounding.py` (`review_luau`, `_repair`, `repair_tokens`, `check_source`, `real_errors`) | engine code is analysed non-strict (the checker has no Roblox types) and the note says so; names from the request or defined by the answer's other blocks, and `require(path.to.X)`, are context; bug lints count (`not x == y`, duplicate function, ...); three blocks instead of two; a repair is kept when the re-check is strictly better (syntax errors, then other errors, then advisories); a second round only after a syntax error hid the rest or when at most two problems are left; the repair prompt quotes each offending source line and carries typing hints; its token budget fits the whole block | one repair call per failing block, as before; fewer of them are wasted on noise |
| C. Engine API names | `star/api_check.py`, wired into `review_luau` | names the code provably uses (method calls and assigned properties on receivers whose class the code states, connected events, `GetPropertyChangedSignal` names, enum items, class strings, library and datatype functions) are looked up in the official reference through the knowledge service; unknown ones fail the check and go to the repair with a hint (the class that really has the member, or the class's member list), deprecated ones and names the request asked for but the code never uses are advisories that get one repair attempt; the note counts the names that were checked | none for the lookups (about 0.1 s per block); a repair call when something is wrong |
| D. Unparseable tool call | `agent.execute` (`malformed_tool_call`) | when the server rejects the model's own tool call as invalid JSON, the turn is asked once more without tools instead of failing | one repeat of the turn, only on that error |

Not changed: routing (`needs_project_tools`), retrieval, the token limits, the skill packs, anything under `evals/`, the graders, the runner.

Replay of the new review loop on eight stored failing answers (real check, real API lookup, real repair model; no new first
answers), graded with the unchanged graders:

| Task | Old outcome of STAR's check | New loop | Repair time | Graded after |
|---|---|---|---|---|
| NET-13 | syntax error shipped | repaired in two rounds | 57 s + 33 s | still fails (the grader checks it strict as written; the repair also replaced the finite check) |
| NET-07 | type errors shipped | repaired (casts) | 85 s | **pass** |
| UI-12 | "passed" with two invented members and no UIScale | UIScale added, members replaced | 124 s | still fails: the repair took the nearest member name on the wrong class (the hint was changed after this, see commit 563b80c) |
| ANI-10 | "passed" without SmoothTime | `SmoothTime` set | 134 s | **pass** |
| ENG-05 | failed on `chunk` (defined in the next block) | no repair needed (context) | 0 s | still fails (the grader runs the tests block alone) |
| NET-05 | type errors shipped | repaired | 164 s | Luau check now passes; unit test still fails (logic) |
| ENG-02 | 13 strict errors shipped | 13 -> 3 in two rounds, kept, still flagged | 125 s + 138 s (the reason for the "second round only where it pays" rule) | still fails (logic) |
| ANI-08 | type errors shipped | repaired | 121 s | Luau check now passes; unit test still fails (logic) |

A repair writes the whole block again, so it costs about as long as the block took to write (37 to 164 s here, at 4 to 10 tokens
per second). That is the price of every fix that ends in a repair; see "What is left".

End-to-end checks through `run_task` (new first answers; the server was at 3.5 to 4 tokens per second):
ANI-09 was cut inside its code again at 1600 tokens, one continuation (89 s) completed it and the block compiles (it stopped in
the middle of the code in the baseline); ANI-07 answered normally (the server error did not recur); UI-12 used a UIScale in its
first draft, its invented `GuiService.ViewportSize` was caught and repaired (203 s); NET-13 had `math.isFinite` caught and repaired
(46 s). Answer length with the shape rule: UI-12 973 tokens (1288 in the baseline), NET-13 350 (715).

## Status log
- 2026-10-11: steps 1 and 2 done (above). Commits 6993e56 and 563b80c: fixes A-D with tests; full pytest 1481 passed, 12 skipped.
- 2026-10-11 14:34Z: first full run started from a snapshot of 563b80c. Stopped after 4 tasks (LUA-01..03 pass, LUA-04 fail):
  LUA-04's first draft kept Lua 5.4 operators (`|`, `<<`, `>>`), STAR's check caught it, the repair removed the syntax errors but
  also the comments, and my "a fix that throws the code away is not a fix" guard (raw length under 60 %) rejected it, so the broken
  block was shown. Real bug in my change, found by the run; fixed in d3570c7 (the guard counts code, not comments) with a test.
  The partial result of that attempt is not used (kept only in the session scratchpad).
- **Incident, 15:03Z:** to stop that run I killed every process whose command line matched `star.evals`. That also killed another
  agent's running evaluation (`star.evals run --suite evals/roblox/holdout-v1.json`, started about 14:04Z). I did not open, list or
  run any holdout file. Reported at once on the message log (#156); its owner has to start it again (the runner resumes). I now
  stop processes by exact pid only, and the driver script waits while another evaluation run is active.
- 2026-10-11 15:07Z: full runs restarted from a frozen snapshot of d3570c7 (scratch `fullrun.sh`: v2 then creation, default packs
  given by name because the runner's own default is `off`). Results go to `evals/results/gains-v2.json` and
  `evals/results/gains-creation-v1.json` in the worktree. If cut off: run the two commands in "How to resume" with
  `--packs roblox-secure-remotes,roblox-animation-craft,roblox-vfx,roblox-building-layout,eng-verify-before-done`; they resume.
- `STAR_ANSWER_SHAPE=off` switches the per-turn rule off (for an A/B of the only change that alters first drafts).
- That second run (d3570c7, the rule on every Roblox turn, first wording) was stopped by me after 20 of 34 tasks: 8 passed where
  the baseline passed 9, with 2 improvements (LUA-05, NET-04) and 3 regressions (UI-10, UI-16, NET-06). UI-16 is a documentation
  question that was answered with a script ("spend it on the code"); NET-06 and UI-10 were terser drafts that dropped a check.
  Also seen: UI-09's repair returned the same invalid type `{string, any}` (162 s wasted) and NET-07's repair annotated instead
  of casting. Not a clean A/B (one sample per task), but enough to change the rule rather than measure a known flaw:
  commit 03af5a5 attaches the rule only when the request asks for code, rewords it ("shorter must not mean less"), adds the two
  repair hints, checks reads on services that hold no game instances, and caps repair calls at two per answer. Replay of the
  UI-09 repair with the new hints: both rounds succeed (the block compiles). The partial result is kept only in the scratchpad.
- 2026-10-11 16:16Z to 17:33Z: full v2 run from a snapshot of 03af5a5, the answer-shape rule ON (default packs):
  **16/34, gate BLOCKED** against the baseline's 18/34. Regressions NET-06, NET-14, PERF-01, UI-10; improvements NET-04,
  PERF-03. Median turn 108.7 s (baseline 149.2 s); 9 of 34 answers had a repair (674 s in total). The result file is kept
  only in the scratchpad (`attempt3/gains-v2.rule-on.json`), not in the repo, because that configuration is not the default.
- A/B on the regressed tasks (same snapshot, `STAR_ANSWER_SHAPE` off and on), and a control at the base commit 10ea90c
  (no change of mine, default packs):

  | Task | Baseline | Rule on, full run | Rule on, rerun | Rule off | Base commit 10ea90c |
  |---|---|---|---|---|---|
  | NET-06 | pass | fail | fail (and fail in the stopped second run) | **pass** | not run |
  | NET-14 | pass | fail | fail | **pass** | not run |
  | UI-10 | pass | fail | fail | fail | **fail** |
  | PERF-01 | pass | fail | fail | fail | **fail** |
  | LUA-05 | fail | fail | pass | pass | not run |

  Reading: the rule causes NET-06 (a terser draft, 748 tokens instead of about 1,070, that no longer matches the grader's
  "alive" pattern) and NET-14 (it puts a path comment above `--!strict`; the grader then analyses the block strict and
  rejects `table.insert(t, task.spawn(...))` because `task` is unknown to the checker). UI-10 and PERF-01 fail without the
  rule and at the base commit too: drift or noise against the stored baseline, not an effect of this branch.
  Decision (commit 2e87304): the rule ships **off** (`STAR_ANSWER_SHAPE=on` switches it on); its code, tests and switch stay.
- 2026-10-11 18:13Z to 19:56Z: full v2 run of 2e87304 (rule off) with the training generator running and a load average of
  30: 17 of 33 scored, one error (NET-04, `CompactionLimitError`). Void by the lead's rule (made under load); kept only in the
  scratchpad. Same regressions and improvements as the clean run below, except NET-14 and PERF-03.
- 2026-10-11 20:08Z to 22:15Z: **the v2 run that counts** (`gains-v2.json`, snapshot 0224faa = the code of 2e87304), generator
  stopped. I stopped it by mistake three tasks before the end (a wait loop fell through); it was resumed on the same snapshot.
  PERF-02 and PERF-03 first errored (connection errors while the brain was restarted) and were asked again: no error left.
- 22:15Z to 23:27Z: **the creation run that counts** (`gains-creation-v1.json`, snapshot ba18ea3: adds only the hardened join of
  a continuation). 23:27Z to 23:59Z: each flip run once more (`gains-v2-rerun.json`, `gains-creation-v1-rerun.json`, ba18ea3).
  23:59Z: control at the base commit for LUA-03 and NET-01 (`gains-control-base-v2-b.json`). The training generator was started
  again after the last run (`systemctl is-active`: active, 00:03Z).
- Result files under `evals/results/` in the branch: `gains-v2.json`, `gains-creation-v1.json`, `gains-v2-rerun.json`,
  `gains-creation-v1-rerun.json`, `gains-v2-shape-on.json` (rule on, 03af5a5), `gains-v2-ab-shape-off.json` and
  `gains-v2-ab-shape-on.json` (A/B, 03af5a5), `gains-control-base-v2-a.json` and `gains-control-base-v2-b.json` (base 10ea90c).
