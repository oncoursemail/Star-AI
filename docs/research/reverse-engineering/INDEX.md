# Reverse-engineering, decompilation and clean-room projects: index and lessons (researched 2026-10-13)

Twenty-one case studies of projects that rebuilt old games, consoles, drivers and operating systems, written for STAR. The goal is the transferable engineering: how they reversed formats, protocols and architecture, how they verified their work, how they organised huge legacy codebases, and what the legal history teaches. No proprietary or decompiled code is reproduced. Each note cites the pages its researcher fetched and marks unverified claims. None of this is legal advice.

STAR material built from this research:
- Skill pack `re-decomp-lessons` (`star/skill_packs/re-decomp-lessons/`): lessons from RE/decomp projects, with `references/playbook.md` and `references/sources.md`.
- Skill pack `eng-legacy-archaeology` (`star/skill_packs/eng-legacy-archaeology/`): method for understanding and changing large inherited codebases, Roblox games included.
- Golden tasks `evals/reverse-engineering/golden-tasks-re-v1.json` (REV-01..REV-06, prose-graded, with reference and bad answers).
- Both packs are catalog-only (the model can load them through the skill catalog). They are not auto-routed and not enabled by default until the evaluation gate has measured them.

## Projects

| Note | Kind | Workflow | Oracle / verification | Key lesson |
|---|---|---|---|---|
| [OpenRCT2](projects/openrct2.md) | Game reimplementation | Incremental, function by function inside the original exe; non-matching | Original process early on; replay checksums on every PR | Replace a live system one piece at a time; guard it with replay hashes |
| [OpenTTD](projects/openttd.md) | Game reimplementation | From disassembly-derived C to an original C++ codebase | Desync checks, versioned savegames, regression saves | Commands as the only way to change state; self-describing versioned save chunks |
| [OpenRA](projects/openra.md) | Engine recreation | Black-box: file formats only, never the executable | World hash every net frame; automated rule migrations | Data-driven rules plus composable traits carry whole games |
| [fheroes2](projects/fheroes2.md) | Engine recreation | From scratch, from asset formats and observation | CI with static analysis; bounded save-version window | Fence "improvements" away from balance-critical original rules |
| [OpenMW](projects/openmw.md) | Engine reimplementation | From scratch, reads original data files | Lua integration tests on a free example game | Global vs local scripts with event messages (maps to Script/LocalScript + remotes) |
| [ScummVM](projects/scummvm.md) | Multi-engine framework | Per-engine reversing behind a plugin contract | Detection by file fingerprint; testbed engine | Small engine contract + shared subsystems give every port for free |
| [DevilutionX](projects/devilutionx.md) | Decomp then port | Binary-close reconstruction, then modernisation | Seeded dungeon-generation tests | Match first, mark original bugs, modernise behind tests |
| [ReactOS](projects/reactos.md) | Clean-room OS | Clean room; shares Wine user-mode code | Conformance tests validated on real Windows | Write the clean-room policy before anyone accuses you |
| [Super Mario 64 decomp](projects/sm64-decomp.md) | Matching decomp | Matching, `NON_MATCHING` fallback | Byte-identical ROM hash in the build | An exact oracle makes every rename and refactor provably safe |
| [ZeldaRET (OoT, MM, TP)](projects/zeldaret.md) | Matching decomps | Matching, then naming and documentation passes | ROM checksum, two reviewers, progress per function | Process scales: reservations, naming ladder, "never accessed leaks" rule |
| [pret](projects/pret.md) | Disassemblies and decomps | Byte-exact rebuilds | Rebuilt ROM checksum | Faithful build by default; fixes behind opt-in flags |
| [N64 PC ports (SoH, sm64ex, N64Recomp)](projects/n64-pc-ports.md) | Ports built on decomps / recompilation | Decomp + platform layer, or static recompilation | Runs against user-extracted assets | Separate engine from content; ship code, never assets |
| [Dolphin](projects/dolphin.md) | Emulator | Hardware RE, JIT, ubershaders | hwtests on real consoles; FifoCI rendering regression | Test against the real hardware; never ship secrets in source |
| [RPCS3](projects/rpcs3.md) | Emulator | LLVM recompilers; HLE replaced by LLE over time | Human-reviewed compatibility database | Track which parts are still stubs; per-version compatibility tiers |
| [Ryujinx and yuzu](projects/ryujinx-yuzu.md) | Emulators (history and legal only) | n/a | n/a | Circumvention and piracy facilitation, not reimplementation, were the attack surface |
| [Wine and Proton](projects/wine-proton.md) | Clean-room API reimplementation | Black-box tests; no disassembly, no leaked source, no LLM code | Conformance suite run on real Windows | Write the test, prove it on the reference, then implement |
| [Asahi Linux GPU](projects/asahi-gpu.md) | Driver RE | Black-box tracing via a hypervisor | Khronos conformance suites | An external conformance suite is the definition of done |
| [Nouveau / NVK / Nova](projects/nouveau.md) | Driver RE | Clean-room tracing; later vendor firmware | Register database; conformance tests | One machine-readable source of truth for discovered facts |
| [Ghidra / IDA ecosystem](projects/ghidra-ida-ecosystem.md) | Tools | Exploration and annotation | The build and diff, not the decompiler view | Decompiler and LLM output are claims to check |
| [LLM-assisted decompilation](projects/llm-decompilation.md) | Research | LLM proposes, verifier decides | Re-executability; byte match | Never declare success without the verifier's output |
| [Matching-decomp tooling](projects/matching-decomp-tooling.md) | Tools | splat/dtk, m2c, objdiff, asm-differ, permuter, decomp.me | Byte-identical object diff | Build the oracle and a fast watch loop first |

