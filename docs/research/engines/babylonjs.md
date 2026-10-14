# Babylon.js: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 9.30.0 (2026-10-08); major 9.0 released 2026-03-26.** Apache-2.0, free.

## At a glance
| | |
|---|---|
| Best for | Full-featured web 3D games and apps: PBR, physics (Havok), GUI, audio, XR, glTF, Gaussian splats, node-based material/particle/render-graph editors |
| Weak at | No full scene/level editor from the core team (Playground + node editors + Inspector only), no built-in networking or persistence, large bundle unless tree-shaken |
| Language(s) | TypeScript (engine written in TS) and JavaScript |
| Editor / tooling | Playground (online code + run), Inspector (`scene.debugLayer`), Node Material Editor, Node Geometry Editor, Node Particle Editor (9.0), Node Render Graph Editor, GUI Editor, Sandbox (asset viewer). A community "Babylon.js Editor" exists (not core team) |
| Platforms (export) | Browsers (WebGL 2, WebGPU), WebXR; native via Babylon Native; desktop/mobile through Electron/Capacitor wrappers |
| License / cost | Apache-2.0, free |
| Roblox-likeness | medium: scene graph of nodes/meshes, built-in physics, GUI, audio, observables like Roblox events; still code-first and client-only |

## Architecture and lifecycle
- `Engine` (WebGL) or `WebGPUEngine` owns the canvas and GPU; `Scene` holds meshes, lights, cameras, materials; a camera renders the scene.
- Main loop: `engine.runRenderLoop(() => scene.render())`. Per-frame hooks are **Observables**: `scene.onBeforeRenderObservable.add(cb)`, `scene.onAfterRenderObservable`, `scene.onBeforePhysicsObservable`, `scene.onKeyboardObservable`, `scene.onPointerObservable`. `add()` returns an `Observer`; remove with `observable.remove(observer)` or `observer.remove()`.
- `engine.getDeltaTime()` returns **milliseconds**.
- Node hierarchy: `Node` -> `TransformNode` -> `AbstractMesh` -> `Mesh`. `mesh.parent = other`, `getChildren()`, `getChildMeshes()`, `metadata` (free-form).
- Disposal: `mesh.dispose()`, `scene.dispose()`, `engine.dispose()`; `AssetContainer` for loading/unloading groups of assets.
- Coordinate system: left-handed, Y-up by default; `scene.useRightHandedSystem = true` to switch (glTF loader handles conversion with a root node).

## Project layout
Typical npm + Vite (ES6 packages):
```
src/main.ts        engine, scene, game code
public/            .glb, textures, sounds, HavokPhysics.wasm if self-hosted
index.html         <canvas id="renderCanvas">
```
```bash
npm install @babylonjs/core @babylonjs/gui @babylonjs/loaders @babylonjs/havok
npm install -D @babylonjs/inspector vite typescript
```
Packages: `@babylonjs/core`, `@babylonjs/gui`, `@babylonjs/loaders`, `@babylonjs/materials`, `@babylonjs/inspector`, `@babylonjs/havok`, serializers, post-processes. The UMD `babylonjs` packages / CDN (`BABYLON.` global) are the other distribution; do not mix the two in one app.

## Scripting idioms
```ts
import { Engine } from "@babylonjs/core/Engines/engine";
import { Scene } from "@babylonjs/core/scene";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import "@babylonjs/core/Materials/standardMaterial"; // default material side effect

const canvas = document.getElementById("renderCanvas") as HTMLCanvasElement;
const engine = new Engine(canvas, true);
const scene = new Scene(engine);
const camera = new ArcRotateCamera("cam", -Math.PI / 2, 1.1, 12, Vector3.Zero(), scene);
camera.attachControl(canvas, true);
new HemisphericLight("light", new Vector3(0, 1, 0), scene);
const box = MeshBuilder.CreateBox("box", { size: 1 }, scene);

scene.onBeforeRenderObservable.add(() => {
  box.rotation.y += engine.getDeltaTime() / 1000;
});
engine.runRenderLoop(() => scene.render());
window.addEventListener("resize", () => engine.resize());
```
- Deep imports (`@babylonjs/core/Meshes/meshBuilder`) tree-shake; the barrel `import { ... } from "@babylonjs/core"` works but pulls everything. 9.x adds a "pure" barrel (`@babylonjs/core/pure`) that needs explicit registration of side effects (forum announcement; check docs before using).
- Side-effect imports you must not forget: loaders (`import "@babylonjs/loaders/glTF"`), Inspector (`import "@babylonjs/core/Debug/debugLayer"; import "@babylonjs/inspector";`), physics engine component (`Physics/physicsEngineComponent`), default `StandardMaterial`.
- Loading glTF (module-level functions, `SceneLoader` class is marked `@deprecated` in 9.x typings):
  ```ts
  import { ImportMeshAsync, LoadAssetContainerAsync } from "@babylonjs/core/Loading/sceneLoader";
  import "@babylonjs/loaders/glTF";
  const result = await ImportMeshAsync("/models/robot.glb", scene);
  const container = await LoadAssetContainerAsync("/models/level.glb", scene);
  container.addAllToScene();
  ```
