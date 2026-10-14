---
name: engine-babylonjs
description: Babylon.js 9.x (2026) web 3D engine with ES6 @babylonjs packages, Havok physics V2, GUI and WebGPU. Use for Babylon.js scene, physics, GUI or loading code.
---
# engine-babylonjs
## Scope
Babylon.js 9.30 (Oct 2026; 9.0 Mar 2026). Check the project's version first (package.json @babylonjs/core, or the UMD BABYLON global).
## Core model
- Engine (WebGL 2) or WebGPUEngine owns the canvas; Scene holds meshes, lights, cameras.
- engine.runRenderLoop(() => scene.render()); per-frame code in onBeforeRenderObservable.
- TransformNode/Mesh hierarchy via parent; metadata for custom data; left-handed Y-up.
- Physics V2: HavokPlugin + PhysicsAggregate / PhysicsBody / PhysicsShape.
- No networking or save system built in.
## Idioms
- Deep imports tree-shake: "@babylonjs/core/Meshes/meshBuilder".
- Side-effect imports: "@babylonjs/loaders/glTF", "@babylonjs/core/Physics/physicsEngineComponent", debugLayer + inspector.
- Load models with ImportMeshAsync / LoadAssetContainerAsync (Loading/sceneLoader).
- engine.getDeltaTime() is milliseconds: divide by 1000.
- Input: scene.onKeyboardObservable (KeyboardEventTypes.KEYDOWN), scene.onPointerObservable.
## Pitfalls
1. Mesh.CreateBox / CreateSphere / CreateGround are deprecated: use MeshBuilder with an options object.
2. PhysicsImpostor with CannonJSPlugin, AmmoJSPlugin or OimoJSPlugin is legacy V1. Use HavokPlugin + PhysicsAggregate.
3. Havok loads async: new HavokPlugin(true, await HavokPhysics()), then scene.enablePhysics(gravity, hk).
4. Setting mesh.position does not move a V2 body (disablePreStep defaults true): use applyImpulse/setLinearVelocity, or disablePreStep = false to teleport.
5. SceneLoader is deprecated in 9.x: use module-level async loaders.
6. Missing side-effect imports give "needs to be imported before" errors or missing loaders.
7. Never mix UMD babylonjs with @babylonjs/* or two versions.
8. WebGPUEngine needs await engine.initAsync(); readPixels is async there.
9. GUI is not in core: AdvancedDynamicTexture comes from @babylonjs/gui.
10. Audio V2 (8.0+): CreateAudioEngineAsync, CreateSoundAsync; unlock needs a user gesture.
11. 9.15 moved to stage-3 decorators: experimentalDecorators false for Babylon decorators.
## Roblox to Babylon.js
- Workspace tree -> Scene + node hierarchy
- Part -> MeshBuilder.CreateBox + PhysicsAggregate (Anchored -> mass 0)
- Script/ModuleScript -> browser TS modules (client only)
- RemoteEvent -> your WebSocket server; DataStore -> localStorage/backend
- Heartbeat/RenderStepped -> onBeforeRenderObservable; TweenService -> Animation.CreateAndStartAnimation
- CollectionService -> Tags; Attributes -> node.metadata
- ScreenGui -> AdvancedDynamicTexture.CreateFullscreenUI; task.wait -> Tools.DelayAsync
- Studio playtest -> Playground or npx vite
## Skeleton
```ts
import { Engine } from "@babylonjs/core/Engines/engine";
import { Scene } from "@babylonjs/core/scene";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { HavokPlugin } from "@babylonjs/core/Physics/v2/Plugins/havokPlugin";
import { PhysicsAggregate } from "@babylonjs/core/Physics/v2/physicsAggregate";
import { PhysicsShapeType } from "@babylonjs/core/Physics/v2/IPhysicsEnginePlugin";
import "@babylonjs/core/Physics/physicsEngineComponent";
import HavokPhysics from "@babylonjs/havok";

const canvas = document.getElementById("renderCanvas") as HTMLCanvasElement;
const engine = new Engine(canvas, true);
const scene = new Scene(engine);
new ArcRotateCamera("cam", -Math.PI / 2, 1.1, 14, Vector3.Zero(), scene).attachControl(canvas, true);
new HemisphericLight("light", new Vector3(0, 1, 0), scene);

scene.enablePhysics(new Vector3(0, -9.81, 0), new HavokPlugin(true, await HavokPhysics()));
const ground = MeshBuilder.CreateGround("ground", { width: 20, height: 20 }, scene);
new PhysicsAggregate(ground, PhysicsShapeType.BOX, { mass: 0 }, scene);
const ball = MeshBuilder.CreateSphere("ball", { diameter: 1 }, scene);
ball.position.y = 5;
new PhysicsAggregate(ball, PhysicsShapeType.SPHERE, { mass: 1, restitution: 0.7 }, scene);

scene.onBeforeRenderObservable.add(() => {
  if (ball.position.y < -5) ball.dispose(); // dt = engine.getDeltaTime() / 1000
});
engine.runRenderLoop(() => scene.render());
window.addEventListener("resize", () => engine.resize());
```
## Verification
Run npx vite or the Playground, read the console, check bodies in the Inspector; tsc for types. Say "not run" if you only wrote the code.
