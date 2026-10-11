# Shared source-backed knowledge

`star.shared_brain` gives Claude, Codex and STAR adapters one local JSON interface
to a selected project's Graphify graph. It retains source locations, extraction
origin, confidence, relationship direction and current source freshness. Query
outcomes become candidate observations. They never become trusted instructions or
approved lessons automatically.

This change adds an operator CLI and an injectable tool adapter. It does not
register tools in STAR's default runtime, change assistant settings, start a
service, or activate a retrieval proposal automatically. A host can use
`SharedBrainTools.definitions()` and `.call()` with its existing tool orchestration.

## Build and retrieve

Run from a STAR checkout with its normal Python dependencies. `refresh` also
requires the optional `graphifyy` package; this implementation was verified with
version 0.9.69. Extraction uses official Graphify AST parsing and its per-file
cache. It invokes no model or semantic extraction backend.

```powershell
python -m star.shared_brain --workspace . refresh
python -m star.shared_brain --workspace . query "ToolWorkshop registry" --budget-chars 3000
python -m star.shared_brain --workspace . stats
python -m star.shared_brain --workspace . tools
python -m star.shared_brain --workspace . call shared_brain_query '{"question":"KnowledgeStore find_ranked"}' --actor codex
```

The default corpus is selected architecture code, including this implementation.
Repeat `refresh --source star/path.py` to choose a smaller explicit corpus. Sources
must be allowed code paths inside the selected project. A source list replaces the
default; it is not a directory scan. Graphify still resolves relationships across
all selected files on each build. Reported changed/reused counts refer to content
digests; Graphify owns parsing-cache behavior.

The generated `graphify-out/graph.json`, freshness manifest, staging cache and
SQLite store are local artifacts. A graph/manifest digest mismatch cannot attest
freshness. Source changes and missing sources are checked during retrieval;
stale or unsafe nodes are excluded by default. Importing an existing graph with
`sync` preserves it as freshness-unknown until a matching build manifest exists.
AST records are extracted references, not approvals. Semantic/imported records
remain candidate references. Unknown references may be returned with that label.

Both assistants must select the **same canonical workspace directory** to share
queries and outcomes. A worktree is a different selected project from its parent
checkout. Copied stores cannot silently bind to another path. After integration,
refresh and initialize a store for the destination checkout instead of copying a
worktree database. `--store` selects an explicit local store directory, still
bound to that workspace. Concurrent first use and incremental imports use locks
and SQLite transactions.

Responses use compact JSON. `budget_chars` bounds the complete serialized query
envelope in Unicode characters, including provenance and metadata; it is not a
tokenizer count. The model tool maximum is 6,000 characters. Links retain their
original source/target direction even when displayed beside an incident node.

## Capture outcomes

Use the query's returned `query_id`:

```powershell
python -m star.shared_brain --workspace . feedback QUERY_ID useful --actor claude
python -m star.shared_brain --workspace . feedback QUERY_ID corrected --actor codex --correction "The relevant symbol is find_ranked in star/knowledge.py."
python -m star.shared_brain --workspace . feedback QUERY_ID dead_end --actor star
python -m star.shared_brain --workspace . lessons
```

Feedback is append-only, scoped to an existing query in this project, and marked
candidate. Corrected outcomes require a correction. Existing lesson secret
screening rejects credential-shaped query/feedback content. The host chooses the
actor; an actor label is attribution, not authentication or permission.

## Evaluate knowledge and tool proposals

`ImprovementLoop` is an operator-owned controller over existing read-only
primitives. Aliases can expand bounded query terms into an existing vocabulary.
Recipes compose configured ToolWorkshop source types (`knowledge`, `workspace`,
`obsidian`, `graphify`, `skills`) and fixed limits. They cannot add a source,
command, import, permission or executable expression.

Construct the controller in a trusted host using a separately managed journal,
fixed `Fixture` values, explicit source files, vocabulary and adapter callbacks:

