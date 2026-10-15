---
name: engine-threejs
description: Three.js r186 (2026) browser 3D library with ES modules, WebGLRenderer or WebGPURenderer and TSL. Use for any Three.js or react-three-fiber code question.
---
# engine-threejs
## Scope
Three.js r186 (npm three 0.186.x, Sep 2026). Check the project's version first (package.json or import map); APIs are renamed often.
## Core model
- Renderer (WebGLRenderer, or WebGPURenderer from 'three/webgpu' with WebGL 2 fallback) draws a Scene from a Camera.
- Scene graph of Object3D: Mesh(BufferGeometry, Material), Group, lights, cameras; userData holds custom data.
- One loop: renderer.setAnimationLoop(cb); time via THREE.Timer (update(t) then getDelta()).
- No physics, UI, input, networking or saves built in.
- GPU resources are freed only by dispose().
## Idioms
- import * as THREE from 'three'; addons from 'three/addons/...js' (OrbitControls, GLTFLoader).
- npm install three + Vite, or an import map + local server (never file://).
- Color maps loaded by TextureLoader: tex.colorSpace = THREE.SRGBColorSpace; keep default renderer.outputColorSpace.
- Shadows: renderer.shadowMap.enabled = true, light.castShadow, mesh.castShadow/receiveShadow.
- Physics: step a Rapier world at a fixed rate, copy body transforms to meshes.
- react-three-fiber 9 (React 19): useFrame((state, delta)) replaces setAnimationLoop.
## Pitfalls
1. THREE.Geometry, Face3 and geometry.vertices were removed in r125: use BufferGeometry + setAttribute.
2. BoxBufferGeometry and other *BufferGeometry aliases are gone: use BoxGeometry, SphereGeometry.
3. outputEncoding, texture.encoding, sRGBEncoding were replaced in r152 by outputColorSpace, colorSpace, SRGBColorSpace.
4. physicallyCorrectLights / useLegacyLights no longer exist; lights use physical units, so old intensities look dark.
5. examples/js globals (THREE.OrbitControls) were removed in r148; build/three.min.js removed in r161. Import addons as modules.
6. PCFSoftShadowMap was removed in r186 (falls back to PCFShadowMap with a warning). Use the default or VSMShadowMap.
7. Clock is deprecated since r183: use THREE.Timer and call timer.update(timestamp) each frame.
8. WebGPURenderer initializes async: use setAnimationLoop or await renderer.init() first. ShaderMaterial, onBeforeCompile and EffectComposer do not work there; use node materials and TSL.
9. WebGPU/TSL imports are 'three/webgpu' and 'three/tsl' (r171); PostProcessing was renamed RenderPipeline (r183).
10. scene.remove does not free memory: dispose geometry, material, textures, render targets. Object3D.dispose (r186) only fires an event.
11. RGBELoader is HDRLoader (r180); CapsuleGeometry length is height (r176); Source is TextureSource (r186).
12. No WebGL 1 since r163; CommonJS build deprecated in r186.
## Roblox to Three.js
- Workspace / Instance tree -> Scene / Object3D tree (add, children, parent)
- Part -> Mesh(BoxGeometry, MeshStandardMaterial); Model -> Group or glTF scene
- Script/LocalScript/ModuleScript -> browser ES modules (client only)
- RemoteEvent -> WebSocket messages to your own server; DataStore -> localStorage or backend
- Heartbeat/RenderStepped -> setAnimationLoop + Timer.getDelta()
- TweenService -> AnimationMixer or tween.module.js addon
- CollectionService/Attributes -> userData
- ScreenGui -> HTML/CSS overlay or CSS2DRenderer; UserInputService -> DOM key/pointer events
- Studio playtest -> npx vite; shipping -> npx vite build and host dist/
## Skeleton
```js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 200);
camera.position.set(0, 4, 8);
const controls = new OrbitControls(camera, renderer.domElement);

const sun = new THREE.DirectionalLight(0xffffff, 3);
sun.position.set(5, 10, 5);
sun.castShadow = true;
scene.add(sun, new THREE.AmbientLight(0xffffff, 0.5));

const cube = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x3366ff }));
cube.castShadow = true;
scene.add(cube);

const timer = new THREE.Timer();
renderer.setAnimationLoop((t) => {
  timer.update(t);
  cube.rotation.y += timer.getDelta();
  controls.update();
  renderer.render(scene, camera);
});
```
## Verification
Run npx vite, open the localhost URL, read the browser console (deprecation warnings print there), watch renderer.info.memory for leaks; tsc if using @types/three. Say "not run" if you only wrote the code.