- Animation: `AnimationGroup` from glTF (`result.animationGroups[0].start(true)`), `Animation.CreateAndStartAnimation(...)` for simple tweens; 9.0 adds animation retargeting.

## Pitfalls (what AI answers get wrong)
1. **Legacy mesh constructors.** `Mesh.CreateBox(name, size, scene)` (and `CreateSphere`, `CreateGround`...) are `@deprecated` ("Please use MeshBuilder instead"). Use `MeshBuilder.CreateBox("b", { size: 1 }, scene)`.
2. **Physics V1 vs V2.** `PhysicsImpostor` with `CannonJSPlugin`/`AmmoJSPlugin`/`OimoJSPlugin` lives under `Physics/v1` and the docs file it under "Legacy". Current physics is V2 with Havok: `HavokPlugin` + `PhysicsAggregate`/`PhysicsBody`/`PhysicsShape`.
   ```ts
   // WRONG (legacy): sphere.physicsImpostor = new PhysicsImpostor(sphere, PhysicsImpostor.SphereImpostor, { mass: 1 }, scene);
   const havok = await HavokPhysics();
   scene.enablePhysics(new Vector3(0, -9.81, 0), new HavokPlugin(true, havok));
   new PhysicsAggregate(sphere, PhysicsShapeType.SPHERE, { mass: 1, restitution: 0.75 }, scene);
   ```
3. **Havok must be initialized asynchronously.** `HavokPhysics()` returns a Promise (loads WASM, needs WebAssembly SIMD; not on iOS < 16.4). Calling `new HavokPlugin()` before it resolves fails. Pass the instance (`new HavokPlugin(true, instance)`) rather than relying on the `HK` global.
4. **Moving a physics body by setting `mesh.position` does nothing** for V2 bodies: `body.disablePreStep` is `true` by default ("True by default for maximum performance"). Use velocities/impulses (`aggregate.body.setLinearVelocity`, `applyImpulse`), set `disablePreStep = false` for teleports, or use `PhysicsMotionType.ANIMATED` for kinematic bodies.
5. **`scene.registerBeforeRender(fn)`** still exists but the observable API (`scene.onBeforeRenderObservable.add`) is idiomatic and removable; prefer it.
6. **`SceneLoader.ImportMesh(...)` callbacks** are legacy; the `SceneLoader` class is `@deprecated` in 9.x typings. Use `ImportMeshAsync(source, scene, options)`, `AppendSceneAsync`, `LoadAssetContainerAsync`, `LoadSceneAsync`. Lower-case variants (`appendSceneAsync`) are deprecated aliases.
7. **Missing side-effect imports in ES6 builds** cause errors like "...needs to be imported before as it contains a side-effect required by your code" or silent missing features (no glTF loader, no Inspector, no picking). Add the specific import.
8. **Mixing `babylonjs` (UMD) with `@babylonjs/core` (ES6)** gives two copies of the engine and `instanceof` failures; the UMD Inspector is not compatible with ES6 builds.
9. **WebGPU engine is async.** `const engine = new WebGPUEngine(canvas); await engine.initAsync();` (check `await WebGPUEngine.IsSupportedAsync`, or use `EngineFactory.CreateAsync`). Texture `readPixels` returns a Promise. Pass `xrCompatible: true` at construction if WebXR is needed.
10. **GUI is a separate package.** `AdvancedDynamicTexture` comes from `@babylonjs/gui`, not core. `BABYLON.GUI.*` only exists in the UMD build.
11. **Audio V2 (8.0+).** New code uses `CreateAudioEngineAsync()` and `CreateSoundAsync(name, url, options)`; the legacy `new Sound(...)` path requires the old audio engine (`audioEngine: true` engine option). Audio unlock waits for a user gesture. (Forum/typings sourced; doc page not fetched.)
12. **TypeScript decorators (9.15.0):** Babylon moved to TC39 stage-3 decorators; set `experimentalDecorators: false` if your own classes use Babylon decorators like `@serialize`, and `@expandToProperty` needs `accessor` fields. UMD bundles now target ES2015.
13. **Camera rotation in right-handed scenes changed in 8.10.1** (no more 180° Y offset on `TargetCamera.rotation`).
14. **`engine.getDeltaTime()` is milliseconds**, not seconds; physics units are meters/kg/seconds.