```python
from star.shared_brain.improve import Evidence, Fixture, ImprovementLoop, Limits
from star.shared_brain.protocol import SharedBrainTools

# graph_source(question, limit) must return bounded Evidence values, with exact
# node identifiers and relative source paths from the selected source manifest.
# Its implementation and all other callbacks are trusted host code.
loop = ImprovementLoop(
    journal_directory,
    source_root=workspace,
    source_files=independently_selected_sources,
    cases=independently_authored_fixtures,
    sources={"graphify": graph_source},
    vocabulary=source_vocabulary,
    limits=Limits(context_chars=3000),
)
tools = SharedBrainTools(brain, actor="star", improvement_loop=loop)
candidate = loop.propose_aliases({"login": ["authenticate"]})
record = loop.evaluate(candidate["id"])
```

Keep fixture authoring, callback construction, journal writes, evaluator files and
operator review outside the model's writable capability. This Python interface
is not a process sandbox. Hash checks detect changed artifacts; they do not stop
a privileged caller from replacing the entire trusted host. Models receive
query/feedback/proposal/status tools only. Evaluation and review are host actions.

The injected controller must bind to the same workspace and evaluate within the
tool's context cap. Active-query dispatch returns the complete evaluated response
without dropping records afterward. A smaller requested budget that cannot fit
that response is rejected, so clipping cannot silently invalidate fixture proof.

Every configured fixture runs for both baseline and candidate, alternating order,
with repeated measurements. Scoring checks expected source paths and optional
exact identifiers belonging to those sources. Explicit `expected_evidence`
source/identifier pairs prevent swapped identities across modules. It also checks
negative/forbidden evidence and required primitive success.
Failures, missing fixture IDs, per-case regressions, stale sources, changed
verifier/fixtures or exceeded latency/context caps block promotion. A candidate
must have a measurable correctness, tool-success or efficiency improvement;
efficiency credit requires a correct successful result. Measured controller time
covers callbacks/context assembly; journal and snapshot overhead are excluded.

Only after separately reviewing a passing exact evaluation digest can the trusted
host call:

```python
approval = dict(evaluation_digest=record["evaluation_digest"],
                human_approved=True, reviewer=operator_identity)
loop.review(record["id"], **approval)
loop.activate(record["id"], **approval)
loop.retrieve("Where is login?")  # Uses the active reviewed version.
loop.rollback(expected_version=record["id"], human_approved=True,
              reviewer=operator_identity)
```

These calls are absent from the model-facing protocol. A hash-chained journal
retains proposal, evaluation, review, activation and rollback history. Source
snapshots, canonical project identity, fixture/configuration digests and verifier
digests are checked again before promotion and retrieval. Rollback restores the
previous immutable configuration only if its sources remain current.

Code candidates may be recorded for separate review through `register_code`,
which reuses selfbuild path validation and syntax checking. Their commit-shaped
metadata is not proof that a Git commit exists. Generated code is never executed,
evaluated or activated by this controller. This is retrieval/configuration
improvement, not model weight training.

Tests exercise a local alias improvement from 2/3 to 3/3 fixed fixtures, active
retrieval after reopening the journal, and rollback to the original result. A
recipe test uses the existing reviewed KnowledgeStore primitive and improves
required tool success without approving another project's candidate note. These
are deterministic local fixtures, not live STAR/Roblox/model evaluations. The
existing independent `star.eval_gate` is an additional check when integrated;
this module does not modify Claude's gate or its fixtures.

## Coordination

```powershell
python -m star.shared_brain --workspace . coordination --collab-root PROJECT_ROOT
python -m star.shared_brain --workspace . coordination --collab-root PROJECT_ROOT --after CURSOR --actor codex --ack
```

The selected root must contain the workspace. This reads bounded snapshots of
the existing `COLLAB/BOARD.md` and `COLLAB/MESSAGES.md`. Durable message IDs and
prefix-digest cursors support incremental reads and detect rewritten history.
An optional local receipt records only which messages were observed. It grants
no ownership or permissions and never edits claims. BOARD, ledger and shared
messages remain the coordination channel; there is no second bus or scheduler.

## Measurements and verification

