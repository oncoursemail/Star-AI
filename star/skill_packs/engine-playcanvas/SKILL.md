---
name: engine-playcanvas
description: PlayCanvas engine 2.x (2.23, 2026) web 3D with ESM scripts, cloud Editor or engine-only npm, ammo.js physics, React and Web Components. Use for PlayCanvas code.
---
# engine-playcanvas
## Scope
PlayCanvas engine 2.23 (Oct 2026; 2.0 was Aug 2024). Check the project's version first and whether it is an Editor or engine-only project.
## Core model
- Entity hierarchy under app.root; behaviour from components (render, camera, light, collision, rigidbody, script, element, sound, anim, gsplat).
- Scripts (script component): initialize, postInitialize, update(dt), postUpdate(dt), destroy event.
- Physics: ammo.js behind rigidbody + collision, fixed 1/60 s steps.
- Same engine in the cloud Editor, npm apps, @playcanvas/react and web components. No networking or saves built in.
## Idioms
- Click Parse in the Editor after changing attributes.
- Input: this.app.keyboard.isPressed(KEY_W), wasPressed for one frame; app.mouse, app.touch, app.gamepads.
- Tags: entity.tags.add('coin'); this.app.root.findByTag('coin'); findByName for single entities.
- Events: this.app.fire('score', n) / this.app.on('score', fn); remove listeners in the destroy handler.
- Engine-only: npm install playcanvas + Vite; register classes with app.scripts.add(X) or entity.script.create(X).
- Primitives: addComponent('render', { type: 'box' }); glTF via container assets.
## Pitfalls
1. pc.createScript is the Classic format (still supported); new code should be ESM extends Script. ScriptType is deprecated.
2. ESM attributes use the JSDoc @attribute tag, not X.attributes.add; they are passed by reference and fire no attr: events.
3. ESM scripts are module scoped and have no load order: export/import shared values, no globals.
4. Engine 2.0 removed WebGL 1, the pre-2016 legacy scripts, AudioSourceComponent (use sound), BasicMaterial and Layer.renderTarget.
5. Gamma, tone mapping are per camera in 2.x; fog lives in scene.fog.type/color/start/end.
6. Color textures need sRGB formats; emissive tint defaults to black, so set emissive white when using an emissive map.
7. ShaderMaterial stopped injecting gamma/tonemap/fog in 2.5; include them yourself.
8. Physics is opt-in: without ammo (Editor IMPORT AMMO, or pc.WasmModule.setConfig('Ammo', ...) + getInstance before start) bodies silently do nothing.
9. Physics owns dynamic bodies: move them with applyForce, applyImpulse, linearVelocity or teleport, not setPosition.
10. Gravity is app.systems.rigidbody.gravity.set(x, y, z); setGravity is deprecated. 2.23 adds gravityScale per body.
11. collision.on('collisionstart'|'contact'|'collisionend'); collision without rigidbody is a trigger (triggerenter/triggerleave).
12. Call material.update() after changing StandardMaterial properties.
## Roblox to PlayCanvas
- Workspace / Instance tree -> app.root entity hierarchy
- Part -> entity with render + collision + rigidbody (Anchored -> type 'static')
- Model -> parent entity or Template asset
- Script/LocalScript -> ESM Script (client only); ModuleScript -> .mjs export
- RemoteEvent -> your WebSocket server; DataStore -> localStorage/backend
- Heartbeat -> update(dt); RenderStepped -> postUpdate(dt)
- TweenService -> animate in update or anim component
- CollectionService -> entity.tags + findByTag; Attributes -> script attributes
- ScreenGui -> screen + element components; UserInputService -> app.keyboard/mouse/touch
- Studio playtest -> Editor Launch tab or npx vite
## Skeleton
```js
import { Script, Vec3, KEY_W, KEY_A, KEY_S, KEY_D } from 'playcanvas';

export class PlayerMove extends Script {
    static scriptName = 'playerMove';

    /** @attribute */
    force = 20;

    initialize() {
        this.dir = new Vec3();
        this.score = 0;
        this.handle = this.entity.collision.on('collisionstart', (result) => {
            if (result.other.tags.has('coin')) {
                result.other.destroy();
                this.app.fire('score', ++this.score);
            }
        });
        this.once('destroy', () => this.handle.off());
    }

    update(dt) {
        const kb = this.app.keyboard;
        this.dir.set(
            (kb.isPressed(KEY_D) ? 1 : 0) - (kb.isPressed(KEY_A) ? 1 : 0),
            0,
            (kb.isPressed(KEY_S) ? 1 : 0) - (kb.isPressed(KEY_W) ? 1 : 0)
        );
        if (this.dir.lengthSq() > 0) {
            this.dir.normalize().mulScalar(this.force);
            this.entity.rigidbody.applyForce(this.dir);
        }
    }
}
```
## Verification
Editor: Parse, attach, Launch, read the console (debug engine shows warnings). Engine-only: npx vite, console; tsc for TS. Say "not run" if you only wrote the code.
