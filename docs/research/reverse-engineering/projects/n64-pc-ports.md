# N64 PC ports on decomps and recompilation (Ship of Harkinian, sm64ex, Zelda 64: Recompiled) — reverse-engineering case study (researched 2026-10-13)

Matching decomps made a second wave possible: native PC ports. Some are built from decompiled C on a reimplemented N64 SDK, like Ship of Harkinian on libultraship and the sm64-port / sm64ex / Render96 family. Others statically recompile the original MIPS binary to C, like N64Recomp and Zelda 64: Recompiled. All of them use "bring your own ROM": assets are extracted locally into an archive (`.otr`/`.o2r`) or read straight from the user's ROM, and are never redistributed.

## 1. What it is and its 2026 state

- **Ship of Harkinian (SoH).** HarbourMasters' Ocarina of Time port. Development began after the OoT decomp finished in November 2021. Windows shipped on 2022-03-22, followed by Linux, macOS, Wii U and Switch builds. The latest stable release listed is 9.2.3 (2026-04-14) (Wikipedia, as of 2026-10-13).
- **More HarbourMasters ports on libultraship (LUS).** 2Ship2Harkinian (Majora's Mask, 2024-05-26), StarShip (Star Fox 64, December 2024), SpaghettiKart (Mario Kart 64, June 2025) and Ghostship (Super Mario 64, January 2026). Wikipedia also lists Lighthouse (Banjo-Kazooie, July 2026) and Paperboat (Paper Mario, September 2026), and a June 2026 plan to extend LUS to GameCube with Twilight Princess. These later items come from a single source (unverified elsewhere).
- **SM64 family.** sm64-port forked the n64decomp tree and added native Linux and Windows builds. sm64ex forked that and added options menus, texture and soundbank loading, analog camera, and GL/D3D11/D3D12 renderers from "n64-fast3d-engine". Render96ex is the Render96 team's fork that adds model and HD texture packs.
- **Zelda 64: Recompiled.** A Majora's Mask PC port released in May 2024 (Time Extension, 2024-05-13). It is built on Mr-Wiseguy's N64Recomp and renders through RT64. It runs at monitor refresh rate, supports any aspect ratio, and loads mods via Thunderstore. It accepts only the US N64 ROM. OoT support is listed as planned.

## 2. How the original was reversed

- **Decomp-based ports** reuse the matching C source from n64decomp/sm64 and zeldaret/oot and mm, compiled in `NON_MATCHING`/`AVOID_UB` mode for PC. libultraship "mimics the functionality" of libultra (the N64 SDK) on modern hardware. It handles windowing, input and audio through SDL3, and renders through a Fast3D display-list interpreter with OpenGL, Metal and DirectX backends.
- **How static recompilation works (N64Recomp).**
  - An ELF from a decomp or disassembly supplies symbols, which are used to split the ROM into functions.
  - Each MIPS instruction is translated literally into C operating on a register context. `jal` becomes a call, branch delay slots are duplicated, and jump tables become `switch` statements.
  - Indirect calls go through a runtime lookup so that relocatable overlays work.
  - RSP microcode can be recompiled too, though RSP overlays cannot yet.
  - A TOML file lists stubs, skipped functions and single-instruction patches.
  - The README says it was tested mostly on IDO and gcc 2.7.2 output.
- **Recomp versus decomp.** Recompiled output is not human-readable ("none of the data is 'readable'", Time Extension). Zelda 64: Recompiled uses headers and some functions from the MM decomp to write patches and enhancements.

## 3. Workflow: matching, non-matching or clean-room

- **The ports do not match the original.** They deliberately diverge with widescreen, high frame rate, randomizers and mods. The matching upstream decomp stays the reference for original behavior.
- **Recomp keeps original semantics** by construction and patches individual functions. Its single-file output mode lets patched functions replace originals at link time.
- **Not clean-room.** All of them depend on reverse-engineered code. The projects avoid assets, not knowledge of the code.

## 4. Testing and verification

- **ROM identity is checked up front.** SoH and 2Ship verify the user's dump against SHA-1 lists in `docs/supportedHashes.json` and offer web checkers (ship.equipment, 2ship.equipment). Zelda 64: Recompiled rejects anything other than the US ROM, converting byte-swapped formats automatically.
- **Staged releases.** SoH offers nightly playtest builds that may crash. sm64ex lands features on `nightly` before `master`.
- **Recomp correctness** rests on literal translation plus the original binary. Frame-rate changes are claimed to have "no effect on gameplay" (README claim, not independently verified).

## 5. Structuring a large legacy codebase

- **Shared platform layer.** Game repos (Shipwright, 2ship2harkinian) carry the decomp tree plus submodules for libultraship, ZAPDTR (HarbourMasters' copy of ZeldaRET's XML-driven ZAPD extractor) and OTRExporter (scripts named `extract_baserom.py`, `extract_assets.py` and `rom_chooser.py`). One LUS engine is shared by every port.
- **How "bring your own ROM" works, conceptually.**
  1. The user supplies a ROM, which is hash-checked.
  2. A ZAPD-style extractor, driven by per-version XML manifests, reads each asset: textures, display lists, animations, scenes and audio.
  3. An exporter serializes them into a resource archive, `oot.o2r`. LUS supports `.otr` (MPQ-compatible) and `.o2r` (ZIP-compatible) formats.
  4. At runtime a resource manager loads resources by path.
  5. Mods are additional `.otr`/`.o2r` archives in a `mods` folder that override paths. Data changes therefore need no new executable.
- **sm64ex** similarly loads textures and soundbanks externally, and offers `--clean`/`distclean` targets that strip all ROM-derived files from the tree.

## 6. Engine architecture insights

- **Display lists are the portability seam.** The games emit N64 GBI display lists. Ports replace the RSP/RDP with a renderer that interprets them (Fast3D in LUS, RT64 for recomp). Widescreen and high frame rates are delivered by the renderer and port layer. The exact interpolation technique was not covered in the fetched sources.
- **Save formats.** sm64ex supports little- and big-endian saves and an optional text save format. SoH saves under `~/.local/share/soh/` on Linux. Both show the original binary save layout being wrapped rather than redesigned.
- **Overlays.** Overlays need explicit runtime support in recompilation (relocation macros and function lookup), Decomp ports compile the overlay C directly, so their overlay handling is simpler (my inference, not checked against the Shipwright source).

## 7. Legal history and lessons

- **May 2020.** Nintendo's lawyers (Wildwood Law Group) filed complaints against download links for the compiled SM64 PC port executable and against YouTube videos, calling it "an unauthorized derivative work" (Nintendo Life). Time Extension in 2026 still describes that port as one Nintendo "tried to scrub from the internet".
- **Since then.** The ports ship source plus asset-free binaries. "The Ship does not include any copyrighted assets" and "we do not condone piracy" (SoH README). Zelda 64: Recompiled states its releases contain no game assets.
- **No public Nintendo action found.** I found none against SoH as of 2026-10-13, though press calls its legality "murky" (Kotaku via Wikipedia). HarbourMasters encourages users to buy official releases.
- **Side note (September 2026).** HarbourMasters faced criticism for undisclosed generative-AI use (Wikipedia). By contrast, the Zelda 64: Recompiled README bans contributions made with generative AI.

## 8. Transferable lessons for STAR

1. **Keep the engine separate from the content and connect them through a resource manager.** In Roblox, gameplay modules should load content (tuning tables, asset IDs, localization) through one loader with override layers: a base pack plus mod or test packs. Live tuning then never needs a code change.
2. **Validate inputs by hash before you start.** Port launchers refuse unknown ROMs. STAR should fingerprint a user's place file or Rojo project version and refuse automated edits on unrecognized layouts.
3. **Wrap the platform, not the game.** LUS reimplements the SDK API so game code barely changes. For Roblox, wrap engine services (DataStoreService, MessagingService, MarketplaceService) behind thin adapters so systems can be unit-tested with fakes and migrated when APIs change.
4. **Keep a faithful upstream.** Keep a canonical template, and have each game or experiment fork pull from it regularly.
5. **Translate literally first, enhance later.** Recomp gets correct behavior first and adds features through patches. When porting legacy Roblox scripts to strict Luau, do a literal, behavior-identical conversion with tests before any redesign.
6. **Distribute only what you own, and say how it was made.** Ship code and tooling, never third-party or ROM-derived assets. Given the SoH controversy, also state your AI-assistance policy in the README.

## Sources

- [HarbourMasters/Shipwright README](https://github.com/HarbourMasters/Shipwright)
- [HarbourMasters/2ship2harkinian README](https://github.com/HarbourMasters/2ship2harkinian)
- [Kenix3/libultraship README](https://github.com/Kenix3/libultraship)
- [HarbourMasters/OTRExporter repo](https://github.com/HarbourMasters/OTRExporter)
- [HarbourMasters/ZAPDTR repo](https://github.com/HarbourMasters/ZAPDTR)
- [N64Recomp README](https://github.com/N64Recomp/N64Recomp)
- [Zelda64Recomp README](https://github.com/Zelda64Recomp/Zelda64Recomp)
- [sm64-port README](https://github.com/sm64-port/sm64-port)
- [sm64pc/sm64ex README](https://github.com/sm64pc/sm64ex)
- [Render96/Render96ex README](https://github.com/Render96/Render96ex)
- [Wikipedia: Ship of Harkinian](https://en.wikipedia.org/wiki/Ship_of_Harkinian)
- [Time Extension: N64Recomp (2024-05-13)](https://www.timeextension.com/news/2024/05/new-tool-allows-n64-games-to-be-played-with-ray-tracing-uncapped-frame-rates-and-ultrawide-support)
- [Time Extension: Ghostship (2026-01-19)](https://www.timeextension.com/news/2026/01/super-mario-64-has-got-another-fanmade-pc-port-from-the-harbour-masters-team)
- [Nintendo Life: SM64 PC port crackdown (2020-05-09)](https://www.nintendolife.com/news/2020/05/nintendo_cracks_down_on_the_super_mario_64_pc_port)
