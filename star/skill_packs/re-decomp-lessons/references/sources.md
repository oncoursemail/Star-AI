# Sources for re-decomp-lessons

Written in STAR's own words on 2026-10-13 from the case studies in `docs/research/reverse-engineering/projects/` (each note lists the pages its researcher fetched, and marks what could not be verified). No code from any project or original game is included. Not verified with the STAR knowledge service /api-lookup: the only Roblox API the pack names is Random.new(seed), documented on the Creator Documentation page below.

Primary sources behind the main claims:

- https://github.com/n64decomp/sm64 (matching decomp: byte-identical ROM rebuild as the oracle)
- https://raw.githubusercontent.com/zeldaret/oot/main/docs/Documenting.md (naming and documentation passes after matching)
- https://raw.githubusercontent.com/pret/pokeemerald/master/include/config.h (faithful build by default; bug fixes behind opt-in flags)
- https://github.com/encounter/objdiff (per-object diff tool for decomp projects)
- https://github.com/simonlindholm/decomp-permuter (searches C variants that compile closer to the target)
- https://github.com/ethteck/splat (splits a binary into code, data and assets)
- https://forums.openrct2.org/topic/2869-does-open-require-the-original-again/ (OpenRCT2: original code fully replaced; original assets still required)
- https://www.openttd.org/news/2026/03/19/steam-changes-update (OpenTTD and the 2026 Atari agreement)
- https://github.com/ihhub/fheroes2/wiki/F.A.Q. (fheroes2: needs original data or the free demo)
- https://github.com/dolphin-emu/hwtests (Dolphin: tests that run on real hardware and the emulator)
- https://github.com/dolphin-emu/fifoci (Dolphin: rendering regression testing from recorded GPU command streams)
- https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/wikis/Clean-Room-Guidelines (Wine clean-room rules: no disassembly of Microsoft code, no leaked source, no LLM-generated code)
- https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/wikis/Conformance-Tests (Wine: tests must pass on real Windows)
- https://github.com/reactos/reactos/blob/master/media/doc/WINESYNC.txt (ReactOS: tracking code shared with Wine)
- https://raw.githubusercontent.com/scummvm/scummvm/master/AI-GUIDELINES.md (ScummVM: disclosure and human responsibility for AI-assisted contributions)
- https://github.com/albertan017/LLM4Decompile (LLM decompilation measured by re-executability)
- https://create.roblox.com/docs/reference/engine/datatypes/Random (Random.new(seed) for seeded, replayable simulations)

Legal statements in the pack are general information drawn from these projects' own policies and from reporting on the yuzu settlement (see `projects/ryujinx-yuzu.md`); they are not legal advice.
