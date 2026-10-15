# PixiJS: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: PixiJS v8.22.0 (2026-10-01); v8.0.0 launched March 2024.** MIT license, free.

## At a glance
| | |
|---|---|
| Best for | Fast 2D rendering in the browser: games built on your own loop, interactive ads, data/visual apps, UI-heavy web games, rendering layer for custom engines |
| Weak at | It is a renderer, not a game engine: no physics, no scenes manager, no audio in core, no editor, no networking, no save system |
| Language(s) | TypeScript / JavaScript (types included in `pixi.js` package) |
| Editor / tooling | No editor. Scaffold with `npm create pixi.js@latest` (Vite templates). Companion libs: `@pixi/react`, `@pixi/sound`, `@pixi/ui`, `@pixi/layout`, `pixi-filters`, PixiJS DevTools |
| Platforms (export) | Browsers (WebGL 1/2, WebGPU, Canvas via extension); wraps into Electron/Capacitor/etc. via third-party tools |
| License / cost | MIT, free |
| Roblox-likeness | low: no world, no physics, no server; you write the loop and all game systems |

## Architecture and lifecycle
- `Application` = renderer + root `stage` (a `Container`) + `ticker`. In v8 it must be created then **awaited**: `const app = new Application(); await app.init({...})`.
- Scene graph: `Container` is the base of everything (v8 removed `DisplayObject`). Leaf nodes (`Sprite`, `Graphics`, `Text`, `Mesh`, `TilingSprite`, `NineSliceSprite`...) **cannot have children** in v8.
- Render loop: `app.ticker` (a `Ticker`) calls listeners each frame then renders `app.stage`. Listener receives the `Ticker` (`ticker.deltaTime` = frame-scaled, `ticker.deltaMS` = ms).
- Renderers: `WebGLRenderer`, `WebGPURenderer`, `CanvasRenderer`; `autoDetectRenderer` prioritizes WebGL by default; opt in with `preference: 'webgpu'`.
- Assets: global `Assets` (promise-based): `Assets.add`, `Assets.load`, `Assets.addBundle`/`loadBundle`, `Assets.init({ manifest })`, `Assets.backgroundLoad`.
- Per-object frame hook: `container.onRender = () => {...}` (replaces overriding `updateTransform`).
- Events: federated pointer events on containers with `eventMode`.

## Project layout
No mandated layout. Typical Vite app from `npm create pixi.js@latest`:
```
index.html
public/assets/           images, spritesheets (.json + .png), fonts
src/main.ts              app.init, Assets, stage setup
src/scenes/*.ts          your own Scene classes (Containers) and a manager you write
src/entities/*.ts
vite.config.ts
```

## Scripting idioms
```ts
import { Application, Assets, Sprite, Container, Graphics, Text } from 'pixi.js';

const app = new Application();
await app.init({ background: '#1099bb', resizeTo: window, antialias: true });
document.body.appendChild(app.canvas);          // v8: canvas, not view

const texture = await Assets.load('/assets/bunny.png');
const bunny = new Sprite(texture);
bunny.anchor.set(0.5);
bunny.position.set(app.screen.width / 2, app.screen.height / 2);
app.stage.addChild(bunny);

app.ticker.add((ticker) => {                     // v8: receives Ticker
  bunny.rotation += 0.05 * ticker.deltaTime;
});
```
- Graphics v8 (shape then fill/stroke): `new Graphics().rect(0, 0, 100, 50).fill(0xff0000).stroke({ width: 2, color: 'white' })`; `circle`, `ellipse`, `poly`, `roundRect`, `star`, `moveTo/lineTo`, holes via `.cut()`. Share geometry with `GraphicsContext`.
- Text v8: `new Text({ text: 'Score: 0', style: { fill: '#ffffff', fontSize: 24 } })`; `BitmapText` for frequently changing text.
- Spritesheet: `const sheet = await Assets.load('/assets/hero.json')`, `new AnimatedSprite(sheet.animations['run'])`, `.animationSpeed = 0.2; .play()`.
- Bundles: `await Assets.init({ manifest })`, `await Assets.loadBundle('game')`.
- Naming: `container.label = 'player'` (v8; `name` deprecated), find with `getChildByLabel`.
- Interaction: `sprite.eventMode = 'static'; sprite.cursor = 'pointer'; sprite.on('pointertap', fn)`.
- Cleanup: `sprite.destroy()`, `container.destroy({ children: true })`, `app.destroy()`; unload with `Assets.unload(key)`.