## Rendering
- WebGL 2 `Engine` and `WebGPUEngine` (docs: "WebGPU implementation is complete" with minor exceptions such as point sizes and triangle fans).
- Materials: `StandardMaterial`, `PBRMaterial`, initial OpenPBR material (9.0), `NodeMaterial` (Node Material Editor), `ShaderMaterial` (GLSL, or WGSL on WebGPU).
- Lighting: `HemisphericLight`, `DirectionalLight`, `PointLight`, `SpotLight`, area lights (8.0) with textured area lights (9.0), Clustered Lighting (9.0, WebGPU and WebGL 2), volumetric lighting (9.0).
- Shadows: `new ShadowGenerator(1024, light)` + `shadowGenerator.addShadowCaster(mesh)` + `ground.receiveShadows = true`; `CascadedShadowGenerator` for large scenes.
- Frame Graph (v1 in 9.0): DAG-based render pipeline, editable in the Node Render Graph Editor or in code.
- Post-processing: `DefaultRenderingPipeline` (bloom, FXAA, tone mapping, DOF), SSAO2, SSR.
- Gaussian splatting: `.ply`, `.splat`, `.spz`, `.sog/.sogs` (9.0), shadows and merging.
- Particles: `ParticleSystem`, `GPUParticleSystem`, Node Particle Editor (9.0), flow maps and attractors.

## Physics
Physics V2 with Havok (`@babylonjs/havok`, 1.3.14). Concepts: `PhysicsBody` (motion type DYNAMIC/STATIC/ANIMATED), `PhysicsShape` (box, sphere, capsule, mesh, convex hull, container), `PhysicsMaterial`, `PhysicsAggregate` (convenience: body + shape + material in one, "works like Physics Plugin V1 Impostors").
```ts
import HavokPhysics from "@babylonjs/havok";
import { HavokPlugin } from "@babylonjs/core/Physics/v2/Plugins/havokPlugin";
import { PhysicsAggregate } from "@babylonjs/core/Physics/v2/physicsAggregate";
import { PhysicsShapeType } from "@babylonjs/core/Physics/v2/IPhysicsEnginePlugin";
import "@babylonjs/core/Physics/physicsEngineComponent";

const hk = new HavokPlugin(true, await HavokPhysics());
scene.enablePhysics(new Vector3(0, -9.81, 0), hk);
new PhysicsAggregate(ground, PhysicsShapeType.BOX, { mass: 0 }, scene);
const ball = new PhysicsAggregate(sphere, PhysicsShapeType.SPHERE, { mass: 1, restitution: 0.6 }, scene);
ball.body.applyImpulse(new Vector3(0, 5, 0), sphere.absolutePosition);
hk.onCollisionObservable.add((ev) => console.log(ev.collider.transformNode.name, ev.collidedAgainst.transformNode.name));
```
- Character controller: `PhysicsCharacterController(position, shapeOptions, scene)` with `checkSupport`, `setVelocity`, `integrate`, `calculateMovement` (9.30 typings).
- Collision callbacks per body: `body.setCollisionCallbackEnabled(true)` then `body.getCollisionObservable()` (or plugin-wide `onCollisionObservable`). Triggers: `shape.isTrigger = true` + `hk.onTriggerCollisionObservable` (plugin typings).
- Raycast: `hk.raycast(from, to, result, query?)` with a `PhysicsRaycastResult`; non-physics picking via `scene.pick` / `scene.pickWithRay`.
- Legacy V1 (Cannon/Ammo/Oimo + `PhysicsImpostor`) still ships under `Physics/v1` for old projects only.

