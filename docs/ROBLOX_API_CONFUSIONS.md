# Roblox API confusable names — reviewed advisory corpus

File: `data/roblox_api_confusions.json` (**80 method-spelling entries**, four variants for each of 20 official Roblox API members). Loader: `star.roblox_api_confusions.load_confusions()`. Scanner: `scan_luau(source)`, returning 1-based line and column plus `wrong`, `right`, `kind` and `source_url` for each match. This is **opt-in read-only data**, not wired into a default system prompt, automatic fix, or evaluation gate.

## Scope and evidence

Official Roblox Creator Hub class reference methods were checked 2026-10-13:
- [Instance](https://create.roblox.com/docs/reference/engine/classes/Instance): 8 canonical members, 32 confusions.
- [Players](https://create.roblox.com/docs/reference/engine/classes/Players): 2 canonical members, 8 confusions.
- [Humanoid](https://create.roblox.com/docs/reference/engine/classes/Humanoid): 3 canonical members, 12 confusions.
- [RemoteEvent](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent): 3 canonical members, 12 confusions.
- [GlobalDataStore](https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore): 3 canonical members, 12 confusions.
- [WorldRoot](https://create.roblox.com/docs/reference/engine/classes/WorldRoot): 1 canonical member, 4 confusions.

Source context: [docs/evals.md](evals.md) documents required/forbidden API-name checks at line 59 and identifies API-name misses or compilation errors as a failure category around line 180. **Those are categories, not proof of these exact spelling errors from observed runs**. All 80 left-hand variants are conservative hypothetical confusions paired with actual documented methods. The official class pages validate the right-hand method and allow checking whether a wrong method exists on that class.

**Excluded as unproven or unsafe (6 topics):** deprecated `wait` versus `task.wait` (different scheduling semantics); legacy `BodyVelocity` versus `LinearVelocity` (different setup); server `LocalPlayer` (runtime context, not invented API); nil-check absence after `FindFirstChild` (control flow, not name confusion); lowercase deprecated aliases like `getChildren` (may still exist); other class-specific methods not checked against an authoritative reference. Do not label deprecated-but-present members as nonexistent.

## Accuracy boundaries

A textual hit cannot establish a receiver's runtime/class type or distinguish a user-defined method on a custom table. Report **"possible Roblox API misspelling; verify the receiver class"**, never "definite error" or auto-replace. Quoted strings, backticks, line comments and block comments are skipped; the detector looks for exact colon-invocation spellings only. It does not parse Luau or execute Roblox Studio. No external requests or filesystem writes occur in scanning.

## Verification

The Python tests enumerate **80 positive and 80 clean corresponding cases** and exercise full multiline snippets, skipped comments/literals, deterministic line numbers, and official-host validation. GitHub CI's pytest run supplies actual execution proof. A true engine-negative test needs Roblox Studio's API checker: the pinned standalone Luau interpreter only parses syntax, not Roblox class members. No generation-accuracy gain was benchmarked, and nothing was enabled by default.
