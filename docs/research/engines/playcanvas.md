# PlayCanvas: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: engine 2.23.2 (2026-10-09); 2.23.0 on 2026-10-01; major 2.0.0 on 2024-08-22.** Engine MIT and free; cloud Editor has Free ($0), Personal ($15/mo) and Organization ($50/seat/mo) plans.

## At a glance
| | |
|---|---|
| Best for | Lightweight browser 3D games, playable ads, product configurators, Gaussian-splat scenes, team editing in a browser editor |
| Weak at | Native console/desktop targets, large open worlds, built-in multiplayer/persistence (none), physics only via ammo.js |
| Language(s) | JavaScript and TypeScript (engine ships `.d.ts`); ESM scripts (`.mjs`) recommended, Classic scripts still supported |
| Editor / tooling | Cloud-hosted collaborative Editor (scene, assets, scripts, Launch tab), VS Code extension (pull/push), Editor MCP server; or engine-only via npm + Vite (`npm create playcanvas@latest`) |
| Platforms (export) | Web (WebGL 2, WebGPU); downloadable static builds; wrap for mobile/desktop with Capacitor/Electron/Cordova (community path) |
| License / cost | Engine MIT; Editor freemium (public projects free, private projects on paid plans per plans FAQ) |
| Roblox-likeness | medium-high: collaborative online editor, entity hierarchy with components, scripts attached to entities with `initialize`/`update`, built-in rigidbody/collision, in-canvas UI elements; but client-only, no hosted servers or data stores |

## Architecture and lifecycle
- Entity-Component system: `pc.Entity` nodes in a hierarchy under `app.root`; behaviour comes from components (`render`, `camera`, `light`, `rigidbody`, `collision`, `script`, `element`, `screen`, `sound`, `anim`, `gsplat`, `particlesystem`, ...).
- `AppBase`/`Application` runs the loop: input -> `update(dt)` on all scripts -> physics fixed steps (1/60 s, interpolated) -> `postUpdate(dt)` -> render. App-level events: `app.on('update', dt => ...)`.
- Script lifecycle (docs "Script Lifecycle"): `initialize()` (once, after attributes set and entity enabled), `postInitialize()` (after all initialize), `update(dt)` (seconds), `postUpdate(dt)`, and `destroy` event (`this.once('destroy', ...)`). Also `enable`/`disable` events. Scripts on one entity run in component list order. Avoid constructors for startup logic.
- Two script formats:
  - **ESM scripts** (`.mjs`, recommended): `class X extends Script { static scriptName = 'x'; ... }`, attributes via `/** @attribute */` JSDoc on class fields.
  - **Classic scripts** (`.js`): `var X = pc.createScript('x'); X.attributes.add(...); X.prototype.update = function (dt) {}`. Still supported "for the foreseeable future".
  - The pre-2016 "legacy scripting system" was removed in engine 2.0 (do not confuse with Classic scripts).
- Editor projects load scripts automatically; engine-only projects must register ESM classes (`registerScript(Class, undefined, app)` or `app.scripts.add(Class)`) to attach by name, or pass the class: `entity.script.create(Class)`.

## Project layout
Editor project: assets panel (models, textures, `.mjs` scripts, templates), scenes, settings (physics: IMPORT AMMO), Launch tab for playtest, build/download from the project dashboard.

Engine-only (official "Using the Engine Standalone"):
```bash
npm create playcanvas@latest my-app -- -f engine   # Vite + TypeScript starter
# or
npm install playcanvas
npm install vite --save-dev
npx vite
```
```
index.html     <canvas id="application">, <script type="module" src="main.js">
main.js        import * as pc from 'playcanvas'
public/        glb, textures, ammo/ammo.wasm.js + ammo.wasm.wasm + ammo.js
```
Other front ends over the same engine: `@playcanvas/react` (0.11.7, React 18.3/19.1, components `<Application>`, `<Entity>`, `<Camera>`, `<Render>`, `<Light>`, hooks `useModel`, `useApp`, physics via `usePhysics` + `sync-ammo`) and `@playcanvas/web-components` (0.28.0, `<pc-app>`, `<pc-scene>`, `<pc-entity>`, `<pc-camera>`, `<pc-render>`, `<pc-rigid-body>`, `<pc-wasm>`).

