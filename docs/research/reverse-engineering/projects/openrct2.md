# OpenRCT2 — reverse-engineering case study (researched 2026-10-13)

OpenRCT2 is a GPL-3.0 reimplementation of RollerCoaster Tycoon 2 (RCT2). It began as a DLL injected into the original executable and was rewritten one procedure at a time until the original binary was no longer needed. It is the textbook case of incremental replacement. Its modern work stands on deterministic multiplayer, checksummed replay regression tests, a versioned chunked save format and a JavaScript plugin API.

## 1. What it is and its 2026 state
- RCT2 was written by Chris Sawyer, almost entirely in x86 assembly, on an engine descended from Transport Tycoon (per the GitHub README). OpenRCT2 started on 2 April 2014 under Ted "IntelOrca" John. Its first release came in December 2014 (Wikipedia).
- Licence: GPL-3.0 or later. As of 2026-10-13 the repo shows about 30.7k commits on `develop` and about 16.4k stars.
- Latest release: v0.5.6 (10 Oct 2026). Before it came v0.5.5 (6 Sep 2026) and v0.5.4 (2 Aug 2026), so the project ships roughly monthly. Recent notes are dominated by plugin API additions, such as footpath-network navigator classes, a map-resize hook and plugin-triggered saves.
- It adds cooperative multiplayer, higher limits, editors and modern platforms. It needs the original RCT2 (or RCT Classic) data. RCT1 data is optional and unlocks the RCT1 scenarios.

## 2. How the original was reversed
- Early READMEs (preserved in forks) describe the method. The original `rct2.exe` was patched so that its import table loaded `openrct2.dll`, whose entry point ran from the game's WinMain. The DLL shared the original process's memory model. That let freshly rewritten C code read and write the game's globals and call routines that had not yet been converted.
- Disassembly and analysis were done in IDA 5.0. Contributors were pointed to IntelOrca for the shared IDA database. Each original procedure was "re-written in C on an individual basis" (old README).
- Milestones: per the RCT fandom wiki (via search; the page itself returned 402 to the fetcher), function replacement finished around October 2015. Release v0.0.5 (2018) announced that "RCT2.EXE is no longer required", and a developer confirmed on the forums that no original code runs any more, although the original assets are still needed.

## 3. Workflow: matching, non-matching or clean-room
- The approach is non-matching but behaviour-faithful. The goal was not a byte-identical binary. It was C code that behaved the same while running inside the original process, which acted as a live oracle.
- Because the code derives from disassembly, it is not a clean-room project. The legal mitigation is to distribute no assets (see §7).
- Once the original process was gone, the team could change the memory layout and gradually move to C++. Wikipedia describes the code as written "incrementally" in C++. No single conversion date could be verified.

## 4. Testing and verification
- **Replay regression tests** (wiki "Replay System"): replays record game actions to `.sv6r` files. Each replay stores a sprite checksum. Every pull request replays a set of recordings and fails if any checksum differs. The `replay_normalise` command packs a recording to one command per tick and regenerates its checksums after an intentional logic change.
- Checksums differ between x86 and x64, so CI checks only x64. That is a concrete reminder that bitwise determinism depends on the platform.
- Playing a replay writes desync logs, which turns a replay into a tool for locating where divergence starts.

## 5. Structuring a large legacy codebase
- The strangler-fig pattern at function granularity kept the game shippable and playable at every commit.
- After independence, refactoring moved to C++ and began removing hard limits. Version 0.4.0 (April 2022) replaced the inherited `sv6` save with the new `.park` format. A developer said it raised "pretty much all the limits" of sv6, including 999×999 maps and up to 255 trains per ride (GamingOnLinux). Importing SV4, SV6, SEA and SV7 is retained. Exporting to SV6 was dropped (forum, community-sourced).
- **Plugin API** (`distribution/scripting/scripting.md`): plugins are JavaScript. Since v0.5.0 they run on QuickJS-NG (ES2023+); earlier versions used Duktape (ES5). There are three plugin types:
  - `local` plugins cannot mutate game state directly.
  - `remote` plugins are pushed from the server to joining clients and may mutate state only inside a custom game action's execute function.
  - `intransient` plugins live for the whole process.
