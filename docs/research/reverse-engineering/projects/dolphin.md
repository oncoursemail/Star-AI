# Dolphin — reverse-engineering case study (researched 2026-10-13)

Dolphin is the long-running, GPL-licensed GameCube/Wii (and now Triforce arcade) emulator. Its engineering is built on hardware tests that run on real consoles, a JIT CPU recompiler, ubershaders that ended shader-compile stutter, and graphics regression CI (FifoCI). Its 2023 Steam release was blocked over a Wii encryption key in its source, which makes it a useful legal case study too.

## 1. What it is and its 2026 state
- Started in 2003 as a closed freeware GameCube emulator. The source was released under GPL-2.0-only in July 2008, then relicensed to GPL-2.0-or-later in May 2015 (Wikipedia).
- Since July 2024 it uses a rolling YYMM release scheme (first was 2407). Wikipedia lists stable 2609 (24 Sep 2026) and preview 2609-57 (4 Oct 2026), as of 2026-10-13. I could not read the official 2609 report because the blog blocked automated access.
- Progress report 2603 (March 2026) brought Triforce arcade support and an MMU "fastmem" path that traces page-table invalidations (`tlbie`). That path roughly doubled Rogue Squadron II/III performance. The same release fixed a netplay desync caused by inaccurate rounding in the `fmadds` instruction. Per a secondary summary, it merged 465 commits.
- Video backends are D3D11, D3D12, OpenGL, Vulkan, Null, and a CPU software renderer kept for debugging. DSP audio offers HLE or LLE, and the LLE mode has interpreter and recompiler submodes (README).

## 2. How the original was reversed
- **Hardware test suite:** `dolphin-emu/hwtests` is built with the devkitPPC/libogc homebrew toolchain. Tests are sent over the network to a Wii running the Homebrew Channel, and results come back over TCP. The same tests can run against the emulator, so console and emulator give comparable outputs. Test areas are `cputest`, `gxtest` and `iostest`.
- Behaviour is pinned down at instruction level. For example, the 2603 desync fix matched the console's exact floating-point rounding by adding error-compensated arithmetic.
- A free DSP firmware replacement shipped in 3.5 (2012), so users no longer needed console DSP code for LLE audio (Wikipedia).

## 3. Workflow: matching, non-matching or clean-room
- Dolphin is behavioural reimplementation, not decompilation. Hardware is described by observation and tests, and nothing is binary-matched.
- Contributing.md says anyone with confidential GameCube/Wii/Triforce knowledge from an NDA or leaks may not contribute at all, "even when the code is unrelated". Piracy is banned in every project channel.
- The same file says contributions come from humans, AI use must be disclosed, and LLMs may not be used for changes to emulated-console behaviour or to "obtain information about the console".

## 4. Testing and verification
- **FifoCI** is described as a "continuous integration service running Dolphin FIFO logs to find graphics rendering regressions" (BSD-2, Python/Django). FIFO logs are recorded GPU command streams that can be replayed without the game. They let rendering changes be checked without running full games, and no game data has to be redistributed. How the frame comparison works (exact versus perceptual) is unverified because fifo.ci blocked access.
- hwtests act as the oracle for CPU, GX and IOS behaviour.
- clang-format 19.1 is enforced, with a `Tools/lint.sh` pre-commit hook.
- Netplay desyncs work as an informal determinism test: two machines must stay bit-identical.

## 5. Structuring a large legacy codebase
- The repo has about 46k commits. Top-level folders are `Source`, `Externals`, `Data`, `Tools` and `Source/Android`.
- A single video-common layer sits above swappable backends, and the Null and Software backends exist for testing and debugging.
- The plugin interface was removed in 3.0 (2011) in favour of an integrated core (Wikipedia).
- The immature "JIT IL" CPU core was deleted in 2017 instead of being kept alive. Dead alternative cores are a maintenance cost.