## Input
- `scene.onKeyboardObservable.add((kb) => { if (kb.type === KeyboardEventTypes.KEYDOWN) ... kb.event.key })`.
- `scene.onPointerObservable.add((pi) => { if (pi.type === PointerEventTypes.POINTERDOWN) pi.pickInfo?.pickedMesh })`.
- `DeviceSourceManager` for unified keyboard/mouse/touch/gamepad polling; `GamepadManager`.
- Cameras have built-in inputs (`camera.attachControl(canvas, true)`; `UniversalCamera` WASD via `keysUp/keysDown/...`).
- `ActionManager` with triggers (`OnPickTrigger`, `OnIntersectionEnterTrigger`) is older but still present.

## UI
`@babylonjs/gui`: 2D fullscreen (`AdvancedDynamicTexture.CreateFullscreenUI("ui")`) or mesh-attached (`CreateForMesh`) UI; controls `Button.CreateSimpleButton`, `TextBlock`, `StackPanel`, `Grid`, `Slider`, `InputText`, `Image`; events `onPointerUpObservable`/`onPointerClickObservable`; `idealWidth`/`idealHeight` for resolution-independent scaling; GUI Editor produces JSON loaded with `ParseFromSnippetAsync`/`parseFromURLAsync`. 3D GUI (`GUI3DManager`) for XR. HTML overlays also work.

## Networking and multiplayer
No built-in support. Use Colyseus, Socket.IO, WebRTC, or a custom WebSocket server; you write server authority. Babylon can run headless with `NullEngine` in Node (useful for server-side simulation).

## Save data
No built-in support. `localStorage`/IndexedDB or a backend. Scene serialization: `SceneSerializer.Serialize(scene)` (from `@babylonjs/core/Misc/sceneSerializer`); glTF export via `@babylonjs/serializers`. Offline asset caching via `Database` (IndexedDB) optional.

## Performance
- Inspector Statistics pane (draw calls, frame time); `SceneInstrumentation`/`EngineInstrumentation`.
- `mesh.freezeWorldMatrix()`, `material.freeze()`, `scene.freezeActiveMeshes()` for static content; `scene.skipPointerMovePicking = true`.
- Instances: `mesh.createInstance()`, thin instances (`thinInstanceAdd`) for thousands of copies; `Mesh.MergeMeshes`.
- `scene.performancePriority = ScenePerformancePriority.Aggressive` (trades features for speed).
- Texture compression (KTX2/Basis), glTF Draco/Meshopt; LOD with `addLODLevel`.
- Tree-shake with deep imports to cut bundle size (docs example: ~2.3 MB -> ~700 KB).
- Snapshot rendering on WebGPU for static scenes.

## Build and export
Vite/webpack bundle to static files; host anywhere. Playground snippets can be downloaded as a project. Babylon Native for native app embedding; Electron/Capacitor wrappers for stores. Serve the Havok `.wasm` alongside the bundle (Vite handles `@babylonjs/havok` imports; some bundlers need it excluded from pre-bundling, community advice).

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| "X needs to be imported before as it contains a side-effect" | Missing side-effect import in ES6 build | Import the named module (loaders, debugLayer, physicsEngineComponent...) |
| glTF load fails "Unable to find a plugin to load .glb files" | Loader not imported | `import "@babylonjs/loaders/glTF"` |
| `scene.debugLayer.show()` throws | Inspector not imported | `import "@babylonjs/core/Debug/debugLayer"; import "@babylonjs/inspector";` |
| Physics objects ignore `mesh.position` changes | `disablePreStep` true | Use velocity/impulse or set `body.disablePreStep = false` |
| `HavokPlugin` errors / undefined HK | Havok not awaited | `const hk = new HavokPlugin(true, await HavokPhysics())` |
| `PhysicsImpostor` code does nothing with Havok | V1 API with V2 plugin | Port to `PhysicsAggregate` |
| Movement speed depends on FPS | Using fixed increments | Multiply by `engine.getDeltaTime() / 1000` |
| WebGPU black canvas | `initAsync()` not awaited | `await engine.initAsync()` before creating the scene |
| Blurry canvas on HiDPI | Default hardware scaling | `new Engine(canvas, true, { adaptToDeviceRatio: true })` |
| GUI button not clickable | Covered by other control / pointer blocker | Set `isPointerBlocker`, check `zIndex` and layer order |
| Two engines / instanceof fails | UMD + ES6 mix or duplicate versions | Use one distribution and one version of all `@babylonjs/*` packages |
| No audio | Audio locked until gesture | `await audioEngine.unlockAsync()` after a click |

