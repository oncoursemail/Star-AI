# STAR evaluation gate

STAR is allowed to improve itself (new skills, routing rules, prompt edits, tool recipes) only if a fixed test set says
the change did not make it worse. This page is how to run that test set, how to put a change through the gate, and what
the numbers can and cannot tell you.

**Read "What this cannot tell us" before quoting any number from here.**

## What exists

| Piece | Where |
|---|---|
| Runner, scoring, gate, sandbox | `star/eval_runner.py`, `star/eval_checks.py`, `star/eval_gate.py`, `star/eval_sandbox.py`; entry point `python -m star.evals` |
| Suite v1 (25 tasks, unchanged copy of the research file) | `evals/roblox/golden-tasks-v1.json` |
| Suite v2 (50 tasks = v1 + 25 new; 34 automated, 16 need Studio) | `evals/roblox/golden-tasks-v2.json` |
| Creation suite v1 (23 automated tasks: animation, VFX, building, UI styles, engineering method) | `evals/roblox/golden-tasks-creation-v1.json` (own baseline `evals/results/baseline-creation-v1.json`; the gate only compares results of the same suite file) |
| Holdout suite v1 (24 automated tasks, written blind and frozen 2026-10-11; only for confirming a change, never for tuning; own `HO-*` tests and references) | `evals/roblox/holdout-v1.json`, `evals/roblox/holdout-v1.sha256`, `docs/evals-holdout.md` |
| Harness-owned Luau: prelude, 28 unit-test bodies, reference answers (`<ID>.md` must pass, `<ID>.bad.md` must fail) | `evals/roblox/prelude.luau`, `evals/roblox/tests/*.luau`, `evals/roblox/reference/*.md` |
| Stored results | `evals/results/*.json` (no private addresses; the answers are kept so a result can be re-scored) |
| Skill packs | `star/skill_packs/<name>/SKILL.md` + `references/sources.md` |
| Tests of all of the above | `tests/test_eval_*.py`, `tests/test_skill_packs.py` |

The harness files are owned by the harness: `star/selfbuild.py` only writes `star/skills/*.py` and `docs/skills/*.md`, and
`tests/test_eval_runner.py` asserts it cannot write anything listed above.

## Running a suite

Needs: the STAR Server and STAR Knowledge reachable on the private network, the server key in `~/.star/server_api_key`
(or `STAR_SERVER_API_KEY`), and SSH key access to the server's container host for the unit tests and the lock probe.
Addresses are never stored in the repository; pass them by environment variable.

```text
set STAR_EVAL_SERVER=http://<server-address>:8080/v1  (the STAR Server URL)
set STAR_EVAL_SSH=<user>@<host-address>                (user@host that can `lxc exec` into the container)
python -m star.evals run --suite evals/roblox/golden-tasks-v2.json --out evals/results/my-run.json
        [--tasks NET-01,UI-09]  [--packs off|all|roblox-ui-layout,...]  [--mode auto]  [--model star-fast]
python -m star.evals list     --suite evals/roblox/golden-tasks-v2.json
python -m star.evals routing  --suite evals/roblox/golden-tasks-v2.json     # which skill pack fires for which task (offline)
python -m star.evals selftest --suite evals/roblox/golden-tasks-v2.json     # references must pass, bad answers and empty answers must fail
python -m star.evals rescore  --suite ... --result old.json --out new.json  # re-score stored answers with corrected checks, no model calls
```

What a run does, for every automated task, one at a time (quality-only, no server lock taken):

1. waits while `/opt/star/lock` exists in the container ("quiet please" for timing runs), then asks `run_task` (the function the
   app itself calls) with provider `star_server`, `mode=auto`, a throw-away `APPDATA`, temperature 0 (set by the app);
