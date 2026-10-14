# Checked worked-example retrieval (OFF by default)

STAR reuses automatically checked Roblox practice answers as **untrusted reference data**. It does not fine-tune, train, update model weights, use embeddings, or contact the brain/server.

## Import and enable

1. Night school exports worked-examples.jsonl using the server/night_school/nightschool/real.py outbox writer. Rows have instruction, response, automated-check evidence, source night-school-verified, reviewed=false, and rights_confirmed=false. Those flags mean **not approved for training**.
2. Transfer an export yourself; STAR never fetches it. From the source installation run:
   `python -m star.worked_examples import /path/to/worked-examples.jsonl --project STAR`
   Optional `--home /path/to/data` selects a test destination. The importer validates every row before writing, skips duplicate IDs without replacement, and keeps everything in a separate local worked_examples.sqlite3. A project may store **at most 500 examples across all imports**; an import that would cross that bound is refused atomically rather than silently hiding later IDs. Duplicate IDs do not overwrite answers or provenance. Owner lessons, notes, files and histories remain unchanged.
3. In Settings > Advanced settings > Knowledge & expert tools, enable **Use checked practice examples** and Save. The setting starts false on existing and new installs. Importing does not switch it on.

## Ranking, size and trust

Dependency-free BM25 ranks request terms with a 3x frequency boost plus Roblox API-style terms from an answer. Whole identifier/camelCase terms prevent incidental substring matches. It demands at least two distinct matching terms, 40% request coverage and score >=0.6. Only one or two complete examples fit into a fixed 2400-character cap and remaining turn context. It never truncates Luau source mid-block.

Retrieved text is clearly marked **claimed automated checks, unreviewed** practice reference, not instructions or Roblox Studio verification. A malicious export could forge its source, so the evidence is **claimed automated-check provenance, not cryptographic proof or human review**. The importer rejects malformed/large files, invalid schema, prompt-override instructions, secret-like values and permission grants. The sanitized activity line displays only the number used, not their code, identifiers or text.

## Tool trade-off

| Option | Licence and upkeep | Local cost | Decision |
| --- | --- | --- | --- |
| Python BM25 in the standard library | Python PSF-2.0; small maintained code | bounded scans across <=500 examples | **Chosen** |
| SQLite FTS5 | SQLite public domain; build availability and schema migration | fast indexing | Not necessary for the capped corpus |
| Embedding model retrieval | Model-dependent licence, download and version upkeep | RAM and model inference | Rejected: cannot meet zero-download offline constraint |

## Measurement

20 independent synthetic practice requests test deterministic retrieval with a fake model recording final prompts. They do not use golden or holdout evaluation data and do not prove real-model answer quality. Real desktop run_task and sanitized frontend activity are tested separately. This is retrieval rather than training.


## Durable corpus and provenance migration

Imports store the exact declared evidence strings and the original
`night-school-verified` source in a separate
`worked_example_provenance` table, with `reviewed=0` and
`rights_confirmed=0`. The six-column `worked_examples` table is
unchanged for compatibility with older installations and learning bundles.
Rows imported before this audit table existed remain usable within the
corpus limit, but **no missing historical evidence is invented**; importing
the same ID again skips it without rewriting the response or provenance.

The per-project 500-row limit is enforced under a SQLite write transaction:
a batch either fits (ignoring existing IDs) or none of its new rows is
committed. Another project has its own independent limit and evidence keys.
A weekly learning bundle (star/learned_week.py) respects the same limit: once a
project holds 500 usable (unexpired) examples, further bundle examples are
skipped and counted in the receipt instead of switching retrieval off.
If an older database already contains more than 500 rows for a project,
both new imports and opt-in retrieval raise an explicit error rather than
silently considering only the first 500 IDs. The database is not pruned
or overwritten automatically; review/archive the legacy records before
using retrieval.

Evidence is **declared by the exporting process**, including text that can
be forged while remaining schema-valid. The audit table makes those claims
inspectable, not authenticated. No importer claim means human review,
Studio execution, training rights or owner-approved lessons. Retrieval
remains OFF by default, and this change does not train a model.
