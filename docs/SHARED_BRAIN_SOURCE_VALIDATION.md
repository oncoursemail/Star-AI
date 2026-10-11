# Shared-brain source validation after the export dependency

The runtime branch contains PR43 and the reviewed PR41 export path fix, commit
`52a7b5147297230c265a8c5b65f5221c1395bdd4`, merged at parent
`4b7058a5526d8e88b43d6a6d0f66e0782fe9516e`. That fix changes the bytes of
`star/lessons.py`. The original frozen comparison source pin correctly rejects
the changed file. Runtime changes to `star/intelligence.py` do not affect an
expected-source pin in that suite.

An independent audit checked all twelve development expected-source files.
Only `lessons.py` needed a current pin. Development declarations
`LessonStore.capture_inferred` at line 527 and `LessonStore.recall` at line 657,
including their original grounding excerpts, are unchanged. The two controls
still check the same source/symbol pairs and behavior.

The new fixture
`tests/fixtures/shared_brain_runtime_source_validation.json` is explicitly
`development_source_validation`. Its lessons overlay records the dependency,
original SHA256, current exact CRLF SHA256, equivalent LF SHA256 and the two
declaration locations/excerpts. Its canonical semantic JSON digest is pinned
in `tests/test_shared_brain_variants.py`; JSON line-ending transport does not
change that digest. The other eleven source pins still come from the unchanged
historical fixture.

Current development variant controls copy those identified source bytes into
disposable projects. Pure LF transport can reconstruct exact pinned CRLF bytes
only when the hash matches. Mixed transport, changed content or a further
unreviewed source edit fails. Tests also verify the two current declarations
and explicitly prove the original historical lessons pin still rejects PR41's
bytes. A development-only benchmark guard probe verifies rejection occurs
before graph queries, store construction or timing. No production freshness
check or benchmark byte check is relaxed.

`tests/fixtures/shared_brain_retrieval.json` retains its original raw SHA256
`516cce6357a4d0796c805d7b03dd53df3a965bb5a70cba1c7f388b5485135696`.
Its original source hashes, queries, split, scoring and disclosed holdout remain
unchanged. The benchmark does not load this overlay and still refuses current
lessons bytes for a comparison against the original source snapshot. Original
result JSON and the immutable measured archive remain unchanged.

These are current-source regression controls, not new performance measurements.
The original result remains 13/19 development and 1/5 disclosed holdout for each
arm, with smaller capped context and higher shared-query latency. No retrieval
algorithm change, change to the historical measured corpus, holdout rerun, live model evaluation
or unseen-performance claim is part of this maintenance. The current development
control corpus includes the reviewed lessons change. Future retrieval tuning
needs a new independently authored holdout. Shared filesystem custody remains
the documented limitation.