- Further API details: `targetApiVersion` and `minApiVersion` keep old plugin behaviour working across breaking changes. An `openrct2.d.ts` typings file is shipped. Hot reload is available, and per-park storage is serialised into the `.park` file.

## 6. Engine architecture insights
- Game time advances in discrete ticks. In multiplayer, clients run slightly behind the server's tick and never past it. Every player action is sent to the server, which relays it, and every peer executes it on the same tick. Sync holds only if all logic is deterministic (wiki "Multiplayer").
- On a desync, the client disconnects and can reconnect. The `stay_connected` debug option keeps it connected for investigation.
- **Game actions** are the single gateway for state mutation. Each one is validated, permission-checked through player groups and executed in lockstep. Plugins must use them too, and touching client-only data such as UI windows in game logic is called out as a desync source.
- **Save format**: a header holds magic, target version, minimum version, chunk count, compression type, uncompressed size and a SHA-1. A chunk table then indexes chunks such as Authoring, Objects, Scenario, Park, Tiles, Rides and Derived (`docs/save-format.md`). The target/min version pair lets a loader refuse files it cannot understand.

## 7. Legal history and lessons
- No takedown or dispute was found as of 2026-10-13 (unverified beyond Wikipedia and the forums). Kotaku commentary argued it could weaken sales of RCT Classic. That is criticism, not a legal action.
- The asset rule is strict. Users must supply RCT2 or RCT Classic files, bought on Steam or GOG. The project ships code, not sprites, sounds or scenarios. Developers described recreating those assets as a very long effort.
- Lesson: distributing only code and pointing at a legitimately bought install has kept a disassembly-derived project alive for more than 12 years.

## 8. Transferable lessons for STAR
1. **Strangler-fig replacement.** When STAR helps refactor a legacy Roblox place, recommend moving one ModuleScript or system at a time behind a stable interface while the game stays playable. This mirrors OpenRCT2's DLL-in-process, function-by-function rewrite.
2. **One mutation gateway.** OpenRCT2's game actions map directly to Luau: every state change goes through a validated server-side action, never through direct client writes to the DataModel. Use RemoteEvent, then a server validator, then a pure apply function. The same choke point gives replay and logging for free.
3. **Replay checksums as regression tests.** Record input/action logs plus a state hash, and fail CI when the hash changes. Add a "normalise and regenerate" command for intentional changes. In Roblox, run pure-logic simulations under TestEZ or run-in-roblox with a seeded `Random.new(seed)` and compare state hashes.
4. **Versioned saves with a target/min version pair.** For DataStore profiles, store `schemaVersion` with a minimum readable version and chain migrations. Keep importers for old formats even after export to them is dropped.
5. **Separate "may mutate" from "UI-only" extension code.** OpenRCT2's local vs remote plugin split maps to Roblox client vs server modules. Client code may only request actions.

## Sources
- https://github.com/OpenRCT2/OpenRCT2 — official repository README
- https://github.com/OpenRCT2/OpenRCT2/releases — v0.5.4–v0.5.6 release notes
- https://en.wikipedia.org/wiki/OpenRCT2 — history and licence
- https://github.com/kevinburke/OpenRCT2 — fork preserving the early README (DLL and IDA method)
- https://forums.openrct2.org/topic/2869-does-open-require-the-original-again/ — executable no longer needed, assets still required
- https://github.com/OpenRCT2/OpenRCT2/wiki/Multiplayer — tick and action sync model
- https://github.com/OpenRCT2/OpenRCT2/wiki/Replay-System — replay checksum CI
- https://github.com/OpenRCT2/OpenRCT2/blob/develop/docs/save-format.md — .park header and chunks
- https://raw.githubusercontent.com/OpenRCT2/OpenRCT2/develop/distribution/scripting/scripting.md — plugin API
- https://www.gamingonlinux.com/2022/04/rollercoaster-tycoon-2-reimplementation-openrct2-has-a-new-save-system/ — .park format in 0.4.0
