# RE / decomp playbook (detail behind SKILL.md)

Each row: a recurring problem, what the projects did, and how to apply it in ordinary (including Roblox) engineering.
Case studies with sources: `docs/research/reverse-engineering/projects/*.md`; summary: `docs/research/reverse-engineering/INDEX.md`.

## Oracles, by project type

| Project type | Oracle | Applied elsewhere |
|---|---|---|
| Matching decomp (sm64, OoT/MM, pret, GameCube/Wii dtk projects) | Rebuilt ROM/DOL checksum equals the original; per-function diff (objdiff, asm-differ) | Refactor-only commits must leave characterization tests unchanged |
| Incremental reimplementation (OpenRCT2 early years) | Original process still running the parts not yet replaced | Strangler: old and new paths side by side, compare outputs |
| Lockstep strategy games (OpenTTD, OpenRA, OpenRCT2 multiplayer) | Per-tick state checksums; recorded replays | Seeded RNG + fixed tick + input logs = replayable bug reports |
| API reimplementation (Wine, ReactOS) | Conformance tests that also pass on real Windows | Write tests against the reference system first, then the new one |
| Emulators (Dolphin, RPCS3) | Hardware test programs; frame-dump / rendering regression (fifoci); compatibility lists | Golden screenshots and golden outputs in CI |
| GPU driver RE (Asahi, Nouveau/NVK) | Khronos conformance test suites; traced command streams of the vendor driver | Use the official spec's test suite when one exists |
| LLM-assisted decompilation | Re-executability (recompile and run tests) or byte match | Never accept generated code on looks alone |

## Matching-decomp loop
1. Split the binary (splat / dtk) into code, data and assets; set up a build that reproduces the original exactly from assembly.
2. Pick one function; get a first C draft (by hand, m2c, or an LLM).
3. Build with the original compiler and flags; diff the function.
4. Iterate: types, statement order, temporaries, loops; share on decomp.me; run decomp-permuter.
5. Matched: commit and remove its assembly. Stuck: keep it guarded as non-matching, with the assembly still used for the build.
6. Later passes: names, types, comments, documentation. Unknowns keep placeholder names.
7. Progress is reported per function and per byte, which keeps the remaining work honest.

## Format reversing loop
1. Collect many samples; keep originals read-only.
2. Hex view; find magic, version, header sizes, offsets, endianness, strings.
3. One controlled change per save; diff; record the field in a spec with a confidence level.
4. Detect checksums and compression before editing.
5. Reader + writer; round-trip every sample byte-for-byte; then edit and confirm in the original program.

## Legal patterns (general information, not legal advice)
- Ship code, never the original's assets, ROMs, firmware or keys; users supply their own legally obtained data.
- Refuse leaked or stolen source entirely; a contributor who has seen it stays away from the affected area.
- Clean room: spec writers and implementers are different people; specs describe behaviour, not code.
- Do not facilitate circumvention or piracy (the factors at issue in the yuzu case); do not bundle or document key extraction.
- Avoid trademarks in names and logos; use your own art.
- STAR declines DRM circumvention, cheats, and Roblox exploits and anything that defeats anti-cheat outright.
