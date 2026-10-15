# DevilutionX — reverse-engineering case study (researched 2026-10-13)

Devilution (2018) reconstructed Diablo's (1996) C source so that it compiles with the original Microsoft toolchain into functions as close to the shipped binary as possible. It used symbol data accidentally left in a Japanese PlayStation port and a hidden debug build on the PC disc. DevilutionX then took that matching baseline and modernised it into a cross-platform, moddable, tested port. It is the clearest case in this set of "match first, then modernise".

## 1. What it is and its 2026 state

- DevilutionX is a port of Diablo and Hellfire for modern systems, with bug fixes and optional quality-of-life features. The README's CI badges list builds for Linux (x86_64/AArch64/x86), macOS, Windows (MinGW and MSVC), Android, iOS, several consoles and Amiga M68K.
- **Latest release seen: 1.5.5, dated 2025-10-30.** It adjusted multiplayer game speeds, added character-name validation and iOS multiplayer over ZeroTier, among other changes. I saw no 2026 release on the GitHub releases page as of 2026-10-13. 1.5.0 added floating damage numbers, made all quests playable in multiplayer, and added PvP arenas.
- **Licence:** "Sustainable Use License", non-commercial only, and derivative works may not be sold. GamingOnLinux describes it as source-available, not open source.
- **Data:** users must supply `DIABDAT.MPQ` from the CD or extract it from the GOG installer. The shareware `spawn.mpq` works for the demo, and Hellfire needs its own MPQs.

## 2. How the original was reversed

- **Symbol leak:** symbol information left in the Japanese PlayStation port mapped file names, functions, variables and types (devilution README; BACKGROUND.md).
- **Hidden debug build:** inside the retail data sits a nested archive containing a debug `DIABLO.EXE` with debug tools and assert strings, which reveal source-level expressions and file names.
- **Toolchain archaeology:** the PE "Rich" header identified the exact compiler and linker versions, and the team inferred the optimisation flags (mostly `/O1`; two linker versions were used). The README targets VC++ 6 SP5 plus the Processor Pack to get functions "compiled as close as possible to the original". Unoptimised beta and alpha builds were used to cross-check interpretations.
- Credited to GalaXyHaXz (2018). After that a contributor community grew around it, and most of the reversing was done by hand (BACKGROUND.md).

## 3. Workflow: matching, non-matching or clean-room

- **Phase 1, matching decompilation (devilution).** Write C until each function compiles to the same (or near-same) machine code as the original. Progress was tracked with a "Binary identical functions" milestone and a Rust-based assembly-diffing tool. Original bugs are deliberately preserved and annotated with `BUGFIX:` comments rather than fixed. The README states the goal as preserving the game "including its bugs".
- **Phase 2, modernisation (DevilutionX).** With behaviour pinned by the matching base, the port moves to portable code and new platform layers, fixes bugs, and adds options and features. Once refactoring starts, binary matching is abandoned.
- **Not clean-room:** the work is derived from the original binaries. The README itself calls the legal status a "gray area".

## 4. Testing and verification

- In the matching phase, the original binary *is* the oracle: function-level assembly diffs prove equivalence.
- After modernisation, the `test/` directory (inspected 2026-10-13) holds roughly 100 GoogleTest-style files:
  - **dungeon-generation tests** per level type (DRLG L1-L4), which check that seeded generation reproduces the expected layouts;
  - pathfinding, items, inventory, stores, missiles, quests, player and save-writing (`writehero`) tests;
  - pack/MPQ, codec and data-file tests;
  - rendering benchmarks.
  
  A `timedemo_test` file suggests deterministic demo replay, but I did not read its contents, so that is **unverified**.
- CI builds every platform on each change. PRs merge after CI passes and at least one review (wiki Contributing page). Test builds are offered to players, with a warning to back up saves first.

## 5. Structuring a large legacy codebase

