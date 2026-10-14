# Zelda Reverse Engineering Team (ZeldaRET: oot, mm, tp) — reverse-engineering case study (researched 2026-10-13)

ZeldaRET runs matching decompilations of Ocarina of Time (oot), Majora's Mask (mm) and, more recently, Twilight Princess (tp). It also maintains the asset tooling (ZAPD) that turns ROM data into editable, XML-described sources. It is the most process-heavy of the fan decomps, with strict rules on leaks, two-reviewer PRs, reservation sheets and Doxygen documentation. That process is why its code later became the base for Ship of Harkinian and Zelda 64: Recompiled patches.

## 1. What it is and its 2026 state

- **oot.** The last function was matched in late 2021, after about two years of work. The team mostly targeted the GameCube Master Quest debug build because its debug features helped (VGC and KeenGamer, 2021-11-27). As of 2026-10-13 the README lists 16 buildable versions: N64 NTSC 1.0, 1.1 and 1.2, PAL 1.0 and 1.1, many GameCube discs including the debug builds, and iQue. The default is `gc-eu-mq-dbg`.
- **mm.** Started March 2021. It reached 100% matching code for the US N64 1.0 release in December 2024, announced by lead "darkeye" (Nintendo Life, 2024-12-12). The README still lists only `n64-us`. A mirror shows multiversion work (n64-jp-1.1) appearing in December 2025 (search result only, unverified on the main repo).
- **tp.** The README says GameCube code is "completely matching" but not every translation unit is linked yet. Debug, Wii and Nvidia Shield versions are in progress. decomp.dev showed 100.00% decompiled and 87.13% fully linked when fetched on 2026-10-13.
- **Neither oot nor mm is a PC port.** Both READMEs say so explicitly: mm "is not, and will not, produce a PC port".

## 2. How the original was reversed

- **Compilers.** The oot `docs/compilers.md` says N64 and GameCube code used IDO. IDO 5.3 built libultra, libleo and the JPEG library, and IDO 7.1 built the game. iQue used a patched EGCS 1.1.2. IDO now runs through ido-static-recomp, which replaced the unmaintained qemu-irix. tp builds with ninja and objdiff and runs Windows compiler binaries through wibo.
- **Setup and splitting.** `make setup` decompresses the ROM, extracts files and assets, and disassembles code and data into per-function assembly. Actors start out as one `.s` file per function plus a data file under `asm/non_matchings/overlays/actors/...` (archived OoT tutorial).
- **Per-function workflow.** mips_to_c (now m2c) produces a literal first-pass C reading. A context generator (`m2ctx.py`) feeds it project types. `diff.py` (asm-differ) shows control-flow, ordering, register and stack differences, which are fixed in that priority. Helper decoders turn InitChain and collider data into readable C.
- **Getting unstuck.** mm's CONTRIBUTING says to share a decomp.me scratch so others can help, and to run decomp-permuter before giving up.

## 3. Workflow: matching, non-matching or clean-room

- **Matching comes first, then documentation.** Imperfect C can be merged under `#ifdef NON_MATCHING`, with the original asm kept as the `GLOBAL_ASM` fallback. `NON_EQUIVALENT` marks code whose behavior differs.
- **Remaining cleanup.** It includes fixing "fake matches" (code that matches but is not plausible source; Nintendo Life), documentation, and making the ROM "shiftable". The oot README warns that some parts are not yet shiftable, so moving code can break hard-coded offsets.
- **Leak policy (not clean-room).** Contributors "must not have accessed leaked source code at any point in time". This covers libultra, the N64 and iQue SDKs, OoT, MM, Animal Forest and any related engine (mm CONTRIBUTING). Press coverage stresses that no leaked or original assets are used.

## 4. Testing and verification

- **The build is the test.** `make` prints `OK` only if the output is byte-identical to the base ROM. mm checks both a compressed and an uncompressed ROM by MD5.
- **Progress tracking.** The README badge links to zelda.deco.mp. tp reports to decomp.dev, which is powered by objdiff's progress reports.
- **Pre-PR checks.** `format.py` (clang-format) and `check_new_warnings.sh` must pass, so a PR cannot add compiler warnings.
- **Human verification.** Each PR needs two reviewers, at least one of them a lead, plus final approval from Kenix. PRs are squash-merged, and contributors merge main into their branch rather than rebasing (mm CONTRIBUTING).

## 5. Structuring a large legacy codebase

- **One folder per actor.** `src/overlays/actors/ovl_<Name>/` holds a `.c` and `.h` per actor. Structs start with the base `Actor` (or `DynaPolyActor`) and unknown fields are padded.
- **Naming ladder.** Unknown functions are `func_<address>` and unknown fields are `unk_<offset>`. Once understood, they get `ActorPrefix_Role` names, for example `EnJj_Init` (OoT tutorial).
- **Documentation.** It uses Doxygen block comments, a `@file` header and `//! @bug` markers above original bugs (oot `Documenting.md`). mm requires documentation for `code/` and `boot/` but not, for now, for overlays.
- **Assets.** XML files in `assets/xml` describe every asset in each ROM file. ZAPD reads them to extract textures, display lists and so on into C and PNG, and converts PNG/JPG/BIN back into C arrays at build time.
- **Logistics.** Contributors reserve one file per PR on a shared Google Sheet. Separate docs cover style, reviewing and tools.

