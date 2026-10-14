# OpenTTD — reverse-engineering case study (researched 2026-10-13)

OpenTTD began in 2003–04 as a disassembly-derived C conversion of Chris Sawyer's assembly-language Transport Tycoon Deluxe (TTD). Twenty years of incremental rewriting turned it into a GPL-2.0 C++ codebase with its own free graphics, sound and music, so it no longer needs any original data. It is the most mature example of moving "from disassembly to an original codebase". The project also shows that a rights holder can reappear decades later.

## 1. What it is and its 2026 state
- Licence: GPL-2.0-only. Some bundled third-party components carry other licences. As of 2026-10-13 the repo shows about 33.2k commits on master and about 8.4k stars.
- As of 2026-10-13 the official site lists stable **15.3**, testing **16.0-beta4** (20 Sep 2026; a hotfix for a multiplayer desync introduced in beta3) and nightly 20261005. Wikipedia dates 15.3 to 4 April 2026.
- Multiplayer supports up to 255 players across 15 companies. It also has user-made AIs (since 0.7.0) and GameScripts (since 1.2.0), both written in Squirrel.
- Distribution: free on openttd.org and in package managers, and on Steam, GOG and the Microsoft Store. Since March 2026, Steam and GOG access for new players is tied to buying Atari's re-release of TTD (see §7).

## 2. How the original was reversed
- TTD (1995) was written "directly in x86 Assembly language" (OpenTTD wiki history page). TTDPatch had already been extending the closed binary by patching it.
- In 2003 Ludvig "ludde" Strigeus began turning the compiled binary into C. The archived wiki history says he used IDA Pro to study the x86 logic, data structures and state machines. Version 0.1.0 shipped in March 2004; the wiki says 14 March and Wikipedia says 6 March.
- Early work restructured the code for readability and restored sound and music. Wikipedia says the codebase "has been gradually rewritten in C++ since 2007".
- The original graphics, sounds and music were initially loaded from the user's TTD CD. Community sets replaced them: OpenGFX, OpenSFX and OpenMSX. Version 1.0.0 (1 April 2010) made them the default, so the game could ship standalone (wiki history page).

## 3. Workflow: matching, non-matching or clean-room
- The work was non-matching and disassembly-derived, not clean-room. A 2004 Wikipedia talk-page comment already questioned the legality on those grounds. Over time the code was refactored and rewritten beyond recognition. The project wiki says the engine was "rewritten", but no maintainer statement was found that quantifies how much disassembly-derived logic remains (unverified).
- Once the code was independent, fidelity to TTD became a design choice, not a constraint. The README says it aims to "closely mimic" the original while adding features.

## 4. Testing and verification
- **Desync tooling** (`docs/desync.md`):
  - Launching with `-d desync=2` recomputes every cache each tick and logs any mismatch. This catches stale-cache bugs even in single-player.
  - `desync=2` and `desync=3` log every command to `commands-out.log`. `desync=3` also writes periodic `dmp_cmds_*.sav` snapshots.
  - A debug build can replay a command log against the start savegame and hit `NOT_REACHED` on a checksum mismatch.
  - You bisect by replaying from successively later snapshots. Two saves can be exported to JSON with a savegame reader tool and diffed.
- The repository contains a `regression` folder (AI/script API regression) and bundles Catch2 for unit tests (seen in the tree; run details not verified).
- The README promises that every revision can load saves from older revisions. That gives an implicit backward-compatibility test target.

## 5. Structuring a large legacy codebase
- The migration was gradual: C first, then C++ from 2007, with no big-bang rewrite. Free asset sets were built in parallel, so legal independence arrived step by step.
- **Extension layers, each with a clear boundary:**
  - **NewGRF** for content (vehicles, industries, graphics).
  - **NoAI** Squirrel AIs. Each AI plays one company.
  - **GameScript (NoGo)** Squirrel scripts. These own no company and can set goals, message players and alter towns or industries.
  - Scripts are distributed through the BaNaNaS content service. They save their own data into dedicated savegame chunks (`AIPL`, `GSDT`).
