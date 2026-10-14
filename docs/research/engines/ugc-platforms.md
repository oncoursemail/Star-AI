# UGC game platforms (Horizon Worlds, HYTOPIA, Rec Room, Core, ZEPETO, The Sandbox, Dreams): STAR engine research
**Verified 2026-10-13 against official docs and news. Current stable: Meta Horizon Worlds desktop editor (early access since early 2026, TypeScript `horizon/*` API); HYTOPIA SDK 0.15.2 (2026-02-13, alpha).** All free to create; revenue rules are platform-specific. Fortnite UEFN and Minecraft have their own docs (`uefn-verse.md`, `minecraft.md`).

## At a glance
| | |
|---|---|
| Best for | Social/multiplayer worlds hosted by a platform with built-in avatars, discovery and payments, the same niche as Roblox |
| Weak at | Portability (no export), long-term stability (several platforms shut down or shrank in 2023-2026), deep engine control |
| Language(s) | Horizon Worlds: TypeScript (plus legacy Code Blocks). HYTOPIA: TypeScript/JavaScript (Node-style server, Bun runtime). Rec Room: Circuits V2 visual scripting (closed). Core: Lua. ZEPETO: TypeScript (ZEPETO Script) in Unity. The Sandbox: visual Game Maker. Dreams: in-game visual logic |
| Editor / tooling | Horizon desktop editor (Windows) + VS Code; HYTOPIA: npm package + local server + browser client + build.hytopia.com map editor; ZEPETO Studio Unity package |
| Platforms (export) | No export anywhere; content runs inside each platform's client (mobile/web/VR depending on platform) |
| License / cost | Free tools; platform ToS own distribution; creator payouts vary (HYTOPIA announced 85% to creators at monetization launch, unverified as launched) |
| Roblox-likeness | high (concept); medium (APIs). Horizon TypeScript components and HYTOPIA entities/events map well to Roblox scripts |

### Status board (2026-10-13)
| Platform | Status | Notes |
|---|---|---|
| Meta Horizon Worlds | Live; strategy is mobile-first | Mar 2026: Meta announced removing Horizon Worlds from Quest on 2026-06-15, reversed within days; VR app kept "for the foreseeable future" but in maintenance mode, no new first-party VR games. Desktop editor in early access; in-VR building tools deprecated ("legacy"). $50M creator fund for mobile/MR worlds. Reality Labs layoffs (Jan 2026). |
| HYTOPIA | Live, alpha SDK | Browser-played voxel multiplayer games; SDK `hytopia` on npm (0.15.2, Feb 2026; "expect breaking changes"); own client/server/engine. |
| Rec Room | **Shut down 2026-06-01** | Announced 2026-03-30; token purchases stopped 2026-05-01, creator token rewards stopped 2026-05-18. Rec Room Studio (Unity-based) only in limited offline mode for locally cached rooms. Snap acquired select assets. Do not recommend for new work. |
| Core (Manticore) | Website still online; no recent development news found | Unreal-based, Lua scripting. Treat as legacy; Manticore's own game Out of Time was shut down. |
| ZEPETO | Live (avatar social app; World SDK on Unity + TypeScript) | Community 2026 guides still use ZEPETO Studio/World SDK; official 2026 changes not verified. |
| The Sandbox | Live but restructured | 2025 layoffs (>50% staff), leadership change, web3/memecoin pivot; Game Maker 0.11 / Game Client 0.12 updates. Risky for new projects. |
| Dreams (PS4) | Live service ended (Sept 2023) | Content playable offline; no new online features. Not a target. |

## Architecture and lifecycle
**Horizon Worlds.** A world is a scene of entities (meshes, triggers, text gizmos, spawn points ...). Scripts are TypeScript classes extending `Component` from the `horizon/core` module, attached to entities, with typed `propsDefinition` (inspector properties), lifecycle `preStart()` (connect events) and `start()`. Execution owner: scripts run on the server by default; ownership can be transferred to a player (local scripts) for responsive input. Events: `CodeBlockEvents` (built-in: player enter/exit world, trigger enter, grab...), custom `NetworkEvent`s and `LocalEvent`s. Some modules (e.g. `horizon/camera`, `horizon/ui`) must be enabled in the editor's script settings before import (community-reported).

