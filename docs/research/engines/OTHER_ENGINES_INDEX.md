# Other game engines: STAR research index

**Verified 2026-10-13.** Research for every notable engine except Unity, Unreal and Godot (covered separately). Each linked page follows the same outline: at a glance, architecture and lifecycle, project layout, scripting idioms, pitfalls, rendering, physics, input, UI, networking, save data, performance, build and export, common bugs and fixes, a Roblox mapping table, a minimal example, sources and confidence/gaps. Every page lists the official URLs it was checked against.

At answer time STAR uses the matching skill pack (`star/skill_packs/engine-<slug>/`), chosen in code only when the prompt names that engine (`star/skill_packs/engines.py`). The packs are **off by default** until the evaluation gate has measured them; switch them on with `STAR_SKILL_PACKS=engines`. Offline golden tasks: `evals/engines/golden-tasks-other-engines-v1.json` (54 tasks, 2 per pack, static checks).

Nothing here was compiled or run in an engine. Versions and API names come from official docs, release notes and changelogs read on the web.

## Comparison

| Engine | Language | Current stable (released) | License / cost | Best for | Export targets | Editor | Roblox-likeness | Pack |
|---|---|---|---|---|---|---|---|---|
| [Fortnite UEFN + Verse](uefn-verse.md) | Verse | Fortnite/UEFN 42.30; Verse language V1 (2026-10-01) | Free tools; Fortnite EULA; Epic creator payouts | Multiplayer Fortnite islands with devices and Verse logic | Inside Fortnite (PC, consoles, mobile, cloud) | yes (UEFN, Windows) | high | `engine-uefn-verse` |
| [s&box (Source 2)](sbox.md) | C#, Razor/SCSS | Steam release (rolling updates) (2026-04-28) | $10 game; engine code MIT; Source 2 core proprietary; no royalties on approved standalone | Multiplayer sandbox games on the sbox.game platform | Windows, Linux (PC only; standalone export preview) | yes (s&box editor) | high | `engine-sbox` |
| [UGC platforms (Meta Horizon Worlds, HYTOPIA; Rec Room/Core/ZEPETO/The Sandbox status)](ugc-platforms.md) | TypeScript (Horizon, HYTOPIA, ZEPETO); visual (Rec Room CV2, Sandbox) | Horizon desktop editor (early access 2026); HYTOPIA SDK 0.15.2 (2026-02-13) | Free tools; platform ToS; platform payouts | Hosted social multiplayer worlds similar to Roblox | Platform clients only (mobile/web/VR); no export | yes (Horizon desktop editor); HYTOPIA: code + web map builder | high | `engine-ugc-platforms` |
| [Minecraft modding (Fabric, NeoForge, data packs, Bedrock add-ons)](minecraft.md) | Java 25; mcfunction/JSON; JavaScript/TypeScript (Bedrock) | Java 26.3 (Fabric API 0.162.0+26.3, NeoForge 26.3.0.x); Bedrock 26.50 with @minecraft/server 2.10.0 (2026-09-15) | Mojang EULA/usage guidelines; Fabric Apache-2.0; NeoForge LGPL-2.1 | Extending Minecraft with mods, data packs and add-ons | Java: Windows/macOS/Linux; Bedrock: Windows, consoles, mobile | no (IntelliJ/Gradle, VS Code; Bedrock Editor in-game) | medium | `engine-minecraft` |
| [Bevy](bevy.md) | Rust | 0.20 (2026-10-08) | MIT OR Apache-2.0 (free) | Code-first Rust 2D/3D games with ECS | Windows, macOS, Linux, Web (wasm), iOS, Android | no (BSN scenes in code; editor in progress) | low | `engine-bevy` |
| [GameMaker](gamemaker.md) | GML (Code and Visual); GMRT roadmap adds JS/TS/C# | LTS 2026.0.0 (IDE 16, GMS2 Runtime 23) (2026-05-21 (Minor Update 1 2026-05-27)) | Proprietary: free non-commercial, Professional $99.99 one-time, Enterprise subscription for consoles | 2D games of any genre, fast prototyping, solo/indie | Windows, macOS, Ubuntu, Android, iOS, tvOS, HTML5, GX.games, Reddit, consoles (Enterprise) | yes (GameMaker IDE) | medium | `engine-gamemaker` |
| [Defold](defold.md) | Lua 5.1 (LuaJIT); C/C++ native extensions | 1.14.0 (2026-10-12) | Defold License (Apache 2.0 derived), free | Small fast 2D games for mobile, web and consoles | Windows x64, macOS, Linux, iOS, Android, HTML5 (wasm), Switch, PlayStation, Xbox | yes (Defold editor) | medium | `engine-defold` |
| [O3DE (Open 3D Engine)](o3de.md) | C++20, Lua, Script Canvas | 26.05.0 (2026-05-27) | Apache-2.0 OR MIT, free | Large 3D sims/games with owned C++ code, robotics | Windows, Linux, Android, iOS, macOS (varies) | yes (O3DE Editor, Project Manager) | low | `engine-o3de` |
| [Stride](stride.md) | C# 14 / .NET 10 | 4.4.0 (2026-10-09) | MIT, free | C#/.NET 3D games and VR with full engine source | Windows, Linux, macOS, Android, iOS | yes (Game Studio, Windows; Linux via Proton) | low | `engine-stride` |
| [Flax Engine](flax.md) | C#, C++, Visual Scripting | 1.12 (1.12.6912) (2026-05-18) | Free; 4% royalty above $250k/quarter | Unity-like C# 3D games with a modern renderer | Windows, Linux, macOS, Android, iOS, Xbox, PlayStation, Switch, Web (experimental) | yes (Flax Editor) | low | `engine-flax` |
| [Cocos Creator](cocos-creator.md) | TypeScript | 3.8.8 (COCOS 4 engine v4.0.0 open-sourced 2026-01) (2025-12-16) | Free (Cocos license); COCOS 4 MIT | 2D/light-3D mobile and mini-game titles (WeChat, Douyin), web and native mobile | Web, iOS, Android, Windows, macOS, HarmonyOS, Chinese mini-game platforms, Facebook Instant | yes (Cocos Creator editor via Dashboard; COCOS 4: CLI + PinK IDE alpha) | medium | `engine-cocos-creator` |
| [Phaser](phaser.md) | JavaScript / TypeScript | 4.2.1 (last v3: 3.90.0) (2026-07-09) | MIT (free) | 2D browser games: arcade, platformers, puzzle, web/playable games | Web browsers (WebGL); desktop/mobile via third-party wrappers | no built-in; optional Phaser Editor v5 (separate product) | low | `engine-phaser` |
| [Three.js](threejs.md) | JavaScript / TypeScript | r186 (npm 0.186.1) (2026-09-08 (0.186.1 patch 2026-09-24)) | MIT (free) | Browser 3D rendering, web experiences, small web games, WebXR | Web browsers (WebGL 2, WebGPU with WebGL 2 fallback); desktop/mobile via wrappers | no (library; basic online threejs.org/editor) | low | `engine-threejs` |
| [Babylon.js](babylonjs.md) | TypeScript / JavaScript | 9.30.0 (2026-10-08 (9.0 on 2026-03-26)) | Apache-2.0 (free) | Full-featured web 3D games/apps with physics (Havok), GUI, XR, node editors | Web browsers (WebGL 2, WebGPU), WebXR; Babylon Native; wrappers for desktop/mobile | Playground + Inspector + node editors (no full level editor from core team) | medium | `engine-babylonjs` |
| [PlayCanvas](playcanvas.md) | JavaScript / TypeScript | 2.23.2 (2026-10-09 (2.0 on 2024-08-22)) | Engine MIT; Editor freemium ($0 / $15 / $50 per seat) | Lightweight browser 3D games, playable ads, configurators, Gaussian splats, collaborative editing | Web browsers (WebGL 2, WebGPU); wrappers for mobile/desktop | yes (cloud collaborative Editor) or engine-only npm | medium | `engine-playcanvas` |
| [PixiJS](pixijs.md) | TypeScript / JavaScript | 8.22.0 (2026-10-01) | MIT (free) | Fast 2D rendering layer for web games and interactive apps (not a full engine) | Web browsers (WebGL, WebGPU, Canvas) | no | low | `engine-pixijs` |
| [LÖVE](love2d.md) | Lua 5.1 (LuaJIT) | 11.5 (12.0 unreleased) (2023-12-03) | zlib, free | Code-first 2D games, jams, prototypes | Windows, macOS, Linux, Android, iOS (web unofficial) | no | low | `engine-love2d` |
| [raylib](raylib.md) | C (many bindings) | 6.0 (2026-04-23) | zlib/libpng (free) | Learning, jams, small 2D/3D games in C | Windows, Linux, macOS, Web, Android, Raspberry Pi | no | low | `engine-raylib` |
| [MonoGame / FNA / KNI](monogame.md) | C# | MonoGame 3.8.6; FNA 26.10; KNI 4.3.9001 (2026-10-07 (MonoGame); 2026-10-01 (FNA); 2026-08-22 (KNI)) | Ms-PL (free) | Code-first 2D games in C# with the XNA API | Windows, macOS, Linux, Android, iOS, consoles (vendor access); web via KNI | no (Content Builder / MGCB Editor for assets) | low | `engine-monogame` |
| [SDL3](sdl3.md) | C | 3.4.18 (2026-10-02) | zlib (free) | Cross-platform window/input/audio/2D renderer/GPU layer for custom engines | Windows, macOS, Linux, iOS, Android, Web, consoles (NDA) | no | low | `engine-sdl3` |
| [Construct 3](construct3.md) | Event sheets; JavaScript / TypeScript | r495.2 stable (LTS r449.5; beta r502) (2026-08-05 (r495 line 2026-07-21)) | Proprietary subscription per seat; free edition limited to 50 events / 2 layers | 2D event-sheet games, web/mobile, education, prototyping | Web (HTML5), Android, iOS, Windows, macOS, Linux, Xbox (UWP), Instant Games | yes (browser-based editor) | low | `engine-construct3` |
| [RPG Maker MZ](rpgmaker-mz.md) | Event commands; JavaScript plugins | 1.10.0 (RPG Maker Unite 1.3.1 is a separate Unity product) (2026-02-02 (official JP forum; Yanfly lists 2026-01-30)) | Proprietary one-time purchase; games royalty-free | JRPG-style 2D games with database and event editor | Windows, macOS, Web (mobile via third-party web wrappers) | yes (RPG Maker MZ editor) | low | `engine-rpgmaker-mz` |
| [Ren'Py](renpy.md) | Ren'Py script + Python 3.12 | 8.5.3 (2026-05-15) | MIT (free, open source) | Visual novels and choice-driven story games | Windows, macOS, Linux, Android, iOS, Web (beta) | launcher + any text editor (official VS Code extension) | low | `engine-renpy` |
| [Solar2D](solar2d.md) | Lua 5.1 | 2026.3736 (2026-10-12) | MIT, free | 2D mobile games and apps | iOS, tvOS, Android, Android TV, macOS, Windows, Linux, HTML5 | no (Simulator only) | low | `engine-solar2d` |
| [Heaps (Haxe)](heaps.md) | Haxe 4.3 (HxSL shaders) | Heaps 2.1.1 (Haxe 4.3.7, HashLink 1.16) (2025-06-07) | Free, open source (MIT per GitHub; Hide BSD-2-Clause) | Code-first 2D/3D games by programmers; Dead Cells / Northgard pedigree | Windows, macOS, Linux (HashLink/HL-C), HTML5 (JS/WebGL), consoles for registered devs | optional (Hide editor, NW.js); VS Code workflow | low | `engine-heaps` |
| [PICO-8 / Picotron / TIC-80](pico8.md) | P8 Lua (PICO-8), Lua 5.4 (Picotron), Lua + many others (TIC-80) | PICO-8 0.2.7; Picotron 0.3.0d2 (beta); TIC-80 1.3.1 (2025-08-16 (PICO-8); 2026-10-05 (TIC-80 1.3.1)) | PICO-8 $14.99, Picotron $19.99 (proprietary); TIC-80 MIT (PRO build paid) | Tiny retro games, jams, learning | Carts (.p8.png/.p64/.tic), HTML/WASM, Windows/macOS/Linux/RPi binaries | yes (built-in code/sprite/map/sfx/music editors) | low | `engine-pico8` |
| [Unity alternatives 2026 (Fyrox, Ebitengine, Macroquad, GDevelop, KAPLAY, Excalibur, Wicked, HYTOPIA)](alternatives-2026.md) | Rust, Go, JS/TS, C++/Lua, visual events | Fyrox 1.0.1; Ebitengine 2.10.5; Macroquad 0.4.16; GDevelop 5.6.283; KAPLAY 3001.0.19; Excalibur 0.32.0; Wicked 0.72.120; HYTOPIA SDK 0.15.2 (2025-06 to 2026-10 (see doc)) | Mostly MIT/Apache-2.0/BSD; HYTOPIA SDK proprietary | Picking a non-Big-3 engine by language/genre; HYTOPIA for Roblox-like hosted multiplayer | Desktop for all; web for most; mobile for Ebitengine/Macroquad/GDevelop; consoles for Wicked | Fyrox, GDevelop, Wicked: yes; others code-only | medium | `engine-alternatives-2026` |

## Which engine for which job

| If the user wants... | Point them at | Why |
|---|---|---|
| Roblox-like hosted multiplayer with a built-in audience | Fortnite UEFN + Verse, s&box, HYTOPIA, Horizon Worlds | Hosted servers, discovery and payouts; you write game logic only |
| To extend an existing huge game | Minecraft (Fabric/NeoForge, data packs, Bedrock add-ons) | Mods and add-ons, not standalone games |
| A 2D game with an editor, no low-level code | GameMaker, Construct 3, GDevelop, Defold | Rooms/layouts, events or simple scripts, many export targets |
| A 2D game written in code | LÖVE, raylib, MonoGame/FNA, Phaser, Heaps, Ebitengine, Macroquad | Small APIs, you own the main loop |
| A browser 3D experience | Three.js (renderer), Babylon.js (full engine), PlayCanvas (engine + cloud editor) | WebGL 2 / WebGPU |
| A 2D renderer for a web app or game UI | PixiJS | Fast scene graph, no physics or game framework |
| Rust ECS | Bevy (code-first), Fyrox (editor) | |
| C# but not Unity | Stride, Flax, MonoGame/FNA, s&box | |
| Large 3D with C++ source | O3DE, Flax, Wicked Engine | |
| Your own engine | SDL3 (platform layer + SDL_GPU), raylib | |
| JRPG / visual novel | RPG Maker MZ, Ren'Py | Genre tools with databases and story scripting |
| Mobile 2D / WeChat mini-games | Cocos Creator, Defold, Solar2D | Small builds, Chinese mini-game platforms (Cocos) |
| Tiny retro games, jams, learning | PICO-8, Picotron, TIC-80 | Hard limits by design |

## Roblox concepts across engines (summary; full tables on each page)

| Roblox | Typical equivalent elsewhere |
|---|---|
| Workspace / Instance tree | Scene graph of nodes or game objects (Phaser Scene, Three.js Object3D, Cocos Node, s&box GameObject); an ECS World of entities (Bevy) |
| Script / LocalScript | No built-in split in single-player engines; on networked platforms: server vs client code (Verse runs server-side, s&box `[Rpc.Broadcast]`/`[Sync]`, Minecraft logical server vs client) |
| ModuleScript | Ordinary language modules (Rust crates/modules, ES modules, Lua `require`, C# classes) |
| RemoteEvent | RPCs or messages in engines with networking (s&box RPCs, O3DE Multiplayer Gem, Minecraft payload packets); none in most 2D engines |
| DataStore | Local save files (LÖVE `love.filesystem`, GameMaker buffers/ini/json, Ren'Py saves and `persistent`); Verse `weak_map(player, t)` persistables; Bedrock dynamic properties |
| RunService.Heartbeat / RenderStepped | `update(dt)` / `draw()` callbacks, Bevy `Update` / `FixedUpdate` schedules, `requestAnimationFrame` / `setAnimationLoop` on the web |
| TweenService | Phaser tweens, GameMaker sequences / animation curves, Defold `go.animate`, Ren'Py ATL, Solar2D `transition` |
| CollectionService tags | ECS marker components (Bevy), object groups/tags (Phaser groups, s&box tags, Construct families) |
| Studio playtest | Engine editor play mode, or run the program; there is no shared cloud playtest outside the UGC platforms |

## Cross-engine pitfalls that models get wrong

1. **Version drift.** Most of these engines broke their API in the last two years: Bevy every release (0.20 now), Phaser 3 to 4, PixiJS 7 to 8, raylib 5 to 6, SDL2 to SDL3, Three.js r1xx renames, Babylon legacy physics to Havok, PlayCanvas legacy scripts to ESM scripts, Minecraft to year-based versions and official Mojang names, Bedrock Script API 1.x to 2.x, MonoGame MGCB to Content Builder. Always ask for or detect the project's version first.
2. **Dead or changed platforms.** Rec Room shut down on 2026-06-01, Dreams online ended in 2023, Core shows no recent activity, Horizon Worlds VR is in maintenance mode with work moving to the desktop editor. Do not recommend building new games on them.
3. **Frame-rate dependence.** Every code-first engine needs `dt` (or a fixed step) for movement; PICO-8 is the exception (fixed 30/60 fps).
4. **Colour ranges and units.** LÖVE uses 0-1 colours since 11.0; raylib uses 0-255 `Color`; Three.js needs explicit colour spaces; Roblox studs are not metres.
5. **Server authority.** Only the networked platforms (UEFN, s&box, Minecraft, O3DE Multiplayer, HYTOPIA, Horizon) have a server; the Roblox rule "never trust the client" still applies there.

## Gaps (honest list)

- Nothing was compiled or run in an engine; skeletons and eval reference answers are checked only by regex.
- Some official sites blocked fetching (love2d.org, construct.net, pixijs.com, parts of the GameMaker manual and Epic's Verse pages); those facts were taken from GitHub mirrors, the Internet Archive or search snippets and are marked on each page.
- Each page ends with a "Confidence and gaps" section listing the API names that could not be confirmed.