## Pitfalls (what AI answers get wrong)
1. **Synchronous Application.** v7 `new Application({ width, height })` then `app.view` -> v8 `const app = new Application(); await app.init({...}); app.canvas`. Using the app before `init` resolves crashes (renderer undefined).
2. **Old Graphics API.** `beginFill/drawRect/endFill`, `lineStyle`, `drawCircle`, `beginHole` are v7. v8: `rect(...).fill(color)`, `stroke({ width, color })`, `circle`, `.cut()`.
3. **`@pixi/*` sub-packages.** v8 is one package: `import { Application, Sprite } from 'pixi.js'`. Do not import `@pixi/app`, `@pixi/graphics`, `@pixi/loaders`. Filters moved to `pixi-filters/<name>`.
4. **`PIXI.Loader` / `app.loader`.** Removed (v7 already). Use `Assets.load`. `Texture.from(url)` no longer loads URLs in v8; load first, then `Texture.from(alias)` or use the returned texture.
5. **Ticker delta.** v8 listener gets a `Ticker`, not a number: `(ticker) => ticker.deltaTime`. Writing `(delta) => x += delta` silently adds an object -> NaN.
6. **Children on leaf nodes.** `sprite.addChild(other)` is not allowed in v8. Wrap both in a `Container`.
7. **Text constructor.** `new Text('hi', style)` (positional) -> `new Text({ text: 'hi', style })`. Same object form for `BitmapText`, `HTMLText`, `BlurFilter`, `TilingSprite`, `Mesh` etc.
8. **Interactivity.** v7 `interactive = true` / `buttonMode` -> `eventMode = 'static'` (or `'dynamic'`) and `cursor = 'pointer'`. Default `eventMode` is `'passive'`. `pointermove` fires only over the object in v8; use `globalpointermove` for drag.
9. **Removed/renamed:** `DisplayObject` (use `Container`), `BaseTexture` (-> `TextureSource`), `cacheAsBitmap = true` (-> `cacheAsTexture(true)`), `settings.*` (-> `AbstractRenderer.defaultOptions` / `DOMAdapter`), `utils.isMobile` (-> `isMobile`), `getBounds()` returns `Bounds` (`.rectangle` for a Rectangle), `NineSlicePlane` -> `NineSliceSprite`, `SimpleRope` -> `MeshRope`, `SCALE_MODES.NEAREST` -> `'nearest'`.
10. **ParticleContainer v8** takes `Particle` objects via `addParticle`, not Sprites via `addChild`; set `boundsArea`.
11. **Assumes a game engine.** There is no `physics`, `scene.start`, `collider`, keyboard manager or audio in core: use your own AABB checks or a physics lib (Matter.js, Rapier, Planck: third-party), `window` keyboard events, and `@pixi/sound`.
12. **Recent v8 minor behavior changes:** 8.18 text width with wrap+align; 8.19 `Container` zero scale now honored; 8.20 `StructsAndGroups.isUniform` -> `accessMode`; 8.21 `Matrix.decompose()` returns negative `scale.x` for mirrored matrices; 8.22 Tab activates accessibility layer by default (`activateOnTab: false` to disable).
13. **`@pixi/react` v8** (for React 19) requires `extend({ Container, Sprite })` before using `<pixiContainer>`/`<pixiSprite>`; the old `<Stage>`/`<Sprite>` component set from `@pixi/react` v7 is obsolete; root component is `<Application>`.

