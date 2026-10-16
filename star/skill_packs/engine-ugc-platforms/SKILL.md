---
name: engine-ugc-platforms
description: Roblox-like UGC platforms in 2026: Meta Horizon Worlds (TypeScript, desktop editor), HYTOPIA SDK 0.15, plus status of Rec Room, Core, ZEPETO, The Sandbox. Use when one of them is named.
---
# engine-ugc-platforms
## Scope
Meta Horizon Worlds desktop editor (early access, TypeScript `horizon/core`), HYTOPIA SDK 0.15.2 (alpha, TypeScript). Status as of Oct 2026: Rec Room shut down on 2026-06-01; Dreams online ended 2023; Core (Manticore, Lua) is dormant; The Sandbox restructured; ZEPETO (Unity + TypeScript) still live. Check the platform's current status and the project's SDK version first.

## Core model
- Hosted platforms: the platform runs servers, avatars, discovery and payments; nothing exports to a standalone game.
- Horizon Worlds: entities in a world; TypeScript classes extend `Component` with `propsDefinition`, `preStart()` (connect events) and `start()`; scripts run on the server unless ownership moves to a player (local). VR building is legacy; the VR app is in maintenance mode, focus is mobile.
- HYTOPIA: you write the authoritative server in TypeScript; `startServer(world => ...)` entry; voxel map JSON; entities with physics; per-player HTML UI; players join from a browser.

## Idioms
- Horizon: `import { Component, PropTypes, CodeBlockEvents, Player } from 'horizon/core';` then `Component.register(MyComp);` at the end.
- Horizon events: `this.connectCodeBlockEvent(this.entity, CodeBlockEvents.OnPlayerEnterTrigger, (p: Player) => ...)`; custom cross-script messages with network or local events.
- Horizon props: `static propsDefinition = { points: { type: PropTypes.Number, default: 1 } };` read as `this.props.points`.
- HYTOPIA: `world.loadMap(map)`, `world.on(PlayerEvent.JOINED_WORLD, ({ player }) => ...)`, `new DefaultPlayerEntity({ player, name })`, `entity.spawn(world, { x, y, z })`.
- HYTOPIA UI: `player.ui.load('ui/index.html')`, `player.ui.sendData({...})`; persistence: `player.getPersistedData()` / `player.setPersistedData(...)`.

## Pitfalls
1. Do not recommend Rec Room (offline since 2026-06-01) or Dreams for new work; Core has no active development.
2. Horizon: building in VR is legacy; use the desktop editor (Windows).
3. Horizon: forgetting `Component.register(...)` hides the component.
4. Horizon: some modules (camera, UI) must be enabled in script settings before import works in the world.
5. Horizon: player input/camera code must run in a player-owned (local) script, not a server script.
6. Horizon: `CodeBlockEvents` casing matters; Code Blocks are the legacy visual system.
7. HYTOPIA SDK is alpha (0.x): pin the version; APIs break between releases.
8. HYTOPIA: load the map before spawning; spawn above ground (y around 10) or players get stuck.
9. None of these run Roblox Luau; Core used plain Lua with a different API.
10. Never promise income: payouts and token prices (The Sandbox) are volatile.

## Roblox to UGC platforms
Script -> Horizon server `Component` / HYTOPIA server `index.ts`
LocalScript -> Horizon local (player-owned) script / HYTOPIA HTML UI script
RemoteEvent -> Horizon network event / HYTOPIA `player.ui.sendData` + UI messages
DataStore -> Horizon persistent player variables / HYTOPIA persisted player data
Players.PlayerAdded -> `CodeBlockEvents.OnPlayerEnterWorld` / `PlayerEvent.JOINED_WORLD`
Humanoid -> Horizon `Player` avatar / HYTOPIA `PlayerEntity`
Attributes -> `propsDefinition`; ScreenGui -> Horizon UI panels / HYTOPIA HTML UI
task.wait -> timers (`setTimeout`); Studio playtest -> editor preview / local server + browser
Part, Model -> entities, meshes, voxel blocks, glTF models

## Skeleton
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

## Verification
HYTOPIA: run the local server from the SDK and join from the HYTOPIA play page against localhost; check the server console. Horizon: compile in the desktop editor script panel and test in preview. Report "not run" unless you saw it run.
