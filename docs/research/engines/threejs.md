# Three.js: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: r186 (npm `three@0.186.0` 2026-09-08; patch `0.186.1` 2026-09-24).** MIT license, free.

## At a glance
| | |
|---|---|
| Best for | Browser 3D rendering: product viewers, data viz, portfolio sites, small web games, WebXR, custom render pipelines |
| Weak at | Being a game engine: no editor-driven workflow, no built-in physics, UI, networking, audio mixer, save system or scene format beyond JSON/glTF |
| Language(s) | JavaScript (ES modules); TypeScript via community `@types/three` (0.186.0) |
| Editor / tooling | No game editor. Online scene editor at threejs.org/editor (basic). Vite recommended by the manual. Browser devtools |
| Platforms (export) | Any modern browser (WebGL 2 via `WebGLRenderer`; WebGPU with WebGL 2 fallback via `WebGPURenderer`); desktop/mobile via wrappers (Electron, Capacitor, Tauri) |
| License / cost | MIT, free |
| Roblox-likeness | low: a rendering library with a scene graph (Object3D tree resembles the Instance tree), but you write the game loop, physics, input and networking yourself |

## Architecture and lifecycle
- A **renderer** (`WebGLRenderer` or `WebGPURenderer`) draws a **Scene** (root `Object3D`) from a **Camera** each frame.
- Scene graph: every node is an `Object3D` with `position`, `rotation`/`quaternion`, `scale`, `children`, `parent`, `add()`, `remove()`, `traverse()`, `getObjectByName()`, `userData` (free-form object, like Attributes).
- Renderables: `Mesh(geometry, material)`, `InstancedMesh`, `BatchedMesh`, `Points`, `Line`, `Sprite`. Geometry is always `BufferGeometry` (the legacy `Geometry` class was removed from core in r125).
- Loop: `renderer.setAnimationLoop(fn)` (preferred; required for WebXR, and auto-awaits WebGPU init). The callback receives a DOMHighResTimeStamp in ms.
- Time: `THREE.Timer` (core since r179; `Clock` deprecated in r183). Call `timer.update(timestamp)` once per frame, then `timer.getDelta()` (seconds). `timer.connect(document)` re-enables Page Visibility handling (opt-in since r174).
- No component system, no scripts attached to objects. Game logic is plain JS you organise yourself (classes, ECS libs such as miniplex/koota/bitECS, or react-three-fiber components).
- Resources (geometries, materials, textures, render targets) are **not garbage collected on the GPU**; call `.dispose()`.

## Project layout
Recommended (manual, "Installation"): npm + Vite.
```
my-game/
  index.html          <script type="module" src="/main.js">
  main.js             import * as THREE from 'three'
  public/             textures, .glb models, audio (served unchanged)
  package.json        "three", devDependency "vite"
```
```bash
npm install --save three
npm install --save-dev vite
npx vite          # dev server on http://localhost:5173
npx vite build    # production bundle in dist/
```
No-build alternative: an import map pointing `three` to `.../three@<version>/build/three.module.js` and `three/addons/` to `.../three@<version>/examples/jsm/`, served by a local static server (`npx serve .`). Opening the HTML file directly from disk breaks module/texture loading.

Package exports (0.186.1 `package.json`): `three`, `three/webgpu`, `three/tsl`, `three/addons`, `three/addons/*`. The CommonJS build is deprecated in r186 and minified builds were removed.