- **Original structure as the scaffold.** The reconstructed file names from the symbol data gave a module map, which made later refactors navigable.
- **Bugs as data:** keeping original bugs annotated, and fixing them as separate visible changes, means every behaviour change is deliberate.
- **Layering:** platform services moved behind portable layers so one codebase targets desktop, mobile, consoles and retro hardware. The exact library names are not stated in sources I fetched; SDL is widely reported but **unverified** here.
- **Modding:** the README advertises modding tools and links to community mods. `Source/lua` contains a Lua subsystem with events, globals, modules and an interactive REPL with autocomplete. Its full scope is **unverified**.
- **Process:** routine fixes and QoL go straight to master; major architectural changes need discussion with project owners first. New assets need a rights check.

## 6. Engine architecture insights

- Content is in MPQ archives with CEL/CL2 sprite formats. DevilutionX converts CL2 to its own CLX representation, and tests cover that conversion. Dungeons are generated procedurally from a seed, so seed reproducibility is the core invariant.
- **Multiplayer:** the port added ZeroTier-based play, which removes port forwarding and adds public game search (2021, v1.3). Later work tuned multiplayer game speeds and added player-stat validation (1.5.1). The details of the original netcode were not covered by sources I fetched.
- Debug builds expose chat-typed debug commands (for example godmode, level change, monster spawn) and `+command` launch arguments for reproducible test setups.

## 7. Legal history and lessons

- Both projects ship no assets, point users to GOG for a legitimate copy, and disclaim any Blizzard affiliation.
- Blizzard has made no public statement that I found. Press describes both projects as having "been left alone" (GamingOnLinux, 2021). No takedown found as of 2026-10-13. That is tolerance, not permission.
- The non-commercial licence reduces commercial-harm arguments, but derivation from binaries keeps the project legally exposed. Contrast this with OpenMW and ReactOS.

## 8. Transferable lessons for STAR

1. **Pin behaviour before you refactor.** When STAR modernises a legacy Roblox game (old `wait()`, deprecated APIs, `_G` globals), first capture current behaviour in tests (seeded outcomes, damage numbers, drop tables), then refactor. That is devilution's "match first" step, done at the behaviour level.
2. **Annotate original bugs instead of silently fixing them.** STAR should label behaviour-changing fixes separately from refactors (a `BUGFIX:`-style note in the PR description) so players' expectations and save data aren't broken unknowingly.
3. **Seeded determinism is testable.** Port the DRLG test idea to Luau: procedural generation driven by `Random.new(seed)` should have golden-output tests in TestEZ/Jest-Lua.
4. **Validate player data from peers.** DevilutionX added stat and name validation for multiplayer. The Roblox parallel is server-side validation of every RemoteEvent argument and DataStore profile load.
5. **Debug commands as fixtures.** Gated, debug-only commands like `+changelevel`/`spawn` make state-dependent bugs reproducible. In Roblox, put them behind a server-checked allowlist and only in test places.
6. **Know your legal footing.** STAR must never help derive code from proprietary binaries or leaked symbols. It should recommend clean behaviour-based reimplementation instead.

## Sources

- [devilution README (diasurgical)](https://github.com/diasurgical/devilution)
- [DevilutionX README](https://github.com/diasurgical/DevilutionX)
- [DevilutionX releases](https://github.com/diasurgical/DevilutionX/releases)
- [DevilutionX BACKGROUND.md](https://github.com/diasurgical/DevilutionX/blob/master/docs/BACKGROUND.md)
- [DevilutionX test directory](https://github.com/diasurgical/DevilutionX/tree/master/test)
- [DevilutionX Lua sources directory](https://github.com/diasurgical/DevilutionX/tree/master/Source/lua)
- [DevilutionX debug docs](https://github.com/diasurgical/DevilutionX/blob/master/docs/debug.md)
- [DevilutionX wiki: Contributing](https://github.com/diasurgical/DevilutionX/wiki/Contributing)
- [GamingOnLinux: DevilutionX 1.3 (2021)](https://www.gamingonlinux.com/2021/11/diablo-and-hellfire-source-port-devilutionx-gets-a-big-upgrade)
