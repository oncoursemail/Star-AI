# ScummVM — reverse-engineering case study (researched 2026-10-13)

ScummVM began in 2001 as a reimplementation of LucasArts' SCUMM script interpreter. It is now a GPL-3.0+ framework that hosts dozens of separately reversed adventure and RPG engines on one shared portability layer. It replaces only the original executables, so users supply their own game data. Its pattern of per-engine plugins, shared subsystems, and detection by file fingerprint is the most reusable architecture lesson in this group of case studies.

## 1. What it is and its 2026 state

- **Latest release: 2026.4.0 "Never-slop", 2026-10-11.** It marks the project's 25th anniversary, measured from Ludvig Strigeus's first public commit. That release alone adds 194 games and 12 engines by the team's count, including more than 140 Wintermute titles, Nancy Drew, Rebel Assault and Dungeon Master.
- In 2026 the project switched to calendar-style versions (2026.1.0 in January, then 2026.2.0, 2026.3.0 and 2026.4.0) and calls this a "new release cadence". The previous line was 2.9.x.
- The site claims "over 325 adventure games" (as of 2026-10-13). New engines go through public testing calls first, four of them in October 2026 alone.
- **Licence:** GPL-3.0-or-later per the repository and CONTRIBUTING ("License: GPLv3+").
- The repository now carries an **AI-GUIDELINES.md**. AI help is allowed only in code the contributor knows well, and it must be disclosed with an `Assisted-by: AGENT:MODEL` commit tag. An AI must never be listed as author or co-author, AI-generated media assets are banned, and humans own the result: "AI agents cannot be used as an excuse for low quality".

## 2. How the original was reversed

- **Per engine, by volunteers, without source.** The FAQ calls this "a long and difficult process". Each engine is its own reverse-engineering project, and a game is only taken on if it fits the project's scope and a developer volunteers.
- **Script tooling is part of the method.** The separate scummvm-tools repository ships decompilers and disassemblers for game bytecode: descumm (SCUMM), degob (Coktel Vision), decine (Cinematique), dekyra (Kyrandia) and desword2 (Broken Sword II). It also has extractors for archive formats. Turning game scripts into readable listings is how the VM's semantics get pinned down.
- **Written specs.** Early SCUMM format and VM specs were published on scummvm.org (copyright David Given 2000-2002). A per-version opcode table lives on the wiki's SCUMM Technical Reference, which I could not fetch because of bot protection.
- **Rights-holder help.** Revolution Software provided source and advice and freewared two games. Others released source or freeware, and Disney and GOG ship ScummVM-based titles (Wikipedia).

## 3. Workflow: matching, non-matching or clean-room

- **Non-matching interpreter reimplementation.** The FAQ says ScummVM is "not an emulator". It replaces the executable with new C++ that runs the original scripts and data. Code structure is not preserved, but script semantics and data formats are.
- The approach is per engine. How engines were reversed (disassembly, script decompilation, rights-holder source) differs between engines and is not formally clean-room. I found no project-wide clean-room policy (**unverified**).
- Some original bugs are worked around in engine code. Wikipedia notes ScummVM avoids "some original bugs".

## 4. Testing and verification

- **Testbed engine** (`engines/testbed`): a fake "game" that exercises backend subsystems: graphics, sound, MIDI, events, filesystem, savegames, video, networking, cloud, printing, speech, TinyGL. It is used to validate each port without needing copyrighted data. (Its purpose is inferred from the file list.)
- **Event Recorder**: records input and replays it to catch regressions after engine changes. The 2026.4.0 notes list Event Recorder improvements. Older developer reports, seen only in search snippets and so **unverified**, say recordings broke whenever polling counts or random-number use changed, and that the recorder was once pulled from daily builds.
- **Detection by file fingerprint** (MD5 plus size) means every supported game variant is a recorded fixture. Unknown variants trigger fallback detection, and users are asked to report the new fingerprints.
- Static analysis (PVS-Studio, clang-tidy), pre-commit hooks, CI config and public game-testing calls cover the rest.

## 5. Structuring a large legacy codebase

