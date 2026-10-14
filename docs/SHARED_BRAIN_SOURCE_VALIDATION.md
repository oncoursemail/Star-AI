# Shared-brain development source validation

The historical retrieval comparison is fixed to its original source bytes.
Current regression controls use a separately identified, **vendored**
development-only source overlay at `tests/fixtures/shared_brain_sources/`.
These twelve source snapshots are copied from the reviewed integration
revision, not from the mutable `star/*.py` files of the test checkout. The
benchmark never silently substitutes this overlay for its historical pins.
These controls establish behavior only on that captured snapshot and cannot
update historical performance claims. Future unrelated source edits therefore
do not invalidate the normal test suite's frozen byte or AST-line checks.

## Captured integration snapshot (immutable test fixtures)

Version 4 of `tests/fixtures/shared_brain_runtime_source_validation.json`
identifies the source bytes from exact Claude integration revision
`77f7e4e7e118a82f72ded480a5ed5b7519731ec7`. Codex normally merged it into
its own runtime branch from `d01342612bada61c7d95d582478a2c0f288d3636`.
This includes retention head `42f5e3e1483c98008b0c1a15e138fcf0436cf156`,
corpus head `384409868dadb54d8dd76d207c230299595dc068`, media head
`39377e7148d93fb3813df9af73e5782c8decbb11` and integration's security fixes.
The pinned twelve source files exactly equal that revision's Git blobs;
the runtime feature files remain separate from these development source pins.

Version 4 supersedes version 3's semantic SHA256
`14beaa290256e84e2005323a6bd74eb6ea5e6eb5444b17f15a64f55d6d6fd320`.
Version 3 identified combined runtime revision
`cdd1a917ebe24423b75063c3c897ad0a06ba8019` before media/security integration.

Version 3 supersedes version 2's semantic SHA256
`0cc405336f98827426a326084ceb80e687b93c0da2b74bb24797aa1c15fe0296`.
Version 2 followed the initial lessons-only overlay, whose semantic SHA256 was
`0ce9202b56faa8b3a18c5404d3c263bdc11b627c4bff5eee81af13a1b236b5fb`.
Earlier versions remain in runtime branch history.

Independent audits checked all twelve development expected-source files.
Four files differ from the historical pins and match the integration revision's
committed Git blobs:

| Source | Last source change | Development declaration |
| --- | --- | --- |
| `star/agent.py` | Retention/media merge, `6467ee5f8447204a167e0881f308d648f87b5b53` | `validate_model_roles`, historical line 112, current line 121 |
| `star/memory.py` | PR45 after PR42, `c8c303232851d0c028b72f1047421a8a650e217a` | `Memory.put`, historical line 24, current line 25 |
| `star/lessons.py` | PR41, `52a7b5147297230c265a8c5b65f5221c1395bdd4` | `LessonStore.capture_inferred`, line 527; `LessonStore.recall`, line 657 |
| `star/selfbuild.py` | Work-branch security preflight, `54ef0b2c606a9524ca14ce60434cc6b3a3d6caa2` | `skill_path`, line 19; `write_source`, line 50 |

All six development symbol identities and original grounding excerpts remain
unchanged. PR42 adds request budgeting/document dispatch and layered compaction;
PR45 adds scoped conversation prefix checkpoints and explicit history pressure;
PR41 normalizes the lessons export destination. Media adds `image_max_side` to
`execute` and forwards it to `image_part`; the merged signature retains
`preserve_history` and its history-pressure path. The declaration used by the
development agent case remains at line 121. Selfbuild now validates the configured
work branch before any model call and clarifies where its draft PR targets;
the two pinned selfbuild declarations and excerpts remain unchanged. This
source audit does not replace independent security review of that change.
Memory and lessons retain their exact version-3 hashes and blobs.
The other eight development
source pins remain the original exact pins. `star/intelligence.py` is not an
expected-source pin in this suite.

## Explicit pins and refusal controls

The fixture is explicitly `development_source_validation`. Every changed
source records its historical SHA256, current exact CRLF SHA256, equivalent
LF SHA256, Git blob identifier, observed source revision, last source-change
commit, historical declaration location and independently verified current
location/excerpt. The canonical semantic JSON SHA256 is
`14d4dd4c11c75d3f873d835048afcab91b9c85ee84afb13485ada8e37f7a124e`,
pinned in `tests/test_shared_brain_variants.py`. JSON line-ending transport
does not change that semantic digest.

Development variant controls copy these identified **vendored** source
bytes, never live STAR implementation files, into disposable projects. Pure LF transport can reconstruct exact pinned CRLF bytes only when
the hash matches. Mixed source transport, changed fixture content or an unreviewed edit to a
vendored snapshot fails. Changes to unrelated live project files do not. Tests verify every current declaration and its
original grounding excerpt, current LF digests and Git blob identifiers.
They also explicitly prove each historical source pin rejects the changed
file and each current pin rejects a further edit.

Four development-only benchmark guard probes verify that the historical
memory, lessons, selfbuild and agent cases reject current bytes before graph queries,
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
current development control corpus contains the exact identified integration
source bytes, including PR41/PR42/PR45, media and work-branch preflight, and is
distinct from that historical measured corpus. This maintenance adds no
retrieval algorithm change, holdout rerun, live model evaluation or new
unseen-performance claim. Future retrieval tuning needs a new independently
authored holdout. Shared filesystem custody remains the documented limitation.
