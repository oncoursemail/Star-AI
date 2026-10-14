# Phaser: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Phaser 4.2.1 "Giedi" (2026-07-09); last v3 is 3.90.0 (2025-05-23).** MIT license, free; Phaser Editor v5 is a separate paid product.

## At a glance
| | |
|---|---|
| Best for | 2D browser games (arcade, platformers, puzzle, idle, web/ad/playable games, Discord activities, mobile web via wrappers) |
| Weak at | 3D (Mesh/Plane and Camera3D removed in v4), large open worlds, built-in networking, native console export |
| Language(s) | JavaScript or TypeScript (types ship in the `phaser` npm package `types/` folder) |
| Editor / tooling | Code-first. Optional Phaser Editor v5 (visual scene editor, released April 2026, Phaser 4 support). `npm create @phaserjs/game@latest` scaffolds Vite/Webpack/React/Vue/Svelte/Next templates |
| Platforms (export) | Any browser (WebGL; Canvas renderer deprecated in v4). Desktop/mobile via third-party wrappers (Electron, Tauri, Capacitor, Cordova) |
| License / cost | MIT, free |
| Roblox-likeness | low: no editor-hosted world, no server, no instance tree with replication; it is a JS rendering/game loop library with scenes |

## Architecture and lifecycle
- `new Phaser.Game(config)` boots one game. It owns renderer, `SceneManager`, `TextureManager`, `CacheManager`, input, sound, plugins and the RAF loop.
- Game is split into **Scenes** (classes extending `Phaser.Scene`, each with a unique `key`). Several scenes can run at once (e.g. `Game` + `HUD` overlay).
- Scene lifecycle (official Scenes concept page):
  1. `init(data)`: receives data passed to `this.scene.start(key, data)`. Reset per-run state here (scene instances are reused on restart).
  2. `preload()`: queue assets on `this.load`. The loader runs after `preload` returns; `create` waits until it finishes.
  3. `create(data)`: build game objects, colliders, input. Only `create` is required for a valid scene.
  4. `update(time, delta)`: every step while the scene is RUNNING. `delta` is ms since last frame.
- Scene control via `this.scene`: `start` (stop this, start target), `launch` (run in parallel), `run`, `pause`/`resume` (pause keeps rendering), `sleep`/`wake` (no update, no render), `stop` (emits `shutdown`), `restart`, `remove` (emits `destroy`).
- Scene systems are injected as properties: `this.add` (GameObjectFactory), `this.make`, `this.physics`, `this.input`, `this.tweens`, `this.time`, `this.cameras`, `this.sound`, `this.load`, `this.events`, `this.registry` (game-wide DataManager), `this.data`.
- Display list: flat per-scene list ordered by `depth`; `Container` groups children with transforms; `Layer` groups for depth/filters without transforms.

## Project layout
Official create-game Vite template (TypeScript):
```
index.html
public/assets/            static assets copied as-is
src/main.ts               creates the Phaser.Game with config
src/game/scenes/Boot.ts   tiny preload (loading bar art)
src/game/scenes/Preloader.ts
src/game/scenes/MainMenu.ts
src/game/scenes/Game.ts
src/game/scenes/GameOver.ts
vite/config.dev.mjs, vite/config.prod.mjs
```
Run `npm install`, `npm run dev` (Vite dev server), `npm run build` (static `dist/`).