2. extracts the fenced Luau blocks of the answer (STAR's own "Luau check" note and sources list are not part of the answer);
3. scores deterministically (below) and rewrites the result file, so a stopped run resumes where it stopped;
4. a task whose infrastructure failed (server down, sandbox unreachable) is `error`, never `fail`.

### The checks

| Check | How |
|---|---|
| Luau block present | at least one fenced `lua`/`luau` block |
| Compiles and type-checks | each block (at most 3) through the knowledge service `/luau/check` (compile + type analysis, never executes). Roblox tasks are checked with `--!strict` rewritten to `--!nonstrict` because the service types Roblox classes as unknown and strict mode then rejects ordinary operations on them; pure-Luau tasks (`compile_mode: exact`) are checked as written. "Unknown global X" is ignored when the task's own prompt names X. |
| Unit tests | the task's Luau test body plus `prelude.luau` plus the answer run **on the server**, in the container as user `star`, in the standalone Luau VM (no `io`, no `os.execute`, no network library), under `prlimit` (256 MB address space, 8 CPU seconds, 1 MB file size, 32 open files) and a 15 s hard `timeout`, in a fresh empty directory. The answer is loaded with `loadstring` into a whitelisted environment (no `require`, its `print` silenced) with small mocks (`game`, `Players`, `DataStoreService`, ...). **Model-written code is never run on the PC.** |
| Type-checker probe | the module plus a deliberately wrong call must be rejected by `/luau/check` (proves generics are not `any`) |
| Required / forbidden API names | regexes over the code with comments removed (and, where marked, strings blanked) so a comment cannot satisfy or break a check |
| Citation | for documentation questions: STAR's sources list must show a retrieved page as *cited*, optionally from a given page family |

## Baseline

`evals/results/baseline-v2.json` is the stored baseline of the current integration build on the real server (see the
numbers and run details in the section "Measured results" below). It is the reference every change is compared with.
A baseline must be re-made whenever the model, the server build, the prompt builder or the suite changes; the gate
refuses to compare results made from different suite files.

## The gate

```text
python -m star.evals gate --baseline evals/results/baseline-v2.json --candidate evals/results/my-change.json [--allow-partial] [--json]
```

Exit status: `0` allowed; `1` blocked (the pass count dropped, or a task that passed in the baseline fails now, even if
another task improved); `2` unusable input (different suite, unreadable file); `3` incomplete (a task errored or was not
run, so no verdict). `--allow-partial` is for a change that can only affect some tasks (a skill pack fires only for
matching prompts): tasks the candidate did not run are reported as *not covered*; an error or a regression among the
tasks it did run still blocks.

### How a proposed change must be run before it is enabled

1. **Do not enable it first.** Add it behind an off switch (a pack is off unless named in `STAR_SKILL_PACKS`; a routing rule or prompt
   edit needs the same kind of switch).
2. Find the tasks it can affect. For a skill pack: `python -m star.evals routing ...`. Tasks it cannot reach produce
   byte-identical requests and need no run; say so in the change description.
3. Run the affected tasks with the change on, into a new result file
   (`python -m star.evals run --suite ... --out evals/results/<change>.json --tasks <ids> --packs <name>`).
4. Run the gate against the baseline with `--allow-partial` when only a subset was run. Exit `0` is required.
5. The same temperature-0 request is not always answered identically by the server (two slots, floating point). If the
   gate blocks, re-run the regressed tasks once and look at the answers before deciding; do not tune the change against
   tasks you will later use to claim success (each task has a `split`: `development` or `holdout`; use holdout tasks only to
   confirm, never to adjust a prompt or a pack).
6. Record the before/after per change in this file, including "no measurable change". A change that does not improve
   anything and costs prompt tokens should stay off.
7. Only then switch it on by default, in the same commit as the result file.

Code that proposes changes by itself (for example the self-builder) calls the helper and must refuse to enable a
change unless `verdict.allowed`:

```python
from star.eval_gate import evaluate_change, gate_change

verdict = evaluate_change("evals/results/baseline-v2.json", "evals/results/my-change.json", allow_partial=True)
if not verdict.allowed:
    raise RuntimeError(verdict.text())          # regressions, errors, missing tasks or a different suite

# or run it end to end; `rerun(ids)` confirms regressions once before they block
verdict = gate_change("evals/results/baseline-v2.json", run_candidate=lambda: my_result_dict, rerun=my_rerun, allow_partial=True)
```

`Verdict` has `allowed`, `code`, `regressions`, `improvements`, `incomplete`, `not_covered`, `flaky`, `notes`, `to_dict()`, `text()`.

## Skill packs

Twelve packs ship in `star/skill_packs/` in the normal Agent Skill format (`SKILL.md` with `name`/`description`, `references/sources.md`
listing the official documentation pages and the API names checked against the knowledge service). They are chosen in code
(`star/skill_packs/__init__.py`): the prompt must read as a Roblox question *and* name the pack's topic, never in quick
chat mode, only the best-matching pack is added (about 240 tokens measured with the server's tokenizer, about 4 s of prompt reading at
roughly 65 tokens per second), and it travels in the per-turn sections after the user's words, never in the system message
(so the server's prompt cache is unaffected). `STAR_SKILL_PACKS=off|all|name,name` overrides which are on; the default list is
`DEFAULT_ENABLED` and contains only packs that passed the gate.

### Measured results (2026-10-11, STAR Server `star-fast`, mode auto, temperature 0, knowledge on, one request at a time)

Every number below was produced by `python -m star.evals run` against the real server and stored in `evals/results/`; nothing here is estimated.
Runs were made from frozen copies of the code so that later edits could not change a running job, and all stored results were
re-scored with the final graders (`python -m star.evals rescore`, no model calls) so that every arm is judged by the same checks.

**Baselines (packs off)**

| Suite | Passed | Unit-test tasks | Pattern-only tasks | Why the failures failed | Median per task |
|---|---|---|---|---|---|
| v2 (34 automated of 50) | **18 / 34 = 52.9 %** | 6 / 15 | 12 / 19 | 9 required API missing, 8 unit tests failed, 3 compile or type errors (a task can have several) | 149 s |
| creation-v1 (23 automated) | **11 / 23 = 47.8 %** | 5 / 13 | 6 / 10 | 7 required API missing, 6 unit tests failed, 2 compile errors, 1 answer cut off before any code, 1 STAR failure (the server rejected the model's own tool call) | 167 s |
| both | 29 / 57 = 50.9 % | | | | |

**Day-1 headroom for the training plan (`docs/research/training-plan.md`, section 6): today's setup passes 52.9 % of the 34 automatable v2
tasks and 47.8 % of the 23 creation tasks (50.9 % of all 57).** Stop rule 1 asks for 90 % or more before training is ruled out for lack of headroom;
this is 37 to 42 points short of it, so that rule does not fire. Read it with the noise below: the same task asked again without any change
flips in about one run in six, so a rate carries roughly plus or minus 3 tasks. Half of the failures are unit-test failures (wrong logic,
which retrieval alone does not fix) and the other half are missing required API names or compile errors (partly instruction following).
What this does not tell us: how many failures were retrieval misses (the right documentation page was never fetched) and how many were model
misses; that split needs the retrieved passages compared with `expected_sources` and was not measured.

**Noise.** Eighteen task runs were repeated with no change at all (packs off): 3 changed result (PERF-01 pass to fail, ANI-05 pass to fail,
ENG-06 pass to fail; none changed from fail to pass), i.e. 17 %. Ten reruns with a pack were compared byte for byte with the first run: nine returned the identical answer, so with the same request the
server is deterministic and such a rerun shows reproducibility, not an independent sample. The six no-pack repeats compared byte for byte all differed
from their baseline answer (the system message carries the date, which differs for the v2 repeats; the creation repeats ran on the same date and still
differed, so server state matters too). A single flip is therefore not evidence about a pack.

**How a pack was judged.** First run on the tasks it fires for, gate with `--allow-partial` against the baseline of that suite. If it
blocked, the regressed tasks were run once more with the pack and, where the baseline arm had not been repeated, once more without it.
A regression counts as reproduced only if the task fails again with the pack while it passes without it; if it also fails without the pack
the baseline arm is unstable for that task and the result is inconclusive. A pack is on by default only if the gate allows it, no regression
is reproduced, and at least one task improved. Because a rerun with the pack is mostly the identical answer, "reproduced" is weaker than it sounds:
it rules out a one-off server hiccup, nothing more.

**Roblox packs from the first wave, on suite v2** (the pack was the only one enabled, so it fired only where listed)

| Pack | Tasks | Passed before -> with pack | Fixed | Broke on the first run | Rerun | Default |
|---|---|---|---|---|---|---|
| roblox-secure-remotes | 9 (fired on 8) | 4 -> 5 | NET-10 | none | not needed | **on** |
| roblox-ui-layout | 7 | 3 -> 4 | UI-12, UI-13 | UI-11 | fails again with the pack, passed twice without it (the rerun's answer differed from the first run's): **reproduced regression, blocked** | off |
| roblox-datastore-safety | 5 | 3 -> 1 (median 167 s -> 313 s) | none | NET-09, NET-14 | both fail again with the pack, both pass without it (same answers as the first run): **reproduced, blocked** | off |
| roblox-animation-tools | 3 | 2 -> 2 | ANI-04 | ANI-05 | fails again with the pack but also failed once without it: inconclusive, no net gain | off |
| roblox-performance-streaming | 3 | 1 -> 1 | PERF-03 | PERF-01 | fails again with the pack but also failed once without it: inconclusive, no net gain | off |

**Creation packs, on suite creation-v1** (the tasks were written together with the packs, from the same documentation; see the limits below)

| Pack | Tasks | Passed before -> with pack | Fixed | Broke | Rerun | Default |
|---|---|---|---|---|---|---|
| roblox-animation-craft | 7 | 2 -> 3 | ANI-10 (SmoothTime on an IKControl) | none | not needed | **on** |
| roblox-vfx | 5 | 3 -> 4 | VFX-05 (emission limits from the docs) | none | not needed | **on** |
| roblox-building-layout | 3 | 2 -> 3 | BLD-01 (unit tests) | none | not needed | **on** |
| roblox-ui-styles | 3 | 3 -> 3 | none | none | not needed | off (no gain) |
| eng-debugging | 3 (+ v2 LUA-02, 1 -> 1) | 3 -> 2 | none | ENG-06 | fails again with the pack and also fails without it: inconclusive, no gain | off |
| eng-test-first | 2 | 0 -> 0 | none | none | not needed | off (no gain) |
| eng-verify-before-done | 2 | 0 -> 1 | ENG-07 | none | not needed | **on** |

Five packs are therefore on by default (`DEFAULT_ENABLED` in `star/skill_packs/__init__.py`): roblox-secure-remotes, roblox-animation-craft,
roblox-vfx, roblox-building-layout and eng-verify-before-done. Measured one pack at a time, the gains are +1 task on v2 (18 -> 19 of 34) and +4 on
creation-v1 (11 -> 15 of 23). The others stay shipped and can be switched on with `STAR_SKILL_PACKS`.

**Honest reading of those gains.**
- The sets are tiny (1 to 9 tasks per pack) and the control flips one task in six, so every "+1" is within noise except the ones that were also
  mechanically plausible: BLD-01 is a real unit-test improvement (a layout algorithm that was wrong became right).
- ANI-10, VFX-05 and ENG-07 improved on a requirement that the pack text states outright (SmoothTime, the 400 / 100 / 20 limits, "say what was not run").
  That shows the pack delivers the fact; it does not show better engineering. VFX-05 is a documentation question whose answer the retrieval had missed.
- `eng-verify-before-done` matters for honesty, not for correctness; STAR does run a static Luau check on its answers, so the grader only forbids claims
  of having tested or executed the code in the game.
- The packs ship even though a task they were written for may never run in Studio: no result here says anything about how the animation or effect looks.
- Two rounds of grader calibration happened after reading answers (v2: three false negatives found in the baseline; creation-v1: first the baseline
  answers, then the answers behind the first regressions of three packs). Every change only loosened a check and every arm was re-scored with the final
  graders, but the graders were tuned with the answers in view, so the pass counts above are optimistic compared with a grader frozen in advance.
  Changes: an `Unknown global` in a usage example after the first code block is a placeholder (`require(path.to.Module)`), not a defect; an annotated signature
  counts as unchanged; a property set through a config table counts as set; a claim of a static check is not a claim of having run the game.
  STAR's own failures (the model-call limit, an empty reply, the server rejecting the model's malformed tool call) count as failed tasks, not infrastructure errors.

## What this cannot tell us

- **It is small.** 34 automated tasks (15 with unit tests, 19 judged only by compile checks plus required/forbidden API names or a
  citation) and 16 that need Studio and were not run. The creation suite adds 23 more (13 with unit tests); its packs were measured on 1 to 7 tasks each. One extra pass or failure moves the rate by about 3 points. Per pack, the
  measured set is 3 to 11 tasks, so a single task flipping is the whole effect.
- **One sample per task.** Temperature 0 makes repeated answers similar but not identical on this server; no confidence interval is claimed.
- **Pattern checks are proxies.** "Uses `UIAspectRatioConstraint`" is evidence of a habit, not of a good-looking UI. Nothing here
  looks at pixels, animations, feel, gameplay, or whether code works inside Roblox Studio (the unit tests run in the plain Luau VM with
  small mocks; they cannot catch an engine behaviour the mock does not model).
- **The authors share a head.** The checks, the packs and the routing triggers were written by the same agent in the same week, from
  the same documentation. A pack that teaches the API name a check looks for will raise that check's score for a reason that may not
  matter to a player. The `development`/`holdout` split and the fact that packs were written before any pack run mitigate this; they do
  not remove it.
- **Wording matters.** Prompts without the word Roblox (or Luau, Studio, R6, R15) are routed by STAR as a quick 650-token chat; the suite
  prompts all carry such a word so they are measured on the Roblox route. A real user who omits it gets less (see the followups).
- **It says nothing about speed, voice, vision, long conversations or tool use.**