## Scripting idioms
```js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;            // PCFShadowMap is the default type
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 500);
camera.position.set(0, 5, 10);
const controls = new OrbitControls(camera, renderer.domElement);

scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 2));
const sun = new THREE.DirectionalLight(0xffffff, 3);
sun.position.set(5, 10, 5);
sun.castShadow = true;
scene.add(sun);

const { scene: model } = await new GLTFLoader().loadAsync('/models/robot.glb');
model.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
scene.add(model);

const timer = new THREE.Timer();
timer.connect(document);
renderer.setAnimationLoop((t) => {
  timer.update(t);
  const dt = timer.getDelta();
  model.rotation.y += dt;
  controls.update();
  renderer.render(scene, camera);
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
```
- Textures used as color (`map`, `emissiveMap`) need `texture.colorSpace = THREE.SRGBColorSpace` when loaded with `TextureLoader`; `GLTFLoader` sets it for you. Data textures (normal, roughness) stay `NoColorSpace`.
- Reuse geometries/materials across meshes; use `InstancedMesh` for many copies.
- Raycasting for picking: `const ray = new THREE.Raycaster(); ray.setFromCamera(ndc, camera); ray.intersectObjects(scene.children, true)`.
- Animation of glTF clips: `const mixer = new THREE.AnimationMixer(model); mixer.clipAction(gltf.animations[0]).play(); mixer.update(dt)` each frame.
- WebGPU path: `import * as THREE from 'three/webgpu'` and `import { ... } from 'three/tsl'`; `new THREE.WebGPURenderer({ antialias: true })`; node materials (`MeshStandardNodeMaterial`) and TSL for custom shaders.

## Pitfalls (what AI answers get wrong)
1. **`THREE.Geometry` / `Face3` are gone (r125).** Use `BufferGeometry` with `setAttribute('position', new THREE.Float32BufferAttribute(arr, 3))`.
   ```js
   // WRONG (pre-r125): const g = new THREE.Geometry(); g.vertices.push(new THREE.Vector3());
   const g = new THREE.BufferGeometry();
   g.setAttribute('position', new THREE.Float32BufferAttribute([0,0,0, 1,0,0, 0,1,0], 3));
   ```
2. **`BoxBufferGeometry`, `SphereBufferGeometry`, ... aliases** were deprecated in r144 and are gone from current builds. Use `BoxGeometry`, `SphereGeometry`, etc.
3. **Color management renames (r152):** `renderer.outputEncoding` -> `renderer.outputColorSpace` (default `SRGBColorSpace`); `texture.encoding` -> `texture.colorSpace`; `sRGBEncoding` -> `SRGBColorSpace`; `LinearEncoding` -> `LinearSRGBColorSpace`. `ColorManagement.enabled` is true by default. r177 renamed `ColorManagement.fromWorkingColorSpace/toWorkingColorSpace` to `workingToColorSpace/colorSpaceToWorking`.
4. **Legacy lights removed:** `physicallyCorrectLights` -> `useLegacyLights` (r150) -> deprecated/false by default (r155) -> no longer exists in `WebGLRenderer` (r186 source has no `useLegacyLights`). Light intensities are physical; old tutorials' `PointLight(0xffffff, 1)` looks far too dark. Raise intensity or set `decay`/`distance` deliberately.
5. **`examples/js` and global `THREE.OrbitControls` are gone (r148).** Import addons as modules: `import { OrbitControls } from 'three/addons/controls/OrbitControls.js'`. `build/three.js` / `three.min.js` were removed in r161; r186 removes the remaining minified builds and deprecates CommonJS.
6. **`PCFSoftShadowMap` removed (r186).** Deprecated r182; r186 warns and silently uses `PCFShadowMap`. Do not set `renderer.shadowMap.type = THREE.PCFSoftShadowMap`; leave default or use `VSMShadowMap`, and soften with `light.shadow.radius`/map size.
7. **`Clock` deprecated (r183)** in favor of `Timer` (in core since r179). `Timer` needs `update(timestamp)` every frame; `getDelta()` without `update()` returns 0.
8. **WebGPURenderer is async.** Use `setAnimationLoop`, or `await renderer.init()` before calling `render()` from your own `requestAnimationFrame`/init code. `renderAsync()`-style methods were deprecated in r181. `ShaderMaterial`, `RawShaderMaterial`, `onBeforeCompile` and `EffectComposer` are **not supported** in `WebGPURenderer`; port to node materials/TSL and its node post-processing (`PostProcessing` was renamed `RenderPipeline` in r183). The manual still describes the renderer as "experimental"; `WebGLRenderer` remains the recommended choice for pure WebGL 2 apps.
9. **Imports for WebGPU/TSL (r171):** `three/webgpu` and `three/tsl`, not deep `examples/jsm/nodes/...` paths from 2023 tutorials. TSL renames: `PI2` -> `TWO_PI` (r181), `varying()` -> `toVarying()` (r173), `TextureNode.uv()` -> `.sample()` (r172), `label()` -> `setName()` (r179).
10. **Removing from scene does not free GPU memory.** Call `geometry.dispose()`, `material.dispose()`, `texture.dispose()`, `renderTarget.dispose()`; controls and renderers are unusable after `dispose()`. r186 adds `Object3D.dispose()` which only fires a `dispose` event (subclasses must call `super.dispose()`); it does not dispose geometry/material for you.
11. **Loader renames:** `RGBELoader` -> `HDRLoader` (r180); `RGBMLoader` removed; `FileLoader.load()` returns nothing since r184 (use the callback or `loadAsync`). `TransformControls` must be added via `scene.add(controls.getHelper())` (r169).
12. **Renamed misc:** `CapsuleGeometry(radius, length)` param is now `height` (r176); `TextGeometry` `height` -> `depth` (r163); `Source` -> `TextureSource` (r186); `LightProbeGrid` -> `LightProbeGridWebGL` (r186); `mergeBufferGeometries` -> `mergeGeometries` (r151); WebGL 1 support removed (r163).
13. **Matrix3 helpers:** `Matrix3.translate/scale/rotate` deprecated (r185). Camera view matrix excludes scale since r183.
14. **Resize:** forgetting `camera.updateProjectionMatrix()` after changing `aspect`/`fov` gives stretched output.