## Scripting idioms
ESM script (docs "ESM Scripts", "ESM Reference"):
```js
import { Script, Vec3, KEY_W, KEY_A, KEY_S, KEY_D } from 'playcanvas';

export class PlayerMove extends Script {
    static scriptName = 'playerMove';

    /**
     * Movement speed in units per second.
     *
     * @attribute
     */
    speed = 5;

    initialize() {
        this._dir = new Vec3();
        this.once('destroy', () => { /* unsubscribe here */ });
    }

    update(dt) {
        const kb = this.app.keyboard;
        this._dir.set(
            (kb.isPressed(KEY_D) ? 1 : 0) - (kb.isPressed(KEY_A) ? 1 : 0),
            0,
            (kb.isPressed(KEY_S) ? 1 : 0) - (kb.isPressed(KEY_W) ? 1 : 0)
        );
        if (this._dir.lengthSq() > 0) {
            this._dir.normalize().mulScalar(this.speed * dt);
            this.entity.translate(this._dir);
        }
    }
}
```
- Attributes are plain class fields; the Editor needs a "Parse" after changes. ESM attributes are passed by reference (not copied) and do not fire `attr:name` events.
- No load order for ESM scripts: use `import`/`export` instead of globals.
- Find things: `this.app.root.findByName('Player')`, `findByTag('coin')`, `entity.tags.add('coin')`, `entity.script.playerMove` (script instance by name).
- Events: `this.app.fire('score', n)` / `this.app.on('score', fn)`; `on()` returns an `EventHandle` with `.off()`. Remove listeners in the `destroy` handler.
- Spawning: `const e = template.resource.instantiate(); this.app.root.addChild(e);` or `entity.clone()` (initialize runs when added to the hierarchy).

## Pitfalls (what AI answers get wrong)
1. **Classic vs ESM.** Many answers only know `pc.createScript('name')` + prototype methods. That still works, but new code should be ESM: `import { Script } from 'playcanvas'; export class X extends Script { static scriptName = 'x'; }` in a `.mjs` file. `ScriptType` is `@deprecated` ("Use Script instead") in 2.23 typings.
   ```js
   // Classic (still supported):
   var Rotate = pc.createScript('rotate');
   Rotate.attributes.add('speed', { type: 'number', default: 10 });
   Rotate.prototype.update = function (dt) { this.entity.rotate(0, this.speed * dt, 0); };
   // ESM (recommended):
   import { Script } from 'playcanvas';
   export class Rotate extends Script {
       static scriptName = 'rotate';
       /** @attribute */
       speed = 10;
       update(dt) { this.entity.rotate(0, this.speed * dt, 0); }
   }
   ```
