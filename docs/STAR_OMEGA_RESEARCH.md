# STAR OMEGA v0.1 — evidence search + pre-failure test planning

**Status:** reviewable source implementation, off by default. This does not deploy a
vector database, ingest the internet, retrain STAR, enable model tools, or start
Roblox Studio. A passing Python unit test is not equivalent to a Studio playtest.

## Research-to-implementation decisions (2026-10-14)

- **SQLite FTS5/BM25:** already integrated in STAR KnowledgeStore. Reuse it instead of
  migrating trusted memories to an unfamiliar database. SQLite documents BM25
  rank order and external-content FTS tradeoffs: https://www.sqlite.org/fts5.html
- **Qdrant:** supports dense+sparse hybrid searches and reciprocal-rank fusion.
  Benchmark only when substantial semantic recall benefit is demonstrated:
  https://qdrant.tech/documentation/search/hybrid-queries/
- **DiskANN:** SSD-aware search for collections beyond memory. Research for
  server-side scale, *not* a package STAR automatically runs:
  https://github.com/microsoft/DiskANN
- **CodeQL and test selection:** use change impact, real diagnostics and targeted
  tests rather than inventing error probabilities. Luau is not a built-in
  CodeQL-supported language: https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/
  and https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/
- **Roblox:** use official Luau analysis and StudioTestService for separately
  authorized execution. A heuristic is *not* proof of an exploit:
  https://luau.org/getting-started/
  https://create.roblox.com/docs/reference/engine/classes/StudioTestService
  https://create.roblox.com/docs/scripting/security/client-server-boundary

## What this change actually adds

### 1. HyperIndex lexical/precision fusion (read-only)

Module: `star/omega_hyperindex.py`

Reads an **existing** local `knowledge.sqlite3`, opened in SQLite read-only mode.
Retrieves reviewed notes in exactly the selected project; unreviewed candidates
remain unavailable. FTS5/BM25 results are combined with a precise
code-identifier signal using reciprocal-rank fusion. An authorized semantic
index **may** provide a bounded list of candidate note IDs; every ID is
rechecked against the original store's reviewed flag and project boundary.

This is a *bridge* for an optional future vector index, not a claim that
embeddings or trillion-scale retrieval are installed. Without FTS5, a fallback
checks only the latest 1,500 reviewed project records and explicitly reports
its limited coverage. Search results carry IDs, source, revision, trust
status, ranking provenance, and retrieval limitations.

Try an existing local memory store:

```powershell
python -m star.omega search "C:\path\to\STAR\knowledge" "MyProject" "OnServerEvent amount" --limit 8
```

No external network access, API keys, or automatic ingestion.

### 2. Futuresight test planner (opt-in to the real Roblox preflight)

Modules: `star/omega_futuresight.py`, `star/roblox_project_preflight.py`

Futuresight reuses source already admitted by the bounded project preflight
and its actual findings (security rules, unknown API diagnostics, loop
warnings, and native Luau diagnostics). It also identifies **test
opportunities** at checked occurrences of RemoteEvents, persistence,
teleports, and lifecycle callbacks. It does **not** label API usage as a
bug. Comments, string literals, and files beyond existing limits must not
generate such test proposals.

The existing optional ModuleScript require graph can contribute missing,
cyclic, and unresolved require scenarios. Each proposal includes its source
file, line, evidence class, invariant and a concrete test to run. The output
states `tests_executed: 0`, `failures_proven: 0` and coverage gaps.

Use it without a knowledge store:

```powershell
python -m star.roblox_project_preflight C:\path\to\place --futuresight --module-requires
```

Optionally attach **already reviewed** project fixes from an existing store:

```powershell
python -m star.roblox_project_preflight C:\path\to\place --futuresight --module-requires --knowledge-root "C:\path\to\STAR\knowledge" --project "MyProject"
```

The knowledge store is read-only; missing or incompatible memory is reported,
not silently created. Previous fixes are references, never executable
instructions. The original preflight CLI and JSON output remain identical
when `--futuresight` is absent. Its exit status still represents the existing
preflight checks, not predicted failures.

## Invariants and tests

New tests in `tests/test_omega_hyperindex_futuresight.py` cover:

1. Reviewed-project-only recall, including external candidate IDs from an
   unrelated project or unreviewed note (which must not leak into results).
2. Bounded FTS5-less fallback, malformed inputs, safe tokenized queries and
   missing-store refusal.
3. No mutation of the local memory database and no mutation or execution of
   user source in preflight.
4. Test proposals for server remote inputs, DataStore failures, and missing
   ModuleScript require targets.
5. No source-usage false positives from comments, strings or oversized files.
6. Deterministic CLI output, opt-in-only changes, coverage limitations, and
   explicit disclosure when historical evidence is unavailable.

## What to measure before adding Qdrant or DiskANN

Use independent, rights-cleared evaluation queries and frozen source snapshots.
Compare STAR's current FTS5 baseline against OMEGA and then against an
*optional* vector backend. Require improved recall@10 **and** latency that
doesn't slow interactive chat; record p50/p95/p99, peak memory, index size,
cold-start time, stale-source rate, and cross-project isolation. Reject
upgrades on inconclusive evidence.

For Futuresight, freeze known-positive and known-negative cases; measure
precision, false alarms, test selection recall, execution budget, and
recovery rates. Never train on the blind holdout used to judge changes.

## Next stages (not implemented in this PR)

- Integrate opt-in retrieval into the agent's query router after paired
  evaluations show an improvement. Do **not** silently replace current memory.
- Add incremental content-hash indexing with source licenses, version
  invalidation, update/delete handling and explicitly authorized external
  retrieval. Do not bulk-copy billions of websites onto owner hardware.
- Add a sandboxed test scheduler for each Futuresight proposal. Use official
  Luau checks for pure code, and permissioned Studio Lab/StudioTestService for
  engine/multiplayer scenarios. Never execute retrieved text automatically.
- Add *calibrated* risk ranking after enough separately verified positive and
  negative examples exist. Until then, priority labels are heuristic, not
  failure probabilities.
- Keep tools off by default, enforce project boundaries, and require
  owner approval for code mutation, Studio access or publishing.

**Acceptance:** CI passing means the bounded offline vertical slice is ready
for review, *not* that trillion-scale infrastructure or a perfect predictive
debugger has shipped.
