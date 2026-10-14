# fheroes2 — reverse-engineering case study (researched 2026-10-13)

fheroes2 is a GPL-2.0 C++ engine written from scratch to recreate Heroes of Might and Magic II (1996, New World Computing / 3DO). It needs the original game data, or the free official demo, to run. It shows how to reproduce original behaviour from asset formats and observation, how to fence off "improvements" from balance-critical rules, and how to keep a small volunteer team shipping monthly with heavy static analysis.

## 1. What it is and its 2026 state
- Licence: GPL-2.0 (Time Extension adds "or any later version"). The language is C++ on SDL. The repo has build folders for desktop, Android, iOS, Emscripten, Switch and PS Vita.
- As of 2026-10-13 the latest release is **1.1.17 (30 June 2026)**. Its highlights are an initial "Auto Playtest" feature for the map editor, AI improvements and rendering optimisations. 1.1.16 (17 May 2026) and 1.1.15 (12 Apr 2026) came before it. Version 1.0.0 shipped 21 Dec 2022 (changelog).
- Activity as of 2026-10-13: about 6k commits and about 3.5k stars.
- History: the original "Free Heroes 2" by Andrey Afletdinov was registered on SourceForge on 9 Dec 2003 and last updated there in Jan 2018. The current "Resurrection" effort is led by Ihar Hubchyk (GitHub: ihhub). Time Extension says an alpha was being shown to new contributors by late 2019.

## 2. How the original was reversed
- The project describes itself as written "from scratch". Its FAQ says the original files are never modified and contrasts the project with mods, which it calls "reverse-engineered modifications of existing games". No public statement about disassembling the executable was found (unverified either way).
- **Format reversing is documented.** Assets come from the original `HEROES2.AGG` archive and related data. The wiki page "Bin file structure" maps the 821-byte per-monster animation `.bin` files field by field: eye position, movement offsets, idle probabilities and delays, walk, shoot and fly speeds, projectile angles, and frame sequences for 34 animation sections. The page is marked incomplete, with question-marked fields, which shows that the reversing was incremental and community-sourced.
- **Behaviour is matched by comparison with the original.** Recent changelog entries tune values to classic H2, such as fade-animation delay, experience and loss calculations, and scouting radius. The team also explicitly fixes bugs present in the original.

## 3. Workflow: matching, non-matching or clean-room
- The approach is a non-matching, black-box-style recreation. Fidelity is judged by observable behaviour and data, not by code parity.
- **Governance fences off balance.** The "Beyond 1.0" wiki page forbids changing monster and building stats, monster behaviour, and existing spell, move and animation logic without strong justification and a balance analysis. New content, such as new monsters, spells or events, is welcome. Features need majority team approval.
- Original HoMM II save files are not supported (FAQ). The engine uses its own save format.

## 4. Testing and verification
- **CI workflows** (as of 2026-10-13, inferred from file names): per-platform builds (MSVC, CMake, Make, Android, iOS), clang-tidy (with PR comments), CodeChecker, include-what-you-use, SonarCloud, a code-style check and translation updates. Heavy static analysis stands in for the large automated test suite that a deterministic engine like OpenTTD's has; no unit-test harness was confirmed (unverified).
- The editor's new **Auto Playtest** (1.1.17) is a step towards automated gameplay verification of maps. Its depth was not verified.
- Much verification is human: Time Extension describes contributors joining as testers and bug hunters, and the team compares against the original game's behaviour.

## 5. Structuring a large legacy codebase
- The team inherited a 2000s-era codebase and modernised it incrementally under strict tooling (clang-format, clang-tidy, IWYU, SonarCloud), not through a rewrite.
- **Save-format versioning** (`save_format_version.h`, described in my own words):
  - Versions form a monotonically increasing list of 16-bit numbers named after the releases that introduced them.
  - A "current" marker and a "minimum supported" marker bound what the loader accepts.
  - Comments require developers to move those markers when they add or retire versions.
  - Old save versions are deliberately pruned, so compatibility is a window, not forever.
- **New map format**: the editor introduced an `fh2m` map format (base code added in 1.0.8–1.0.11 in 2023, language support in 1.1.3 in 2024). The original `MP2` maps remain loadable (MP2 support assumed from gameplay, not verified in docs).
- The wiki includes "Adding a new option into the game" and "Code style" pages, which are lightweight contributor process docs.

