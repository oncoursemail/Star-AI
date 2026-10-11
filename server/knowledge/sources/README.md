# Future documentation corpora

The live STAR Knowledge server indexes only the entries in `../corpora.json` (Roblox Creator Docs
and the Luau site). These nine JSON files are **plans**, not checkout lists: nothing here is
fetched, embedded, served or added to the nightly refresh. The Luau manifest describes the
existing `luau-site` source and must not cause a second copy to be ingested.

Each file identifies an official source and its revision/root, separately describes the text
and code-sample licences (licence URL, publisher's evidence URL and exact supporting quote),
records whether redistribution is allowed, the attribution/conditions, inclusion/exclusion
boundaries, a **non-measured** estimated document-count range, review cadence and a
public-page citation pattern. Content inside a repository or page with its own licence,
third-party art, translations and external examples must be reviewed separately.

## Licence decisions

| Corpus | Text | Samples | Ingestion decision |
|---|---|---|---|
| Unity Manual | CC BY-NC-ND 4.0 | Unity Companion License v1.4 | **link-only** |
| Unity Scripting API | CC BY-NC-ND 4.0 | Unity Companion License v1.4 | **link-only** |
| Microsoft C#/.NET | CC BY 4.0 | MIT | metadata marked ingest-allowed |
| MDN Web Docs | CC BY-SA 2.5+ (page exceptions) | CC0 for newer snippets, MIT for older | metadata marked ingest-allowed; preserve legacy snippet credits |
| Python standard library | PSF v2 | PSF v2 or 0BSD (modern examples) | metadata marked ingest-allowed |
| TypeScript Handbook | CC BY 4.0 | MIT | metadata marked ingest-allowed |
| Lua 5.4 Reference Manual | Lua MIT | Lua MIT | metadata marked ingest-allowed |
| Luau site | MIT | MIT | metadata only; already in the live index |
| Godot documentation | CC BY 3.0; `classes/` MIT | CC BY 3.0 or MIT according to path | metadata marked ingest-allowed |

Unity's [documentation terms](https://unity.com/legal/docs-terms) also give a
**purpose-limited AI permission** to help users learn/use Unity, and prohibit competing uses.
The Unity Companion License is limited to Unity-dependent development. Neither is a
general-purpose grant for STAR's mixed-engine corpus; Unity remains link-only. Do not copy
the documentation into a local full-text store or quote it in generated search passages
without a separate permission review. The Scripting API landing page discusses example
reuse differently; the more restrictive documentation-wide terms govern this catalogue.

The [MDN publisher guidance](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license)
says that snippets predating August 20, 2010 use MIT and authorship/version may be hard to
recover. Do not infer an old snippet is CC0; a future importer must retain the correct
authorship and licence notices or exclude it. For Godot, inspect `classes/` separately
because its contents are MIT rather than the documentation's default CC BY.

## Loader

`starkb.manifests.load_manifests()` returns an offline, schema-validated catalogue.
`load_manifest(path)` validates a single entry. Neither downloads documentation.
**Before any future fetch, chunking, storage or quoting**, an importer must use
`load_manifest(path, for_ingestion=True)` or `require_ingestion_rights(manifest)`.
Pass `include_code_samples=True` when the content contains samples (and keep the
licence-specific attribution). The loader raises `IngestionNotAllowed` on link-only
corpora or disallowed samples; it fails on unsupported schemas, missing rights and
malformed records. No ingestion integration is included in this change.

From the repository root run:

```bash
pytest -q tests/test_knowledge_manifests.py
pytest -q
python -m pytest -q server/knowledge/tests
```

Licence facts checked against the linked first-party documentation/README/licence files
on 2026-10-11. Rights or terms can change: reverify on each scheduled review before adding
any actual ingestion. The planning counts and cadences are proposals, not observed measurements.
