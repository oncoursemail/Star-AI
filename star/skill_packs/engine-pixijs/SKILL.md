---
name: engine-pixijs
description: PixiJS v8 2D WebGL/WebGPU renderer for JS/TS. Use for Pixi apps, sprites, Graphics, Assets, ticker, events, and v7->v8 migration.
---
# engine-pixijs
## Scope
PixiJS v8 (8.22 as of Oct 2026). Check the project's version first (`package.json` "pixi.js"); v7 code (sync Application, beginFill, @pixi/* packages) is wrong for v8. PixiJS is a renderer, not a full engine: no physics, scenes, audio core, editor or networking.
## Core model
- `Application` = renderer + `stage` (root `Container`) + `ticker`; create, then `await app.init({...})`, then append `app.canvas`.
- Everything is a `Container`; leaf nodes (`Sprite`, `Graphics`, `Text`) cannot have children in v8.
- Per frame: `app.ticker.add((ticker) => ...)` with `ticker.deltaTime` (frame-scaled) or `ticker.deltaMS`.
- Assets load through the promise-based `Assets` API; WebGL is the default renderer, WebGPU via `preference: 'webgpu'`.
## Idioms
- `const tex = await Assets.load('/assets/hero.png'); const s = new Sprite(tex); s.anchor.set(0.5);`
- Graphics: `new Graphics().rect(0, 0, 100, 40).fill(0xff0000).stroke({ width: 2, color: 'white' })`.
- Text: `new Text({ text: 'Score: 0', style: { fill: '#fff', fontSize: 24 } })`; `BitmapText` for per-frame changes.
- Pointer: `s.eventMode = 'static'; s.cursor = 'pointer'; s.on('pointertap', fn)`; drag with `globalpointermove`.
- Keyboard: plain `window` keydown/keyup listeners (Pixi has none).
- Layers as Containers (world, ui); own scene manager and AABB checks.
- `destroy({ children: true })`; `Assets.unload` frees textures.
## Pitfalls
1. `new Application({ width, height })` used synchronously is v7: v8 needs `await app.init({...})`.
2. `app.view` -> `app.canvas`.
3. `beginFill/drawRect/endFill/lineStyle` are v7: use `rect().fill()`, `circle()`, `stroke({...})`, holes with `cut()`.
4. Import only from `'pixi.js'`; `@pixi/app`, `@pixi/graphics` sub-packages are v7. Filters extras: `pixi-filters/<name>`.
5. `PIXI.Loader` / `app.loader` are gone; `Texture.from(url)` no longer loads URLs: `await Assets.load(url)` first.
6. Ticker callback gets a `Ticker`, not a number: `(ticker) => ticker.deltaTime`.
7. `sprite.addChild(...)` fails on leaf nodes in v8: use a parent `Container`.
8. `new Text('hi', style)` -> `new Text({ text: 'hi', style })`; filters/TilingSprite/Mesh constructors take option objects.
9. `interactive = true` / `buttonMode` -> `eventMode = 'static'` + `cursor`; default eventMode is `'passive'`.
10. Removed/renamed: `DisplayObject`, `BaseTexture` -> `TextureSource`, `cacheAsBitmap` -> `cacheAsTexture(true)`, `settings` -> `AbstractRenderer.defaultOptions`, `getBounds().rectangle`, `name` -> `label`, `NineSlicePlane` -> `NineSliceSprite`.
11. ParticleContainer v8 takes `Particle` via `addParticle`, not Sprites.
12. Recent minors: 8.21 `Matrix.decompose` gives negative `scale.x` for mirrored matrices; 8.20 `isUniform` -> `accessMode`; `@pixi/react` v8 needs `extend({...})` and `<Application>`.
## Roblox to PixiJS
- Workspace tree -> `app.stage` Container tree
- Part -> `Sprite` or `Graphics` (no physics body)
- Model -> `Container`
- LocalScript/ModuleScript -> ES modules; server Script -> none
- RemoteEvent -> WebSocket; DataStore -> `localStorage`/backend
- Heartbeat/RenderStepped -> `app.ticker.add`
- TweenService -> lerp in ticker or a tween library
- ScreenGui -> UI Container above world, `@pixi/ui`, or HTML overlay
- UserInputService -> pointer events + window key events
- task.wait -> await a timer Promise
- Studio playtest -> `npm run dev`; shipping -> `npm run build`
## Skeleton
```ts
import { Application, Assets, Sprite, Container, Text } from 'pixi.js';

const app = new Application();
await app.init({ background: '#1d1d2b', resizeTo: window });
document.body.appendChild(app.canvas);

const world = new Container();
app.stage.addChild(world);
const hero = new Sprite(await Assets.load('/assets/hero.png'));
hero.anchor.set(0.5);
hero.position.set(app.screen.width / 2, app.screen.height / 2);
world.addChild(hero);

const label = new Text({ text: 'Score: 0', style: { fill: '#ffffff', fontSize: 24 } });
app.stage.addChild(label);

const keys = new Set<string>();
window.addEventListener('keydown', (e) => keys.add(e.key));
window.addEventListener('keyup', (e) => keys.delete(e.key));

app.ticker.add((ticker) => {
  const v = 5 * ticker.deltaTime;
  if (keys.has('ArrowLeft')) hero.x -= v;
  if (keys.has('ArrowRight')) hero.x += v;
});
```
## Verification
Run `npm install`, `npm run dev` and check the browser console and canvas; `npx tsc --noEmit` for types; `npm run build` for a release bundle. Report only checks you actually ran.