2. **ESM attributes use JSDoc `@attribute`, not `X.attributes.add`** and not TS decorators. Mixing the two styles in one class does nothing useful.
3. **Engine 2.0 dropped WebGL 1**, the pre-2016 legacy script system, `AudioSourceComponent` (use `SoundComponent`), `BasicMaterial` (use `StandardMaterial` emissive), `Layer.renderTarget` (set render target on the camera), and the `pc.apps/pc.common/pc.config/pc.data/pc.type` namespaces. Deprecation warnings from 1.x became hard removals.
4. **Gamma, tone mapping and fog moved (2.x):** they are per camera now (`camera.gammaCorrection`, `camera.toneMapping`), and fog is `scene.fog.type/color/start/end` instead of `scene.fogColor`, `scene.fogEnd`.
5. **Colors are sRGB and color textures need sRGB formats** (`PIXELFORMAT_SRGBA8` / sRGB encoding on texture assets) since 2.0; StandardMaterial tint flags were removed and tint always applies (emissive defaults to black, so set `emissive` to white when using an emissive map/video).
6. **`ShaderMaterial` no longer auto-injects gamma/tonemap/fog (2.5.0).** Include `gammaCorrectOutput`, `toneMap`, `addFog` yourself. `new pc.Material()` cannot be instantiated; use `ShaderMaterial`.
7. **Physics is opt-in.** Without ammo.js loaded, `rigidbody`/`collision` components are inert with no error. Editor: Settings > Physics > IMPORT AMMO. Engine-only: `pc.WasmModule.setConfig('Ammo', {...})` + `getInstance` before creating the app, and include `CollisionComponentSystem`/`RigidBodyComponentSystem` when using `AppBase`.
8. **Do not move dynamic bodies by setting entity position**; physics overwrites it each step. Use `applyForce`, `applyImpulse`, `linearVelocity`, or `rigidbody.teleport(...)`. Kinematic/static bodies are moved via the entity transform.
9. **Gravity:** `app.systems.rigidbody.gravity.set(0, -9.81, 0)`; the older `setGravity()` is deprecated. 2.23 adds per-body `gravityScale`.
10. **Model vs Render component.** Old answers use `addComponent('model', {type:'box'})` and `asset.resource.model`; current docs use `render` components (`addComponent('render', { type: 'box' })`) and glTF container assets (`asset.resource.instantiateRenderEntity()`).
11. **Collision events**: `entity.collision.on('collisionstart' | 'contact' | 'collisionend', cb)`; triggers (collision without rigidbody) fire `triggerenter`/`triggerleave`. Events fire per physics step, not per frame. Static/kinematic pairs never collide.
12. **Engine-only apps must register ESM scripts by class** before `entity.script.create('name')`, otherwise the name lookup fails.
13. **2.22/2.23 changes:** wire drawing methods removed from `AppBase`, frustum planes stored in a typed array, `ParticleSystemComponent.noFog` deprecated for `useFog`, physics public API "tightened" in 2.23, immediate mesh rendering removed.

## Rendering
- `pc.createGraphicsDevice(canvas, { deviceTypes: [pc.DEVICETYPE_WEBGPU] })` prefers WebGPU and falls back to WebGL 2; `new pc.Application(canvas)` creates a WebGL 2 device for you.
- `StandardMaterial` (PBR, metalness or specular workflow), `ShaderMaterial` (GLSL and WGSL variants), clustered lighting, shadows (cascades for directional lights), `CameraFrame` post-processing (bloom, SSAO, DOF, TAA, color grading).
- glTF via container assets; Draco/Basis compression; lightmapper; batching (`BatchGroup`); hardware instancing.
- **Gaussian splats** are first-class: `gsplat` component, `.ply`/compressed/SOG formats, LOD streaming (2.20 example streams 250M splats), GPU sorting, splat shadows; SuperSplat editor and splat-transform tools.
- WebXR via `XrManager` (`app.xr`).

## Physics
ammo.js (Bullet) via components. Body types `'static' | 'dynamic' | 'kinematic'` (`BODYTYPE_*`). Collision shapes `box`, `sphere`, `capsule`, `cylinder`, `cone`, `mesh`, `compound`. Joint component is alpha.
```js
// engine-only setup
pc.WasmModule.setConfig('Ammo', {
    glueUrl: 'ammo/ammo.wasm.js', wasmUrl: 'ammo/ammo.wasm.wasm', fallbackUrl: 'ammo/ammo.js'
});
await new Promise((resolve) => pc.WasmModule.getInstance('Ammo', resolve));
const app = new pc.Application(canvas);

const ball = new pc.Entity('ball');
ball.addComponent('render', { type: 'sphere' });
ball.addComponent('collision', { type: 'sphere', radius: 0.5 });
ball.addComponent('rigidbody', { type: 'dynamic', mass: 1, restitution: 0.5 });
app.root.addChild(ball);
ball.rigidbody.applyImpulse(0, 5, 0);
const hit = app.systems.rigidbody.raycastFirst(new pc.Vec3(0, 10, 0), new pc.Vec3(0, -10, 0));
```
Alternatives (Rapier, Jolt) are listed in the docs but have no official integration; the `PhysicsWorld` backend layer (alpha) is the intended seam.