**HYTOPIA.** Authoritative Node-style game server you write in TypeScript; `startServer(world => {...})` is the entry point; the world loads a voxel map JSON (built in build.hytopia.com), entities (`Entity`, `PlayerEntity`, `DefaultPlayerEntity`) with physics colliders (Rapier-based simulation, `world.simulation`), event-driven API (`world.on(PlayerEvent.JOINED_WORLD, ...)`), per-player HTML UI (`player.ui.load('ui/index.html')`). Platform hosts and scales servers; players join in a browser.

**Rec Room (historical).** Rooms built in-headset/in-app with Maker Pen; Circuits V2 visual scripting (chips wired by ports, execution and data wires, CV2 "Room Events"); Rec Room Studio was a Unity-based editor for importing assets and authoring rooms. Platform offline since 2026-06-01.

**Core (legacy).** Unreal-based; "Core Content" templates; Lua scripts as `Script` objects in a hierarchy (Default Context, Client Context, Server Context, Static Context), networked properties and `Events.Broadcast`/`BroadcastToServer`. Closest historical Roblox clone.

**ZEPETO World.** Unity project + ZEPETO Studio package; `ZepetoScriptBehaviour` TypeScript classes compiled for the ZEPETO runtime; multiplayer through a ZEPETO multiplay server (Colyseus-like room state, server written in TypeScript). Verify against current ZEPETO docs before use.

## Project layout
Horizon Worlds: the world lives in Meta's cloud; desktop editor syncs scripts to a local folder (`scripts/*.ts`) with generated type definitions for VS Code; assets imported as FBX/textures through the editor.
HYTOPIA:
```
my-game/
  index.ts            # startServer(...)
  assets/map.json     # exported from build.hytopia.com
  assets/ui/index.html
  package.json        # "hytopia" dependency
```
ZEPETO: Unity `Assets/` with `*.ts` ZEPETO scripts, `World.multiplay/` for server code.

## Scripting idioms
Horizon Worlds component (forum- and template-confirmed shape; check generated typings):
```ts
import { Component, PropTypes, CodeBlockEvents, Player, Entity } from 'horizon/core';

class ScoreZone extends Component<typeof ScoreZone> {
  static propsDefinition = {
    points: { type: PropTypes.Number, default: 1 },
  };

  preStart() {
    this.connectCodeBlockEvent(this.entity, CodeBlockEvents.OnPlayerEnterTrigger, (player: Player) => {
      console.log(`${player.name.get()} +${this.props.points}`);
    });
  }

  start() {}
}
Component.register(ScoreZone);
```
HYTOPIA server (from SDK boilerplate 0.15.2):
```ts
import { startServer, DefaultPlayerEntity, PlayerEvent } from 'hytopia';
import worldMap from './assets/map.json';

startServer(world => {
  world.loadMap(worldMap);
  world.on(PlayerEvent.JOINED_WORLD, ({ player }) => {
    const playerEntity = new DefaultPlayerEntity({ player, name: 'Player' });
    playerEntity.spawn(world, { x: 0, y: 10, z: 0 });
    player.ui.load('ui/index.html');
  });
});
```

## Pitfalls (what AI answers get wrong)
1. **Recommending dead platforms.** Rec Room shut down 2026-06-01; Dreams online ended 2023; Core is dormant. Check status first.
2. **Horizon Worlds VR claims.** VR building is legacy; VR app is maintenance-only; new work targets mobile/desktop via the desktop editor. Do not tell users to build in-headset.
3. **Horizon Code Blocks vs TypeScript.** Code Blocks are the legacy visual system; TypeScript is current. Mixing them needs `CodeBlockEvent` bridges. Event names are case-sensitive (`CodeBlockEvents`, not `CodeblockEvents`).
4. **Forgetting `Component.register(MyClass)`** in Horizon scripts: the component never appears in the editor.
5. **Horizon API modules gated by settings** (`horizon/camera`, `horizon/ui` ...): import compiles in VS Code but fails in the world until enabled (community-reported).
6. **Horizon local vs server execution.** Input/camera code must run on a player-owned (local) script; server scripts cannot read a player's input. Ownership transfer is explicit.
7. **HYTOPIA alpha churn.** SDK 0.x breaks between versions; pin `hytopia` version and read its `docs/server.md` for the installed version.
8. **HYTOPIA map coordinates.** Spawning above y=0 matters (boilerplate spawns at y=10); spawning inside blocks traps the player.
9. **Assuming Roblox Luau works anywhere else.** Only Core used Lua (not Luau); none of these accept Roblox scripts.
10. **The Sandbox / NFT claims.** LAND/asset ownership and token economics are volatile; never present earnings as reliable.