## Rendering
- `WebGLRenderer` (WebGL 2 only since r163): stable, supports `ShaderMaterial`, `EffectComposer` post-processing from `three/addons/postprocessing/`.
- `WebGPURenderer` (`three/webgpu`): WebGPU backend with automatic WebGL 2 fallback (`forceWebGL: true` to force). Node materials + TSL compile to WGSL or GLSL. Node post-processing (`RenderPipeline`, `pass()`, bloom/SSGI/SSR/TRAA nodes). Compute shaders (`computeAsync` deprecated r181; `compileComputeAsync` added r186). WebXR support added r185.
- Materials: `MeshStandardMaterial`/`MeshPhysicalMaterial` (PBR), `MeshLambertMaterial`, `MeshPhongMaterial` (these two gained `scene.environment` IBL in r183), `MeshBasicMaterial` (unlit), `MeshToonMaterial`.
- Environment: `scene.environment = pmremTexture` for IBL, `scene.background`, `scene.environmentIntensity` (r163). `RoomEnvironment` addon for a quick neutral environment.
- Tone mapping: `renderer.toneMapping = THREE.ACESFilmicToneMapping` (or `AgXToneMapping`, `NeutralToneMapping`); applies only when rendering to screen.
- Shadows: `renderer.shadowMap.enabled = true`; per light `castShadow`, per mesh `castShadow`/`receiveShadow`; tune `light.shadow.camera` bounds and `shadow.bias`. r186 adds `SunLight` with cascaded shadow maps.
- Assets: glTF/GLB via `GLTFLoader` (+ `DRACOLoader`, `KTX2Loader`, `MeshoptDecoder`). Gaussian splats: `GaussianSplat` and `GaussianSplatPLYLoader` (names from r186 release notes; unverified beyond the notes).

## Physics
No built-in physics. Manual "Physics" page lists three approaches:
1. Addon wrappers in `examples/jsm/physics/`: `AmmoPhysics`, `JoltPhysics`, `RapierPhysics` (quick start, limited).
2. JS libraries: `cannon-es` (MIT; manual notes it is "apparently no longer maintained"; npm latest 0.20.0 from 2022), `phy`.
3. WASM engines directly: Rapier (`@dimforge/rapier3d` or `-compat`, 0.21.0 Sep 2026), JoltPhysics.js, PhysX, Ammo.js.