## Input
`app.keyboard.isPressed(pc.KEY_W)` (held), `wasPressed` (this frame), `app.keyboard.on(pc.EVENT_KEYDOWN, cb)`; `app.mouse.on(pc.EVENT_MOUSEDOWN, cb)`, pointer lock via `app.mouse.enablePointerLock()`; `app.touch`; `app.gamepads` (2.23 polls per frame). Picking with `camera.camera.screenToWorld` + `raycastFirst`, or the framebuffer `Picker`. Ready-made `CameraControls` script ships with the engine.

## UI
In-canvas UI: `screen` component (root, screen-space or world-space) + `element` components (`image`, `text`, `group`) + `button`, `layoutgroup`, `scrollview`, `scrollbar`. Text uses MSDF font assets. HTML/CSS overlays are the alternative for forms, text input and accessibility. React and Web Components expose `<Screen>`/`<Element>` and `<pc-screen>`/`<pc-element>`.

## Networking and multiplayer
No built-in support. Use Colyseus, Photon, Socket.IO or custom WebSockets/WebRTC from scripts; the server is yours. The engine runs headless in Node.js (2.23: "headless Node.js support without jsdom"), useful for server simulation.

## Save data
No built-in support. `localStorage`/IndexedDB or a backend. Editor scenes are stored in the cloud project, not at runtime.

## Performance
- MiniStats (`new pc.MiniStats(app)`) and the profiler build; Chrome devtools.
- Batching and instancing; texture compression (Basis); Draco meshes; asset preloading flags; lightmaps instead of realtime lights.
- Keep per-frame allocations out of `update` (reuse `Vec3`s).
- Limit shadow casters; use LOD for splats (`gsplat` LOD budgets in 2.22/2.23).
- `app.setCanvasResolution(pc.RESOLUTION_AUTO)` and cap device pixel ratio (`device.maxPixelRatio`) on mobile.

## Build and export
Editor: download a self-contained build (zip) or host on PlayCanvas from the project dashboard; also release to playable-ad networks. Engine-only: `npx vite build` and host `dist/` anywhere. Native app stores via a WebView wrapper (community route).

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Rigidbody does nothing, no errors | ammo.js not loaded | Editor: IMPORT AMMO; engine: `WasmModule.setConfig` + wait before creating app |
| Entity snaps back after setting position | Dynamic body owned by physics | `rigidbody.teleport()` or forces/velocity |
| `script 'x' is not found` / create by name fails | ESM class not registered (engine-only) | `app.scripts.add(X)` or `entity.script.create(X)` |
| Global variable undefined across scripts | ESM module scope | `export`/`import` the value |
| Attribute change in Editor not visible | Script not re-parsed | Click Parse on the script asset |
| Emissive map / video texture black | Emissive tint black by default | Set `material.emissive = pc.Color.WHITE`; `material.update()` |
| Material change not visible | Forgot `material.update()` | Call `update()` after changing StandardMaterial props |
| Custom shader errors `gammaCorrectOutput` missing | 2.5 ShaderMaterial change | Include the functions explicitly |
| Colors too bright/washed out | Linear/sRGB mismatch | Use sRGB formats for color textures; colors are sRGB |
| Collision events never fire | Both bodies static/kinematic, or missing collision component | Make one body dynamic; add `collision` |
| Code from 1.x uses `pc.app` / `model` component | Removed/legacy APIs | Use `this.app`, `render` component, container assets |

