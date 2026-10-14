# Matching-decompilation tooling — reverse-engineering case study (researched 2026-10-13)

Matching decompilation writes C/C++ that compiles, with the original compiler and flags, into byte-identical object code. A small, mostly permissively licensed toolchain makes this practical: splat and decomp-toolkit split the binary into objects, m2c drafts C from assembly, asm-differ and objdiff diff the result, and decomp-permuter searches for matching variants.
decomp.me hosts shared scratches and decomp.dev tracks progress. The whole ecosystem is built around a deterministic oracle.

## 1. What it is and its 2026 state

- decomp.me: a collaborative decompilation site (Next.js + Django, MIT, self-hostable via Docker). asm-differ "is currently the default viewer used by decomp.me" (asm-differ README).
- asm-differ (diff.py, Unlicense): an assembly diff viewer for MIPS, PPC, AArch64, ARM32, SH2/SH4, m68k and limited x86, with a watch mode that rebuilds on save. It points to objdiff as the more modern alternative.
- objdiff (Apache-2.0/MIT, Rust):
  - Diffs whole relocatable objects, functions and data, across ARM, ARM64, MIPS, PowerPC, SuperH and x86.
  - Demangles GCC, MSVC, CodeWarrior and Itanium names.
  - Has a GUI, a CLI, a WASM/web build and a VS Code extension in progress.
  - Its progress reports power decomp.dev.
- splat (MIT): splits N64, PSX, PS2 and PSP binaries. It points GameCube and Wii projects to dtk.
- decomp-toolkit, "dtk" (Apache-2.0/MIT):
  - Analyses function boundaries, signatures and relocations, and splits DOL/REL files into relocatable objects.
  - Writes objects directly without an assembler, generates the CodeWarrior linker script, and verifies the linked result byte-for-byte.
- dtk-template: a configure.py + ninja scaffold using `config.yml`, `symbols.txt` and `splits.txt`, with per-version configs, objdiff integration, CI and decomp.dev reporting. It works "without committing game assets."
- m2c (formerly mips_to_c, GPL-3.0): turns MIPS, PowerPC, ARM and SuperH assembly into C for the IDO, GCC and MWCC compilers. The README calls it "fairly functional" but warns of suboptimal loops.
- decomp-permuter (MIT): rewrites a function into many equivalent forms and keeps the best-scoring ones. permuter@home distributes the search.
- decomp.dev (as of 2026-10-13) lists projects with matched and linked percentages.
  - Complete: Super Smash Bros. Melee, Parasite Eve and Legend of Mana.
  - Nearly complete: Pikmin 2 at 99.63% and Metroid Prime at 92.53%.

## 2. How the original was reversed

1. Split. splat (YAML segment config) or dtk (`dol split`) cuts the ROM or executable into per-file objects and asm.
2. Draft. m2c turns a function's asm into C, using a `--context` file of types and prototypes. It also supports a custom stack-layout struct.
3. Match. Edit the C, rebuild, and diff in objdiff or asm-differ until there are zero differences.
4. Polish. Use the permuter for the last register-allocation mismatches.
5. Name. Types and names are recovered over time and shared through symbol files.

## 3. Workflow: matching, non-matching or clean-room

- In matching work, each translation unit is marked done only when it re-links byte-identically. dtk's "fully-shiftable objects" let matched code move without breaking the build.
- Non-matching, functionally equivalent C is allowed in some projects. It is tracked separately, because it can hide subtle behaviour differences and blocks a shiftable or matching build.
- These projects are not clean-room. They are derived from studying the original binary, so they distribute source only and never ROMs or assets (dtk-template avoids committing assets).

## 4. Testing and verification

- The oracle is the original compiler plus an object diff. Watch modes (asm-differ `-mwo`, objdiff auto-rebuild) close the loop in seconds.
- Permuter scoring:
  - Diffs objdump output, penalising differing, reordered or changed instructions. Zero means a match, and stack offsets are ignored unless `--stack-diffs` is set.
  - The README calls the scorer "far from a perfect system."
  - Random mode makes many nonsensical edits: "it's up to you to pick out the ones that look sensible."
- Whole-binary verification: dtk/dtk-template rebuild the full DOL and compare it with the original. CI keeps the build green.
- Progress is computed from objdiff reports, not self-reported (decomp.dev).

## 5. Structuring a large legacy codebase

- Symbol and split files are the shared database: `symbols.txt` / `splits.txt` (dtk) and symbol-address lists for splat (exact file conventions unverified; see the splat wiki), all under version control.
- Per-unit metadata in `objdiff.json` lists target and base object paths. The README recommends generating this file from the build script and keeping it out of git. Units marked auto-generated are hidden in the UI but still counted in progress.
- Multiple game versions get separate configs selected by a configure flag (dtk-template).

## 6. Engine architecture insights

- Compiler identification comes first. A function can only match with the exact compiler build and flags, so each era has its own toolchain: SGI IDO and GCC on N64, MetroWerks CodeWarrior (mwcc/mwld) on GameCube/Wii. Decompedia (decomp.wiki) covers how to identify the compiler, its version and flags.
- Register allocation and instruction scheduling are the last-mile problems. That is exactly where the permuter beats humans and LLMs (permuter README; Chris Lewis's agent write-up).

## 7. Legal history and lessons

- Tool licences are permissive (MIT, Apache-2.0, Unlicense) except m2c (GPL-3.0). Incorporating m2c code into a product carries copyleft obligations, though running it as a tool does not.
- Precedent: Sega v. Accolade (9th Cir. 1992) treated disassembly to reach functional elements as fair use. 17 U.S.C. §1201(f) is a narrow interoperability exemption. Neither covers redistributing the original game, so projects require users to supply their own copy.

## 8. Transferable lessons for STAR

1. Build the oracle before writing code. STAR should first set up the diff, test or verify command, then iterate. If the oracle cannot run, the result is labelled unverified.
2. Make the loop fast and automatic, with watch-mode rebuilds and a numeric score. In Roblox, run `selene`, `luau-analyze --!strict` and TestEZ specs in a single command after every edit.
3. Split before you solve. Work per unit (function or ModuleScript) with focused context, not the whole repo.
4. Use search tools for the last mile only. Brute-force variant search is good at register-level noise and produces implausible code early. STAR should reach for it only when nearly matched, and filter the output for readability.
5. Pin the toolchain. The exact compiler version decides success. STAR should record versions (Luau/Rojo/Wally, Studio build) in project files and check them before diagnosing "mysterious" differences.
6. Generate progress from artefacts, not claims. Compute progress from tool reports (objdiff-style JSON or test counts) and show those numbers to the user.

## Sources

- [decomp.me GitHub](https://github.com/decompme/decomp.me)
- [asm-differ GitHub](https://github.com/simonlindholm/asm-differ)
- [objdiff GitHub](https://github.com/encounter/objdiff)
- [splat GitHub](https://github.com/ethteck/splat)
- [decomp-toolkit GitHub](https://github.com/encounter/decomp-toolkit)
- [dtk-template GitHub](https://github.com/encounter/dtk-template)
- [m2c GitHub](https://github.com/matt-kempster/m2c)
- [decomp-permuter GitHub](https://github.com/simonlindholm/decomp-permuter)
- [decomp.dev progress tracker](https://decomp.dev/)
- [Decompedia (decomp.wiki)](https://decomp.wiki/)
- [Chris Lewis — Using coding agents to decompile N64 games](https://blog.chrislewis.au/using-coding-agents-to-decompile-nintendo-64-games/)
- [Wikipedia — Sega v. Accolade](https://en.wikipedia.org/wiki/Sega_v._Accolade)
