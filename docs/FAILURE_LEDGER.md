# Failure ledger and targeted practice

This feature is opt-in. It reads the stored JSON evaluation results,
attributes every record marked `fail` to one primary, evidence-backed cause, and
can write **new** practice exercises that target each failure's own cause, from
one family of task specifications per cause (`star/practice_gen.py`, W4 of
`docs/research/self-improving-star-claude-v2.md`). It never runs a model, never
modifies evaluation files, never writes into `evals/` or the blind holdout, and
does not enrol tasks into night school by itself. Only `ledger verify` contacts
the STAR server, and only its Luau checker and sandboxed Luau VM.

## Commands

- Inspect failures, with an evidence row for each failed attempt:

      python -m star.evals ledger

- Write targeted practice for the recorded failures (one task per distinct
  failed task and cause; `--per-failure K` for more, `--leading-only` for the
  most frequent cause, `--count N` for the first N failures):

      python -m star.evals ledger practice --out ledger-practice/targeted.json

- Write the whole per-cause catalogue (300 tasks; `--total N` for fewer):

      python -m star.evals ledger pool --out pool-v2/ledger-practice-v2.json --selftest-out selftest-v2

- Check a self-test folder with the real harness (reference answers must pass,
  bad answers must fail and be labelled with the task's own cause, empty
  answers must fail):

      STAR_EVAL_SERVER=http://<container>:8080/v1 STAR_EVAL_SSH=<user>@<lxd-host> \
        python -m star.evals ledger verify --dir selftest-v2

The pool folder gets the task file, `prelude.luau` (the evaluation harness
prelude, byte for byte) and `tests/LG-*.luau`. Reference and bad answers go
only to the separate `--selftest-out` folder (refused when it is the pool
folder). Existing files are never overwritten. Both report commands accept
`--results DIR` and `--suites DIR`.

Results marked `error` (infrastructure), `pass`, or `skipped` are
excluded. Result files belonging to a holdout suite are ignored, and
the holdout catalog is never opened. A classification is a reproducible
**primary label**, not a proven diagnosis of model cognition; retry attempts
can receive different labels if their recorded failed checks differ.

## Ledger on the stored result files

The 26 JSON files currently committed under `evals/results/` contain
65 failed attempts involving 34 distinct task IDs. Counts include independent
baseline, control, skill-pack and rerun attempts. This table is obtained by
applying the exact ordered rules in `star/failure_ledger.py` to those records:

| Cause | Failed attempts | Distinct IDs with this cause | Illustrative stored evidence |
|---|---:|---:|---|
| Wrong logic | 15 | 10 | baseline-v2 / SYS-01: failing `unit_tests` assertions |
| Required feature missing | 25 | 16 | baseline-v2 / UI-12: `require:uiscale` |
| Self-check error left unrepaired | 13 | 8 | baseline-v2 / NET-07: `luau_check[1]` type error |
| Answer cut off | 11 | 9 | baseline-creation-v1 / ANI-07: `product_failure` |
| Invented API name | 1 | 1 | baseline-v2 / NET-05: `Unknown type 'Players.Player'` |
| **Total** | **65** | **34 overall** | Per-cause distinct IDs overlap across reruns |


Rule priority: recorded truncation/no answer/no Luau block; unknown
external identifier or dotted type reported by Luau checking; other Luau
static/typecheck or harness-loading errors; a failing unit-test assertion
named `required feature: X` (it checks that a requested function exists, so
it is a missing feature); other failing runtime unit tests; missing required
or forbidden pattern/citation; finally a legacy failure-reason fallback. The
CLI prints the actual matching check/detail for each row. A product-call parse
failure is classified as "answer cut off" because STAR delivered no usable
answer; an unknown global may instead be a typo. Those caveats are visible and
should be reviewed before promoting a lesson.


The planning brief names counts **12, 9, 9, 8, 3** (41 total). In that
order, the checked-in corpus differs by **+3, +16, +4, +3, -2**. The
referenced `docs/research/20261012/learning-loop.md` is absent from
`star/next`, so there is no trustworthy inclusion list, classification
priority, or run timestamp for that 41-failure cohort. The stored corpus
includes repeated task attempts and currently totals 65, not 41. Therefore
these two tables cannot be equated; do not tune the rules merely to force
the old numbers. To reproduce the 41-count table exactly, the lead would
need to supply the cohort selection and labels without using the blind
holdout suite.


## Practice generation (per cause, with real runnable checks)

The first version used one fixed clamp-and-floor template for every cause, so
a task "for" an invented API or a cut-off answer did not exercise either. Each
cause now has its own family in `star/practice_gen.py`:

| Cause | Specs | What the task demands | Bad answer (must fail for this cause) |
|---|---:|---|---|
| Wrong logic | 6 | Small behaviour specs with exact edges: cooldown ready at exactly `duration`, damage falloff clamped at both ends, fixed-size history oldest first, competition ranking with ties, capped wave sizes, level thresholds | The classic bug: `>` for `>=`, no far clamp, ring order, dense ranking, off-by-one wave, `<` threshold |
| Required feature missing | 6 | Modules whose prompt lists every method (inventory, party, settings, quest, round timer, shop); the unit test asserts each one exists (`required feature: X`) and works | The reference with one method left out (which one varies by variant) |
| Self-check error left unrepaired | 6 | `--!strict` modules (typed vectors, optional lookups, a queue, a typed helper, a typed summary, an if-chain) | A real strict-mode error: `nil` for `Vec`, unnarrowed `Entry?`, `string` for `number`, argument count, missing field, missing `end` |
| Answer cut off | 4 | Long modules (8-9 functions: text formatting, tile grid, bank ledger with undo, matchmaking with a snake draft) in one compact block | The module stopping mid-way inside an unclosed fence |
| Invented API name | 6 | Utilities that must use the real built-ins (`string.split`, `table.find`, `math.clamp`, `string.sub`, `string.format`, `bit32`) | One call to a helper module that does not exist (`StringUtil`, `TableUtil`, ...): Luau reports "Unknown global" |

Each spec has 10 variants (the long-module specs 15) that change the numbers,
names, data and game context, so the catalogue holds **300 tasks, 60 per
cause**. Every task has static Luau checking (`compile_mode: exact`, strict
where the cause needs it), required/forbidden patterns and a runtime unit test
(3 to 13 assertions) that runs in the server's Luau VM with the evaluation
harness prelude. Ids are `LG-<cause>-<spec>-NN`; they never use the holdout's
`HO-` prefix.

Targeted generation (`ledger practice`) maps every distinct failed (task,
cause) to a task of that cause's family, chosen by a hash of the failed task id
(stable), never repeating a task. On the committed results it writes 44 tasks
(wrong logic 10, required feature missing 16, self-check 8, cut off 9, invented
API 1); `--leading-only` writes the 16 for the leading cause.

Guards: the writer refuses any path inside `evals/` or named golden/holdout,
compares every prompt with every golden prompt (no eight-token verbatim
stretch, token overlap below 0.45), and night school's own loader (`load_pool`)
accepts all 300 with nothing dropped (tested). A test also compares every
prompt with every suite in `evals/roblox` including the holdout (overlap below
0.45); the generator itself never reads it. About a fifth of the new tasks fall
into night school's validation slice by its id hash; that slice is a
development slice, not the blind holdout.

### Real verification (server 1 Luau checker and VM, no model)

RAN on 2026-10-13 with `ledger verify` (the harness's own scorer: the knowledge
service's Luau checker and the container's sandboxed Luau VM; no model call):

- First 30-task run: 18/30. It found two real defects, both fixed: the
  `--!strict` pattern was matched against comment-stripped code (it now uses
  the `raw` scope), and the new "required feature" label rule had a broken
  regex escape (every required-feature bad answer was labelled wrong logic).
- Full catalogue after the fixes: **300/300**: every reference answer passes,
  every bad answer fails and the ledger labels it with the task's own cause,
  every empty answer fails.
- Final run on the committed code (after small variant changes): **300/300**.

Examples of what the real checker printed for bad answers (now pinned in
`tests/test_practice_gen.py`): `Expected this to be 'Vec', but got 'nil'`,
`Value of type 'Entry?' could be nil`, `Argument count mismatch. Function
expects 2 arguments, but only 1 is specified`, `Expected 'end' (to close
'function' at line 4), got <eof>`, `Unknown global 'StringUtil'`.

What this does and does not show: the tasks are well formed and their checks
discriminate (a correct answer passes, the named mistake fails and is labelled
correctly). It does not show that practising them makes STAR better; that is
for night school's paired gate (W1) on the validation slice and, later, the
holdout. The unit tests use the harness's stand-ins, not Roblox Studio.

## Tool choice (licensing, upkeep and cost)

| Approach | Licence | Upkeep | Offline cost / trade-off |
|---|---|---|---|
| **Python standard-library rules and templates (chosen)** | PSF-2.0 for Python | Low: review explicit patterns when check IDs change | No extra dependency, deterministic, negligible CPU; imperfect diagnosis is inspectable |
| scikit-learn feature classifier | BSD-3-Clause | Medium: versioned labeled training data and model retraining | Local CPU inference, requires enough truth labels that do not yet exist |
| llama.cpp local language-model classification | MIT | Medium-high: model version, prompt calibration, quality regressions | Local CPU/GPU and RAM usage, less reproducible without gold labels |

Rule-based evidence was selected because stored checks are already
structured, the feature must work fully offline, and each claim can point
back to recorded diagnostics. The generated practice tests measure a
specific fresh skill and deliberately do not modify or score on holdout
data. No model-quality improvement is claimed merely from making this tool.
