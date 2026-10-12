# Failure ledger and targeted practice

This feature is opt-in and offline. It reads the stored JSON evaluation results,
attributes every record marked `fail` to one primary, evidence-backed cause, and
can write **new**, parametrized practice exercises for the most frequent cause.
It does not contact a brain, execute Luau, modify evaluation files, or enroll
tasks into night school automatically.

## Commands

- Inspect failures, with an evidence row for each failed attempt:

      python -m star.evals ledger

- Explicitly write a standalone night-school-compatible practice pool:

      python -m star.evals ledger practice --out ledger-practice/targeted.json

  This creates `targeted.json`, `prelude.luau`, and
  `tests/LEDGER-*.luau` in that directory. No file is written without
  `practice --out`; existing outputs are never overwritten. The caller
  chooses whether to copy or generate into an actual night-school pool.
  `--count N` limits exercises to N distinct source task IDs. Both commands
  accept `--results DIR` and `--suites DIR`.

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
static/typecheck or harness-loading errors; failing runtime unit tests;
missing required or forbidden pattern/citation; finally a legacy
failure-reason fallback. The CLI prints the actual matching check/detail
for each row. A product-call parse failure is classified as "answer cut off"
because STAR delivered no usable answer; an unknown global may instead be
a typo. Those caveats are visible and should be reviewed before promoting
a lesson.

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

## Practice generation

The current largest cause is **required feature missing** (25 failed
attempts, 16 distinct source IDs), so a default practice generation
produces **16 unique exercises**. Each uses a fixed Luau template with
parametrized limits and multiplication, a new game scenario chosen from
the original task's **category** (for example UI, remotes, animation,
VFX, performance), and a new stable hashed ID. It does not use the
golden prompt or reuse golden test code.

Each practice task includes static compilation and required/forbidden
checks plus a generated Luau test with **four** behavioral assertions:
the function is returned, fractional input is floored before scaling,
the low boundary is respected, and the high boundary is respected.
The output includes a minimal sandbox prelude and is validated by
night school's actual `load_pool` in the tests. A copy guard compares
every generated prompt with every golden task by token overlap, rejecting
any eight-token verbatim stretch or high overall overlap. The separate
holdout file is never read.

The CI unit tests use a scripted sandbox to exercise the actual
`score_answer` code path and its checks; they do **not** execute an
actual Luau VM. Full runtime validation awaits an explicitly authorized
night-school run. Generated tasks are not switched on by default.

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
