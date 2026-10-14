# Super Mario 64 decompilation (n64decomp/sm64) — reverse-engineering case study (researched 2026-10-13)

The n64decomp/sm64 project rebuilt Super Mario 64 as C source that compiles back to byte-identical ROMs for five regional releases. It is the decomp that showed fan "matching decompilation" works for a whole 3D console game. Within months it had produced PC ports, mods and a wave of follow-on N64 decomps.

## 1. What it is and its 2026 state

- It is a full decompilation that builds `sm64.jp/us/eu/sh/cn.z64`, each checked against a published SHA-1. The five versions are Japan, North America, Europe, Shindou and iQue Player (README, as of 2026-10-13).
- The README still says "naming and documentation ... are in progress". Code coverage is done, but readability work continues.
- Press reports that fans finished decompiling it in 2019 after about two years. A separate team released a PC port about nine months later (VGC, 2021). Early mirrored commits date from August 2019. The exact public release date is unverified.
- As of 2026 the decomp is the base for many ports. They include sm64-port, sm64ex and Render96ex, and since January 2026 HarbourMasters' "Ghostship" (Time Extension, 2026-01-19).

## 2. How the original was reversed

- **Compiler identification.** The Makefile uses IDO by default. JP and US are built with `-g`, which means no optimization. EU, Shindou and iQue use `-O2`. Some libultra, math and audio files have their own per-file overrides (`-O2`, `-O3`, loop-unroll flags). Getting a match required recovering these flags file by file. The iQue build uses a separate EGCS-based toolchain.
- **Running a 1990s IRIX compiler on modern hosts.** It was first run under qemu-irix. Now ido-static-recomp is the default: the IRIX compiler binaries are statically recompiled into native programs.
- **Inline assembly in C files.** `asm_processor` lets a C file mix decompiled functions with `GLOBAL_ASM` blocks of original assembly. A file can therefore be converted one function at a time while the ROM stays matching.
- **Splitting.** The tree separates `asm/` (handwritten assembly plus `non_matchings/`), `lib/` (the SDK), `rsp/` (audio and Fast3D microcode), `actors/`, `levels/` and `assets/`. Assets are extracted from a user-supplied `baserom.<VERSION>.z64`.

## 3. Workflow: matching, non-matching or clean-room

- **The default is matching.** With `COMPARE=1`, the build runs a `sha1sum` against the target hash after linking.
- **`NON_MATCHING=1`** also defines `AVOID_UB` and switches to "functionally equivalent C implementations" that avoid undefined behavior. A non-N64 target (a PC port) forces it on. This is the bridge from an exact replica to portable code.
- **Microcode selection.** `GRUCODE` picks the graphics microcode: f3d_old, f3d_new, f3dex, f3dex2 or f3dzex. Hash comparison is turned off automatically for any version and microcode pair that never shipped.
- **Not clean-room.** Contributors read the original machine code directly. It is reverse engineering, not a clean-room spec-and-reimplement process.

## 4. Testing and verification

- **The ROM hash is the oracle.** "OK" means every byte matches. Any change in code generation, data layout or link order breaks it at once.
- **Function-level diffing.** asm-differ-style diffs, and later objdiff and decomp.me scratches, show the remaining instruction, register and stack differences. decomp-permuter randomly rewrites a function to search for register-allocation matches, and it scores 0 when the function matches fully. Its README warns that many "improvements" are nonsense, so a human has to review them.
- **Long build paths break the build.** Paths over 255 characters fail because of the recompiled IDO. It is a reminder that the oracle toolchain has quirks you have to preserve.

## 5. Structuring a large legacy codebase

- The engine is split into scripting interpreters, visible in `src/engine` as `behavior_script`, `level_script`, `geo_layout`, `graph_node` and `surface_collision`/`surface_load`. Game logic lives in `src/game`. Audio, the "goddard" title-screen head and menus each have their own folder.
- Data is kept close to the code that uses it: `actors/` holds object behaviors and display lists, and `levels/` holds per-level scripts and geometry.
- **Build options as the only switches.** `VERSION`, `GRUCODE`, `COMPARE` and `NON_MATCHING` are the single source of truth. Version differences are `#if` blocks inside one tree, not forks.

## 6. Engine architecture insights

