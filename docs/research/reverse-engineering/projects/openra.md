# OpenRA — reverse-engineering case study (researched 2026-10-13)

OpenRA is a GPL-3.0 C#/.NET engine that recreates Westwood's Command & Conquer (Tiberian Dawn), Red Alert and Dune 2000 as mods of one data-driven engine. It is the clearest example of a black-box, clean-room-style reimplementation. It reverse-engineered file formats only, never the executable. It also shows how much a rules language (MiniYaml) plus a trait system can carry. Its lockstep netcode with per-frame sync hashes and sync reports is a reference design.

## 1. What it is and its 2026 state
- Licence: GPL-3.0. The language is C# on .NET (INSTALL.md now requires **.NET 10**), with SDL, OpenGL and Lua 5.1. As of 2026-10-13 the repo shows about 30.9k commits on the default `bleed` branch and about 17.6k stars.
- As of 2026-10-13 the openra.net front page leads with **playtest-20261011** (release candidate, 11 Oct 2026). Its highlights:
  - a completed Dune 2000 campaign;
  - QuickSave and reworked save/load;
  - AI expansion improvements;
  - the move to .NET 10, with native Windows on ARM and aarch64 AppImage builds.
- An earlier playtest (20260222) added random map generators for all three games. The latest *stable* tag was not verified.
- A standalone Tiberian Dawn HD mod supports assets from the C&C Remastered Collection. A content manager lets players choose classic or remastered art and audio.

## 2. How the original was reversed
- The official FAQ calls OpenRA a clean-room engine built by reverse engineering the *game files*, with no disassembly, DLL injection or binary patching.
- The work centred on asset and container formats and on the original INI rules. `OpenRA.Utility` exposes the results as tools:
  - archive inspection: `--list-mix`, `--list-installshield`, `--extract`;
  - sprite conversion: `--png`, `--shp`, `--png-sheet-export` and `--png-sheet-import`;
  - map and rules import from the originals: `--import-ra-map`, `--import-td-map`, `--rules-import`.
- The repo root ships a `global mix database.dat`, which looks like a filename lookup table for MIX archives. Its purpose is not documented on the page I saw (unverified).

## 3. Workflow: matching, non-matching or clean-room
- The approach is a black-box reimplementation. Behaviour was rebuilt from observation and data, with no code derived from the binary.
- The FAQ explicitly says it is "not a clone". It deliberately modernises gameplay with right-click controls, attack-move, veterancy, fog of war, rebalanced factions and a tabbed build palette.
- Fidelity therefore means the feel and the content, not instruction-level parity. This frees the architecture completely: C#, a trait/actor model and YAML rules.

## 4. Testing and verification
- **Desync detection in production** (`OrderManager.cs`, described in plain words):
  - After each net frame's orders are applied, every client hashes the world state (`World.SyncHash`) and also records a defeat-state bitmask. Both are broadcast.
  - Each received hash is compared with the first one received for that frame. A mismatch marks the game out of sync, dumps a report and tells players to compare logs.
- **Sync reports** (`SyncReport.cs`):
  - A ring buffer keeps the last seven frames.
  - Each frame records the frame number, the shared RNG's last value and call count, and the orders issued.
  - It also records every actor trait that has a non-zero sync hash, together with its `[Sync]`-marked fields.
  - Values are rendered to text lazily, only when a report is needed.
- The FAQ asks players to submit `syncreport.log` from *several* clients and diff them to find the offending trait.
- The utility includes `--check-yaml`, `--check-missing-sprites` and several code-convention checks. An `OpenRA.Test` project and a GitHub Actions CI workflow exist (test contents not examined).
- Replays are recorded games played back through the same order pipeline. Sync reports are disabled during playback.

## 5. Structuring a large legacy codebase
- OpenRA had no legacy code to port. Its "legacy" is game *content*, so the structure is engine versus mods:
  - `OpenRA.Game` is the core;
  - `OpenRA.Mods.Common` holds shared traits;
  - `OpenRA.Mods.Cnc` and `OpenRA.Mods.D2k` hold game-specific code;
  - `mods/` holds the YAML content.
  A separate **Mod SDK** lets third parties build whole new RTS games.