## 6. Engine architecture insights

- **Actors.** Everything that moves or interacts is an actor: Link, enemies, NPCs, grass, and even the fishing pond, the largest actor. Most actors are overlays loaded "only when the game needs them" (OoT tutorial).
- **Actor lifecycle.** Each actor has four lifecycle functions: Init, Destroy, Update and Draw. They are declared through a profile/init-vars record. Update often dispatches through an "action function" pointer, which is a hand-rolled state machine.
- **Data-driven setup.** InitChains and collider initialisers are compact tables decoded at spawn time.
- **MM schedules.** MM adds a dedicated schedule scripting language for its 3-day NPC timetables, documented in `schedule_scripting_language.md`.
- **Not verified here.** The GameState loop and the frame-pacing and RNG details are not covered in the sources fetched.

## 7. Legal history and lessons

- **No ROMs or assets in the repos.** Users supply a legally obtained ROM, and builds extract assets locally. The repos also ship no original assembly (mm and tp READMEs).
- **The 2020 gigaleak** reportedly contained OoT and SM64 source (Wikipedia). ZeldaRET's lifetime "never accessed" rule keeps that material out by excluding people, not only files. It is a provenance firewall.
- **No Nintendo action found.** I found no record of action against the oot or mm repos as of 2026-10-13. Commentators call the legal status "murky" (Wikipedia on SoH, citing Kotaku).
- **No ports.** The decomp teams say they do not make ports, which keeps them away from the kind of binaries Nintendo has targeted.

## 8. Transferable lessons for STAR

1. **Grow names along a confidence ladder.** In unknown legacy Luau, rename `func_…`/`unk_…`-style placeholders only once their behavior is understood, and record the uncertainty in a comment. Never guess a confident name.
2. **Make ownership explicit.** A reservation sheet with one file, one PR maps directly to `star claim`. STAR should claim at file granularity and link the branch when abandoning work.
3. **Gate merges on a mechanical oracle plus two humans.** For Roblox systems, CI should run TestEZ, Selene and StyLua, plus a no-new-warnings check under `--!strict`. A reviewer then judges naming and plausibility, the equivalent of catching "fake matches".
4. **Separate assets from code.** XML manifests describe assets and a tool extracts or rebuilds them. For Roblox, keep a Rojo project plus a declarative asset manifest (IDs, purpose, owner) separate from gameplay modules, so code review never has to diff binary `.rbxm` files.
5. **Build an actor-style lifecycle.** Init, Update, Draw and Destroy plus an action-function state machine is a good template for CollectionService-tagged components in Roblox. Use a constructor, a Heartbeat update, a cosmetic client-only render step, and a Destroy that disconnects every connection to prevent leaks.
6. **Set provenance rules early.** STAR's knowledge base should refuse leaked or proprietary code outright, and that includes Roblox engine internals or exploit dumps, rather than "cleaning" it afterwards.

## Sources

- [zeldaret/oot README](https://github.com/zeldaret/oot)
- [zeldaret/mm README](https://github.com/zeldaret/mm)
- [mm docs/CONTRIBUTING.md (reservations, NON_MATCHING, leak policy, review)](https://raw.githubusercontent.com/zeldaret/mm/main/docs/CONTRIBUTING.md)
- [oot docs/compilers.md (IDO 5.3/7.1, EGCS)](https://raw.githubusercontent.com/zeldaret/oot/main/docs/compilers.md)
- [oot docs/Documenting.md (Doxygen style)](https://raw.githubusercontent.com/zeldaret/oot/main/docs/Documenting.md)
- [Archived OoT tutorial: beginning_decomp.md](https://raw.githubusercontent.com/zeldaret/oot/9963e7f5d5fa8caee329f6b40e393d8a2c45390b/docs/tutorial/beginning_decomp.md)
- [Archived OoT tutorial: introduction.md (actors and overlays)](https://raw.githubusercontent.com/zeldaret/oot/9963e7f5d5fa8caee329f6b40e393d8a2c45390b/docs/tutorial/introduction.md)
- [zeldaret/ZAPD README](https://github.com/zeldaret/ZAPD)
- [zeldaret/tp README](https://github.com/zeldaret/tp)
- [decomp.dev project list (TP progress)](https://decomp.dev/projects)
- [objdiff README](https://github.com/encounter/objdiff)
- [VGC: Zelda 64 fully decompiled (2021-11-27)](https://www.videogameschronicle.com/news/zelda-64-has-been-fully-decompiled-potentially-opening-the-door-for-mods-and-ports/)
- [Nintendo Life: Majora's Mask decomp at 100% (2024-12-12)](https://www.nintendolife.com/news/2024/12/zelda-majoras-mask-decompilation-project-now-at-100percent)
