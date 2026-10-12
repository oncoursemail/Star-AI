# Lesson hygiene: proposals, not automatic changes

`star/lessons_hygiene.py` examines the records described in
[How STAR learns](STAR_LEARNING.md). It accepts the existing frozen `Lesson` objects,
`Lesson.public()` dictionaries, or lesson dictionaries from a `star-lessons-v1` export.
It never calls the lesson writers, promotes a candidate, changes permissions, or
modifies a lesson's text, status, source, evidence, project or use count.

## Command line

```sh
python -m star.lessons_hygiene report
python -m star.lessons_hygiene report --home ./star-data --stale-days 90
python -m star.lessons_hygiene report --input lessons.json --as-of 2026-10-12T00:00:00Z
python -m star.lessons_hygiene report --input lessons.json --project global --project-name "Harbor Tools"
```

The default data folder matches `desktop_core.app_data`: `APPDATA/STAR` on Windows
(with the same home-folder fallback), or `XDG_DATA_HOME/star-ai` elsewhere (default
`~/.local/share/star-ai`). `--home` names that data folder, **not** its `knowledge`
subdirectory. The database is `knowledge/knowledge.sqlite3` below it.

The only output is a JSON report on stdout. A missing database produces an empty
report with a warning and creates no folders or database. Invalid input, an unreadable
database or a pre-lessons schema produces a diagnostic on stderr and exit status 2;
no repair or migration is attempted. A successful report returns 0 even when proposals
exist. There is no `apply` command.

The SQLite connection uses `mode=ro` and `query_only`, not `LessonStore` initialization,
which can migrate a database. It reads every lesson, without the review page's list
limits, and includes committed records in a live application's WAL. It does not use
`immutable=1`, which would miss WAL changes. SQLite may participate in normal WAL
coordination; the report cannot write application records or schema.

## What the report contains

`format` is `star-lessons-hygiene-v1`; `review_required` is always true. `as_of` is UTC,
`scanned` counts all supplied records (including retired ones), and `proposals` contains
pairwise merge/contradiction proposals and individual stale/scope proposals. Every
proposal carries the original lesson IDs, project and evidence objects containing
`lesson_id`, `source` and the full original `evidence` excerpt. No provenance is replaced
with the preferred wording and no evidence is concatenated into a clipped text field.

Only `accepted` and `candidate` records enter duplicate, contradiction and scope checks.
Rejected, superseded and already merged records are not proposed for revival. Inactivity
and override checks apply only to accepted lessons; waiting for review is not evidence
that a candidate is stale.

### Near duplicates and merge proposals

Subject-token overlap covers at least 80% of the shorter subject and at least 50% of the
longer, with at least two shared tokens. Exact normalized text can match shorter rules.
Normalization handles Unicode, case, whitespace, simple plurals and dotted identifiers
such as `task.wait`. The thresholds are intentionally conservative. Unlike recall's
subject-only matching, the hygiene pipeline checks instruction direction first.

An optional injected embedding callable adds cosine-similarity matches (default 0.93).
It is called once per distinct active text in a report; invalid, empty, zero, non-finite
or mismatched vectors fall back to token matching with warnings. Exceptions from the
callable do not expose provider diagnostics or lose lexical findings. The default CLI
never creates a client, loads a model, requires a GPU, calls a keyring or sends text
anywhere. A caller supplying `embed` is responsible for keeping that callable local and
appropriate for the data; nothing opts in to a remote embedding service automatically.

A merge proposes one **existing, verbatim** wording. Specificity is ranked by unique
subject tokens, explicit numeric/conditional constraints, accepted status on a tie,
and then the lower ID for deterministic results. A more detailed candidate can supply
the proposed wording, but remains untrusted until explicitly reviewed. Both original
evidence records survive in the proposal. These are pairwise suggestions, not a
transitive cluster or an automatic union of possibly incompatible instructions.

Merges never cross exact project identifiers. Suspect global records naming different
projects are not folded together, nor is project-specific wording folded into generic
global advice. Conflicting numeric values, unmatched conditions/negation and opposing
instructions block a merge even with an identical embedding.

### Contradiction candidates

