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
| Unity Scripting API | CC BY-NC-ND 4.0 | Scripting Reference example grant (no credit required, non-sublicensable) | **link-only** for reference text |
| Microsoft C#/.NET | CC BY 4.0 | MIT | metadata marked ingest-allowed |
| MDN Web Docs | CC BY-SA 2.5 (page exceptions) | CC0 for newer snippets, MIT for older | metadata marked ingest-allowed; preserve legacy snippet credits |
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
without a separate permission review. The [Scripting API landing page](https://docs.unity.com/en-us/engine/6000.5/script-reference)
expressly permits redistribution of its examples without crediting Unity; that exception
**does not license the surrounding reference text**. The official [offline archive](https://docs.unity.com/en-us/engine/6000.5/manual/offline-documentation)
(~300 MB) includes both sources, but it is not downloaded by STAR.

The [MDN publisher guidance](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license)
says that snippets predating August 20, 2010 use MIT and authorship/version may be hard to
recover. Do not infer an old snippet is CC0; a future importer must retain the correct
authorship and licence notices or exclude it. For Godot, inspect `classes/` separately
because its contents are MIT rather than the documentation's default CC BY.


## Publisher licence excerpts

These are short exact extracts from the linked publishers' own terms or files. Each JSON
manifest also records separately linked evidence for both text and samples.

- [Unity Manual and Scripting Reference terms](https://docs.unity.com/en-us/engine/6000.5/manual/terms-of-use):
  “Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International”.
  The same page places Manual snippets under the Unity Companion License.
- [Unity Scripting API example exception](https://docs.unity.com/en-us/engine/6000.5/script-reference):
  “to modify, and to distribute the examples without crediting Unity”.
- [Microsoft .NET text licence](https://github.com/dotnet/docs/blob/main/LICENSE):
  “Creative Commons Attribution 4.0 International Public License”.
  [Sample licence](https://github.com/dotnet/docs/blob/main/LICENSE-CODE):
  “The MIT License (MIT)”.
- [MDN prose licence](https://github.com/mdn/content/blob/main/LICENSE.md):
  “All prose content is available under” CC BY-SA 2.5.
  [Sample licence](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license):
  “Code samples added on or after August 20, 2010 are in the public domain CC0”.
- [Python documentation licence](https://docs.python.org/3/license.html):
  “Python software and documentation are licensed under the Python Software Foundation License Version 2.”
  For modern examples: “dual licensed under the PSF License Version 2” and 0BSD.
- [TypeScript website legal notice](https://github.com/microsoft/TypeScript-Website/blob/v2/README.md):
  “Creative Commons Attribution 4.0 International Public License” for text;
  “MIT License” for code.
- [Lua 5.4 manual](https://www.lua.org/manual/5.4/manual.html):
  “Freely available under the terms of the Lua license.”
  The [MIT licence](https://www.lua.org/license.html) grants permission to reproduce and redistribute.
- [Luau site MIT licence](https://github.com/luau-lang/site/blob/master/LICENSE.md):
  “Permission is hereby granted, free of charge”;
  substantial copies retain the copyright/permission notice.
- [Godot docs README](https://github.com/godotengine/godot-docs/blob/master/README.md):
  “With the exception of the `classes/` folder” (CC BY 3.0);
  reference files are “distributed under the MIT license”.

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