Pattern: step the physics world at a fixed rate and copy body transforms to meshes.
```js
import RAPIER from '@dimforge/rapier3d-compat';
await RAPIER.init();
const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
world.createCollider(RAPIER.ColliderDesc.cuboid(10, 0.1, 10));               // static ground
const body = world.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(0, 4, 0));
world.createCollider(RAPIER.ColliderDesc.cuboid(0.5, 0.5, 0.5), body);
// per frame:
world.step();
const p = body.translation(), q = body.rotation();
mesh.position.set(p.x, p.y, p.z);
mesh.quaternion.set(q.x, q.y, q.z, q.w);
```
React: `@react-three/rapier` (community, pmndrs). Simple games can use `Box3.intersectsBox` / `Sphere` checks or the `Capsule`/`Octree` addons (`examples/jsm/math/`) used by the official FPS example.

## Input
No input system. Use DOM events: `keydown`/`keyup` into a `Set`, `pointermove`, `pointerdown` on `renderer.domElement`, Gamepad API (`navigator.getGamepads()`), `PointerLockControls` addon for FPS look. Picking with `Raycaster`.

## UI
No in-engine UI. Use HTML/CSS overlays (absolute-positioned DOM over the canvas), `CSS2DRenderer`/`CSS3DRenderer` addons for labels attached to 3D objects, `lil-gui` (`three/addons/libs/lil-gui.module.min.js`) for debug panels, or React DOM with r3f + `@react-three/drei` `<Html>`. r184/r185 add `HTMLTexture` (HTML-in-canvas texture; experimental browser feature).

## Networking and multiplayer
No built-in support. Use WebSocket/WebRTC libraries (Colyseus, Socket.IO, geckos.io, PeerJS) and implement server authority yourself (Node server holding the true state).

## Save data
No built-in support. `localStorage` / IndexedDB in the browser, or your own backend. Scene serialization: `object.toJSON()` + `ObjectLoader` (JSON format 4.7 since r177), or `GLTFExporter`.

## Performance
- Watch `renderer.info` (draw calls, triangles, geometries/textures in memory).
- Batch: `InstancedMesh`, `BatchedMesh`, `BufferGeometryUtils.mergeGeometries`; share materials.
- Cap pixel ratio (`Math.min(devicePixelRatio, 2)`); limit shadow-casting lights and shadow map size.
- Compress assets: Draco/Meshopt geometry, KTX2 textures.
- Avoid allocating `Vector3`/`Quaternion` every frame; keep scratch objects.
- Dispose GPU resources on level change; `renderer.compileAsync(scene, camera)` to pre-warm shaders.
- Render on demand for non-game apps (only call `render()` on change).
- stats.js / `stats-gl` for FPS.