The report recognizes same-topic positive/negative imperatives, including `always use`
versus `never use`, `do not`, `don't`, `avoid`, and `stop using`. It also recognizes common
opposites such as enable/disable, include/exclude, allow/disallow, keep/remove and
accept/reject, plus reversed `instead of`, `rather than`, `not`, and `prefer ... over ...`
choices. Clause-level directions keep negation about one topic from automatically
negating another topic in the same lesson. Such pairs produce contradiction candidates,
never merge proposals.

This is a lexical heuristic, not an entailment model. It does not prove that the lessons
cannot both hold in different contexts, recognize every natural-language instruction,
or resolve an exception. A reviewer must read both originals. Similarity and longer
wording likewise do not prove that one lesson safely subsumes another.

### Staleness and explicit override observations

An accepted lesson is an inactivity candidate when at least `stale_days` have elapsed
since `last_used`, or since `created` if `uses` is zero. The boundary is inclusive.
`updated` is deliberately not a use time: an edit or review must not disguise inactivity.
Naive historical timestamps are interpreted as UTC; invalid, future or inconsistent
histories produce a warning rather than invented staleness. `as_of` is explicit in the
pure API and configurable on the CLI, making a saved report reproducible.

**The existing `lesson_use` table counts recall, not whether the model obeyed a lesson
or the owner overrode it.** Neither a high use count nor `supersedes_id` proves "always
overridden." For this check the caller supplies explicit observations:

```python
from datetime import datetime, timezone
from star.lessons_hygiene import OverrideObservation, build_report

observations = [
    OverrideObservation(15, "chat:example#1", True),
    OverrideObservation(15, "chat:example#2", True),
    OverrideObservation(15, "chat:example#3", True),
]
report = build_report(
    lessons,
    as_of=datetime(2026, 10, 12, tzinfo=timezone.utc),
    overrides=observations,
    # embed=local_embedding_function,  # optional: text -> finite numeric vector
)
```

The CLI accepts `--overrides outcomes.json`, a JSON list of objects with `lesson_id`,
`source` and boolean `overridden`. At least three distinct observation sources are
required by default; repeated sources count only once, conflicting observations are
rejected, and any non-override blocks the "all supplied observations" finding. All
outcome sources are included as additional evidence. The report explicitly says that
unobserved turns remain unknown. With no supplied observations it warns that override
checks lack evidence; it does not silently assume that zero overrides occurred.

### Scope checks

`global` (case-insensitive) is a **lint convention**, not a new runtime recall scope.
In particular, the existing default project `STAR` is not treated as global. Other
labels can be supplied using repeatable `--global-project` or the API's `global_projects`.

The checker uses non-global project identifiers found in the supplied records, explicit
`project "Quoted Name"` / `project CapitalizedName` mentions, and optional known names
(`--project-name`, repeatable, or `project_names`). Matching uses word boundaries and
prefers a longer project name over an overlapping shorter name. A global lesson naming
exactly one project receives a scope proposal with `suggested_project`. A lesson naming
multiple projects does not get an arbitrary single-project reassignment. Unknown names
without an explicit project marker can be missed; supply the project catalog when it
is available. Generic wording such as "this project" is not a named project.

## Review and tests

The existing review page still controls approval, editing and rejection through
`human_approved=True`. This report is not an input to `reviewLesson` and introduces no
merge or project-move action. The reviewer must inspect the identified originals and
both evidence records; generating the report never constitutes approval.

`tests/fixtures/lessons_hygiene.json` contains exactly forty synthetic lesson records,
including two lexical duplicate pairs, five contradiction pairs, three single-project
scope violations, two old unused/used lessons, an exact-age boundary, an always-overridden
sample and negative controls. An injected test embedding adds one known paraphrase pair.

```sh
pytest -q tests/test_lessons_hygiene.py tests/test_lessons_hygiene_store.py
pytest -q
```

The first test module executes the pure report, the actual module CLI and its SQLite
reader (including uncheckpointed WAL, missing/old databases, exports, and records beyond
review-page limits). The store integration module tests the real frozen `Lesson` type,
`LessonStore` capture/export/recall/review methods, database immutability during reporting,
and parity with the actual desktop data-folder function. All test data is synthetic;
no embedding service, network, GPU or real keyring is needed by these tests.