## Cross-project lessons

1. **Build the oracle first.** Every project that finished had an automatic "same or different" check: ROM checksums, the original running side by side, tests passing on real Windows or real hardware, replay hashes, conformance suites. Work that bypasses the oracle is unverified.
2. **Replace incrementally behind a working whole.** OpenRCT2 (inside the original exe), OpenTTD (twenty years of rewriting), Wine and ReactOS (one DLL at a time). No project succeeded with a big-bang rewrite of something it did not understand.
3. **Match first, make readable second.** Matching decomps separate correctness (byte-exact) from understanding (naming and documentation passes). Unknowns keep placeholder names until evidence arrives. Non-matching code is labelled as such.
4. **Determinism is a testing tool.** Fixed ticks, seeded RNG, no wall-clock reads in simulation, ordered iteration, and state hashes per tick turn rare bugs into replayable regression tests (OpenTTD, OpenRA, OpenRCT2, DevilutionX's seeded generation tests).
5. **Funnel state changes through one gateway.** OpenTTD commands, OpenRCT2 game actions, OpenMW events: validated, network-safe, testable. This is the same shape as server-authoritative RemoteEvent handling in Roblox.
6. **Separate engine, rules and content.** Data-driven rules (OpenRA MiniYaml, OpenTTD add-on data), plugin and scripting APIs (OpenRCT2 JavaScript, OpenMW Lua), engine plugins (ScummVM) and resource archives (Ship of Harkinian) keep mods and fixes out of the core.
7. **Save formats outlive code.** Versioned, self-describing chunks with migration chains (OpenTTD, OpenRCT2 `.park`, fheroes2's supported-version window). The Roblox equivalent is a schema version in every DataStore record with load-time migration.
8. **Reverse formats by controlled experiment and prove parsers by round trip.** Change one thing, diff, record in a spec; reader + writer must reproduce every sample byte-for-byte.
9. **Process scales knowledge.** Reservations, two reviewers, documentation standards and progress dashboards (ZeldaRET, pret) let hundreds of volunteers work on one codebase without collisions.
10. **Tools and LLMs propose; oracles decide.** Decompilers, m2c, permuters and LLMs generate candidates. The compiler, the diff, the conformance suite or the re-execution test is the judge. Agents with no diff tool reported false matches (see the LLM-decompilation note).

## Legal lessons

General information from the projects' own policies and public reporting; not legal advice.
- **Ship code, never the original's assets.** OpenRCT2, OpenMW, ScummVM, fheroes2, DevilutionX and the N64 ports make users supply their own legally obtained data. OpenTTD went further and replaced all original assets with free ones.
- **Clean hands.** ZeldaRET only accepts contributors who have never accessed leaked Nintendo source. Wine forbids disassembling Microsoft code, using leaked source, and LLM-generated code. ReactOS's 2006 audit froze development after a single allegation.
- **Clean room means separation.** One person studies behaviour and writes a spec; another implements from the spec.
- **What got projects shut down.** yuzu (settled for $2.4M in March 2024, taking Citra with it) and Ryujinx (October 2024) ended over DMCA anti-circumvention and piracy-facilitation claims: key handling, guides, and paid early access during a leak. Emulation itself was not ruled illegal. Dolphin's Steam release was blocked by a Wii encryption key in its source, not by a court ruling.
- **Rights holders can change the deal.** OpenTTD's 2026 agreement with Atari shows that even a long-tolerated, asset-free project depends on the rights holder's goodwill.
- **AI-assisted contributions.** Wine refuses LLM-generated code; ScummVM requires disclosure and full human responsibility. Check a project's policy before contributing generated code.
- **For STAR users making Roblox games:** recreating mechanics is different from copying code, art, music or trademarks. STAR declines DRM circumvention, piracy, cheats, and Roblox exploits or any work that defeats anti-cheat.

## Roblox and Luau takeaways

- Before refactoring an inherited game, capture its behaviour with characterization tests (the oracle), then change one module at a time (`eng-legacy-archaeology`).
- Run round simulations in fixed server ticks with their own `Random.new(seed)`; log player actions with tick numbers; hash state for replay tests.
- Route every state change through validated server-side actions.
- Version every DataStore record and migrate on load; test migrations on copied records in a test place.
- Keep tuning data in ModuleScript tables (data-driven rules) rather than scattered constants.

## Known gaps

- Several primary sites blocked automated fetching (dolphin-emu.org, fifo.ci, rpcs3.net and its wiki, winehq.org/news, decomp.me, Phoronix, the OpenMW and ScummVM wikis). Claims resting on search summaries or secondary sources are marked "unverified" in the notes.
- Legal details of the yuzu complaint come from press summaries, not the filing itself.
- The OpenTTD Atari purchase date rests on a blog post. The terms of the agreement are not public.
- The 2026 state of the Switch-emulator forks and of Asahi GPU support on M3 hardware is unverified.
- Engine internals (game loop, RNG, save layout) for the N64 decomps were not covered by the fetched sources.