## Rendering
- WebGL (default), WebGPU (`preference: 'webgpu'`), Canvas. Same scene API for all.
- Display objects: `Sprite`, `AnimatedSprite`, `TilingSprite`, `NineSliceSprite`, `Graphics`, `Text`/`BitmapText`/`HTMLText`, `Mesh`/`MeshPlane`/`MeshRope`, `ParticleContainer` + `Particle`, `RenderLayer` (v8.7+, render order independent of hierarchy).
- Ordering: `zIndex` with `container.sortableChildren = true`, or child order.
- Filters: `BlurFilter`, `ColorMatrixFilter`, `DisplacementFilter`, `AlphaFilter`, `NoiseFilter` in core; more in `pixi-filters`. Masks: `container.mask = graphics` or `setMask({ mask, inverse, channel })` (8.18 added `channel`).
- `RenderTexture` + `app.renderer.render({ container, target })` for offscreen drawing.
- Culling is manual in v8: `cullable = true` + `Culler.shared.cull(...)` or `CullerPlugin`.

## Physics
No built-in support. Do your own AABB/circle math, or integrate third-party libs (Matter.js, Planck.js, Rapier JS) by copying body positions to sprites each tick.

## Input
- Pointer/mouse/touch via federated events: `eventMode`, `on('pointerdown' | 'pointerup' | 'pointertap' | 'pointerover' | 'pointerout' | 'globalpointermove' | 'wheel')`, `hitArea = new Rectangle(...)`.
- Stage-wide: `app.stage.eventMode = 'static'; app.stage.hitArea = app.screen;`.
- Keyboard and gamepad: no built-in support; use `window.addEventListener('keydown', ...)` and the browser Gamepad API.

## UI
- Core gives `Text`, `BitmapText`, `HTMLText`, `NineSliceSprite`, interactive containers.
- `@pixi/ui` (buttons, sliders, checkboxes, scroll boxes, inputs) and `@pixi/layout` (flexbox layout) are official companion packages; or overlay normal HTML/React DOM over the canvas.
- Accessibility: built-in `AccessibilitySystem` (`accessible = true`, `accessibleTitle`).

## Networking and multiplayer
No built-in support. Use WebSocket/WebRTC or libs (Colyseus, socket.io: community).

## Save data
No built-in support. `localStorage` / IndexedDB / backend.

## Performance
- Use spritesheets/atlases so sprites batch; one texture source per batch is cheapest.
- `ParticleContainer` with `Particle` for thousands of simple sprites; set `dynamicProperties` only for what changes.
- `cacheAsTexture(true)` for static complex containers (Graphics-heavy UI).
- Reuse `GraphicsContext` between many identical Graphics.
- Avoid changing `Text` every frame; use `BitmapText`.
- Set `eventMode = 'none'` on non-interactive subtrees to skip hit testing; cull off-screen.
- Destroy textures you load dynamically (`Assets.unload`) to free GPU memory.

## Build and export
- `npm create pixi.js@latest` -> Vite project; `npm run dev`, `npm run build` -> static `dist/`.
- Serve over http(s); assets fetched by URL.
- Native packaging only through third-party wrappers.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `Cannot read properties of undefined (reading 'canvas')` / blank page | Used app before `await app.init()` | Await `init` inside an async function/top-level await |
| `app.view` undefined / deprecated warning | v8 rename | `app.canvas` |
| `beginFill is not a function` | v7 Graphics API | `rect(...).fill(color)` |
| Rotation becomes NaN | Ticker callback treats arg as number | Use `ticker.deltaTime` |
| Clicks do nothing | `eventMode` default is `passive` | `eventMode = 'static'` |
| Drag stops when pointer leaves sprite | v8 `pointermove` only over object | Listen to `globalpointermove` |
| Texture blank from URL | `Texture.from(url)` no longer loads | `await Assets.load(url)` |
| Error adding child to Sprite | Leaf nodes cannot have children | Use a parent `Container` |
| Mirrored sprite tween jumps after 8.21 | `decompose` now gives negative scale.x | Read scale sign instead of skew |
| Blurry pixel art | Linear filtering | `texture.source.scaleMode = 'nearest'` |