- **Data-driven scripting.** Objects run small bytecode-like "behavior scripts", and levels load through "level scripts". The render tree is built from "geo layouts" into a graph of nodes. This much is from the file names. Details of the bytecode semantics are not covered here.
- **Rendering.** The game emits N64 display lists that RSP microcode executes. That is why `GRUCODE` exists, and why PC ports replace the RSP/RDP path with a display-list interpreter.
- **Collision.** It uses a dedicated surface system that loads static and dynamic surfaces separately.

## 7. Legal history and lessons

- **The decomp ships no assets.** Users supply their own ROM, and assets are extracted locally (README).
- **May 2020.** Within a week of a PC port appearing, Nintendo, through Wildwood Law Group, filed complaints against download links for the compiled executable and against YouTube footage. One complaint called the file "an unauthorized derivative work" (Nintendo Life, 2020-05-09). Reader claims that those binaries bundled assets are unverified. The enforcement targeted distributed builds, not the source repo, which still exists in 2026.
- **The July 2020 "gigaleak"** reportedly included N64 source for SM64 and OoT (Wikipedia). Decomps finished before the leak can point to independent provenance. Later projects banned contributors who had seen leaked material (see zeldaret.md).
- **Earlier takedowns.** Nintendo took down a fan "Super Mario 64 HD" in 2015 and "Super Mario 64 Online" in 2017 (Wikipedia).
- **Lesson.** Separate the source from the assets and never distribute binaries that contain assets. The legal risk sits on whatever you redistribute.

## 8. Transferable lessons for STAR

1. **Use an exact oracle to make refactors safe.** For a Roblox place, keep golden snapshots of pure-logic outputs, for example a damage table run over 10k seeded inputs or a serialized DataStore schema. CI should fail on any diff. Renames and documentation passes then become provably behavior-preserving, the way a `COMPARE=1` build does for the decomp.
2. **Use `NON_MATCHING`-style dual paths during migrations.** When rewriting a Luau module, keep the old implementation behind a flag, run both in tests, and assert equal results. Delete the old one only after the comparison stays green.
3. **Make the toolchain part of the spec.** Matching depended on exact compiler flags per file. Pin the Rojo, Wally, Selene and StyLua versions, and Luau type-check mode per file, in config, because tool upgrades change output.
4. **Convert incrementally inside one file.** `GLOBAL_ASM` let assembly and C coexist. In Roblox, wrap legacy scripts behind a ModuleScript interface and move one function at a time behind the same API.
5. **Separate the asset pipeline from the code.** Commit code only. Generate or import assets through a separate, reproducible step, just as the decomp extracts assets from `baserom` and never commits them.
6. **Prefer data-driven interpreters.** SM64's behavior and level scripts map to config-driven systems in Roblox, such as ModuleScript tables of ability or level definitions. Designers can then change content without touching engine code.

## Sources

- [n64decomp/sm64 README](https://github.com/n64decomp/sm64)
- [n64decomp/sm64 Makefile (compiler, OPT_FLAGS, COMPARE, NON_MATCHING)](https://raw.githubusercontent.com/n64decomp/sm64/master/Makefile)
- [sm64 src/engine directory listing](https://github.com/n64decomp/sm64/tree/master/src/engine)
- [decomp-permuter README](https://github.com/simonlindholm/decomp-permuter)
- [Nintendo Life: Nintendo cracks down on the SM64 PC port (2020-05-09)](https://www.nintendolife.com/news/2020/05/nintendo_cracks_down_on_the_super_mario_64_pc_port)
- [VGC: Zelda 64 fully decompiled, with SM64 background (2021-11-27)](https://www.videogameschronicle.com/news/zelda-64-has-been-fully-decompiled-potentially-opening-the-door-for-mods-and-ports/)
- [Wikipedia: Intellectual property protection by Nintendo (gigaleak, earlier SM64 takedowns)](https://en.wikipedia.org/wiki/Intellectual_property_protection_by_Nintendo)
- [Time Extension: Ghostship SM64 PC port (2026-01-19)](https://www.timeextension.com/news/2026/01/super-mario-64-has-got-another-fanmade-pc-port-from-the-harbour-masters-team)
- [sm64-port README](https://github.com/sm64-port/sm64-port)