## Build and export
`npx vite build` -> static `dist/` that any static host can serve (GitHub Pages, Netlify, itch.io HTML upload). Desktop via Electron/Tauri, mobile via Capacitor or a WebView. Keep `public/` asset paths absolute (`/models/x.glb`) or use `import.meta.env.BASE_URL` when hosting under a sub-path.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Black screen, no errors | No light with a lit material, or camera inside/behind object | Add lights or use `MeshBasicMaterial`; move camera; `camera.lookAt(0,0,0)` |
| `THREE.Geometry is not a constructor` | Code written for < r125 | Port to `BufferGeometry` |
| `BoxBufferGeometry is not a constructor` | Removed alias | `BoxGeometry` |
| Textures look washed out / too dark | Wrong color space | `tex.colorSpace = THREE.SRGBColorSpace` for color maps; keep default `outputColorSpace` |
| Scene much darker than tutorial | Physical light units (legacy lights removed) | Increase intensities; check `decay` |
| `Failed to resolve module specifier "three"` | Bare import without bundler/import map | Use Vite or add an import map |
| `OrbitControls is not a constructor` / `THREE.OrbitControls undefined` | Old global addon usage | `import { OrbitControls } from 'three/addons/controls/OrbitControls.js'` |
| CORS error loading .glb | Opened file:// | Serve with `npx vite` / `npx serve .` |
| Memory grows each level | GPU resources not disposed | Traverse old scene and `dispose()` geometry/material/textures |
| Stretched image after resize | Missing `updateProjectionMatrix()` | Update aspect + projection + `setSize` in resize handler |
| WebGPU: nothing renders on first frame | Rendering before init | `setAnimationLoop` or `await renderer.init()` |
| Custom ShaderMaterial invisible in WebGPURenderer | Not supported there | Use `WebGLRenderer` or port to TSL node material |
| Shadow acne / peter-panning | Bias | Tune `light.shadow.bias` / `normalBias`; tighten shadow camera |
| Warning "PCFSoftShadowMap has been removed" | r186 | Use `PCFShadowMap` (default) or `VSMShadowMap` |

## Mapping from Roblox
| Roblox | Three.js | Notes |
|---|---|---|
| Workspace / Instance tree | `Scene` / `Object3D` tree (`add`, `children`, `parent`) | No services; you own everything |
| Part | `Mesh(new BoxGeometry(), new MeshStandardMaterial())` | No collision unless you add physics |
| Model | `Group` (or loaded glTF scene) | `PrimaryPart` -> pick a child or use the group transform |
| Script / LocalScript | Plain ES modules running in the browser (all "client") | No server unless you write one |
| ModuleScript | ES module `export`/`import` | |
| RemoteEvent | WebSocket messages (Colyseus/Socket.IO) | Build server authority yourself |
| DataStore | `localStorage`/IndexedDB or your backend | |
| Players | No concept; your network layer tracks players | |
| Humanoid | No equivalent; character controller + `AnimationMixer` | Rapier has a KinematicCharacterController |
| RunService.Heartbeat / RenderStepped | `renderer.setAnimationLoop(cb)` + `Timer.getDelta()` | Single loop; run fixed-step physics inside |
| TweenService | No built-in; `three/addons/libs/tween.module.js` or GSAP, or `AnimationMixer` | |
| CollectionService tags | `object.userData.tags` + `traverse()`, or `layers`, or an ECS | |
| Attributes | `object.userData` | Exported to glTF extras |
| ScreenGui | HTML/CSS overlay; `CSS2DRenderer` | |
| UserInputService | DOM `keydown`/`pointer*`/Gamepad API | |
| task.wait | `await new Promise(r => setTimeout(r, ms))` or timers in the loop | |
| Studio playtest | `npx vite` dev server + browser devtools | |
| Publishing | `npx vite build` then host `dist/` | |