## Rendering
Horizon: Meta's proprietary engine, mobile/Quest budgets (low poly, baked lighting, texture limits). HYTOPIA: browser WebGL client (Three.js-based per community sources, unverified), voxel blocks + glTF models. ZEPETO: Unity URP-like on mobile. The Sandbox: voxel (VoxEdit assets).

## Physics
Horizon: built-in physics on entities (`PhysicalEntity` with `applyForce`, motion types; verify names in typings), triggers via trigger gizmos. HYTOPIA: rigid bodies + colliders on entities, `world.simulation` with debug rendering (`enableDebugRendering(true)`). ZEPETO: Unity physics.

## Input
Horizon: player input via `PlayerControls` / input actions on local scripts (verify), grab/trigger events. HYTOPIA: `DefaultPlayerEntity` maps WASD/mouse automatically; custom input via `player.input` and the player entity controller. ZEPETO: Unity input + ZEPETO character controller.

## UI
Horizon: custom UI panels (`horizon/ui`, `UIComponent` with bindings; enable module first), text gizmos. HYTOPIA: per-player HTML/CSS/JS UI loaded with `player.ui.load(...)`, server-to-UI messages with `player.ui.sendData(data)` (confirmed); also `append`, `lockPointer`. ZEPETO: Unity UGUI.

## Networking and multiplayer
All are hosted multiplayer. Horizon: server-authoritative by default; `NetworkEvent` for cross-owner messages, `LocalEvent` within one owner. HYTOPIA: server authoritative, state replicated automatically for entities; UI messages per player. ZEPETO: multiplay room server (TypeScript) with schema-synced state.

## Save data
Horizon: Persistent Player Variables (PPVs) defined in the editor's variable groups and read/written via `world.persistentStorage` (verify exact API in typings). HYTOPIA: `player.getPersistedData()` / `player.setPersistedData(...)` per player and `PersistenceManager` for global data (names confirmed in SDK 0.15.2 API docs; signatures not read). ZEPETO: DataStorage for multiplay (verify). Rec Room's cloud variables are gone with the platform.

## Performance
Horizon: tight entity/script/memory caps per world, mobile first; avoid per-frame `World.onUpdate` work where events suffice. HYTOPIA: server tick in Node/Bun; avoid per-tick allocations; limit entity count and physics debug rendering in production.

## Build and export
No standalone export. Horizon: save/release the world through the desktop editor to the Horizon platform (age 13+, supported countries; Creator Program, $50M fund bonuses for mobile/MR worlds). HYTOPIA: develop locally (`hytopia` server + play at hytopia.com/play against localhost), then upload to the platform. ZEPETO: upload World via ZEPETO Studio. Fortnite comparison: UEFN has the largest audience and real payouts (engagement + in-island transactions) but Fortnite-only content; Roblox remains the most general and best-documented.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Horizon script not in component list | Missing `Component.register` or compile error | Register class; check script console |
| Horizon import fails at runtime | API module not enabled | Enable in script settings |
| Horizon input ignored | Script runs on server | Transfer ownership to player / local script |
| HYTOPIA player falls forever | Spawn outside map / map not loaded | `world.loadMap(map)` before spawning; spawn above ground |
| HYTOPIA API missing after upgrade | Alpha breaking change | Pin version; read release notes |
| Rec Room/Dreams instructions don't work | Platform offline | Pick a live platform |

## Mapping from Roblox
| Roblox | Horizon Worlds / HYTOPIA | Notes |
|---|---|---|
| Workspace / Instance tree | Horizon world entity hierarchy / HYTOPIA `World` + entities + voxel map | |
| Part | Horizon mesh/shape entity / HYTOPIA block or `Entity` with collider | |
| Model | Horizon asset template / HYTOPIA model entity (glTF) | |
| Script | Horizon `Component` (server-owned) / HYTOPIA server `index.ts` | |
| LocalScript | Horizon local (player-owned) script / HYTOPIA UI script (HTML) | |
| ModuleScript | TS module import | |
| RemoteEvent | Horizon `NetworkEvent` / HYTOPIA UI data messages | |
| DataStore | Horizon persistent player variables / HYTOPIA persistence API | verify |
| Players | `PlayerEvent.JOINED_WORLD` (HYTOPIA), `CodeBlockEvents.OnPlayerEnterWorld` (Horizon) | |
| Humanoid | Horizon avatar `Player` / HYTOPIA `PlayerEntity` + controller | |
| RunService.Heartbeat | Horizon `World.onUpdate` event (verify) / HYTOPIA tick hooks | |
| RenderStepped | No direct equivalent | |
| TweenService | Horizon animation/`moveTo` helpers (verify) / manual lerp | |
| CollectionService tags | Horizon entity tags (verify) / HYTOPIA entity tags | |
| Attributes | `propsDefinition` (Horizon) | Editor-set props |
| ScreenGui | `horizon/ui` panels / HYTOPIA HTML UI | |
| UserInputService | Horizon player input actions (local) / HYTOPIA controller | |
| task.wait | `this.async.setTimeout` (Horizon, verify) / `setTimeout` (HYTOPIA) | |
| Studio playtest | Horizon editor preview / local HYTOPIA server + browser | |
| Publishing | Platform upload + review | |

