# RPCS3 — reverse-engineering case study (researched 2026-10-13)

RPCS3 is the open-source PlayStation 3 emulator and debugger. Its core is LLVM-based recompilers for the Cell processor's PPU and SPU cores, which use different architectures. It moves system libraries over time from high-level reimplementations (HLE) to loading the real firmware modules (LLE). It tracks progress in a large, human-reviewed compatibility database.

## 1. What it is and its 2026 state
- The project describes itself as "the world's first free and open-source PlayStation 3 emulator/debugger". It is C++, mostly GPL-2.0-only, and runs on Windows, Linux, macOS and FreeBSD. It started in 2011 (DH and Hykem) and moved to GitHub in 2013 (README; Wikipedia).
- Version 0.0.39 shipped in January 2026 and 0.0.40 in April 2026. TSX support was removed in November 2025 because nobody maintained it, and a native Arm64 macOS build has existed since September 2024 (Wikipedia; Recalbox).
- In April 2026, lead developer Elad found previously unrecognised SPU usage patterns and added code paths that produce lighter host code. The team reported a 5-7% average FPS gain in Twisted Metal. Earlier, in June 2024, SPU work had given 30-100% gains on 4-core CPUs (Recalbox, Tom's Hardware).
- Compatibility: the team announced 75% Playable on 14 July 2026 (The FPS Review). The project's GitHub wiki table, as of September 2026, lists 3,563 entries: 2,809 Playable, 721 Ingame, 31 Intro, 2 Loadable and 0 Nothing. Every listed title has been at least "loadable" since Christmas 2022.

## 2. How the original was reversed
- The Developer Information wiki points to public IBM/Sony Cell documentation: the Cell Broadband Engine Architecture, the SPU ISA and ABI, and the SPE runtime library. That covers the CPU side from published specifications.
- For the RSX GPU command FIFO and the LV2 kernel syscalls, the project relies on community documentation (psdevwiki), which it calls "partially incomplete" or "a bit incomplete". Undocumented behaviour is therefore worked out by observing games and system modules.

## 3. Workflow: matching, non-matching or clean-room
- RPCS3 is behavioural reimplementation. HLE modules are optional reimplementations of firmware PRX libraries. Users install official firmware from Sony's site, and the emulator then loads the real modules (LLE) where its own versions are missing or inaccurate.
- The roadmap's medium-term goal is to "allow to LLE more system modules". Its long-term goal is to implement every module so firmware is no longer needed. In short, LLE is used for correctness now, and full HLE coverage is the end goal for independence.
- The README's AI policy allows AI "for research and reverse engineering". Contributors must fully understand submitted code, and AI-opened PRs must disclose their scope and the human testing behind them.

## 4. Testing and verification
- The compatibility list is tracked per Game ID, split by media (disc and digital separately), not per title. Each Game ID has its own forum thread, and reports follow guidelines and are "reviewed" before listing. Status levels are Playable, Ingame, Intro, Loadable and Nothing. Ratings depend on game version, build, settings and hardware.
- The roadmap admits the gap: writing automated tests "to reduce bugs" is still a medium-term item. Most verification comes from community game testing plus reviewers.
- An LLVM-based SPU interpreter shares the recompiler's backend, so the two cannot diverge (2019 report; seen only via search summary, so unverified).

## 5. Structuring a large legacy codebase
- `rpcs3/Emu/Cell` keeps each CPU concern in its own file: `PPUInterpreter`, `PPUTranslator` (LLVM), `PPUAnalyser`, `SPUInterpreter`, `SPUASMJITRecompiler`, `SPULLVMRecompiler`, `SPUCommonRecompiler` and `SPUAnalyser`. HLE libraries live under `Modules/` and the kernel under `lv2/`.
- Analysis (finding functions and blocks) is separate from code generation, so several backends can share it.
- The roadmap plans to make LLVM mandatory, remove the "SPU Precise" mode, merge the texture and surface caches, and drop RTTI. In other words, it is cutting down the number of parallel paths.
- Game-specific fixes go through a separate game patching system documented on the project wiki, not into the core.

## 6. Engine architecture insights
- **Two heterogeneous CPU types:** the PowerPC-like PPU and up to seven SIMD SPUs with local store. Each gets its own recompiler, with an interpreter fallback.
- **Runtime compilation cost:** new SPU code compiled at runtime causes hitches, so the project added caching and multithreaded precompilation. Code loaded at different addresses used to force recompiles until the code was made position-independent. Both points come from 2019 reports seen via search summaries.
- **RSX:** the GPU translates PS3 shaders to host APIs and keeps surface and texture caches. RSX-Cell synchronisation is a named short-term rework item.
- Save states were added in July 2022 (Wikipedia).

## 7. Legal history and lessons
*Not legal advice; historical summary only.*
- *Sony v. Connectix* (9th Cir., Feb 2000) held that intermediate copies made while reverse-engineering the PlayStation BIOS were fair use, because the shipped emulator held no Sony code. It also held that lost console sales did not defeat fair use.
- *Sony v. Bleem* (2000) protected comparative screenshots as fair use. Even so, Bleem closed in Nov 2001 under the cost of defending patent suits. Winning in court did not keep the company alive.
- RPCS3 has not been sued by Sony as of 2026-10-13. Its notable episode was a September 2017 Atlus DMCA against its Patreon page over Persona 5 promotion, settled by removing those references (Wikipedia).
- Why RPCS3 survived where yuzu did not (inference): it ships no console keys or firmware, users download firmware from Sony's own site, and it has avoided promoting specific unreleased or pirated titles.

## 8. Transferable lessons for STAR
1. **Keep separate analyser and code generator.** RPCS3 splits `*Analyser` from `*Recompiler`. When STAR rewrites or lints Luau, parse into an analysis model once (scopes, remotes, DataStore calls), then run several passes over it.
2. **Replace mocks with real modules step by step (HLE to LLE).** Start with stubbed Roblox services (mock DataStoreService or MarketplaceService) for fast tests. Swap in real services in a throwaway place as each stub's behaviour is confirmed, and keep a list of which services are still stubs.
3. **Use a compatibility matrix with defined tiers.** Rate STAR's generated systems against named Roblox templates or game types, using fixed levels (Nothing, Loads, Runs, Playable) and a review step. Track by exact version, as RPCS3 tracks by Game ID rather than title.
4. **Pay for JIT compile once.** Precompile and cache expensive work, such as STAR's prompt or graph builds and Roblox `require` chains, so it isn't paid on the hot path. Avoid caches keyed on things that move, such as addresses or file paths.
5. **Keep per-title patches outside the core.** Put game-specific Luau workarounds in a data-driven patch table keyed by place ID, not as `if game.PlaceId == ...` branches in shared modules.
6. **Be honest about missing tests.** RPCS3's roadmap openly lists missing automated tests. STAR's notes should mark "not verified" in the same way.

## Sources
- [RPCS3 GitHub README (AI policy, license)](https://github.com/RPCS3/rpcs3)
- [RPCS3 — Wikipedia](https://en.wikipedia.org/wiki/RPCS3)
- [RPCS3 wiki — Roadmap](https://github.com/RPCS3/rpcs3/wiki/Roadmap)
- [RPCS3 wiki — Game Compatibility](https://github.com/RPCS3/rpcs3/wiki/Game-Compatibility)
- [RPCS3 wiki — Developer Information](https://github.com/RPCS3/rpcs3/wiki/Developer-Information)
- [RPCS3 source tree — Emu/Cell](https://github.com/RPCS3/rpcs3/tree/master/rpcs3/Emu/Cell)
- [The FPS Review — RPCS3 crosses 75% playable (July 2026)](https://www.thefpsreview.com/2026/07/16/rpcs3-crosses-75-ps3-compatibility-three-quarters-of-the-entire-playstation-3-library-now-playable-on-pc/)
- [Recalbox — RPCS3 Cell/SPU breakthrough (April 2026)](https://www.recalbox.com/blog/2026-04-06-rpcs3-emulation-playstation-3-retrogaming/)
- [Tom's Hardware — Cell CPU breakthrough](https://tomshardware.com/video-games/playstation/rpcs3-ps3-emulator-gets-cell-cpu-breakthrough-that-improves-performance-in-all-games)
- [Sony v. Connectix — Wikipedia](https://en.wikipedia.org/wiki/Sony_Computer_Entertainment,_Inc._v._Connectix_Corp.)
- [Bleem! — Wikipedia](https://en.wikipedia.org/wiki/Bleem!)
