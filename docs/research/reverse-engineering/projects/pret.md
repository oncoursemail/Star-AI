# pret (Pokémon Reverse Engineering Tools) — reverse-engineering case study (researched 2026-10-13)

pret is an umbrella community that rebuilds Pokémon games, plus a few related titles, from ROM to source that reassembles or recompiles byte-for-byte. The Game Boy and Game Boy Color games are kept as annotated assembly disassemblies, built with RGBDS. GBA, DS, N64 and Wii titles are C decompilations. Its main legacy is social as much as technical: projects such as pokecrystal and pokeemerald became the standard base for ROM hacks and spawned "expansion" forks that stay in sync with upstream.

## 1. What it is and its 2026 state

- pret describes itself as fans trying to "reverse engineer our favorite video games", and says the name officially means nothing (pret.github.io). It is coordinated through Discord and IRC (libera #pret).
- **Game Boy / Game Boy Color, SM83 assembly:** pokered, pokeyellow, pokegold, pokecrystal, poketcg and poketcg2, pokepinball, pokepuzzle, and the Space World '97 prototype pokegold-spaceworld.
- **N64:** pokestadium and pokestadiumgs.
- **GBA (C plus ARM7TDMI assembly):** pokeruby, pokeemerald, pokefirered, pokepinballrs, pmd-red and others.
- **DS:** pokediamond, pokeplatinum, pokeheartgold and pmd-sky.
- **Wii:** pokerevo.
- **Repository activity** as of 2026-10-13: pokered has about 5.0k stars, 1.3k forks and 2,831 commits. pokecrystal has about 2.5k stars, 983 forks and 5,284 commits. Per-project completion percentages were not checked (unverified).

## 2. How the original was reversed

- **Game Boy titles.** The ROM is disassembled into SM83 assembly. Labels, data tables, text and graphics are then recovered by hand into readable source with symbolic names. A `symbols` branch publishes symbol files for debuggers. Shared tooling lives in gb-asm-tools and the older pokemon-reverse-engineering-tools repo.
- **GBA titles.** These are C decompilations built with agbcc, pret's "GBA C compiler" repo, which reproduces the original toolchain's code generation for matching. Its exact GCC lineage was not confirmed from a fetched source (unverified).
- **Multiple build outputs.** pokecrystal builds Crystal UE 1.0 and 1.1, the Australian release, two PS3 Virtual Console binaries and a patch file. pokered also builds a debug "BLUEMONS.GB" and patch files. Each has a SHA-1 in the README.

## 3. Workflow: matching, non-matching or clean-room

- **The default build is matching.** `make compare` prints `pokeemerald.gba: OK` or `FAILED` (INSTALL.md). Every ROM in a README has a published SHA-1.
- **"Modern" builds are the non-matching escape hatch.** `make modern` compiles pokeemerald with devkitARM's `arm-none-eabi-gcc` instead of agbcc, and `DINFO=1` adds debug info.
- **Flags in `include/config.h`.** A commented-out `BUGFIX` define turns on fixes for known original bugs. `UBFIX` (fixes for undefined behavior) turns on automatically when `MODERN` or `BUGFIX` is set. The matching build therefore stays the default and changes are opt-in.
- **Leaked material is handled differently from ZeldaRET.** pret hosts a Space World '97 prototype disassembly and a "#prototypes-and-leaks" Discord channel (pret.github.io). How that prototype ROM was obtained is not stated in its README. I found no lifetime "never accessed leaks" contributor rule like ZeldaRET's (unverified either way).

## 4. Testing and verification

- **The SHA-1 is the oracle** for every target, including Virtual Console builds and patch files.
- **Documented bugs as test cases.** pokecrystal's `docs/bugs_and_glitches.md` catalogs about 90 original bugs in eight categories: battle engines, overworld, graphics, audio, text, scripted events and internal routines. Each entry has a fix shown as a diff against the source. Where a fix would break link-battle compatibility, the doc suggests applying it only outside Colosseum link mode.
- **Toolchain checks.** pokered includes `.rgbds-version` and `rgbdscheck.asm`. Judging by their names they pin and check the assembler version, but I did not open the files to confirm this.

## 5. Structuring a large legacy codebase

- Every repo follows the same skeleton: README with hashes, `INSTALL.md`, a wiki of tutorials, a `symbols` branch and a Discord channel per project. Contributors can move between games easily.
- The pokecrystal wiki has 183 pages, mostly tutorials for adding moves, types, maps, music and Pokémon, or porting later-generation features. It also has pages on "Code cleanup" guidelines, "Hard-coded logic" (behavior not stored in tables) and community "Branches" that can serve as a base.
- Data is split from engine code, so content edits (tables, text, maps) do not require touching logic. The wiki's "hard-coded logic" page exists to document the cases where that split is missing.

## 6. Engine architecture insights

- **Link compatibility is a hard constraint.** The bug fixes have to preserve the byte-level protocol and battle logic shared with unmodified Gold, Silver and Crystal cartridges.
- **Save integrity.** Some original bugs, such as save corruption from power loss mid-save, have no simple fix. The doc says they would need a redesigned save system.
- **Hacks cannot link with the official games.** pokeemerald-expansion only supports multiplayer between games built on itself, and sends projects that need official compatibility back to vanilla pokeemerald.
- **Not covered.** Details of the RNG, frame loop and save-block layout are not covered by the fetched sources.

## 7. Legal history and lessons

- **Source only.** Repos ship source and tooling, and users must provide the original ROM, which is checked by hash. I found no Nintendo, Game Freak or TPC takedown against pret repos as of 2026-10-13 (absence of evidence, unverified).
- **The 2020 leaks hit nearby communities.** Vice reported in July 2020 that the gigaleak included a full development history of Diamond and Pearl, and that Glitch City Laboratories reverted its wiki and closed its forums over the Pokémon source leaks. This shows how leaked code can contaminate a research community.
- **Lesson.** Every public artifact should be derivable from your own analysis plus a user-supplied original. Keep any prototype or leak discussion fenced off.

## 8. Transferable lessons for STAR

1. **Make the default a faithful baseline and every change an explicit flag.** The `BUGFIX`/`UBFIX`/`MODERN` pattern maps to Roblox feature flags in a shared `Config` ModuleScript. Keep the shipped behavior as the default and switch new behavior on per test place.
2. **Treat a bug catalog as a deliverable.** For every Roblox system STAR reviews, keep a `bugs_and_glitches`-style doc listing symptom, cause, fix diff and compatibility caveat. It doubles as a regression-test list.
3. **Respect compatibility contracts.** Link-battle compatibility parallels DataStore schema compatibility. Never change saved data shapes without a versioned migration, the way pret fixes are gated to stay compatible with link mode.
4. **Pin toolchain versions with a guard.** `.rgbds-version` plus a check file maps to pinned versions in `aftman.toml`/`rokit.toml` and a CI step that fails on mismatch.
5. **Keep an upstream-faithful core with downstream expansions.** The pokeemerald to pokeemerald-expansion split suggests keeping STAR's Roblox templates minimal and canonical, with feature packs as separate layers that merge upstream regularly.
6. **Tutorial wikis grow communities.** Small, task-shaped how-tos ("add a new move") beat large reference docs. STAR's knowledge notes should include recipe-style Luau guides.

## Sources

- [pret.github.io (project list and community)](https://pret.github.io/)
- [pret/pokered README](https://github.com/pret/pokered)
- [pret/pokecrystal README](https://github.com/pret/pokecrystal)
- [pokecrystal docs/bugs_and_glitches.md](https://raw.githubusercontent.com/pret/pokecrystal/master/docs/bugs_and_glitches.md)
- [pokecrystal wiki](https://github.com/pret/pokecrystal/wiki)
- [pret/pokeemerald README](https://github.com/pret/pokeemerald)
- [pokeemerald INSTALL.md (agbcc, make compare, make modern)](https://raw.githubusercontent.com/pret/pokeemerald/master/INSTALL.md)
- [pokeemerald include/config.h (BUGFIX/UBFIX/MODERN)](https://raw.githubusercontent.com/pret/pokeemerald/master/include/config.h)
- [pret/pokegold-spaceworld README](https://github.com/pret/pokegold-spaceworld)
- [rh-hideout/pokeemerald-expansion README](https://github.com/rh-hideout/pokeemerald-expansion)
- [Vice: Nintendo gigaleak coverage (2020-07-28)](https://vice.com/en/article/a-massive-leak-of-nintendo-source-code-is-causing-chaos-in-video-games)