## 6. Engine architecture insights
- The game is turn-based, so it needs no tick-level lockstep. The "Network architecture design" wiki page (last edited May 2022) notes that the game is "not a real time game". Its plan is:
  - an asio-based TCP layer (done);
  - a handshake and message system with a small binary header (`fh2`, type, size, big-endian);
  - a version check in the handshake;
  - mandatory encryption "to prevent cheating".
  Only the first two stages had status labels, so network multiplayer was still not shipped as of that page (unverified for 2026).
- Rendering was modernised to high resolutions and a larger view while reusing original sprites. The project has no dedicated artist and prefers reusing existing assets.
- The AI was rewritten and described as "superior to the original" (Time Extension). Most 1.1.x releases list AI changes, which makes the AI the main area of ongoing engineering.

## 7. Legal history and lessons
- The team states that all rights to the original game and its resources belong to the former 3DO Company, with those rights since passed to Ubisoft. The repo says it does "not encourage and do[es] not support any form of illegal usage".
- **Asset policy**: users copy `ANIM`, `DATA`, `MAPS` and `MUSIC` from their own copy. The team recommends GOG or the Ubisoft Store. Bundled scripts fetch the free official demo or extract a purchased GOG installer with innoextract. Gentoo's package asks users to accept the GOG EULA or demo licence.
- No takedown or dispute was found as of 2026-10-13 (unverified).
- Lesson: the legally free demo serves as a zero-cost on-ramp, and the rights holder's store gets an explicit recommendation.

## 8. Transferable lessons for STAR
1. **Write a balance-freeze policy.** Separate "fidelity rules" (stats, damage formulas) from "additive content" in a Roblox game's design docs and data tables. STAR should warn when an edit touches frozen tables.
2. **Turn-based needs no lockstep, only authority.** For Roblox turn-based or card games, keep the server as the single source of truth and send validated moves. Avoid simulating on clients. The fheroes2 network design document reasons this way.
3. **Bounded save compatibility.** Keep DataStore schema versions in one module with `CURRENT` and `MIN_SUPPORTED` constants and an enforced rule to update both. Migrate anything at or above `MIN_SUPPORTED` and reject anything older with a clear message.
4. **Document formats as field tables.** When STAR reverse-documents a user's own data (place files, legacy module tables), produce field-by-field tables with "?" for unknowns, like the `.bin` page, instead of guessing.
5. **Use static analysis as a safety net.** fheroes2 leans on clang-tidy, SonarCloud and IWYU in CI. The Luau equivalent is `--!strict`, Selene and StyLua on every PR, which is cheap and catches regressions in a small team.

## Sources
- https://github.com/ihhub/fheroes2 — repository README (licence, data requirement, platforms)
- https://github.com/ihhub/fheroes2/releases — 1.1.15–1.1.17 release notes
- https://raw.githubusercontent.com/ihhub/fheroes2/master/changelog.txt — dated changelog, 1.0.0 date, fidelity fixes
- https://raw.githubusercontent.com/ihhub/fheroes2/master/docs/INSTALL.md — required data folders, demo scripts, innoextract
- https://github.com/ihhub/fheroes2/blob/master/docs/README.md — rights statement (3DO to Ubisoft)
- https://github.com/ihhub/fheroes2/wiki/Bin-file-structure — documented monster animation format
- https://github.com/ihhub/fheroes2/wiki/Beyond-1.0 — balance and feature governance
- https://github.com/ihhub/fheroes2/wiki/Network-architecture-design — turn-based networking plan
- https://github.com/ihhub/fheroes2/wiki/F.A.Q. — from scratch, no original saves
- https://raw.githubusercontent.com/ihhub/fheroes2/master/src/fheroes2/system/save_format_version.h — save versioning scheme (read, not copied)
- https://github.com/ihhub/fheroes2/tree/master/.github/workflows — CI workflow list
- https://sourceforge.net/projects/fheroes2/ — original SourceForge project (2003)
- https://www.timeextension.com/features/how-fans-are-resurrecting-heroes-of-might-and-magic-ii — team and revival history
