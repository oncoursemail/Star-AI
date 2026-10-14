---
name: engine-cocos-creator
description: Cocos Creator 3.8.x (TypeScript, node/component editor; COCOS 4 successor). Use for Cocos components, prefabs, bundles, 2D/3D physics, mini-game builds.
---
# engine-cocos-creator
## Scope
Cocos Creator 3.8 LTS (3.8.8, Dec 2025) with TypeScript; COCOS 4 (MIT, Jan 2026) is the engine successor with a CLI and new IDE. Check the project's version first (`package.json` creator version). 2.x `cc.Class` JS and Cocos2d-x C++/Lua are different, legacy APIs.
## Core model
- Scene -> `Node` tree -> `Component`s. Your scripts are `@ccclass` classes extending `Component`, attached to nodes in the editor.
- Lifecycle: `onLoad` -> `onEnable` -> `start` -> `update(dt)` -> `lateUpdate(dt)` -> `onDisable` -> `onDestroy` (dt in seconds).
- 2D/UI content lives under a `Canvas` node; size/anchor via `UITransform`.
- Assets: `assets/resources` + Asset Bundles; Prefabs via `instantiate`.
## Idioms
- `import { _decorator, Component, Node } from 'cc'; const { ccclass, property } = _decorator;`
- `@property(Prefab) enemy: Prefab | null = null;`, `@property({ type: [Node] })`, `@integer`.
- Move with `node.setPosition(x, y, z)`; reuse a `Vec3` temp in `update`.
- Input: `input.on(Input.EventType.KEY_DOWN, this.onKey, this)` in `onLoad`, `input.off` in `onDestroy`; `KeyCode.KEY_A`.
- Touch: `node.on(Node.EventType.TOUCH_START, cb, this)`.
- Tween: `tween(node).to(0.5, { position: v3(0, 100, 0) }, { easing: 'backOut' }).start()`.
- Timers: `this.scheduleOnce(fn, sec)`, `this.schedule(fn, interval)`.
- Load: `resources.load('img/hero/spriteFrame', SpriteFrame, cb)`; `assetManager.loadBundle('lvl2', cb)`.
- Save: `sys.localStorage.setItem('save', JSON.stringify(data))`.
- `NodePool` for pooling; `director.loadScene('Game')`.
## Pitfalls
1. 2.x style `cc.Class`, global `cc.` calls, `cc.loader.loadRes`: 3.x uses imports from `'cc'`, `@ccclass`, `resources.load`.
2. `node.width/height/color/opacity` are 2.x: use `UITransform.setContentSize`, `sprite.color`, `UIOpacity`.
3. `node.x = 5` or `node.position.x = 5` does nothing: call `setPosition`.
4. `zIndex` removed: use `setSiblingIndex`.
5. `systemEvent` deprecated since 3.4: use `input`.
6. Action system (`runAction`, `cc.moveTo`, `cc.sequence`) removed: use `tween`.
7. Physics names: `RigidBody2D`, `BoxCollider2D`, `Contact2DType`, `PhysicsSystem2D`; 3D `RigidBody`, `BoxCollider` (not `RigidBody3D`, not `cc.PhysicsBoxCollider`).
8. 2D contacts: register `collider.on(Contact2DType.BEGIN_CONTACT, cb, this)` and enable `enabledContactListener` on the RigidBody2D; Builtin 2D physics only sends BEGIN/END.
9. Do not destroy nodes or keep contact params in a contact callback; defer via `scheduleOnce`.
10. `resources.load` paths: no extension, under `assets/resources`, add `/spriteFrame` or `/texture` for images.
11. `audioEngine` removed: use `AudioSource`; `CC_EDITOR` -> `EDITOR` from `'cc/env'`.
12. Node `layer` must match camera `visibility`, or nothing renders.
## Roblox to Cocos Creator
- Workspace tree -> node tree; Instance -> Node + Components
- Part -> Node + Sprite (2D) or MeshRenderer + collider (3D)
- Model -> parent Node or Prefab
- LocalScript -> `@ccclass` Component; ModuleScript -> TS module; server Script -> none
- RemoteEvent -> WebSocket; DataStore -> `sys.localStorage`/backend
- Heartbeat -> `update(dt)`; RenderStepped -> `lateUpdate(dt)`
- TweenService -> `tween()`; Attributes -> `@property` fields
- ScreenGui -> Canvas + Widget; UserInputService -> `input`
- task.wait -> `scheduleOnce`; Studio playtest -> editor Preview; shipping -> Project Build panel
## Skeleton
```ts
import { _decorator, Component, Vec3, input, Input, EventKeyboard, KeyCode } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('Mover')
export class Mover extends Component {
  @property
  speed = 300;

  private dir = 0;
  private tmp = new Vec3();

  onLoad() {
    input.on(Input.EventType.KEY_DOWN, this.onDown, this);
    input.on(Input.EventType.KEY_UP, this.onUp, this);
  }
  onDestroy() {
    input.off(Input.EventType.KEY_DOWN, this.onDown, this);
    input.off(Input.EventType.KEY_UP, this.onUp, this);
  }
  private onDown(e: EventKeyboard) {
    if (e.keyCode === KeyCode.KEY_A) this.dir = -1;
    if (e.keyCode === KeyCode.KEY_D) this.dir = 1;
  }
  private onUp() { this.dir = 0; }
  update(dt: number) {
    this.node.getPosition(this.tmp);
    this.tmp.x += this.dir * this.speed * dt;
    this.node.setPosition(this.tmp);
  }
}
```
## Verification
Open the project in the matching Cocos Creator version, check the Console panel after script compile, press Preview and test; build via Project > Build. Report only checks you actually ran.
