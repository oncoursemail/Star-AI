# Roblox XML attachments

Attach `.rbxmx` models or `.rbxlx` places through the normal chat file picker.
They become documents, never images, and use the existing immutable artifact
store, project/chat isolation, integrity checks, cancellation, source locations,
and hard character budget. The model receives the compact outline first, then
the script index, then relevant property/source excerpts as room permits.
Coverage and excerpt markers identify omissions. This does not run Studio or Luau.

Binary `.rbxm` and `.rbxl` files are recognized only to explain that an XML export
is required. Binary headers disguised with an XML extension are also refused.
Renaming a binary file is not conversion: export XML from Roblox Studio.

## Read-only Python API

```python
from pathlib import Path
from star.rbx_xml import read

model = read(Path('example.rbxmx'))
print(model.outline(max_depth=6, max_nodes=200, budget_chars=8000))
print(model.script_list())  # path, kind, line_count, summary; no source bodies
print(model.focus('/Demo/Logic/Server', budget_chars=6000))
```

`model.roots` and `model.instances` expose class, original name, children,
whitelisted properties, source, and descendant/script counts. `model.scripts`
retains complete inline source within the parser limits. Empty inline source
is distinct from unavailable/shared source; unavailable source has an explicit
warning. XML parsing normalizes XML line endings; source is never evaluated.

Focus paths are exact, case-sensitive identifiers copied from the outline or
script list, not XPath, filesystem paths, or fuzzy matches. Names are
percent-encoded by segment (`A/B` becomes `A%2FB`). Duplicate siblings receive
`[1]`, `[2]`, etc.; literal brackets are encoded. An empty name is `%00` and a
literal `%00` name is `%2500`. Focus returns one subtree or script, never its
siblings, and applies a hard output-character budget with an omission marker.

The deterministic script summaries are **lexical hints**, not a Luau parser,
call graph, or safety review. They list literal `GetService` calls, simple
`require(...)` expressions, visible remote method/event uses, and named function
definitions (including assigned anonymous functions). Comments and ordinary
string contents do not produce fictitious calls. Backtick interpolations are
opaque. Dynamic expressions, alias resolution, and escaped service names are
not resolved. Summary items are sorted and bounded; no model or network is used.

## Limits and exclusions

The hardened `defusedxml.ElementTree.DefusedXMLParser` is configured to forbid
DTDs, entity declarations, and external references. The parser never resolves
XInclude or asset URLs. It checks depth and element/text counts while building,
not only after constructing an unbounded tree.

- Input: 16 MiB, checked before parsing and again on bounded streaming reads.
- XML depth: 64; elements: 200,000; instances: 20,000; XML text: 2,000,000 characters.
- Names: 256 characters; canonical paths: 4,096 characters.
- Default outline: six levels, 200 displayed nodes, 8,000 characters, with counts
  and explicit depth/node/character omissions.
- Chat documents additionally retain the existing 1,000,000-character extraction
  cap and storage/context budgets; large accepted XML can still exceed that cap.

Only the explicit `USEFUL_PROPERTIES` whitelist is retained (common script,
part/physics, transform, UI, asset identifiers, scalar values, and PrimaryPart
references). Unknown properties and embedded binary data are not interpreted.
References/URLs remain inert identifiers. Shared/external script source is not
fetched. Symlink/non-regular input, malformed XML, invalid recognized property
values, duplicate useful properties, and limit violations are refused.

## Regression tests

```sh
python -m pytest -q tests/test_rbx_xml.py tests/test_rbx_documents.py tests/test_rbx_chat_attachments.py
```

Fixtures under `tests/fixtures/rbx_xml/` are handwritten synthetic XML. The
security tests include an entity-expansion bomb, UTF-16 DTDs, external entities,
malformed input, structural limits, and an actual sparse oversized file. Storage
tests exercise the real DocumentStore/KnowledgeStore. Bridge tests compile and
execute the actual nested picker/chat methods without launching Qt, then use
real attachment classification and document ingestion with a fake model boundary.
These tests do not establish native Windows GUI, live model, or Studio acceptance.