- Top-level split: `engines/` (one directory per engine), with shared `common/`, `graphics/`, `audio/`, `video/`, `image/`, `math/`, `gui/`, `backends/` (platform ports), `base/` (plugin loading) and `devtools/`.
- **Plugin contract:** each engine provides a MetaEngine. AdvancedMetaEngine handles detection from descriptor tables of file names, MD5 and size, offers an optional `fallbackDetectExtern` hook, and instantiates the engine through `createInstance`. The base MetaEngine also standardises savegames (`listSaves`, sorted by slot; extended-save headers with thumbnails and autosave slots) and GUI options.
- The result: new engines inherit launcher UI, saves, keymapping, audio mixing and every platform port for free. That shared layer is what makes 300+ games across a dozen-plus platforms maintainable.
- ScummVM absorbed its 3D sister project ResidualVM around 2020-21 (Wikipedia). A TinyGL software renderer is now part of the shared stack, and Testbed exercises it.

## 6. Engine architecture insights

- **SCUMM VM** (scummvm.org spec): bytecode with *automatic cooperative threading*.
  - Up to 25 script slots run at once, each with 16 words of locals, and every script runs once per frame until it yields.
  - A script can spawn a child, which pends the parent. Nesting goes 15 deep.
  - Slot states are RUNNING, PENDED, DELAYED and FROZEN.
  - V5 encodes operand types in opcode bits. V6 switched to a single 100-word stack shared by all threads, so a script must leave the stack empty before anything that can deschedule it.
- My generalisation, which I did not verify engine by engine: engines run an interpreter loop that polls events, runs script slots, updates actors, renders, and feeds the mixer. Saves then have to capture VM variables and slot state, so the shared MetaEngine save API standardises the container (header, thumbnail, slot) while each engine owns the payload.

## 7. Legal history and lessons

- LucasArts sent an early cease-and-desist. About four years of work with its lawyers produced an agreement that let development continue. A 2008 dispute over a Wii port with Mistic Software was settled in 2009 (Wikipedia).
- A strict no-piracy policy: no assets are shipped, and the FAQ says "abandonware" is not a legal concept.
- Long-term cooperation with rights holders (freeware releases, official ScummVM-based storefront releases) became a legal moat and a distribution channel.

## 8. Transferable lessons for STAR

1. **The SCUMM VM is Roblox's task scheduler in miniature.** Cooperative per-frame threads that must yield map onto Luau coroutines and `task.spawn`/`task.wait`. STAR should explain Luau yielding with this model and flag code that yields inside shared-state critical sections. That is the same hazard as V6's shared stack.
2. **Plugin and shared-subsystem split.** Recommend a Roblox layout where each game system is a ModuleScript "engine" behind a small contract (`init`, `start`, save hooks), with input, saving and UI provided by shared services. That is ScummVM's MetaEngine idea.
3. **Fingerprint-driven detection.** For STAR's tooling, identify a project's variant (Rojo vs Studio-only, Wally packages, `--!strict`) from file signatures, with an explicit fallback path and a request to report unknown cases.
4. **Testbed over real content.** Keep a synthetic test place that exercises DataStore, remotes, UI and physics without production data.
5. **Record and replay is fragile when the RNG or polling isn't deterministic.** Seed `Random.new(seed)` and drive time explicitly in Luau tests.
6. **Adopt ScummVM-style AI-contribution hygiene.** Disclose assistance, keep humans as authors, and never submit code the human does not understand. STAR's outputs should be easy for the user to review.

## Sources

- [ScummVM news (2026.4.0 release, testing calls)](https://www.scummvm.org/news/)
- [ScummVM GitHub releases](https://github.com/scummvm/scummvm/releases)
- [ScummVM GitHub repo/README](https://github.com/scummvm/scummvm)
- [ScummVM AI-GUIDELINES.md](https://raw.githubusercontent.com/scummvm/scummvm/master/AI-GUIDELINES.md)
- [ScummVM CONTRIBUTING.md](https://github.com/scummvm/scummvm/blob/master/CONTRIBUTING.md)
- [ScummVM FAQ (docs)](https://docs.scummvm.org/en/latest/help/faq.html)
- [scummvm-tools README (descumm etc.)](https://github.com/scummvm/scummvm-tools)
- [Testbed engine directory](https://github.com/scummvm/scummvm/tree/master/engines/testbed)
- [AdvancedMetaEngineBase API docs](https://doxygen.scummvm.org/d6/df9/class_advanced_meta_engine_base.html)
- [ScummMetaEngine API docs](https://doxygen.scummvm.org/d7/de3/class_scumm_meta_engine.html)
- [SCUMM script/VM spec (old scummvm.org docs)](https://www.scummvm.org/old/docs/specs/scrp.php)
- [Wikipedia: ScummVM](https://en.wikipedia.org/wiki/ScummVM)