## Minimal example
`main.js` (r186, WebGLRenderer, npm + Vite). WASD moves a cube; touching coins scores.
```js
import * as THREE from 'three';

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87ceeb);
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 200);
scene.add(new THREE.HemisphereLight(0xffffff, 0x556655, 2.5));

const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: 0x55aa55 }));
ground.rotation.x = -Math.PI / 2;
scene.add(ground);

const player = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x3366ff }));
player.position.y = 0.5;
scene.add(player);

const coinGeo = new THREE.CylinderGeometry(0.4, 0.4, 0.1, 24);
const coinMat = new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.6, roughness: 0.3 });
const coins = [];
for (let i = 0; i < 10; i++) {
  const c = new THREE.Mesh(coinGeo, coinMat);
  c.position.set(THREE.MathUtils.randFloatSpread(30), 0.6, THREE.MathUtils.randFloatSpread(30));
  c.rotation.x = Math.PI / 2;
  scene.add(c);
  coins.push(c);
}

const hud = Object.assign(document.createElement('div'), { textContent: 'Score: 0' });
hud.style.cssText = 'position:fixed;top:8px;left:8px;font:20px sans-serif;color:#fff';
document.body.appendChild(hud);

const keys = new Set();
addEventListener('keydown', (e) => keys.add(e.code));
addEventListener('keyup', (e) => keys.delete(e.code));

const timer = new THREE.Timer();
timer.connect(document);
const move = new THREE.Vector3();
const playerBox = new THREE.Box3();
const coinBox = new THREE.Box3();
let score = 0;

renderer.setAnimationLoop((t) => {
  timer.update(t);
  const dt = timer.getDelta();
  move.set((keys.has('KeyD') ? 1 : 0) - (keys.has('KeyA') ? 1 : 0), 0,
           (keys.has('KeyS') ? 1 : 0) - (keys.has('KeyW') ? 1 : 0));
  if (move.lengthSq() > 0) player.position.addScaledVector(move.normalize(), 8 * dt);

  playerBox.setFromObject(player);
  for (let i = coins.length - 1; i >= 0; i--) {
    const c = coins[i];
    c.rotation.z += 3 * dt;
    if (playerBox.intersectsBox(coinBox.setFromObject(c))) {
      scene.remove(c);           // geometry/material are shared, so do not dispose them here
      coins.splice(i, 1);
      hud.textContent = `Score: ${++score}`;
    }
  }
  camera.position.set(player.position.x, 10, player.position.z + 12);
  camera.lookAt(player.position);
  renderer.render(scene, camera);
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
```
react-three-fiber note: `@react-three/fiber` 9.x (peer React `>=19 <19.4`, three `>=0.156`) wraps the same objects as JSX (`<mesh>`, `<boxGeometry>`), uses `useFrame((state, delta) => ...)` instead of `setAnimationLoop`, and disposes objects on unmount automatically.

## Sources
- https://github.com/mrdoob/three.js/releases (r183-r186 release notes and dates)
- https://github.com/mrdoob/three.js/releases/tag/r186 (PCFSoftShadowMap removal, TextureSource rename, Object3D.dispose, CommonJS deprecation, minified builds removed)
- https://github.com/mrdoob/three.js/wiki/Migration-Guide (r125 Geometry removal, r144 BufferGeometry aliases, r148 examples/js removal, r152 color management, r155 useLegacyLights, r161-r186 renames)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/installation.html (npm + Vite, import map, local server)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/webgpurenderer.html (three/webgpu import, WebGL 2 fallback, init/setAnimationLoop, unsupported ShaderMaterial/onBeforeCompile/EffectComposer, experimental status)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/physics.html (AmmoPhysics/JoltPhysics/RapierPhysics addons, cannon-es maintenance status, WASM engines)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/how-to-dispose-of-objects.html (dispose rules, renderer.info)
- https://raw.githubusercontent.com/mrdoob/three.js/r186/src/core/Timer.js and .../src/core/Clock.js (Timer API; Clock deprecation warning r183)
- https://raw.githubusercontent.com/mrdoob/three.js/r186/src/renderers/WebGLRenderer.js and .../webgl/WebGLShadowMap.js (outputColorSpace default, no useLegacyLights, PCFSoftShadowMap fallback warning)
- https://registry.npmjs.org/three (version/date, package exports) and https://registry.npmjs.org/@react-three/fiber (9.8.1 peer deps)
- https://rapier.rs/docs/user_guides/javascript/getting_started_js (World, RigidBodyDesc, ColliderDesc, step)

## Confidence and gaps
- High: version/dates, migration renames, color management, WebGPU usage rules, dispose rules (official wiki, manual and r186 source).
- Medium: GaussianSplat class names (release-notes titles only). `HTMLTexture` depends on an experimental browser API.
- Rapier `-compat` `init()` pattern is from the Rapier docs plus common usage; the docs page shows the non-compat dynamic `import()` form.
- Not verified: r187 timing (none released as of 2026-10-13); `@react-three/rapier` and drei current versions.
