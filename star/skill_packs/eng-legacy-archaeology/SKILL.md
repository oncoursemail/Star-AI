---
name: eng-legacy-archaeology
description: Method for understanding and safely changing a large, old or undocumented codebase (including inherited Roblox games): map before moving, capture current behaviour as characterization tests, find seams, replace incrementally, keep data formats compatible. Use for inherited projects, spaghetti scripts, rewrites, migrations and "what does this code even do" questions.
---
# Legacy codebase archaeology
Adapted from how decompilation and reimplementation projects tame codebases nobody fully understands, plus Michael Feathers' legacy-code method and the strangler pattern.

## 1. Map before you move
- Inventory entry points, modules, globals, shared state, network messages, saved-data keys and scheduled jobs. Record who calls what and where data flows.
- Read the history: commit log, blame, old issues. Odd code is often load-bearing; find out why it exists before removing it.
- Write the map down (a short architecture note) and mark every claim as observed, inferred or unknown.

## 2. Capture behaviour before changing it
- Characterization (golden master) tests record what the code does now, bugs included. They are the oracle that makes refactoring safe, the same role a byte-exact rebuild plays in a matching decomp.
- Mask nondeterminism first: seed random generators, fix clocks, sort unordered output.

## 3. Find seams and change one thing at a time
- A seam is a place where behaviour can be swapped without editing callers: a module boundary, an injected dependency, a wrapper.
- Refactor-only commits must keep behaviour identical and be checked against the oracle; behaviour changes go in separate, small commits with their own test.

## 4. Replace incrementally (strangler)
- Route one path through new code while the old path still works; compare outputs (shadow or differential runs); retire the old path only when the new one has matched for long enough.
- Never start with a full rewrite of an unknown system.

## 5. Name only with evidence
- Keep placeholder names for things you do not understand yet; rename when tests or traces confirm the meaning. Document as you learn, next to the code.
- Track progress visibly: modules mapped, tested, cleaned.

## 6. Keep data compatible
- Saved data outlives code. Version every stored record, migrate on load, never silently drop unknown fields, and test the migration with real old records before shipping.

## Roblox specifics
- Get the place into files with Rojo so the code has history, diff and search.
- Inventory every RemoteEvent and RemoteFunction, every DataStore name and key pattern, every use of _G or shared, every while-true loop and every connection that is never disconnected.
- Move shared state from _G into ModuleScripts behind a small API, one system at a time.
- Before touching saving code, add a schema version and a load-time migration, and test it against copied real records in a test place, never the live one.

## Report
- The map, the riskiest areas, the oracle you built, the next smallest safe step, and what remains unknown.
