---
name: re-decomp-lessons
description: Engineering lessons from reverse-engineering, decompilation and clean-room reimplementation projects (OpenRCT2, OpenTTD, OpenMW, ScummVM, the N64 and Pokemon decomps, Dolphin, Wine). Use when reimplementing or porting an old system, reversing a file or save format, building replay or byte-exact regression oracles, judging LLM-decompiled code, or checking that a recreation stays legally clean.
---
# Learning from reverse-engineering and decomp projects
These are lessons from long-running open projects that rebuilt old games, consoles and operating systems. They are engineering method, not legal advice, and never a reason to help with piracy, DRM or key circumvention, cheats, Roblox exploits, or anything that defeats anti-cheat: decline those and offer the legitimate version of the task.

## 1. Get an oracle before you change anything
- Every project that finished had a cheap, automatic way to say "same" or "different": a rebuilt ROM whose checksum equals the original (sm64, OoT, pret), the original program run side by side (OpenRCT2 early on), conformance tests that also run on real Windows (Wine), hardware test programs and frame dumps (Dolphin), saved replays and desync checksums (OpenTTD, OpenRA).
- Put the oracle in CI. A change that has not been compared against the oracle is unverified, however plausible it reads.
- STAR's optional `re_compare_artifacts` tool can independently verify byte equality for two workspace files or bounded function ranges. PASS is not proof of a trustworthy original, semantic equivalence or a working port; the owner must anchor reference provenance and the runner must be outside the candidate's control.

## 2. Replace incrementally behind a working whole
- OpenRCT2 started as a library loaded into the original executable and replaced functions one at a time, so the game was playable every day. ReactOS and Wine replace one DLL or API at a time. This is the strangler pattern: never a big-bang rewrite.
- Keep the old and the new path runnable together and compare their outputs (differential testing) until the new one wins.

## 3. Match first, then make it readable
- Matching decomps write source that compiles to exactly the original bytes with the original compiler and flags; only then do naming and documentation passes. A non-matching fallback is marked as such, never passed off as matching.
- Unknowns keep honest placeholder names (an address or "unk") until evidence supports a real name. Guessed names spread wrong mental models.
- Track progress per function or module (matched, documented, tested) so the remaining work is visible.

## 4. Reverse formats with controlled experiments
- Change one thing in the program, save, diff the bytes. Find the magic number, header, version field, endianness, length prefixes, offsets and checksums. Write what you learn into a spec as you go.
- Implement reader and writer together and test the round trip: reading then writing an untouched file must give identical bytes, across many real samples.

## 5. Determinism makes bugs reproducible
- Lockstep games (OpenTTD, OpenRA) run a fixed tick, seed every random generator, avoid unordered iteration and wall-clock reads in simulation, and hash state each tick to detect desyncs. Recorded inputs then replay the same game, which turns rare bugs into regression tests.

## 6. Separate engine, rules and content
- Data-driven rules (OpenRA rule files, OpenTTD add-on data, OpenMW and OpenRCT2 scripting) let mods and fixes land without engine changes. Users supply the original data files; the project ships only its own code and assets.
- Save formats carry a version and a migration chain; old saves keep loading.

## 7. Legal hygiene the projects converged on
- Never distribute original assets, ROMs, firmware or keys. Never use leaked source: decomp teams refuse it to keep clean hands.
- Clean room means one person studies behaviour and writes a spec, another implements from the spec. Wine forbids contributors from disassembling Microsoft code.
- The projects that were shut down or sued were tied to circumvention and piracy facilitation (the yuzu case settled in 2024), not to independent reimplementation as such. Copying mechanics is different from copying code, art, music or trademarks. Point people to a lawyer for real decisions.

## 8. How an AI assistant should help
- Propose candidates; let the oracle decide. Never call decompiled or translated code correct until it compiles and matches, or passes re-execution tests against the original behaviour.
- Say which claims are verified, inferred or unknown.
- Respect each project's AI policy: Wine refuses LLM-generated code, ScummVM requires AI help to be disclosed with a human taking full responsibility. Check the contribution rules before suggesting generated code for a project.

## Roblox and Luau parallels
- Before refactoring a live game, capture its behaviour as characterization tests (the oracle), then change one module at a time.
- Use a fixed-step server simulation with seeded Random objects and logged inputs so a round can be replayed in a test.
- Version every DataStore record and migrate on load; test with real old records.
- "Remake a classic" in Roblox: recreate mechanics with original art, sound and names.