## Mapping from Roblox
| Roblox | PixiJS | Notes |
|---|---|---|
| Workspace / Instance tree | `app.stage` Container tree | Pure display graph |
| Part | `Sprite` or `Graphics().rect().fill()` | No physics body |
| Model | `Container` | Leaf nodes cannot parent |
| Script (server) | No equivalent | Browser only |
| LocalScript | Your TS modules | |
| ModuleScript | ES module | |
| RemoteEvent | WebSocket messages | Not built in |
| DataStore | `localStorage` / backend | Not built in |
| Players | Not applicable | |
| Humanoid | Your own player class | No character controller |
| RunService.Heartbeat / RenderStepped | `app.ticker.add((ticker) => ...)` | Also per-object `onRender` |
| TweenService | No core tween; use GSAP or a lib (third-party) | Or lerp in ticker |
| CollectionService tags | `label`, your own registries | |
| Attributes | Plain JS fields on your classes | |
| ScreenGui | Separate UI `Container` above world, `@pixi/ui`, or HTML overlay | |
| UserInputService | Federated pointer events + `window` key events | |
| task.wait | `await` a Promise/timer or count ticker time | |
| Studio playtest | `npm run dev` | |
| Publishing | `npm run build`, host `dist/` | |

## Minimal example
Keyboard movement, AABB pickup, score (PixiJS v8, TypeScript, no asset files).
```ts
import { Application, Graphics, Text, Container } from 'pixi.js';

const app = new Application();
await app.init({ background: '#1d1d2b', width: 800, height: 600 });
document.body.appendChild(app.canvas);

const world = new Container();
app.stage.addChild(world);

const player = new Graphics().rect(-16, -16, 32, 32).fill(0x33aaff);
player.position.set(400, 300);
const coin = new Graphics().circle(0, 0, 10).fill(0xffdd00);
world.addChild(player, coin);

const scoreText = new Text({ text: 'Score: 0', style: { fill: '#ffffff', fontSize: 24 } });
scoreText.position.set(16, 16);
app.stage.addChild(scoreText);

let score = 0;
const keys = new Set<string>();
window.addEventListener('keydown', (e) => keys.add(e.key));
window.addEventListener('keyup', (e) => keys.delete(e.key));

function placeCoin() {
  coin.position.set(40 + Math.random() * 720, 40 + Math.random() * 520);
}
placeCoin();

app.ticker.add((ticker) => {
  const speed = 4 * ticker.deltaTime;
  if (keys.has('ArrowLeft')) player.x -= speed;
  if (keys.has('ArrowRight')) player.x += speed;
  if (keys.has('ArrowUp')) player.y -= speed;
  if (keys.has('ArrowDown')) player.y += speed;
  player.x = Math.max(16, Math.min(784, player.x));
  player.y = Math.max(16, Math.min(584, player.y));

  const dx = Math.abs(player.x - coin.x);
  const dy = Math.abs(player.y - coin.y);
  if (dx < 26 && dy < 26) {
    score += 1;
    scoreText.text = `Score: ${score}`;
    placeCoin();
  }
});
```

## Sources
- https://github.com/pixijs/pixijs/releases (v8.16.0 through v8.22.0 dates and behavior changes)
- https://github.com/pixijs/pixijs/releases/tag/v8.22.0 (v8.22.0 2026-10-01 contents)
- https://raw.githubusercontent.com/pixijs/pixijs/dev/src/__docs__/migrations/v8.md (official v7 -> v8 migration guide: all v8 breaking changes listed)
- https://pixijs.download/release/docs/app.ApplicationOptions.html (init options: preference, resizeTo, background, sharedTicker)
- https://pixijs.download/release/docs/rendering.autoDetectRenderer.html (WebGL prioritized by default)
- https://pixijs.download/release/docs/events.html (eventMode values, pointer events, globalpointermove, hitArea, cursor)
- https://github.com/pixijs/pixi-react (@pixi/react for v8: extend API, Application component, useTick)
- https://pixijs.com/blog/june-2026 (community repost seen via search: v8.18/8.19 features; pixijs.com was not fetchable from this environment)

## Confidence and gaps
- High: v8 API changes (official migration guide), release list/dates, events, Application options.
- Medium: `npm create pixi.js@latest` command, `@pixi/ui`/`@pixi/layout` status, `RenderLayer` version (from prior v8 knowledge; pixijs.com blocked here).
- Year of v8.22.0 date inferred from sequence (v8.16.0 Feb 2026 ... v8.22.0 Oct 1); GitHub page omitted the year.
- No v9 announcement found.
