# STAR SourceMap: compact, dependency-ranked code navigation (2026-10-15)

## Source-backed rationale

Aider's repo map extracts declarations and references and prioritizes them under
a bounded context budget. A coding model can then decide *which* files to read
before attempting an edit. This is more useful than adding every source file to
the prompt, but a heuristic map is not equivalent to a compiler, language
server, tested import graph, or complete knowledge of the repository.

Primary source: https://aider.chat/docs/repomap.html
Additional background: https://aider.chat/2023/10/22/repomap.html

STAR already has `workspace_search(mode="symbols")` from its code-navigation
feature and `star/omega_hyperindex.py` for *reviewed knowledge notes*. This PR
adds a distinct read-only **source declaration map**. It reuses the existing
private-workspace resolver, symbol parsers and scan exclusions rather than
installing new indexing services.

## New opt-in tool path

Use the existing tool's new mode:

```json
{"query": "inventory", "mode": "map"}
```

It returns small file/symbol hints through `workspace_search` only when the
model or user explicitly asks for map mode. Text and symbols modes are unchanged.

Implementation: `star/repo_map.py`, `star/code_navigation.py`, and
`star/workspace.py`. No new Python dependencies, model calls, background scans,
persistent index, GPU process, network access or permission changes.

- Reuses secure workspace scanning: hidden/generated folders, sensitive file
  names, symlinks, oversized source files and escapes are excluded.
- Python declarations use the existing AST parser. Luau, TypeScript, GDScript,
  JavaScript and C# use existing **heuristic** declaration recognizers.
- Builds a bounded cross-file reference graph only for identifiers with a
  single candidate defining file. It does **not** claim semantic resolution.
- Performs eight deterministic centrality iterations to break query-relevance
  ties in favor of more commonly referenced files.
- Returns declaration signatures, file paths, source lines and method caveats;
  never imports or executes code or copies the entire source body into output.
- Hard bounds: at most 320 scanned code files, 6 MB of combined source text,
  5,000 unique identifier words per file, 48 extracted definitions per file,
  12 returned files, seven declarations per file, and 6,000 output characters
  approximately (JSON serialization budget).
- `incomplete=true` identifies partial scans, symbol caps, file budgets or
  output trimming. No result is labeled an actual compilation or Studio test.
- The map is generated from current files, so editing source updates later
  results without a stale persistent cache.

## Testing and activation gates

Target tests: `python -m pytest tests/test_repo_map.py
tests/test_code_navigation.py -q`.

Release gating must compare `text`, `symbols` and `map` on the same frozen
repository questions and real coding tasks, measuring:

1. correct file found @ 1/5/10, with and without identically named symbols;
2. time to find an editable file, p50/p95 latency and peak memory on Windows;
3. additional context characters/tokens used per correct edit;
4. Luau/Roblox held-out code task pass rate, with identical model/settings;
5. correct project-scope isolation and no reads of protected locations.

If the compact map does not improve meaningful file choice or code correctness,
keep the legacy mode and remove the feature. This PR does NOT claim an inference
speedup, verified semantic dependency resolution, production acceptance or
activation on either Brain machine.

## Next (not part of this PR)

Benchmark incremental content-hash caching only after measuring repeated
scanning; replace weak regex parsing with verified Luau/TS tree-sitter or LSP
where robust and licensable; correlate symbols to Rojo ModuleScript/service
boundaries; feed *selected* file context through STAR's existing volatile turn
section, without changing fixed cached system prefixes.
