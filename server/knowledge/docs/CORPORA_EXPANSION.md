# Offline official-source corpus candidates

This slice supplies a source catalogue, local snapshot verifier, bounded raw-excerpt readers,
an incremental inventory and a separate SQLite candidate builder/preview. It does not fetch
documentation, call models, run engines, embed new text, change the live service or activate
mixed corpora. The shipped catalogue has **no resolved revisions or reviewed licence hashes**.
No upstream documentation text is shipped here; tests use independently authored fixtures.

The live `corpora.json`, fetch/refresh jobs, HTTP service, search defaults, gateway and evaluation
fixtures remain unchanged. Existing Roblox and Luau walkers remain the production defaults.
Candidate previews require explicit source IDs and a `candidate_only` database marker.

## Source review

| Source | Upstream and licence evidence | Proposed source selection |
|---|---|---|
| Roblox | [Official creator-docs licence statement](https://github.com/Roblox/creator-docs#licenses): prose CC BY 4.0, samples MIT | Selected guide/reference source files. Existing exact Roblox API lookup remains authoritative; the candidate YAML reader is raw reference text. |
| Luau | [MIT licence](https://github.com/luau-lang/site/blob/master/LICENSE.md); retain Roblox and Lua.org/PUC-Rio notices | Language guides, with news separately tagged when explicitly selected. |
| Godot guides | [Official licence statement](https://github.com/godotengine/godot-docs/tree/4.7#license): CC BY 3.0, attribution to Juan Linietsky, Ariel Manzur and the Godot community | Version-matched scripting, UI and animation RST. The separate `classes/` exception is MIT and must not inherit the guide licence. |
| Godot XML | [Engine MIT licence](https://github.com/godotengine/godot/blob/master/LICENSE.txt) | Selected `doc/classes/*.xml` at an engine-release commit; no normalized symbol/signature generation. |
| C#/.NET | [CC BY 4.0 prose](https://github.com/dotnet/docs/blob/main/LICENSE), [MIT samples](https://github.com/dotnet/docs/blob/main/LICENSE-CODE) | Selected C# fundamentals/async, core testing and standard-library guides; compatibility per article. |
| MDN | [Content licence](https://github.com/mdn/content/blob/main/LICENSE.md): prose CC BY-SA 2.5; samples since 2010-08-20 CC0, earlier samples MIT | Selected HTML/CSS/DOM/web APIs. Sample history is unresolved until independently checked; copied/adapted prose retains applicable attribution/ShareAlike terms. |
| TypeScript | [CC BY 4.0 prose](https://github.com/microsoft/TypeScript-Website/blob/v2/LICENSE), [MIT samples](https://github.com/microsoft/TypeScript-Website/blob/v2/LICENSE-CODE) | Selected English handbook; `v2` is the website branch, not TypeScript 2. |
| Python | [Official licence](https://github.com/python/cpython/blob/3.14/Doc/license.rst): PSF v2, documentation examples additionally 0BSD since 3.8.6 | Selected tutorial/reference/library RST for the project's actual release; retain incorporated third-party notices. |
| Unity | [Documentation terms](https://unity.com/legal/docs-terms), [agentic-access terms](https://unity.com/legal/terms-of-service) | Enforced metadata/link-only entry. Applicable documentation use and STAR client/model authorization remain unresolved. |

Licences permit conditional copying/reuse, not engine execution or vendor endorsement. Preserve
copyright, title, source, licence links and modification notices where applicable. Do not ship
corpus text/indexes in the public installer or repository. Private indexing does not remove
obligations for excerpts or adaptations that are later shared. This slice grants no training,
engine invocation, permission changes or automatic acceptance of upstream licence changes.

## Preparing a reviewed local manifest

Copy the catalogue outside the public repository. Select explicit file paths; no wildcard or
directory traversal is allowed. Resolve each project-matching release/ref to its **full commit
SHA**, obtain the approved paths through the separately controlled source-acquisition process,
and independently review/hash the complete licence evidence at that revision. Set `permission`
to `reviewed-copy` only after that review. `branch` records the update selector; it is never a pin.
The source paths in the shipped catalogue are proposed and must be checked against the snapshot.

The verifier requires canonical declared upstream, registered checkout root, exact HEAD SHA,
clean tracked/untracked state, tracked bytes matching Git blobs, reviewed licence hashes and
recognized licence identifiers. It checks again before publishing a candidate. Origin URLs are
local declarations: this process **does not cryptographically authenticate upstream provenance**.
Licence markers only cross-check an independently reviewed hash; they are not a legal classifier.
Checkout bytes must match the source blob exactly; filtered/CRLF-transformed checkouts fail
visibly rather than acquiring a misleading source hash.

Bounds: at most 12 manifest sources; 256 KiB manifest; 2 MiB per document; 32 MiB per source
ceiling; 64 MiB/50,000 chunks combined. Most proposed new sources choose 100 files/10 MiB/5,000
chunks. Roblox has a larger preservation ceiling. Licence files are bounded at 256 KiB. Each
selected path, symlink/junction, UTF-8 error, missing file and excessive line is checked explicitly.
The new readers do not crawl or follow includes. Long source lines fail instead of being cut.

## Commands

From `server/knowledge/`, with an existing Python runtime:

```text
python -m starkb.corpus_cli plan --sources-dir <local-snapshots>
python -m starkb.corpus_cli --manifest <reviewed-local-manifest.json> plan --sources-dir <local-snapshots> --previous <checkpointed-snapshot.sqlite3> --source luau-site
python -m starkb.corpus_cli --manifest <reviewed-local-manifest.json> build-candidate --sources-dir <local-snapshots> --previous <checkpointed-snapshot.sqlite3> --source luau-site --output <new-candidate.sqlite3>
python -m starkb.corpus_cli preview "cancel previous animation" --db <new-candidate.sqlite3> --source luau-site
```

`plan` writes nothing and uses no network/models. It reports unavailable/dirty/unreviewed
sources rather than labelling them pinned. Local Git metadata queries disable optional locks
and fsmonitor; they do not fetch/reset/create objects. Plans carry deterministic manifest,
policy, previous-index and file hashes plus added/changed/removed/unchanged file inventory.
The optional previous index must be a stable checkpointed snapshot: WAL/SHM companions are
refused, and immutable read-only SQLite avoids creating them during a dry-run.

`build-candidate` requires explicit source IDs and a new output file in an existing directory.
It creates a temporary candidate, optionally backs up a stable previous index read-only,
replaces only explicitly selected sources, and preserves all other sources/vectors/questions.
Each selected source is guarded against losing more than 20% of either chunks or existing paths.
Unchanged embedding-input hashes remain reusable; no new vectors are generated. Indexing still
re-parses selected files and rebuilds FTS in the isolated candidate; this is not a promise of
file-level incremental parsing or measured refresh speed.

The final file is published by an exclusive hard link, never by replacing an existing file.
Failures/cancellation discard the temporary candidate; the supplied index stays untouched.
Filesystems without hard-link support fail visibly. There is no live activation command.

## Excerpt fidelity and evidence

Markdown/MDX, RST, Godot XML and YAML are retained as raw source lines with exact line spans,
heading hints, source kind, full-file hash, compatibility, licence rules and attribution.
Unsupported macros/includes/directives/HTML remain visible with warnings; none are executed.
Long blocks can span excerpts. Continuations are labelled and all examples remain
`standalone_example_verified=false`. RST language hints are not a rendered semantic AST.
No synthetic code, generated signatures or renderer-dependent anchors are invented.

Preview uses local FTS only, requires explicit registered sources, returns full bounded
passages and reports omissions by budget. Citations use immutable upstream source-file URLs,
not guessed rendered-documentation URLs. Baseline passages preserved from an older index have
their original provenance but explicitly lack new raw-line metadata. All text is untrusted
reference material and cannot alter permissions.

## Refresh and activation remain separate work

Future acquisition should resolve allowed metadata, fetch only approved changed paths at the
new SHA, stop on unknown licence/terms/compatibility, stage a candidate and freeze its manifest
before independent acceptance. Keep the previous snapshot for rollback. Do not automate wider
source selection or change permissions. Do not run retrieval evaluation only after publication.

Before live expansion, add reviewed source/version selection through the existing service
boundary and measure Roblox regression plus cross-engine citation/API correctness on independent
fixtures. An index containing more sources is not evidence of better answers. The current
candidate parser does not replace engine tests, rendering/device checks, Claude's evaluation
gate, shared-brain review or server scheduling. Actual upstream ingestion/deployment is not
established by this implementation or its synthetic tests.
