# Shared-brain development source validation

The historical retrieval comparison is fixed to its original source bytes.
Current regression controls use a separately identified development-only
overlay; the benchmark never reads it. These controls establish behavior on
the current source snapshot and cannot update historical performance claims.

## Current integration snapshot

Version 2 of `tests/fixtures/shared_brain_runtime_source_validation.json`
identifies the no-commit merge of integration revision
`ceb5a6a610dd7be8341d79fe40576e97d2c9d4bc` into runtime head
`f73217cc682a1423034e4cbcb1d716d1d723506d`. This follows the initial
lessons-only overlay, whose semantic SHA256 was
`0ce9202b56faa8b3a18c5404d3c263bdc11b627c4bff5eee81af13a1b236b5fb`.
That earlier version remains in runtime head history.

Independent audits checked all twelve development expected-source files.
Three files differ from the historical pins and match the incoming revision's
staged Git blobs:

| Source | Last source change | Development declaration |
| --- | --- | --- |
| `star/agent.py` | PR42, `22144eacafec8eaf7f1d4f3291c8e4d8a87bc9c2` | `validate_model_roles`, line 112 |
| `star/memory.py` | PR42, `22144eacafec8eaf7f1d4f3291c8e4d8a87bc9c2` | `Memory.put`, historical line 24, current line 25 |
| `star/lessons.py` | PR41, `52a7b5147297230c265a8c5b65f5221c1395bdd4` | `LessonStore.capture_inferred`, line 527; `LessonStore.recall`, line 657 |

All four development symbol identities and original grounding excerpts remain
unchanged. PR42 adds request budgeting/document dispatch and layered compaction;
PR41 normalizes the lessons export destination. The other nine development
source pins remain the original exact pins. `star/intelligence.py` is not an
expected-source pin in this suite.

## Explicit pins and refusal controls

The fixture is explicitly `development_source_validation`. Every changed
source records its historical SHA256, current exact CRLF SHA256, equivalent
LF SHA256, Git blob identifier, observed source revision, last source-change
commit, historical declaration location and independently verified current
location/excerpt. The canonical semantic JSON SHA256 is
`0cc405336f98827426a326084ceb80e687b93c0da2b74bb24797aa1c15fe0296`,
pinned in `tests/test_shared_brain_variants.py`. JSON line-ending transport
does not change that semantic digest.

Development variant controls copy these identified source bytes into disposable
projects. Pure LF transport can reconstruct exact pinned CRLF bytes only when
the hash matches. Mixed source transport, changed content or a further
unreviewed source edit fails. Tests verify every current declaration and its
original grounding excerpt, current LF digests and Git blob identifiers.
They also explicitly prove each historical source pin rejects the changed
file and each current pin rejects a further edit.

Three development-only benchmark guard probes verify that the historical
memory, lessons and agent cases reject current bytes before graph queries,
store construction or timing. No production freshness check or benchmark byte
check is relaxed. No comparison measurement runs in these guard probes.

## Historical evidence remains unchanged

`tests/fixtures/shared_brain_retrieval.json` retains its original raw SHA256
`516cce6357a4d0796c805d7b03dd53df3a965bb5a70cba1c7f388b5485135696`.
Its source hashes, queries, split, scoring and disclosed holdout remain
unchanged. Original result JSON and the immutable measured archive remain
unchanged. The benchmark still refuses these changed files against the original
source snapshot.

The original result remains 13/19 development and 1/5 disclosed holdout for
each arm, with smaller capped context and higher shared-query latency. The
current development control corpus contains reviewed PR41/PR42 bytes and is
distinct from that historical measured corpus. This maintenance adds no
retrieval algorithm change, holdout rerun, live model evaluation or new
unseen-performance claim. Future retrieval tuning needs a new independently
authored holdout. Shared filesystem custody remains the documented limitation.
