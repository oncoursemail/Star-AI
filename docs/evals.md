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
| Harness-owned Luau: prelude, 15 unit-test bodies, reference answers | `evals/roblox/prelude.luau`, `evals/roblox/tests/*.luau`, `evals/roblox/reference/*.md` |
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
set STAR_EVAL_SERVER=http://192.168.1.20:8080/v1      (the STAR Server URL)
set STAR_EVAL_SSH=someone@192.168.1.10                 (user@host that can `lxc exec` into the container)
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

Five packs ship in `star/skill_packs/` in the normal Agent Skill format (`SKILL.md` with `name`/`description`, `references/sources.md`
listing the official documentation pages and the API names checked against the knowledge service). They are chosen in code
(`star/skill_packs/__init__.py`): the prompt must read as a Roblox question *and* name the pack's topic, never in quick
chat mode, only the best-matching pack is added (about 240 tokens measured with the server's tokenizer, about 4 s of prompt reading at
roughly 65 tokens per second), and it travels in the per-turn sections after the user's words, never in the system message
(so the server's prompt cache is unaffected). `STAR_SKILL_PACKS=off|all|name,name` overrides which are on; the default list is
`DEFAULT_ENABLED` and contains only packs that passed the gate.

MEASURED_RESULTS_PLACEHOLDER

## What this cannot tell us

- **It is small.** 34 automated tasks (15 with unit tests, 19 judged only by compile checks plus required/forbidden API names or a
  citation) and 16 that need Studio and were not run. One extra pass or failure moves the rate by about 3 points. Per pack, the
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
