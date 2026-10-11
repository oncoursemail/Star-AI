# STAR Data, Obsidian & Graphify — Grounded Intelligence Upgrade

**Research snapshot:** 2026-10-11  
**Status:** Review-only source candidate, not a published STAR build. Neither native Windows nor real Qwen/Obsidian/Graphify acceptance is claimed.

## Research conclusion

STAR already includes bounded Decimal arithmetic for attached data, opt-in Markdown vault searching, read-only Graphify graph queries and reviewed project memory. The highest-return improvement is better *evidence quality*: structured profiling, explicit note links, source locations, tool relevance and honesty about missing or incomplete results, not merely adding tool schemas to every request.

### Verified references

| Technology | Verified capability | STAR design decision |
|---|---|---|
| Obsidian notes | Local Markdown, wiki-links, headings and link aliases | Read direct wiki-link references conservatively. Never promote unreviewed notes to accepted memory |
| Obsidian Graph | Displays internal-link relationships | Links represent navigable references, not proof of a claim |
| Obsidian Bases | Dynamic views over Markdown note properties and files | Future opt-in read-only YAML property queries and project dashboards |
| Graphify | NetworkX node-link JSON with attributed EXTRACTED/INFERRED/AMBIGUOUS relationships | Keep provenance and mark partially returned graph paths |
| SQLite FTS5 | Full-text indexing, BM25 and trigram tokenization | Benchmark project-scoped hybrid retrieval against the current keyword baseline |
| DuckDB | CSV/Parquet analysis and pushdown over selected files | Future scoped analytics worker with bounded, host-generated queries; no arbitrary model SQL |

Sources:
- Obsidian internal links: https://obsidian.md/help/links
- Obsidian Graph: https://obsidian.md/help/plugins/graph
- Obsidian Bases: https://obsidian.md/help/bases
- Obsidian Vault API: https://docs.obsidian.md/Plugins/Vault
- Graphify architecture and confidence: https://github.com/Graphify-Labs/graphify/blob/v8/docs/how-it-works.md
- SQLite FTS5: https://www.sqlite.org/fts5.html
- DuckDB multi-file processing: https://duckdb.org/docs/current/data/multiple_files/overview
- DuckDB Parquet pushdown: https://duckdb.org/docs/stable/data/parquet/overview
- MCP security: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices

## Implemented in this candidate

**1. Attached-table quality profiles.** star_data_analyze now accepts operation=profile. For an exact attached dataset_id, it reports per-column observed missing, numeric, text, boolean, formula-looking and out-of-range numeric counts, a heuristic type assessment and numeric min/max. No raw string samples or formula execution. Optional exact column profiling works on wide tables. Maximum 40 columns or 200,000 inspected cells per request; existing 50,000-row dataset limit remains. Source/parser warnings are preserved. No independent file path or executable query is accepted.

**2. Obsidian wiki-links and backlinks.** star_obsidian_links takes one selected vault-relative Markdown path and returns outgoing links, backlinks, first source line, totals and partial-scan status. Aliases and heading fragments are stripped to resolve links; fenced example blocks are ignored. Only unique visible note names or explicit vault-relative targets are followed. Ambiguous names, hidden directories, symlinks, traversals and unsupported external links are never guessed. It scans at most 2,500 visible notes, uses 64 KB previews and a 24 MB total budget. A partial scan cannot prove an absent backlink.

**3. Honest Graphify path completeness.** For relationship paths exceeding 30 returned nodes, the API now exposes truncated=true, returned_hops separately from full discovered hops, and a warning that the visible path omits the destination. Inferred graph edges remain inferred; this is not code execution or a test of behavior.

**4. Explicit profiling provenance.** The document tool distinguishes observational table profiles from exact Decimal calculations. Neither is treated as externally verified truth when its attached source has missing or incomplete records.

## Target evidence-first architecture

1. Intent and scope: user chooses attached tables, workspace and opt-in vault; an executable policy checks authorization.
2. Tool selection: reveal only the relevant read-only tool contracts, then request further details incrementally.
3. Evidence ledger: record source, path or line, extracted/inferred status, timestamp, calculation and missing-data flags.
4. Claim construction: reason from retrieved evidence and explicitly disclose where an assertion is not verified.
5. Independent checks: recompute numeric values with local validators, verify graph claims against code, and compare decisions against reviewed project memory.
6. Answer: provide citations and linked next actions; visually render genuine data with React/Recharts only when meaningful.
7. Feedback: use owner-reviewed findings and real benchmarks to improve retrieval and tool routing, without auto-promoting model guesses.

## Follow-up engineering priorities

### P1 — Retrieval effectiveness
Build frozen datasets of real-vault tasks. Compare keyword matching, SQLite FTS5/BM25 and optional local embeddings or reranking. Measure Recall@5, MRR, exact citations and p50/p95 latency. Index only approved project scopes, invalidate on changes, do not read hidden note data.

### P2 — Graph integrity and freshness
Record graph export time, file digest/commit and source fingerprints. Report when the current project may have changed since Graphify export. Preserve graph edge direction, source references and extracted/inferred uncertainty. Do not follow arbitrary source paths from graph metadata.

### P3 — Obsidian richer semantics
Add safe YAML frontmatter, Markdown-style links, aliases and local relative-path resolution behind fixed fixtures. Optional Bases-compatible views may be useful. User authorization and separate review are required before any note writing or synchronization.

### P4 — Broader statistics
Introduce robust type contracts, dates, distributions, quantiles and grouped data-quality diagnostics. For large data, evaluate an isolated DuckDB worker that opens only user-approved tables, restricts memory/CPU and blocks network, extension loading and model-written arbitrary SQL.

### P5 — Multi-tool optimization
Add a per-turn tool budget, deterministic dependency planner, permission-aware source merging, observable error recovery and a small model-readable tool catalog. A stronger result must be shown in independent holdout tasks, not inferred from a higher count of plugins, agents or tokens.

### P6 — Visual evidence
Use existing Recharts UI for plots from real results with axis labels, units, null states and source links. Do not fabricate analytics, user activity, trends or plot points.

## Release gates: proposed targets, not achieved scores

| Gate | Proposed expectation |
|---|---|
| Data profiles | Every fixture count is exact; malformed and mixed cells are exposed; no formulas executed |
| Obsidian isolation | Zero unauthorized path/symlink/hidden reads; no ambiguous-link guesses |
| Link quality | At least 95% precision for the specifically supported wiki-link corpus, with line evidence |
| Graph evidence | Zero unlabeled truncated path results; no inferred relationship presented as extracted |
| General answer quality | Demonstrated improvement on owner-reviewed real tasks compared with a frozen baseline |
| Performance | Track p50/p95 retrieval latency, context bytes and memory use; no unreviewed regression |
| Live acceptance | Separately verify real Windows 11, Qwen tool selection, owner vault, exported graph and installer upgrade |

Offline development checks:
- python -m compileall -q star main.py
- python -m pytest -q
- frontend Vitest and build checks when relevant
- python -m star.evals gate for activation-relevant changes
- Real Windows/Obsidian/Graphify smoke tests before release

## Safety and limitations

These changes do not silently enable Obsidian, add a cloud provider, open arbitrary URLs, run user-supplied SQL, execute Graphify, write vault content, train model weights or bypass Roblox Studio edit permissions. All returned notes, table contents and graph records remain untrusted reference data. The model may use them to produce a cited answer but cannot use them to grant itself new permissions.

A reviewable source PR and mocked tests are not evidence that a public release includes this functionality.