## Minimal example
HYTOPIA: give a point to a player every time they join and show it in their UI.
```ts
import { startServer, DefaultPlayerEntity, PlayerEvent } from 'hytopia';
import worldMap from './assets/map.json';

const scores = new Map<string, number>();

startServer(world => {
  world.loadMap(worldMap);
  world.on(PlayerEvent.JOINED_WORLD, ({ player }) => {
    const entity = new DefaultPlayerEntity({ player, name: 'Player' });
    entity.spawn(world, { x: 0, y: 10, z: 0 });
    const next = (scores.get(player.id) ?? 0) + 1;
    scores.set(player.id, next);
    player.ui.load('ui/index.html');
    player.ui.sendData({ score: next });
  });
});
```

## Sources
- https://developers.meta.com/horizon/blog/empowering-horizon-creators-with-a-new-50m-fund-and-advanced-tools-for-mobile-and-mr-worlds (desktop editor, TypeScript, $50M fund)
- https://developers.meta.com/horizon-worlds/support/ (Horizon creator support; desktop editor)
- https://beta.developers.meta.com/horizon-worlds/learn/videos/scripting-your-world/ (preStart, connectCodeBlockEvent)
- https://communityforums.atmeta.com/discussions/General_Development_Discussion/connecting--sending-events/1313173 (community: horizon/core imports, propsDefinition, CodeBlockEvents)
- https://communityforums.atmeta.com/discussions/Creator_Discussion/psa-typescript-import-apis-that-need-to-be-manually-enabled-in-desktop-editor/1318587 (community: API modules gated by settings)
- https://euronews.com/next/2026/03/20/meta-u-turns-on-horizon-worlds-vr-shutdown-after-user-backlash (VR shutdown reversal)
- https://www.pocketgamer.biz/meta-pulls-horizon-worlds-from-vr-as-platform-shifts-to-mobile (mobile pivot)
- https://unpkg.com/hytopia@0.15.2/boilerplate/index.ts (official SDK boilerplate)
- https://unpkg.com/hytopia@0.15.2/README.md (alpha status, TypeScript, browser play)
- https://registry.npmjs.org/hytopia (0.15.2 released 2026-02-13)
- https://unpkg.com/hytopia@0.15.2/docs/server.player.md (Player members: id, ui, input, getPersistedData/setPersistedData) and server.playerui.md (sendData, load)
- https://gamesbeat.com/hytopias-post-minecraft-pivot-aims-to-give-ugc-developers-more-control/ (85% creator share at monetization launch)
- https://uploadvr.com/rec-room-to-shut-down-in-june (Rec Room shutdown)
- https://roadtovr.com/rec-room-shutdown-snap-acquisition-2026/ (Snap asset acquisition, dates)
- https://www.coregames.com/ (Core site still online 2026-10-13)
- https://cointelegraph.com/news/the-sandbox-restructuring-ai-layoffs-cofounders-role-shift (The Sandbox restructuring)

## Confidence and gaps
- High: Rec Room shutdown dates; Horizon VR reversal + desktop editor; HYTOPIA boilerplate API and version.
- Medium: Horizon TypeScript names beyond `Component`, `propsDefinition`, `preStart/start`, `connectCodeBlockEvent`, `CodeBlockEvents` (official TS docs required login and could not be fetched); HYTOPIA physics names and persistence signatures.
- Low / not verified: Core's operational status beyond the website; ZEPETO 2026 SDK changes; The Sandbox Game Maker 2026 version; Overwolf (no UGC game-creation product relevant to STAR found; it mainly runs CurseForge mod distribution).