## Mapping from Roblox
| Roblox | PlayCanvas | Notes |
|---|---|---|
| Workspace / Instance tree | `app.root` Entity hierarchy | Editor hierarchy panel |
| Part | Entity + `render` (box) + `collision` + `rigidbody` | Anchored -> `type: 'static'` |
| Model | Parent Entity or Template asset | Templates ~ packages/prefabs |
| Script / LocalScript | ESM `Script` attached via `script` component | All client-side |
| ModuleScript | `.mjs` module with `export` | |
| RemoteEvent | WebSocket messages (Colyseus etc.) | |
| DataStore | localStorage / your backend | |
| Players | No concept; netcode | |
| Humanoid | Kinematic/dynamic capsule + `anim` component state graph | |
| RunService.Heartbeat | `update(dt)` / `app.on('update')` | dt in seconds |
| RenderStepped | `postUpdate(dt)` / `app.on('postupdate')` | |
| TweenService | No engine tween; animate in `update`, `anim` component, or a tween library | |
| CollectionService tags | `entity.tags.add('coin')`, `app.root.findByTag('coin')` | Built in |
| Attributes | Script attributes (`@attribute` fields) | Editable per entity in the Editor |
| ScreenGui | `screen` + `element` components | |
| UserInputService | `app.keyboard`, `app.mouse`, `app.touch`, `app.gamepads` | |
| task.wait | `setTimeout`/Promise, or timers in `update` | |
| Studio playtest | Editor Launch tab (or `npx vite`) | |
| Publishing | Editor build/download or host; engine-only `vite build` | |

## Minimal example
Engine-only `main.js` (playcanvas 2.23, ammo in `public/ammo/`). WASD rolls a ball; coins are triggers that add score.
```js
import * as pc from 'playcanvas';
import { Script } from 'playcanvas';

pc.WasmModule.setConfig('Ammo', {
    glueUrl: '/ammo/ammo.wasm.js', wasmUrl: '/ammo/ammo.wasm.wasm', fallbackUrl: '/ammo/ammo.js'
});
await new Promise((resolve) => pc.WasmModule.getInstance('Ammo', resolve));

const canvas = document.getElementById('application');
const app = new pc.Application(canvas, {
    keyboard: new pc.Keyboard(window)
});
app.setCanvasFillMode(pc.FILLMODE_FILL_WINDOW);
app.setCanvasResolution(pc.RESOLUTION_AUTO);
window.addEventListener('resize', () => app.resizeCanvas());

class Roll extends Script {
    static scriptName = 'roll';
    /** @attribute */
    force = 20;
    score = 0;

    initialize() {
        this.app.on('coin', () => { this.score++; this.app.fire('score:changed', this.score); });
    }

    update(dt) {
        const kb = this.app.keyboard;
        const x = (kb.isPressed(pc.KEY_D) ? 1 : 0) - (kb.isPressed(pc.KEY_A) ? 1 : 0);
        const z = (kb.isPressed(pc.KEY_S) ? 1 : 0) - (kb.isPressed(pc.KEY_W) ? 1 : 0);
        if (x || z) this.entity.rigidbody.applyForce(x * this.force, 0, z * this.force);
    }
}

const ground = new pc.Entity('ground');
ground.addComponent('render', { type: 'box' });
ground.addComponent('collision', { type: 'box', halfExtents: new pc.Vec3(20, 0.5, 20) });
ground.addComponent('rigidbody', { type: 'static' });
ground.setLocalScale(40, 1, 40);
ground.setPosition(0, -0.5, 0);
app.root.addChild(ground);

const ball = new pc.Entity('ball');
ball.addComponent('render', { type: 'sphere' });
ball.addComponent('collision', { type: 'sphere', radius: 0.5 });
ball.addComponent('rigidbody', { type: 'dynamic', mass: 1 });
ball.addComponent('script');
ball.script.create(Roll);
ball.setPosition(0, 1, 0);
app.root.addChild(ball);

for (let i = 0; i < 8; i++) {
    const coin = new pc.Entity('coin');
    coin.tags.add('coin');
    coin.addComponent('render', { type: 'cylinder' });
    coin.addComponent('collision', { type: 'sphere', radius: 0.5 }); // no rigidbody -> trigger volume
    coin.setLocalScale(0.8, 0.1, 0.8);
    coin.setPosition(Math.random() * 30 - 15, 0.5, Math.random() * 30 - 15);
    coin.collision.on('triggerenter', (other) => {
        if (other.name !== 'ball') return;
        app.fire('coin');
        coin.destroy();
    });
    app.root.addChild(coin);
}

const camera = new pc.Entity('camera');
camera.addComponent('camera', { clearColor: new pc.Color(0.5, 0.7, 0.9) });
app.root.addChild(camera);
const light = new pc.Entity('light');
light.addComponent('light', { type: 'directional', castShadows: true });
light.setEulerAngles(45, 30, 0);
app.root.addChild(light);

const hud = document.createElement('div');
hud.style.cssText = 'position:fixed;top:8px;left:8px;color:#fff;font:20px sans-serif';
hud.textContent = 'Score: 0';
document.body.appendChild(hud);
app.on('score:changed', (s) => { hud.textContent = `Score: ${s}`; });

app.on('update', () => {
    const p = ball.getPosition();
    camera.setPosition(p.x, p.y + 8, p.z + 12);
    camera.lookAt(p);
});

app.start();
```