## 6. Engine architecture insights
- The CPU is a PowerPC JIT for x86-64 and AArch64. The ARMv7 Android build was kept until the AArch64 JIT was ready. "Fastmem" maps guest memory so that loads and stores hit host memory directly.
- **Ubershaders (2017):** an interpreter of the console's fixed-function pixel pipeline runs on the GPU. It covers frames while specialised shaders compile in the background, trading some GPU cost for no stutter (Wikipedia).
- DSP has HLE (fast) and LLE (accurate) as user-selectable paths.

## 7. Legal history and lessons
*Not legal advice; historical summary only.*
- Dolphin announced a Steam early-access release in March 2023. On 26-27 May 2023 it said the release was "indefinitely postponed" after Valve relayed a Nintendo cease-and-desist that cited the DMCA. A reported excerpt said Dolphin incorporates "cryptographic keys without Nintendo's authorisation" (VGC).
- In July 2023 Dolphin cancelled the Steam release and gave a correction: Valve had contacted Nintendo, and no DMCA notice was issued. After consulting counsel, Dolphin kept the Wii common key in its source, citing interoperability and the key's wide public availability (Wikipedia summarising Dolphin's 20 July 2023 post).
- Nintendo told press that Dolphin "illegally circumvents" its protection measures. As of 2026-10-13 no lawsuit is reported, and Dolphin still ships from its own site and GitHub.
- Background precedent: *Sony v. Connectix* (9th Cir. 2000) held that intermediate copies made while reverse-engineering a BIOS for an emulator were fair use, because the shipped product contained no copied code.
- Lesson: a distribution channel such as Steam can be closed off with no court ruling at all. Embedded secrets are the weak point, while clean behavioural reimplementation is the strong one.

## 8. Transferable lessons for STAR
1. **Keep an oracle test suite run against the reference.** For Roblox, write small TestEZ/Jest-Lua specs that pin down engine behaviour STAR relies on, such as `task.wait` timing, `Instance` event ordering and `RemoteEvent` delivery order. Run them in Studio and treat failures as spec changes, the way hwtests are treated.
2. **Record and replay.** FIFO logs capture the input stream so output can be checked without the whole game. For Luau, record RemoteEvent traffic or input logs and replay them into pure modules to catch regressions deterministically.
3. **Hide latency behind a generic slow path.** Ubershaders run a general interpreter while the specialised version compiles. In Roblox, show a generic placeholder (ViewportFrame or LOD model) while assets stream in, rather than blocking on `ContentProvider:PreloadAsync`.
4. **Treat determinism as a test.** Netplay desync showed a one-ulp rounding bug. For server-authoritative Roblox code, run the same simulation on server and client and log divergence, and never trust client results.
5. **Ship no secrets.** Dolphin's one embedded key cost it Steam. STAR should never put API keys, DataStore secrets or webhook URLs in generated Luau. Keep them in server-only config or HttpService secrets.
6. **Follow AI provenance rules.** Dolphin bans LLM-derived console knowledge and Wine bans LLM code. STAR should tag AI-generated contributions and respect per-repo AI policies before proposing patches upstream.
7. **Delete immature parallel cores, as Dolphin did with JIT IL.** One maintained code path beats two half-maintained ones.

## Sources
- [Dolphin (emulator) — Wikipedia](https://en.wikipedia.org/wiki/Dolphin_(emulator))
- [dolphin-emu/dolphin GitHub README](https://github.com/dolphin-emu/dolphin)
- [Dolphin Contributing.md (NDA/LLM rules)](https://github.com/dolphin-emu/dolphin/blob/master/Contributing.md)
- [dolphin-emu/hwtests — hardware test suite](https://github.com/dolphin-emu/hwtests)
- [dolphin-emu/fifoci — graphics regression CI](https://github.com/dolphin-emu/fifoci)
- [VGC — Nintendo blocked Dolphin's Steam version (May 2023)](https://www.videogameschronicle.com/news/nintendo-has-blocked-the-steam-version-of-gamecube-and-wii-emulator-dolphin/)
- [GeekNews summary of Dolphin Progress Report 2603](https://news.hada.io/topic?id=27474)
- [Sony v. Connectix — Wikipedia](https://en.wikipedia.org/wiki/Sony_Computer_Entertainment,_Inc._v._Connectix_Corp.)