- **Savegame format** (`docs/savegame_format.md`):
  - A 4-byte tag names the compression (none, zlib or LZMA; LZO is deprecated), followed by a 16-bit savegame version.
  - The body is a sequence of chunks with 4-letter tags such as `PLYR`.
  - Since version 295, "Table" chunks carry a self-describing header with field names and types, so readers can skip unknown fields.
  - Patch packs are told to prefix their custom fields with `__<shortname>`, which lets vanilla builds ignore them.

## 6. Engine architecture insights
- **Deterministic lockstep** (`docs/desync.md`):
  - A joining client receives a full savegame.
  - After that, only non-predictable inputs travel over the network: commands from players, AIs, GameScripts, the admin port and rcon. The server also sends "advance to frame N" signals.
  - A command first runs locally in test mode. The server then queues it with a frame number, and every client executes it in the same frame and order.
  - The server periodically sends its RNG state as a checksum. Because the RNG is the checksum, divergence is detected only once it has spread to the RNG, often long after it began.
- **Documented desync causes:**
  - incomplete save or load, or state not reset before a load;
  - stale caches;
  - undefined ordering, such as sorting items with equal keys;
  - 32/64-bit or endianness differences;
  - a command's test run mutating state;
  - state changed outside the command system.
- These rules are a portable checklist for any lockstep simulation.

## 7. Legal history and lessons
- For years OpenTTD existed in a grey zone: disassembly-derived and tolerated, with no active rights holder. Free base sets removed any need for proprietary assets.
- Atari SA bought the Transport Tycoon rights in 2024 (per a rubenwardy blog post; not verified from a primary source) and re-released TTD on Steam and GOG in March 2026. OpenTTD's 2026-03-19 post says Atari approached the team and a compromise was agreed. On those stores, new players must first buy TTD. Existing owners and the free website downloads are unaffected, and Atari agreed to contribute to server costs. The team states that Atari did not pressure it and the project "retains its full independence".
- Critics argued that implicit legal leverage remained and asked whether the permission is irrevocable; its terms are not public (rubenwardy blog).
- Lesson: shipping without proprietary assets is necessary but not sufficient. A disassembly-derived codebase stays exposed to a revived rights holder. Negotiating openly preserved the project.

## 8. Transferable lessons for STAR
1. **Commands as the only mutation path, with test-then-execute.** In Luau, every server action should run a pure `validate()` that never mutates state, then an `apply()`. OpenTTD's rule that a test run must not change state maps directly to RemoteEvent handlers.
2. **Ship a desync and cache checklist.** Teach STAR to flag four things in Roblox simulation code: `pairs()` iteration order used for gameplay decisions, unseeded `math.random`, client-only values feeding server logic, and stale caches. OpenTTD's list is a ready rubric.
3. **A cache-validation debug mode.** Add a flag that recomputes derived state every tick and asserts it equals the cached value. This is cheap to build in Luau and catches whole classes of bugs.
4. **Self-describing save tables.** Store DataStore profiles as named fields with a `version`. Readers should ignore unknown keys, and experimental fields should get a namespace prefix. Never rely on positional arrays.
5. **Command logs plus snapshot bisection.** Log server actions with tick numbers and snapshot state periodically, then replay to bisect regressions. That works for Roblox bug reports too.

## Sources
- https://github.com/OpenTTD/OpenTTD — repository README (licence, base sets, save compatibility)
- https://en.wikipedia.org/wiki/OpenTTD — history, C++ transition, versions, Atari note
- https://www.openttd.org/news/ — release news (15.3, 16.0 betas)
- https://www.openttd.org/news/2026/03/19/steam-changes-update — official statement on the Atari agreement
- https://blog.rubenwardy.com/2026/03/17/openttd-ttd-release/ — critical analysis of the Atari arrangement
- https://wiki.openttd.org/en/Archive/OpenTTD/OpenTTD%20History — origin via IDA Pro, free asset sets, 1.0.0
- https://raw.githubusercontent.com/OpenTTD/OpenTTD/master/docs/desync.md — lockstep model and desync debugging
- https://raw.githubusercontent.com/OpenTTD/OpenTTD/master/docs/savegame_format.md — chunked, versioned save format
- https://wiki.openttd.org/en/Manual/Game%20script — GameScript (NoGo)
- https://wiki.openttd.org/en/Development/Script/ — NoAI Squirrel AIs