## Scripting idioms
Game config (v4):
```ts
import Phaser from 'phaser';
import { Game as MainGame } from './scenes/Game';

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,            // WebGL, falls back to Canvas (deprecated in v4)
  width: 1024,
  height: 768,
  parent: 'game-container',
  backgroundColor: '#028af8',
  pixelArt: false,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  physics: { default: 'arcade', arcade: { gravity: { x: 0, y: 300 }, debug: false } },
  scene: [MainGame],
};
export default new Phaser.Game(config);
```
Scene class with typed fields:
```ts
export class Game extends Phaser.Scene {
  private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  constructor() { super('Game'); }
  preload() {
    this.load.image('sky', 'assets/sky.png');
    this.load.spritesheet('dude', 'assets/dude.png', { frameWidth: 32, frameHeight: 48 });
  }
  create() {
    this.player = this.physics.add.sprite(100, 450, 'dude');
    this.player.setCollideWorldBounds(true);
    this.cursors = this.input.keyboard!.createCursorKeys(); // keyboard can be null in TS types
  }
  update(time: number, delta: number) {
    if (this.cursors.left.isDown) this.player.setVelocityX(-160);
    else if (this.cursors.right.isDown) this.player.setVelocityX(160);
    else this.player.setVelocityX(0);
  }
}
```
Other idioms:
- Animations: `this.anims.create({ key: 'left', frames: this.anims.generateFrameNumbers('dude', { start: 0, end: 3 }), frameRate: 10, repeat: -1 })`, then `sprite.anims.play('left', true)`.
- Tweens: `this.tweens.add({ targets: obj, x: 400, duration: 500, ease: 'Sine.easeInOut', yoyo: true, repeat: -1 })`. Chains: `this.tweens.chain({...})`. Timelines: `this.add.timeline([...])` (3.60+).
- Timers: `this.time.delayedCall(1000, fn)`; `this.time.addEvent({ delay: 500, loop: true, callback: fn })`. Never `setTimeout` (ignores scene pause/time scale).
- Events: `this.events.on('custom', fn)`; cross-scene via `this.registry` or `this.game.events`. Clean up with `this.events.once('shutdown', ...)`.
- Particles (3.60+ API, still v4): `this.add.particles(x, y, 'flare', { speed: 100, lifespan: 600, scale: { start: 1, end: 0 } })`.
- Groups/pooling: `this.physics.add.group({ classType: Bullet, maxSize: 30, runChildUpdate: true })`, `group.get(x, y)`, then `setActive(false).setVisible(false)` to recycle.