- **MiniYaml**: a line-oriented, indentation-based format. `Inherits` merges a template tree, and multiple inherits use `@` suffixes such as `Inherits@AUTOTARGET`. A `^` prefix marks abstract templates. For example, a Red Alert rifleman inherits `^Soldier` and then sets cost and tooltip.
- Actors are bags of traits. New behaviour means a new C# trait in a mod DLL, and a mod can consist of YAML alone. Maps can carry rule overrides, and missions are scripted in Lua.
- **Rule migration between releases**: `--update-mod <source>` and `--update-map` apply named update rules to a mod's or map's YAML, with a `--detailed` dry run before `--apply`. Breaking rule changes come with automated migrations instead of manual upgrade notes.
- Introspection tools: `--resolved-rules` prints the fully merged rule tree, and `--docs`, `--lua-docs` and `--emmy-lua-api` generate documentation from the code.

## 6. Engine architecture insights
- **Deterministic lockstep with batching**:
  - Local ticks and net frames are separate counters. A tick is a net frame when it is divisible by the lobby's `NetFrameInterval`. The server can raise that interval to trade input latency for jitter tolerance.
  - A client stalls until every client's packet for the frame has arrived.
  - Packets are checked to carry the expected frame number, so a misrouted packet cannot cause a silent desync.
  - "Immediate" orders, such as chat, bypass the simulation queue.
  - Disconnects are inserted into the order stream, so every peer handles them on the same frame.
- The server mostly relays orders. The original FAQ says server and clients must run identical versions, because behaviour differences cause desyncs.
- The simulation uses fixed-point world units for determinism. Identifiers such as `WPos` and `WDist` are commonly cited, but I did not verify them from a fetched source.

## 7. Legal history and lessons
- EA released C&C and Red Alert as freeware; Wikipedia gives 31 Aug 2008 for Red Alert. OpenRA's content installer downloads stripped-down mirrored asset packs (about 15 MB rather than a 700 MB ISO) or extracts files from discs or digital copies. The FAQ says these assets are "not covered by OpenRA's GNU General Public License".
- EA later released the remastered TD/RA source under the GPL (2020) and the original-game source (Feb 2025), per Wikipedia. OpenRA supports Remastered assets but must still respect gaps; for example, the Soviet campaign videos are missing because EA did not include them.
- No takedown of OpenRA was found (unverified).
- Lesson: clean-room engine + freeware or owned assets + a cooperative publisher is the lowest-risk configuration of the four projects.

## 8. Transferable lessons for STAR
1. **Data-driven rules with inheritance.** Model Roblox unit, weapon and item definitions as Luau tables with a template and override merge, similar to `Inherits` and `^Template`. Give STAR a "resolved rules" dump command so designers can see the merged result.
2. **Composition over hierarchy.** OpenRA actors are trait bags. In Roblox, use CollectionService tags plus per-component modules instead of deep class trees.
3. **Per-frame state hash with a ring-buffer sync report.** For server-authoritative Roblox games, hash the authoritative simulation each tick in tests. Keep the last N frames of inputs and RNG state (`Random.new(seed)`) so a divergence or regression report says *which field* changed.
4. **Automated content migrations.** Ship `update-rules`-style migration functions when changing data schemas. This mirrors DataStore schema migrations: a named, idempotent migration plus a dry-run mode.
5. **Separate immediate from simulated messages.** Chat and UI pings should bypass the deterministic tick queue. Gameplay orders go through the tick-stamped, server-validated path.
6. **Clean-room by default.** For any "recreate game X" request, STAR should reimplement behaviour from observation and from formats the user owns, never from disassembled code. It should also require users to supply their own assets.

## Sources
- https://github.com/OpenRA/OpenRA — repository (licence, layout, docs links)
- https://github.com/OpenRA/OpenRA/blob/bleed/INSTALL.md — .NET 10 and original-disk content requirement
- https://www.openra.net/ — playtest-20261011 news and the TD HD mod
- https://github.com/OpenRA/OpenRA/wiki/FAQ — clean-room statement, freeware assets, sync reports
- https://www.openra.net/book/modding/miniyaml/index.html — MiniYaml syntax and inheritance
- https://github.com/OpenRA/OpenRA/wiki/Modding-Guide — traits, Mod SDK, mod.yaml
- https://github.com/OpenRA/OpenRA/wiki/Utility — update-mod, check-yaml and format tools
- https://raw.githubusercontent.com/OpenRA/OpenRA/bleed/OpenRA.Game/Network/OrderManager.cs — lockstep and sync-hash logic (read, not copied)
- https://raw.githubusercontent.com/OpenRA/OpenRA/bleed/OpenRA.Game/Network/SyncReport.cs — desync report design (read, not copied)
- https://en.wikipedia.org/wiki/OpenRA — redirects to the Red Alert article; freeware date and EA source releases