`scripts/shared_brain_benchmark.py` compares existing `GraphifyGraph` retrieval
and shared retrieval against the same export and independently authored fixed
source/symbol cases. Fixtures include expected source hashes and exact symbols.
Development and holdout results are separate. Both arms use top eight matches;
shared output has a 3,000-character whole-envelope cap, while the baseline has no
character cap. Do not attribute cap-driven context reduction to better ranking.

```powershell
python scripts/shared_brain_benchmark.py --workspace . --split development --output comparison.json
```

Reports measure local source/symbol retrieval, wall time and serialized context.
Shared wall time includes source freshness checks and query audit persistence;
the baseline includes neither. Estimated tokens are characters divided by four,
not tokenizer measurements. No model answer quality, general intelligence,
generated skill execution, server or Roblox task success is inferred.

The recorded source-byte pins belong to the measured Windows checkout. The
benchmark rejects mismatching bytes, including another checkout's line endings;
its result is scoped to that snapshot. Independent variant tests can reconstruct
the exact pinned CRLF bytes in a disposable copy from an equivalent LF checkout,
only when the existing SHA256 verifies that reconstruction. Actual content drift
still fails. The JSON fixture itself has an explicit LF checkout attribute so
its frozen digest survives Git transport.

Focused tests cover actual Graphify extraction/deletion, copied-project refusal,
concurrent imports/first use, stale/missing sources, secret screening, bounded
responses, independent decoys/noise, schema controls, immutable fixture/verifier
checks, review/activation and rollback. Optional extraction tests require the
Graphify runtime. Real Windows symlink tests may skip when the account lacks
creation privileges; simulated link/junction checks still run.

### Recorded local comparison, 2026-10-11

[Machine-readable results](shared-brain-results-20261011.json) record the frozen
fixture and graph digests, measurements and limitations.

| Measure | Existing Graphify retrieval | Shared retrieval |
| --- | ---: | ---: |
| Development source + symbol cases | 13/19 | 13/19 |
| Previously unread holdout cases | 1/5 | 1/5 |
| Combined cases | 14/24 | 14/24 |
| Median serialized context, all samples | 3,885.5 characters | 2,842 characters |
| Median local wall time, all samples | 1.830 ms | 46.623 ms |

The approximately 27% context reduction comes with the shared 3,000-character
cap; the baseline has no character cap. This does not establish better ranking.
Shared timing includes freshness checks and audit persistence. Its added latency
is visible, and the holdout result is weak. No broad quality or speed improvement
is claimed and no project optimization was activated from these measurements.
Future tuning needs a new independently authored holdout.

The frozen comparison build used 20 selected sources (489 nodes, 990 edges); the next unchanged
build reported 20 reused sources, zero changed sources and 709 ms. Extraction
invoked no model. Independent fixture authoring and a pre-holdout freeze provide
procedural separation, not cryptographic custody: agents share the filesystem.
Owned background checks finished before timing; other host work was not controlled.

Validation: final full Python suite **1,092 passed / 14 skipped**, frontend **114 passed**,
TypeScript and Vite build passed, Python compilation passed. Skips comprise 11
host symlink-privilege cases, two explicitly opt-in live-service checks and one
missing optional PySide6 UI check. The suite used disposable APPDATA; simulated
link/junction controls passed. CLI smoke exercised query, all three candidate
outcomes, paged coordination and a receipt without changing the board. Actor
labels in this smoke are attribution from one host, not proof of live requests
by the other assistants.

After the measured freeze, platform validation gained the Windows 3.11 reparse
fallback and test-only Git transport controls. Metrics retain their original
frozen snapshot; there was no ranking/configuration tuning or holdout rerun.
These platform cases were simulated on Windows Python 3.12; actual Linux and
Python 3.11 execution are not claimed.

For Claude's analyzer, consume frozen result/evaluation JSON and aggregate
`shared_brain_stats`, preserving exact task IDs, measurement scope, errors,
regressions and unknown metrics. Keep raw query/feedback text out of evidence
packs. Analyzer proposal files should cite the same evidence-pack digest;
scorecards should retain failed predictions. The existing collaboration toolbox
owns launchers and messaging. This module supplies local references and evaluation
contracts; autonomous settings and generated-code sandboxes remain separate work.
