# STAR CLIP THAT — Recorder Interoperability, Creator Skills, Recompilation & Game Lab

**Research date:** October 15, 2026. **Status:** implemented pilot behind two independent draft PRs; not merged, released, or Windows hardware-verified.

**Scope:** This is a repository-grounded engineering plan. STAR is an experimental local-first desktop assistant, not a verified general-purpose console porting suite or a full Medal clone. Do not turn research pages, community code, screenshots, downloaded skills, or AI prose into code-execution permissions.

- Base pilot: [#427](https://github.com/oncoursemail/Star-AI/pull/427) (OBS replay controls + deterministic companion event contract; draft).
- This follow-on branch: **local clip file browser, SteelSeries GG Moments developer-event prototype, Game Lab source catalog.** It is stacked on #427; merging this branch without #427's base requires deliberate conflict review and correct retargeting.
- Owner's original approved STAR character artwork stays unchanged. No external waifu screenshot is uploaded to this public repo.
- No game processes were hooked or launched; no video/audio was captured or uploaded by the development process.

## 1. Goal and system boundary

One command, several honest outcomes:

> "STAR, clip that!" / "STAR, clip that shit!"

| Backend | Can STAR issue a capture/save command through a documented channel? | Current support / gate |
|---|---|---|
| OBS Studio 28+ | Yes, authenticated OBS WebSocket v5 replay buffer | **Draft #427** manual Connect/Start/Save/Stop. OBS must be installed, connected, running, properly set up and native tested. |
| SteelSeries GG Moments | Yes, **for developer-owned games**, via local GameSense rule registration + event trigger | This draft: status/register/trigger test-event. No verified captured file and no third-party-game control. |
| Medal | Yes for **approved game developers**, via Medal auto-clipping developer event protocol; separately imports external recorder files | Research/design only; an arbitrary local app cannot claim Medal's developer API for all games. |
| Outplayed | Uses Overwolf-supported games/events and its own capture modes; Overwolf has replay APIs **inside its application environment** | STAR can index the owner's local video exports. A true direct adapter requires an approved Overwolf app integration. |
| NVIDIA Instant Replay / ShadowPlay | Has user-facing hotkeys and local files | STAR can index clips from the chosen folder. No verified universal third-party control API. |
| AMD ReLive / Adrenalin | Similar user-facing capture and local files | Directory-based interoperability, not third-party capture claims. |
| RePlays / better-outplayed / WatchDog | Open-source recorder references | STAR can index their local videos. Deep native integration depends on audited API/license and hardware testing. |
| Any recorder exporting ordinary videos | Yes, **read-only local folder browsing** | This draft: user-selected folder, video metadata only, open an indexed video in OS player. No auto-delete, upload or copying. |

Sources:
- Medal official developer events: https://medal.tv/developer/auto-clipping
- Medal importing external recorder clips (OBS, ShadowPlay, ReLive): https://support.medal.tv/support/solutions/articles/48001210933/
- SteelSeries GameSense Moments event contract: https://github.com/SteelSeries/gamesense-sdk/blob/master/doc/api/sending-moments-events.md
- SteelSeries GameSense server discovery: https://github.com/SteelSeries/gamesense-sdk/blob/master/doc/api/sending-game-events.md
- Overwolf replay capture API: https://dev.overwolf.com/ow-native/reference/media/replays/
- Overwolf game developer events SDK: https://dev.overwolf.com/ow-native/live-game-data-gep/events-sdk-for-game-developers/
- Outplayed capture mode limitations: https://support.overwolf.com/support/solutions/articles/9000284659-how-to-use-outplayed
- OBS: https://obsproject.com/kb/remote-control-guide and https://github.com/obsproject/obs-websocket

### Why use multiple backends?

Most gamers already have a preferred recorder. STAR should act as **a privacy-preserving command router and creator assistant**, not force users to replace all capture software. A single button or local keyword routes only to supported, configured adapters. Native hooks, UI automation mimicking undocumented shortcuts, remote control ports exposed outside loopback, and unapproved authentication workarounds are **not** a valid default.

The command must return typed evidence:

```text
ClipRequest {
  provider: obs | steelseries_developer | medal_approved_developer | future_native
  game: observed | user_selected | unknown
  event_source: hotkey | authorized_voice | official_game_event
  started_at, requested_pre_seconds, requested_post_seconds
  state: queued | requested | accepted | saved_verified | failed
  file_path?: only after explicit local file verification
  evidence?: request id / source status / OS filename
}
```

A successful API response is **only accepted/requested**, not `saved_verified`. STAR must verify the actual file exists, is nonzero, is stable after output and is playable, with a duration/audio sanity check. Never fabricate kill events, model successes or clips.

### Actual changes in this pull request

**`star/clip_library.py`**: The owner chooses a folder through Qt. STAR visits only a limited two-level directory tree, skips symlinks, caps entries/results, indexes supported local video extensions and returns filenames, relative paths, byte sizes and modification time only. Opening uses a previously indexed ID, not an arbitrary model/user-supplied path. The selected scope is in memory only. It does not copy, transcode, delete, monitor or upload videos.

**`star/steelseries_moments.py`**: Reads the local `coreProps.json` for GameSense address, validates literal `127.0.0.1` and nonprivileged port, disables proxy forwarding and redirects, sends fixed `register_autoclip_rules` and `autoclip` payloads only for a human-confirmed `STAR_...` development game, and labels response as event acceptance only. No secret/payload from arbitrary game, no background event listening.

**`star/game_lab_catalog.py`**: static curated links and metadata; statuses `pilot_in_pr`, `research_only`, `archived`. No downloader, skill runner, installation system, network request or arbitrary URL control.

**Qt + React**: Existing Tools page gets the explicit Clip Interoperability panel and collapsed Game Lab directory. All backend actions use the restricted Qt allowlist and (for I/O) workers. Both integrations are unavailable on the static public website preview.

Tests: read-only catalog integrity, video symlink/path boundary/revocation/caps, fake GameSense registration and explicit authorization, existing backend and frontend regression suites. **A passing fake proves a contract, not that SteelSeries saved an actual clip.**

### Next steps to reach actual Medal parity

1. Per-recorder capability negotiation; don't show Start/Save buttons for providers lacking a documented API.
2. Optional global hotkey with shortcut-conflict detection and opt-in local push-to-talk/wake phrase (voice never accepted from game/chat/LLM text).
3. Native Windows Graphics Capture + WASAPI + hardware encoder + crash-safe compressed GOP ring buffer; quota and audio/overlay exclusion.
4. Clip Library SQLite index, thumbnails, player, trim, crop, captions, game sessions, searchable metadata; only owner-approved export and sharing.
5. Explicit platform-specific game event SDK bridges and per-title replay-event precision/recall benchmarks.
6. Creator workflows: Discord/Twitch/YouTube; confirm channel/account/audience/media before upload, never scrape logged-in cookies.
7. GPU/CPU/FPS acceptance on Windows + games: 1080p60, 1440p60, dropped frame %, p95/p99 frame time, audio sync, max RAM/VRAM, disk fill behavior, DRM/anti-cheat compatibility without injection.

**No self-play or automatic gameplay capture is activated here.** User approval for recording is separate from mic input, event listeners, modding and external uploads.

## 2. Your game-dev skill sources

### `gamedev-skills/awesome-gamedev-agent-skills`

https://github.com/gamedev-skills/awesome-gamedev-agent-skills

Project README reports **74 Agent Skills and a router spanning 10 engines** (Godot, Unity, Unreal, Phaser, PixiJS, Three.js, Bevy, pygame, LÖVE and Roblox). Skills are `SKILL.md` documents with engine fingerprints and task routing; the workflow emphasizes coherent asset families, source-pinned engine versions, validation and in-engine visual review. Published under Apache-2.0 according to the project.

**STAR integration:** STAR already has `star/agent_skills.py`, `star/skill_packs/`, `star/skill_routing.py`, and reviewed engine packs. Do not wholesale install 74 new skills on every turn or execute `npx skills add` without human review. Instead:
- Snapshot versioned source metadata; run license/security check; import selected, approved **text** references into existing `SkillLibrary`.
- Precedence: STAR policy + engine's official docs > reviewed local skills > outside source text.
- Use the existing engine detector and topic router. Enforce **one authoritative engine per edit task**; genres/art/design/test skills can compose.
- Respect `SKILL.md` frontmatter limits, path boundaries and prompt-injection treatment as untrusted input.
- Held-out eval: Roblox/Unity/Godot/Unreal 30+ task routing, incorrect-engine false positives, quoted third-party instructions, no permission inflation, and answer quality before enabling.
- Generate art-direction specs, sprite atlases, 3D rigs, reference alignment and test results. A screenshot or an attractive sample is not proof of a working, editable scene.

The `gamedev-skills` GitHub organization currently centers this public repository: https://github.com/gamedev-skills .

### `rehan-remade/universal-modder`

https://github.com/rehan-remade/universal-modder

The README describes the ten-stage modding loop: retrieve knowledge → identify engine → sandbox/backup → read code → build small slice → create assets → verify in game → record → package → preserve verified lessons. It offers Agent Skills, a `um` CLI and optional fal/ComfyUI artwork/MCP integrations. Repository advertises MIT; **do not mistake licensing for sandbox safety**.

The `um_run`-style wrapper can invoke powerful local commands. STAR should **not** enable universal execution as an agent tool, run downloaded setup scripts, modify multiplayer clients, defeat anti-cheat or load unknown DLLs. Build a *review-and-plan* adapter first: source recognition, engine route, per-game rights checklist, isolated VM plan, backup path, known-good version/hash, planned test probes and human-reviewed patch artifacts. Later, allow a **fixed allowlist** of operations in an isolated, throwaway test environment, and record results. STAR's existing `star/reverse_engineering.py` already has bounded read-only analysis tools; extend them, don't bypass them.

Suggested workflows: GameMaker script/resource extraction for self-owned projects; Unity authorized mod pack inspector; Unreal asset-format exploration; Godot scene patch review; local single-player quality-of-life mods; open-source game reimplementation tests.

## 3. Reverse engineering, recompilation and decompilation sources

Distinguish four separate methods:

- **Static recompilation:** translate original machine instructions ahead of time into native code; requires kernel, graphics, IO, memory and title-specific shims. A compiled recompiler does not imply a runnable game.
- **Matching decompilation:** iteratively author C/C++ that compiles to original machine-code bytes with exact original toolchain. The scoring oracle is objective at the function/object level.
- **Clean-room reimplementation:** independently implement documented formats/protocols/behaviors with regression cases, not copied code or art.
- **Emulation/source port:** reproduce runtime hardware/API or compile available source for new platforms. Technically and legally distinct from static recompilation.

### Link-by-link findings

| Resource | What it actually offers | STAR use | Status/limits |
|---|---|---|---|
| https://github.com/SubmitGame/awesome-decomp-games | Generated catalog of matching decomp projects, static recomp, source ports, remakes, browser ports. Its 2026-10-15 README reports 2,093 projects for 1,862 games. | Source selection & metadata comparison | Catalog claim; per-project health, copyright and source must be independently verified. |
| https://github.com/omonkeyz/Fortnite-Rust | Pure-Rust tooling for pak and UE4 cooked `.uasset` analysis; not a proven full modern Fortnite replacement. Its README reports encrypted assets as errors rather than decrypting them. | Learn robust parsers, file-format fixtures, before/after asset-index diff | Research/owned older assets only; **no Fortnite DRM, encryption or anti-cheat bypass**. |
| https://recompiledgames.com/ | Broad index of browser/native fan ports; live page reported 52 projects and 38 links up at its last check. | Discover examples and compare actual runtime method | Site includes remakes and unknown methods: don't call all entries static recomps or verified safe. |
| https://github.com/sp00nznet/ps3recomp | PS3 Cell PPU/SPU static recompilation and HLE runtime. README differentiates library tests from actual games: game running demonstrated on Windows; no in-tree macOS/Linux title boots verified. | PPU/SPU/compiler/oracle practice plan with owned data | Experimental, title-specific integration and real graphics/audio verification required. |
| https://github.com/sp00nznet/xboxrecomp | Original Xbox XBE parser → disassembler → function/ABI analysis → generated C → HLE/runtime with D3D8, DirectSound and input bridges. | Reusable staged validation templates | Requires owned XBE/data and title-specific work; libraries alone don't make a playable game. Third-party LGPL components need review. |
| https://github.com/rexdex/recompiler | Historical Xbox 360 XEX static recompilation experiment, with demo apps and advanced GPU/CPU research. | Study legacy design and tracing/oracle techniques | README says real games weren't demonstrated; do not advertise turnkey Xbox 360 conversion. README filename is lowercase `readme.md`. |
| https://decomp.dev/ | Community matching decompilation progress reports and GitHub bot | Research project progress and existing matching baselines | Source: https://github.com/encounter/decomp.dev ; public site and supplied Wayback snapshot were inaccessible to this research client; no live API schema audited. |
| https://web.archive.org/web/20261013045303/https://decomp.dev/ | Oct 13 archived snapshot link provided by owner | Historical reference | Archived page was not retrievable in this session; **not verified**. |
| https://github.com/shibbo?tab=repositories | Nintendo GameCube/Wii/Switch modding/decompilation editors and toolchains (e.g., `Fushigi`, `aurora`, `3DWDecomp`, `swspl`) | Research level editors, container/asset parsers and compatibility wrappers | Each repo must be reviewed separately before any local execution or copying. |
| https://decomp.me/ | Volunteer-run collaborative scratchpad for matching **individual functions**. Identical assembly matching is the criterion; m2c drafts are only starting points. | Per-function compiler oracle workflow and expert collaboration | Not automatic whole-ROM decompilation. https://www.decomp.me/faq |
| https://github.com/i12bp8/decomp.wtf | AI-agent orchestration of function matching against original compilers, local MCP + multi-worker workflow | Read archived methods + reproducible tests only | **Archived/discontinued**. Author explicitly cites community opposition to AI decompilation and asks to respect opt-outs. **No automatic upstream AI contributions**. |
| https://osgameclones.com/ | Repository-backed catalog of open-source or source-available reimplementations | Prefer lawful reimplementations with tests and redistributable assets | Source dataset: https://github.com/opengaming/osgameclones ; individual content licenses differ. |
| https://xb.live/ | Original Xbox community services, stats, achievements, lobbies/events and documented API | Consent-based friend/lobby/status and research integrations | Service has login and private data; use officially permitted endpoints, not session interception/scraping. https://xb.live/ecosystem |
| https://github.com/Teraflopping/xrevive | Windows launcher for original Xbox statically recompiled titles plus xb.live-connected features | Launcher architecture, signed-update pattern, per-title runtime matrix | Windows x64 hosted executables; user supplies game data. Experimental, not universal Xbox/PS3 solution. |

### Further primary tools and examples to research

- **Ghidra:** https://github.com/NationalSecurityAgency/ghidra — STAR already includes a bounded wrapper. Use headless analysis only inside an owner-selected workspace with fixed scripts.
- **objdiff:** https://github.com/encounter/objdiff — assembly/object comparison and match oracle; useful for function-level verification.
- **decompals resources:** https://github.com/decompals/decompedia — community docs by console/toolchain.
- **N64Recomp:** https://github.com/N64Recomp/N64Recomp — well-documented static recompilation reference; not a universal compiler and game-specific metadata required.
- **GameCube/Wii original compiler bridges:** https://github.com/decompals/wibo — safely bounded toolchain compatibility.
- **Unreal official Remote Control:** https://dev.epicgames.com/documentation/en-us/unreal-engine/remote-control-quick-start-for-unreal-engine — powerful editor HTTP/WebSocket interface, beta, do not expose to public internet.
- **Unity Test Framework:** https://docs.unity.com/en-us/engine/6000.7/manual/programming-environment/test-framework-introduction/reference-command-line — supports batch-mode test reports; a passing script is not visual proof.
- **Godot command line:** https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html — headless project import/validation/tests on an isolated owner-selected project.
- **Roblox official Studio MCP:** https://create.roblox.com/docs/studio/mcp — separately scoped and verified in approved test places.
- **RenderDoc/Tracy/PIX:** evaluate graphics profiling for authorized applications with license/platform restrictions and no anti-cheat bypass. Avoid game injectors during protected online play.

### Why not automatically install every tool?

Projects can ship binaries, scripts, telemetry, dependencies, shader caches, exposed HTTP control endpoints, and instructions that ask for privileged PC access. An AI-agent tool catalog is *untrusted reference material*. Importing `SKILL.md` is not a permit to execute or overwrite game installs. For preservation, require the owner to affirm their legitimate input files and distribution rights, keep copyrighted executable/data out of STAR's public GitHub, and obtain separate approval before running a game's executable or third-party tool.

## 4. STAR game-dev research architecture

**Already present:** `star/game_projects.py` detects Godot/Unity/Unreal projects read-only; `star/engine_evidence.py` traces bounded links; `star/agent_skills.py` reads portable text skills; `star/skill_packs/` has reviewed engine and reverse-engineering methods; `star/reverse_engineering.py` has scoped read-only analysis and fixed external-tool recipes; `star/skill_routing.py` matches approved skill packs and falls back conservatively.

**Add next (review-gated):**

```text
Owner-selected project folder
  -> safe engine fingerprint + explicit version
  -> source/license/rights and compiler prerequisites report
  -> reviewed Agent Skills router (NOT raw untrusted instructions)
  -> one testable task with owner-approved edit scope
  -> static parser / compiler checks in isolated worker
  -> editor/Studio native run + screenshots + logs + checksums
  -> owner visual acceptance and correction
  -> optional clip/replay evidence + named CI artifacts
  -> proposed lesson (evidence attached), separate promotion gate
```

Do not let an agent auto-modify evaluators, acceptance gates, hidden PR branches or provenance metadata. Use per-engine licenses and SDK permissions, not a universal "AI can run anything" flag.

### Star Game Lab capability proposals

1. **Engine Fingerprint:** identify Roblox/Godot/Unity/Unreal/Bevy etc. from project files with bounded path traversal and exact version capture.
2. **SourceMap for game assets:** typed links between scenes, script classes, sprites, rigs, audio and VFX; no hallucinated unseen dependencies.
3. **Modding Planner:** select sanctioned editor/mod SDK and backup strategy; only analyze first.
4. **Recomp Preflight:** check architecture/ABI, imports, original compiler, module HLE coverage and owned content without executing it.
5. **Matching Oracle:** object-level byte comparison with original hashes in a quarantined local/private workspace; scores and skipped tests visible.
6. **Native Trial:** run only reviewed task manifests in VM/test hardware, collect logs, timings and crashes; never alter live multiplayer installation.
7. **Clip Proof:** after approved capture, link `ClipRequest` evidence to code/visual finding or bug regression, with timestamp and hash.
8. **Package Integrity:** build manifests, license checks, provenance, checksum, no redistribution of game data.
9. **Public Data Source Broker:** link curated sites/repositories with their current license and archived/stale state; no web page can grant a new permission.
10. **STAR Skill School:** learn from successful controlled experiments and human corrections, measure before/after performance on protected holdouts.

## 5. Living multi-AI companions: concrete animation integration

The owner has approved Star's original exact identity. Use `StarPet` / `StarFace` already in the repo. Draft #427 adds a **pure companion event director** but no new rigged character. Do not copy the TikTok orange-haired/purple-haired fan images into public release assets.

Implementation pipeline:
- Design original model/provider-themed chibi anime character packs with commissioned/editable source and attribution; distinguish decorative personas from actual vendor trademarks and endorsements.
- Rig with an editor/runtime selected after license audit: Rive `@rive-app/react-canvas` or Inochi2D. Rive runtime licensing is not necessarily the same as its content export pricing; Live2D SDK is separate.
- Expand true states: idle, blink, breathe, reading, thinking, typing, tool execution, speaking with visemes, errored, celebrate, sleepy and asleep, locomotion, walk/run/jump.
- Add relationship-free playful choreography: walk past each other, chase/tag, group high-five, surprised gaze, hide-and-seek. Optional user-controlled affection (hug/kiss) with distinct toggles, no surprise interruptions.
- Cat/dog modes must morph actual layered rig parts (attached ears, tails, face poses), not paste floating JPEG fragments.
- Subscribe to **actual provider/model/tool run events** using stable `actorId` and `runId`. No hallucinated speech, task status or feelings; no independent user message sending.
- Pause/play only when idle, sufficient layout space, never behind controls or covering the current code; observe reduced-motion, user preference, performance budget and clipping GPU priority.
- Required QA: 6-character interaction videos, 64/128/256px silhouettes, 2–3 angles, consistent costume/hands, sprite source review, true mouth/voice sync, Windows native FPS and CPU/GPU tests, owner approval.

**Priority:** Finish testable recording + workflow first, then character rig fidelity and event bridge; avoid impressive-looking placeholder creatures becoming permanent UI debt.

## 6. Other integrations that would materially improve STAR

| Category | Candidate integrations | Value & safe gate |
|---|---|---|
| Open-source recorder editing | RePlays, FFmpeg, LosslessCut, PySceneDetect, Auto-Editor | Read files chosen by owner; edits are generated as **new copies**; source and license reviewed |
| Streaming & creation | OBS streaming via WebSocket, Twitch EventSub, Discord bot, YouTube uploader | Distinct livestream/upload consent; OBS streaming switch never exposed to automatic model tool |
| Dev capture/profiling | RenderDoc, Tracy, perf/ETW, Nsight | Explicit authorisation, native executable compatibility, no multiplayer anti-cheat injection |
| Game engine editing | Roblox Studio MCP, Godot EditorPlugin, Unity Editor test runner, Unreal Remote Control | Per-project permissions, immutable baseline, native validation |
| Modding/build library | Nexus Mods, mod.io, Steam Workshop, GitHub Releases | Official API/auth, account scopes, signed package and malware/license checks; no raw install |
| Game library | Playnite, Steam Game Recording, PC game library metadata | Local export/official interfaces; no cookie scraping or unsupported process hooks |
| Community & retro | xb.live, RetroAchievements, LiveSplit and speedrun splits | Owner-approved public/profile data, documented API, privacy/minor safety |
| Music | Nuclear Music Player MCP | Optional control; avoid copyrighted music in uploaded gameplay clips |
| Asset production | Blender MCP, ComfyUI, Aseprite, Krita, SVG tooling | Editable source + rights/license evidence + deterministic exported asset checks |
| Build/collab | GitHub, CI test artifacts, selective Agent Skills | Draft PRs with evidence; never auto-merge or silently install new tools |

## 7. Tests and blockers

**Existing draft code is not a new public STAR release.** Success levels:
- Source committed: yes for the above backend/frontend pilots and reference catalog.
- Unit tests written: yes; CI outcome must be separately checked.
- Cross-provider native recording captured: **not yet verified**.
- Medal approved developer key: **not supplied; cannot claim this integration active**.
- SteelSeries Moments present and verified on the owner PC: **not yet tested**.
- Game engine/modding execution: **not enabled**; no game files accessed.
- Waifu rig packs: **research/contract stage**; no original provider character assets finalized.
- Windows installer with the integrations: **not published**.

Acceptance for a released feature is at least one playable sample video from a real Windows session plus UI state that shows the actual file, failed permissions rejected by tests, passing CI/packaged `STAR.exe --doctor`, and owner approval of rendered UI. Native benchmark results must show whether recording impacts game frame times.

### Licensing and rights

- `gamedev-skills`: Apache-2.0 per repository; `universal-modder`: MIT per repository, but scripts/third-party assets may have separate terms.
- `decomp.wtf`: MIT source but archived, with community AI contribution opt-out concerns.
- `ps3recomp`, `xboxrecomp`: MIT for their own code, with third-party components requiring separate review (e.g., LGPL xemu portions).
- `rexdex/recompiler`: inspect repository LICENSE before copying; do not conflate a public repo with unrestricted source redistribution.
- Metal/Medal/Outplayed/SteelSeries are brand and service names; no official endorsement is implied.
- Reverse engineering rights differ by jurisdiction. Owning a physical game does **not automatically authorize redistributing copyrighted source, art, music or decrypted assets**. The system must support legitimate interoperability, preservation of lawfully held files, and clean-room original work.

## 8. Concrete work-order

**M0 (this code review):** static reviewed source index + explicit cross-recorder local files + GG developer-event request tests + frontend types/coverage. No privileged tool additions.

**M1:** after review and merge, native Windows 11 machine with OBS and SteelSeries GG: prove real clip saved, media hash/duration/audio, file listing, restart/permission errors. Fix failures and inspect screenshot quality.

**M2:** real native recorder/hotkey/voice (when owner explicitly authorizes mic), after that independent auto-highlights in specifically documented supported games.

**M3:** game-engine skill import with explicit per-skill review, source pinning, native Godot/Unity/Roblox evaluation and art/style acceptance.

**M4:** recomp/decomp planning adapters and owner-owned sample programs in VM. No download or redistribution of commercial game bytes.

**M5:** original rigged multi-AI companions from approved artwork and true event stream; dog/cat forms and opt-in playful interactions.

All higher stages must have separate reviewer sign-off, measured acceptance and user-controlled permissions. Never claim a title was ported, a clip existed, or a character was animated solely because source files or README claims exist.