## Sources
- https://github.com/playcanvas/engine/releases (2.22.0-2.23.2 notes and dates; 2.22 breaking changes)
- https://github.com/playcanvas/engine/releases/tag/v2.0.0 (2.0 breaking changes: WebGL1, legacy scripts, AudioSourceComponent, BasicMaterial, namespaces)
- https://github.com/playcanvas/engine/releases/tag/v2.23.0 (useFog, physics API tightening, removals)
- https://registry.npmjs.org/playcanvas (2.23.2 on 2026-10-09; 2.0.0 on 2024-08-22); https://registry.npmjs.org/@playcanvas/react ; https://registry.npmjs.org/@playcanvas/web-components
- https://developer.playcanvas.com/user-manual/scripting/esm-scripts/ (via raw source https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/scripting/esm-scripts.md: Script class, .mjs, registerScript)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/scripting/migration-guide.md (Classic still supported, module scope, no load order, attributes by reference)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/scripting/script-lifecycle.md (initialize/postInitialize/update/postUpdate/destroy)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/scripting/script-attributes/esm.md (`@attribute` JSDoc)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/engine/standalone.md (npm + Vite, create playcanvas, createGraphicsDevice, AppBase/AppOptions)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/engine/migrations.md (1.x -> 2.x and 2.5 migration notes)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/physics/physics-basics.md, .../physics/collision-events.md, .../physics/ammo-alternatives.md, .../physics/forces-and-impulses.md (ammo loading, gravity property, fixed step, events, alternatives)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/user-interface/index.md (screen/element/button components)
- https://raw.githubusercontent.com/playcanvas/developer-site/main/docs/user-manual/react/index.mdx and .../web-components/index.md (React and Web Components front ends)
- https://unpkg.com/playcanvas@2.23.2/build/playcanvas.d.ts (Script, ScriptType @deprecated, gravityScale, BODYTYPE_*, KEY_W, GSplatComponent, raycastFirst)
- https://playcanvas.com/plans (Editor plan prices)

## Confidence and gaps
- High: versions/dates, ESM vs Classic scripts, 2.0 breaking changes, physics setup and events, standalone setup.
- Medium: Editor plan details (plans page is ambiguous on private projects for Free); `model` component is still in typings, "prefer render" is from current docs usage, not an explicit deprecation.
- Checked in 2.23.2 typings: `Application` options accept `keyboard: new Keyboard(window)`; `Mouse#enablePointerLock`; `instantiateRenderEntity`.
- Not verified: Editor build/download UI wording; playable-ad export details; WebGPU default in the Editor (a forum question in the 2.20 thread was unanswered).