## Mapping from Roblox
| Roblox | Babylon.js | Notes |
|---|---|---|
| Workspace / Instance tree | `Scene` + `Node`/`TransformNode`/`Mesh` hierarchy (`parent`) | |
| Part | `MeshBuilder.CreateBox(...)` + `PhysicsAggregate` | Anchored -> `mass: 0` (static) |
| Model | `TransformNode` parent, or loaded glTF `__root__` | |
| Script / LocalScript | TS/JS modules in the browser (client only) | No server runtime |
| ModuleScript | ES module | |
| RemoteEvent | WebSocket messages (Colyseus/Socket.IO) | |
| DataStore | localStorage/IndexedDB or backend | |
| Players | No concept; your netcode | |
| Humanoid | `PhysicsCharacterController` + `AnimationGroup`s | |
| RunService.Heartbeat | `scene.onBeforeRenderObservable` / `onBeforePhysicsObservable` | Delta in ms |
| RenderStepped | `scene.onBeforeRenderObservable` | |
| TweenService | `Animation.CreateAndStartAnimation`, `AnimationGroup` | |
| CollectionService tags | `Tags.AddTagsTo(mesh, "coin")` + `scene.getMeshesByTags("coin")` | Tags system exists in core |
| Attributes | `node.metadata` | glTF extras land in metadata |
| ScreenGui | `AdvancedDynamicTexture.CreateFullscreenUI` | |
| UserInputService | `scene.onKeyboardObservable`, `onPointerObservable`, `DeviceSourceManager` | |
| task.wait | `await Tools.DelayAsync(ms)` or `setTimeout`/Promise | |
| Studio playtest | Playground or `npx vite` + Inspector | |
| Publishing | Bundle and host static files | |

## Minimal example
`src/main.ts` (Babylon 9.x, ES6, Havok). Arrow keys/WASD push a ball; touching a coin scores.
```ts
import { Engine } from "@babylonjs/core/Engines/engine";
import { Scene } from "@babylonjs/core/scene";
import { FollowCamera } from "@babylonjs/core/Cameras/followCamera";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { KeyboardEventTypes } from "@babylonjs/core/Events/keyboardEvents";
import { HavokPlugin } from "@babylonjs/core/Physics/v2/Plugins/havokPlugin";
import { PhysicsAggregate } from "@babylonjs/core/Physics/v2/physicsAggregate";
import { PhysicsShapeType } from "@babylonjs/core/Physics/v2/IPhysicsEnginePlugin";
import "@babylonjs/core/Physics/physicsEngineComponent";
import "@babylonjs/core/Materials/standardMaterial";
import { AdvancedDynamicTexture } from "@babylonjs/gui/2D/advancedDynamicTexture";
import { TextBlock } from "@babylonjs/gui/2D/controls/textBlock";
import { Control } from "@babylonjs/gui/2D/controls/control";
import HavokPhysics from "@babylonjs/havok";

const canvas = document.getElementById("renderCanvas") as HTMLCanvasElement;
const engine = new Engine(canvas, true);
const scene = new Scene(engine);
new HemisphericLight("light", new Vector3(0, 1, 0), scene);

scene.enablePhysics(new Vector3(0, -9.81, 0), new HavokPlugin(true, await HavokPhysics()));

const ground = MeshBuilder.CreateGround("ground", { width: 40, height: 40 }, scene);
new PhysicsAggregate(ground, PhysicsShapeType.BOX, { mass: 0 }, scene);

const player = MeshBuilder.CreateSphere("player", { diameter: 1 }, scene);
player.position.y = 1;
const playerPhys = new PhysicsAggregate(player, PhysicsShapeType.SPHERE, { mass: 1, friction: 0.8 }, scene);

const coins = Array.from({ length: 8 }, (_, i) => {
  const c = MeshBuilder.CreateTorus(`coin${i}`, { diameter: 0.8, thickness: 0.15 }, scene);
  c.position.set(Math.random() * 30 - 15, 0.6, Math.random() * 30 - 15);
  return c;
});

const camera = new FollowCamera("cam", new Vector3(0, 8, -12), scene, player);
camera.radius = 12;
camera.heightOffset = 6;

const ui = AdvancedDynamicTexture.CreateFullscreenUI("ui");
const label = new TextBlock("score", "Score: 0");
label.color = "white";
label.fontSize = 28;
label.textHorizontalAlignment = Control.HORIZONTAL_ALIGNMENT_LEFT;
label.textVerticalAlignment = Control.VERTICAL_ALIGNMENT_TOP;
label.paddingLeft = "12px";
label.paddingTop = "12px";
ui.addControl(label);

const keys = new Set<string>();
scene.onKeyboardObservable.add((kb) => {
  const k = kb.event.key.toLowerCase();
  if (kb.type === KeyboardEventTypes.KEYDOWN) keys.add(k); else keys.delete(k);
});

let score = 0;
scene.onBeforeRenderObservable.add(() => {
  const dt = engine.getDeltaTime() / 1000;
  const x = (keys.has("d") || keys.has("arrowright") ? 1 : 0) - (keys.has("a") || keys.has("arrowleft") ? 1 : 0);
  const z = (keys.has("w") || keys.has("arrowup") ? 1 : 0) - (keys.has("s") || keys.has("arrowdown") ? 1 : 0);
  playerPhys.body.applyImpulse(new Vector3(x, 0, z).scale(6 * dt), player.absolutePosition);

  for (let i = coins.length - 1; i >= 0; i--) {
    coins[i].rotation.y += 3 * dt;
    if (coins[i].intersectsMesh(player, false)) {
      coins[i].dispose();
      coins.splice(i, 1);
      label.text = `Score: ${++score}`;
    }
  }
});

engine.runRenderLoop(() => scene.render());
window.addEventListener("resize", () => engine.resize());
```
(Top-level `await` needs an ES2022 module target, which Vite provides.)