## Pitfalls (what AI answers get wrong)
1. **Phaser 2 / Phaser CE syntax.** `new Phaser.Game(800, 600, Phaser.AUTO, '', { preload, create, update })`, `game.add.sprite`, `game.physics.startSystem(Phaser.Physics.ARCADE)`, `game.physics.arcade.enable(sprite)`, `sprite.body.velocity.x = 150`, `game.load.image` all are Phaser 2. Phaser 3/4 use a config object and scene-scoped `this.add`, `this.physics.add.sprite`, `sprite.setVelocityX`.
2. **v4 tint:** `setTintFill()` and `tintFill` are removed. Use `sprite.setTint(0xff0000).setTintMode(Phaser.TintModes.FILL)`. Modes: `MULTIPLY`, `FILL`, `ADD`, `SCREEN`, `OVERLAY`, `HARD_LIGHT`.
3. **v4 FX -> Filters:** `preFX`/`postFX` replaced by `obj.filters.internal` / `obj.filters.external` (also on cameras). Bloom/Shine/Circle FX became `Phaser.Actions.AddEffectBloom()`, `AddEffectShine()`, `AddMaskShape()`; Gradient FX became a `Gradient` game object.
4. **v4 masks:** `new Phaser.Display.Masks.BitmapMask(...)` removed. Use `sprite.filters.internal.addMask(maskObject)`. `GeometryMask` is Canvas-only now.
5. **v4 custom pipelines:** `setPipeline(...)`, `WebGLPipeline`, `PostFXPipeline` classes are gone; rewrite as RenderNodes. Lighting: `sprite.setPipeline('Light2D')` -> `sprite.setLighting(true)`; lights need an explicit `z`.
6. **v4 geometry/math:** `Phaser.Geom.Point` removed (use `Phaser.Math.Vector2`). `Phaser.Math.TAU` is now 2*PI (was PI/2 in v3); `Math.PI2` removed; new `Math.PI_OVER_2`. `Phaser.Struct.Set/Map` replaced by native `Set`/`Map`.
7. **v4 DynamicTexture/RenderTexture:** draw commands are buffered; you must call `rt.render()` after `draw`/`stamp`.
8. **v4 defaults:** `roundPixels` default changed true -> false (pixel art may shimmer; set `pixelArt: true` or `roundPixels: true`). `Mesh`, `Plane`, Camera3D/Layer3D plugins removed. Bundled Spine plugins no longer updated (use Esoteric's official plugin). Compressed textures need Y-flip re-encode.
9. **3.60 changes still often missed:** particles `this.add.particles(key).createEmitter({...})` (removed in 3.60) -> `this.add.particles(x, y, key, config)`. Tween timelines `this.tweens.timeline` -> `this.add.timeline`. 
10. **Static Arcade bodies do not follow their game object.** After `setScale`/`setPosition` on a static sprite, call `refreshBody()` (or `group.refresh()`).
11. **`collider` vs `overlap`.** `overlap` detects only; `collider` separates. For floors use `body.blocked.down` (world/tiles) or `body.touching.down` (bodies), not both interchangeably.
12. **Scene restart keeps class fields.** `this.scene.restart()` reuses the instance; reset counters in `init()`, not in the constructor.
13. **Loader timing.** Assets loaded in `create` need `this.load.start()` and a `complete` listener; keys are global per game (`TextureManager`), so re-loading the same key logs a warning and keeps the old texture.
14. **Import form.** Official README uses `import Phaser from 'phaser'`. Do not import from `phaser/src/...` in app code.
15. **Arcade vs Matter:** a body is in one world only; Arcade (AABB/circle, fast) and Matter (polygons, constraints) bodies never collide with each other.

## Rendering
- WebGL renderer rewritten in v4 ("render nodes"). Canvas renderer still exists but is deprecated.
- Game objects: `Image`, `Sprite`, `Text`, `BitmapText`, `TileSprite`, `Graphics`, `Rectangle`/`Arc`/shapes, `Container`, `Layer`, `Video`, `DOMElement`, `Shader`, `Gradient` (v4), `Extern`, `Zone`, `Tilemap`/`TilemapLayer`, `NineSlice`, `Rope`, `DynamicTexture`/`RenderTexture`.
- Depth: `setDepth(n)`; scroll factor `setScrollFactor(0)` for HUD-like objects in the main camera.
- Filters (v4): any game object or camera; e.g. glow/blur/shadow/color matrix (`colorMatrix.colorMatrix.sepia()` in v4).
- Texture orientation changed to GL (Y=0 bottom) in v4; matters only for custom shaders and compressed textures.

## Physics
- **Arcade** (default, fast AABB + circles): config `physics: { default: 'arcade', arcade: { gravity: { x: 0, y: 300 }, debug: true } }`. `this.physics.add.sprite/image/staticSprite/group/staticGroup/existing`. `this.physics.add.collider(a, b, cb, processCb, ctx)`, `this.physics.add.overlap(a, b, cb)`. Body: `setVelocity`, `setBounce`, `setCollideWorldBounds`, `setImmovable`, `setAllowGravity(false)`, `body.onFloor()`.
- **Matter.js** (`default: 'matter'`): `this.matter.add.sprite(x, y, key, frame, { shape })`, constraints, sensors, collision events `this.matter.world.on('collisionstart', (event, a, b) => ...)`. Heavier; use for rotation/polygon/joint physics.
- Tilemap collisions: `layer.setCollisionByProperty({ collides: true })` then `this.physics.add.collider(player, layer)`.
- No built-in 3D physics.

## Input
- Keyboard: `this.input.keyboard!.createCursorKeys()`, `this.input.keyboard!.addKeys('W,A,S,D')`, `this.input.keyboard!.on('keydown-SPACE', fn)`, `Phaser.Input.Keyboard.JustDown(key)`.
- Pointer: `obj.setInteractive()` then `obj.on('pointerdown', (pointer) => ...)`; scene-wide `this.input.on('pointerdown', ...)`. `this.input.activePointer`, multi-touch `this.input.addPointer(2)`.
- Drag: `this.input.setDraggable(obj)`, `'drag'` event.
- Gamepad: enable `input: { gamepad: true }` in config, `this.input.gamepad.once('connected', pad => ...)`.

## UI
- No widget toolkit. Build with `Text`, `BitmapText`, `NineSlice`, `Image` + `setInteractive`, or a parallel `HUD` scene launched with `this.scene.launch('HUD')`.
- `DOMElement` (`this.add.dom(...)`, config `dom: { createContainer: true }`) for HTML forms; v4 throws if no DOM container.
- Community: rexUI plugin (phaser3-rex-plugins) (community, verify v4 compatibility).

## Networking and multiplayer
No built-in support. Use WebSocket/WebRTC libraries yourself (community: Colyseus, socket.io, Geckos.io). Keep the server authoritative; Phaser runs only in the browser (headless server use is possible but unofficial).

## Save data
No built-in save system. Use `localStorage.setItem('save', JSON.stringify(state))` (sync, small), IndexedDB for larger data, or a backend. `this.registry` / `this.data` are in-memory only.

## Performance
- Use texture atlases (`this.load.atlas`, `this.load.multiatlas`) so sprites batch.
- Pool objects (groups with `maxSize`, `get`, `killAndHide`) instead of create/destroy per frame.
- Avoid per-frame `new Phaser.Math.Vector2()` allocations; reuse.
- v4 lighting changes the shader and breaks batches; light only what you need.
- Text re-renders a canvas on every `setText`; prefer `BitmapText` for scores updated each frame.
- Turn off `arcade.debug` in production; use `physics.world.setBounds` and spatial `useTree` defaults sensibly.

## Build and export
- `npm run build` (Vite template) -> static `dist/` folder; host on any static server or itch.io/Poki/CrazyGames.
- Load the game over http(s), not `file://` (loader XHR fails under CORS).
- Mobile/desktop apps through Capacitor/Cordova/Electron/Tauri (third-party).
- Phaser Editor v5: visual scenes compile to TS/JS scene code; project templates moved to Phaser 4.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Green/black box instead of sprite | Texture key not loaded or typo, or path 404 | Check Network tab; load in `preload`; same key string |
| `this.physics` undefined | No `physics` in game config or scene config | Add `physics: { default: 'arcade' }` |
| Player falls through platform | Platform is a non-physics image, or static body not refreshed after scale | Use `this.physics.add.staticGroup()`; call `refreshBody()` |
| `setTintFill is not a function` | Phaser 4 removed it | `setTint(c).setTintMode(Phaser.TintModes.FILL)` |
| `BitmapMask is not a constructor` | Removed in v4 | `obj.filters.internal.addMask(maskObj)` |
| RenderTexture stays empty in v4 | Draw commands buffered | Call `rt.render()` |
| Score resets wrongly / doubles after restart | State kept in fields or duplicate listeners | Reset in `init()`; remove listeners on `shutdown` |
| `createEmitter is not a function` | Particle API changed in 3.60 | `this.add.particles(x, y, key, config)` |
| Assets fail when opening index.html | `file://` loading blocked | Use `npm run dev` or any local http server |
| Blurry pixel art | Smoothing on / roundPixels false in v4 | `pixelArt: true` in config |

## Mapping from Roblox
| Roblox | Phaser | Notes |
|---|---|---|
| Workspace / Instance tree | Scene display list, `Container` | Flat list per scene; no parenting of physics bodies |
| Part | `this.physics.add.image` / `Rectangle` shape with Arcade body | 2D only |
| Model | `Container` or `Group` | Group = logical collection, Container = transform parent |
| Script (server) | No equivalent | All code runs in the browser; add your own server |
| LocalScript | Scene class code | Everything is client-side |
| ModuleScript | ES module (`import`/`export`) | Bundled by Vite |
| RemoteEvent | WebSocket message (Colyseus/socket.io) | Not built in |
| DataStore | `localStorage` or your backend | No cloud save |
| Players | Not applicable | Single local player unless you add networking |
| Humanoid | Your own player class extending `Phaser.Physics.Arcade.Sprite` | Write movement/health yourself |
| RunService.Heartbeat / RenderStepped | `update(time, delta)` / `this.events.on('update')`, `'postupdate'` | delta in ms, not seconds |
| TweenService | `this.tweens.add({...})` | ease names like `'Sine.easeInOut'` |
| CollectionService tags | Groups, `setData('tag', ...)`, `setName` | `getData`/`setData` per object |
| Attributes | `obj.setData(key, value)` / `obj.data` | Emits `changedata` events |
| ScreenGui | Separate HUD scene or `setScrollFactor(0)` objects | |
| UserInputService | `this.input`, `this.input.keyboard`, `this.input.gamepad` | |
| task.wait | `this.time.delayedCall(ms, fn)` | No coroutines; use callbacks/async |
| Studio playtest | `npm run dev` + browser | Hot reload via Vite |
| Publishing | `npm run build`, upload `dist/` | Any static host |

## Minimal example
Move with arrows, collect stars, score (Phaser 4, TypeScript; assets are generated so no files needed).
```ts
import Phaser from 'phaser';

class Play extends Phaser.Scene {
  private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
  private stars!: Phaser.Physics.Arcade.Group;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private scoreText!: Phaser.GameObjects.Text;
  private score = 0;

  constructor() { super('Play'); }

  init() { this.score = 0; }

  create() {
    const g = this.make.graphics({ x: 0, y: 0 }, false);
    g.fillStyle(0x33aaff).fillRect(0, 0, 32, 32).generateTexture('box', 32, 32);
    g.clear().fillStyle(0xffdd00).fillCircle(8, 8, 8).generateTexture('star', 16, 16);
    g.clear().fillStyle(0x228833).fillRect(0, 0, 800, 32).generateTexture('ground', 800, 32);
    g.destroy();

    const platforms = this.physics.add.staticGroup();
    platforms.create(400, 584, 'ground');

    this.player = this.physics.add.sprite(100, 400, 'box');
    this.player.setCollideWorldBounds(true);

    this.stars = this.physics.add.group({ key: 'star', repeat: 9, setXY: { x: 40, y: 0, stepX: 80 } });
    this.stars.children.iterate((child) => {
      (child as Phaser.Physics.Arcade.Image).setBounceY(Phaser.Math.FloatBetween(0.3, 0.6));
      return true;
    });

    this.physics.add.collider(this.player, platforms);
    this.physics.add.collider(this.stars, platforms);
    this.physics.add.overlap(this.player, this.stars, (_p, star) => {
      (star as Phaser.Physics.Arcade.Image).disableBody(true, true);
      this.score += 10;
      this.scoreText.setText(`Score: ${this.score}`);
    });

    this.scoreText = this.add.text(16, 16, 'Score: 0', { fontSize: '24px', color: '#ffffff' });
    this.cursors = this.input.keyboard!.createCursorKeys();
  }

  update() {
    const speed = 200;
    if (this.cursors.left.isDown) this.player.setVelocityX(-speed);
    else if (this.cursors.right.isDown) this.player.setVelocityX(speed);
    else this.player.setVelocityX(0);
    if (this.cursors.up.isDown && this.player.body.blocked.down) this.player.setVelocityY(-330);
  }
}

new Phaser.Game({
  type: Phaser.AUTO,
  width: 800,
  height: 600,
  backgroundColor: '#1d1d2b',
  physics: { default: 'arcade', arcade: { gravity: { x: 0, y: 400 }, debug: false } },
  scene: [Play],
});
```

## Sources
- https://github.com/phaserjs/phaser/releases (v4.2.1 2026-07-09, v4.2.0 2026-06-19, v4.1.0 2026-04-30, v4.0.0 2026-04-10, v3.90.0 2025-05-23; v4 tint/stencil/filter padding notes)
- https://github.com/phaserjs/phaser (README: version 4.2.1, `npm install phaser`, `import Phaser from 'phaser'`, Arcade + Matter built in, TS types folder, AI skills folder)
- https://raw.githubusercontent.com/phaserjs/phaser/HEAD/changelog/v4/4.0/MIGRATION-GUIDE.md (all v3 -> v4 breaking changes listed above)
- https://phaser.io/news/2026/04/migrating-from-phaser-3-to-phaser-4-what-you-need-to-know (summary of v4 changes)
- https://docs.phaser.io/phaser/concepts/scenes (lifecycle, scene control, shutdown/destroy events, restart pitfalls)
- https://docs.phaser.io/phaser/concepts/physics/arcade (Arcade config, factories, collider/overlap, static refreshBody, blocked vs touching)
- https://github.com/phaserjs/create-game (`npm create @phaserjs/game@latest`, template list)
- https://phaser.io/news/2026/04/phaser-editor-v5-release (Phaser Editor v5 released, Phaser 4 support, filters)

## Confidence and gaps
- High: versions/dates (GitHub releases), v4 breaking changes (official migration guide), Arcade API, scene lifecycle.
- Medium: Matter API names (`this.matter.add.sprite`, `collisionstart`) from long-standing v3 docs; not re-read for v4 but README confirms Matter is still bundled.
- Medium: particles/timeline/3.60 notes and input snippets are from v3.60+ knowledge; not re-fetched this session.
- Unverified: rexUI v4 compatibility; Phaser Editor v5 pricing details.