## Sources
- https://github.com/BabylonJS/Babylon.js/releases (9.23-9.30 release list; none flagged breaking)
- https://registry.npmjs.org/@babylonjs/core (9.30.0 on 2026-10-08; 9.0.0 on 2026-03-26; 8.0.0 on 2025-03-27)
- https://blogs.windows.com/windowsdeveloper/2026/03/26/announcing-babylon-js-9-0/ (9.0 features: Clustered Lighting, Frame Graph v1, Node Particle Editor, splats, retargeting, new inspector)
- https://doc.babylonjs.com/breaking-changes (9.15.0 decorators/ES2015, 8.10.1 camera, 8.2.0 translucency, 7.0 changes)
- https://doc.babylonjs.com/features/featuresDeepDive/physics/usingPhysicsEngine (HavokPlugin, PhysicsAggregate, PhysicsShapeType)
- https://doc.babylonjs.com/features/featuresDeepDive/physics/havokPlugin (@babylonjs/havok install, HavokPhysics(), new HavokPlugin(true, instance), SIMD requirement)
- https://doc.babylonjs.com/legacy/physics/usingPhysicsEngine (V1 plugins filed under Legacy, Physics/v1 paths)
- https://doc.babylonjs.com/setup/frameworkPackages/es6Support (package names, side-effect imports, tree shaking, Inspector import)
- https://doc.babylonjs.com/setup/support/webGPU/webGPUStatus and https://doc.babylonjs.com/setup/support/webGPU/webGPUBreakingChanges (WebGPU completeness, initAsync, async readPixels, xrCompatible)
- https://doc.babylonjs.com/features/featuresDeepDive/gui/gui (AdvancedDynamicTexture, Button, TextBlock, idealWidth)
- https://doc.babylonjs.com/features/featuresDeepDive/importers/loadingFileTypes (module-level loaders; SceneLoader legacy)
- https://unpkg.com/@babylonjs/core@9.30.0/ typings: Physics/v2/*.d.ts, Loading/sceneLoader.d.ts, Meshes/mesh.pure.d.ts, scene.pure.d.ts (disablePreStep default, SceneLoader @deprecated, Mesh.CreateBox @deprecated, PhysicsCharacterController)
- https://forum.babylonjs.com/t/audio-engine-v2-usage/56965 (community/maintainer forum: CreateAudioEngineAsync, CreateSoundAsync, unlock)
- https://forum.babylonjs.com/t/pure-barrel-for-better-tree-shaking-in-babylonjs-core/63455 (forum: @babylonjs/core/pure)

## Confidence and gaps
- High: versions/dates, Havok V2 setup, PhysicsAggregate, deprecated `Mesh.CreateBox` and `SceneLoader`, ES6 side-effect imports, WebGPU async init, GUI basics.
- Medium: Audio V2 API (forum + typings, doc page 404'd); `@babylonjs/core/pure` registration rules; 9.0 "all-new inspector" details (API for it not verified, `scene.debugLayer.show()` still documented).
- Verified in 9.30 typings: `Tools.DelayAsync`, `onTriggerCollisionObservable`, `raycast(from,to,result,query?)`, `Tags.AddTagsTo`, `getMeshesByTags`. Babylon.js Editor is community-maintained; its status not checked.
