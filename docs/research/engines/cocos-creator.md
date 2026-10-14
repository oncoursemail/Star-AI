# Cocos Creator: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Cocos Creator 3.8.8 (2025-12-16, 3.8 LTS line); engine successor "COCOS 4" (v4.0.0 tag, open-sourced 2026-01-05, MIT).** Cocos Creator 3.8 is free to use (Cocos license); COCOS 4 engine is MIT.

## At a glance
| | |
|---|---|
| Best for | 2D and light-3D mobile/casual games, especially Chinese mini-game platforms (WeChat, Douyin, Alipay, Taobao, OPPO, vivo, Huawei, Honor), web (H5) and native mobile |
| Weak at | High-end 3D, console export, large Western community/asset store, built-in multiplayer |
| Language(s) | TypeScript (recommended; JavaScript also accepted). Engine core is C++ with TS API |
| Editor / tooling | Cocos Creator editor installed via Cocos Dashboard; VS Code for scripts. COCOS 4: headless `cocos-cli` + new "PinK" IDE (alpha as of 2026) |
| Platforms (export) | Web Mobile, Web Desktop, iOS, Android, Windows, macOS, HarmonyOS (Next), Google Play (and Play Games PC), WeChat/Douyin/Alipay/Taobao/Baidu/OPPO/vivo/Huawei/Honor mini/quick games, Facebook Instant Games |
| License / cost | Free. 3.8: Cocos license (commercial use allowed). COCOS 4 engine: MIT |
| Roblox-likeness | medium: visual editor with node tree, prefabs, components attached to nodes, play-in-editor preview; but no server/replication and no hosted platform |

## Architecture and lifecycle
- **Scene -> Node tree -> Components.** Every object is a `Node` (transform, active, layer, children). Behavior lives in `Component` subclasses attached to nodes (`Sprite`, `Label`, `UITransform`, `RigidBody2D`, your scripts).
- 2D content must sit under a node with `Canvas` (+ `UITransform`) so the 2D/UI renderer draws it; 3D uses `MeshRenderer` and `Camera`.
- Component lifecycle (official order): `onLoad()` -> `onEnable()` -> `start()` -> `update(deltaTime)` (every frame, before animations) -> `lateUpdate(deltaTime)` (after animation/physics) -> `onDisable()` -> `onDestroy()`. `onLoad` always runs before any `start`. `deltaTime` is in **seconds**.
- `director` runs the main loop and scenes (`director.loadScene('Game')`, `director.preloadScene`). Persist across scenes with `director.addPersistRootNode(node)`.
- Scheduler on every Component: `this.schedule(fn, interval)`, `this.scheduleOnce(fn, delay)`, `this.unschedule(fn)`.
- Assets via `assetManager` with **Asset Bundles**; built-in bundles `main`, `resources`, `start-scene`, `internal`. Dynamic loading only from `assets/resources` or a custom bundle.
- Decorators register classes for serialization/editor: `@ccclass('Name')`, `@property(...)`.

## Project layout
```
assets/                 everything the editor manages (scenes .scene, prefabs .prefab, scripts .ts, textures)
assets/resources/       special folder: loadable at runtime with resources.load (create manually, root of assets)
assets/scripts/         your components (any folder name works)
library/ temp/ local/   generated caches (do not commit)
settings/               project settings
profiles/               editor/user settings
build/                  build output per platform
extensions/             editor extensions
package.json, tsconfig.json
```
Every asset has a `.meta` file with a UUID; always move/rename assets inside the editor (or move .meta with it).

## Scripting idioms
```ts
import { _decorator, Component, Node, Vec3, input, Input, EventKeyboard, KeyCode, Prefab, instantiate } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('PlayerController')
export class PlayerController extends Component {
  @property
  speed = 200;                         // shown in Inspector (number inferred)

  @property(Prefab)
  bulletPrefab: Prefab | null = null;  // drag a prefab in the editor

  @property({ type: [Node] })
  waypoints: Node[] = [];

  private dir = 0;
  private tmp = new Vec3();            // reuse, avoid per-frame allocation

  onLoad() {
    input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    input.on(Input.EventType.KEY_UP, this.onKeyUp, this);
  }
  onDestroy() {
    input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    input.off(Input.EventType.KEY_UP, this.onKeyUp, this);
  }
  onKeyDown(e: EventKeyboard) {
    if (e.keyCode === KeyCode.KEY_A) this.dir = -1;
    if (e.keyCode === KeyCode.KEY_D) this.dir = 1;
  }
  onKeyUp(e: EventKeyboard) {
    if (e.keyCode === KeyCode.KEY_A || e.keyCode === KeyCode.KEY_D) this.dir = 0;
  }
  update(deltaTime: number) {
    this.node.getPosition(this.tmp);
    this.tmp.x += this.dir * this.speed * deltaTime;
    this.node.setPosition(this.tmp);   // position is read-only: always setPosition
  }
  fire() {
    if (!this.bulletPrefab) return;
    const b = instantiate(this.bulletPrefab);
    b.setParent(this.node.parent);
    b.setWorldPosition(this.node.worldPosition);
  }
}
```
Other idioms:
- Get components: `this.getComponent(Sprite)`, `this.node.getComponent(Label)`, `getComponentInChildren`, `this.node.getChildByName('Hud')`, `find('Canvas/Hud')`.
- Decorators: `@integer`, `@float`, `@property({ type: CCInteger })`, `@property({ visible: false })`, `@property({ serializable: false })`, class decorators `@requireComponent(Sprite)`, `@executionOrder(-1)`, `@executeInEditMode(true)`, `@menu('Game/Player')`.
- Node events: `this.node.on(Node.EventType.TOUCH_START, this.onTouch, this)`; custom: `this.node.emit('hit', dmg)` / `this.node.on('hit', fn, this)`.
- Tween: `tween(this.node).to(0.5, { position: v3(0, 100, 0) }, { easing: 'backOut' }).call(() => {...}).start();` stop with `Tween.stopAllByTarget(this.node)`.
- Load at runtime: `resources.load('prefabs/Enemy', Prefab, (err, prefab) => {...})`; sprite frames need the sub-asset path `'images/hero/spriteFrame'`.
- Bundles: `assetManager.loadBundle('level2', (err, bundle) => bundle.load('Boss', Prefab, cb))`.
- Size/anchor of 2D nodes: `this.node.getComponent(UITransform)!.setContentSize(100, 50)`; opacity via `UIOpacity`; color on the renderable (`sprite.color = new Color(255, 0, 0)`).

## Pitfalls (what AI answers get wrong)
1. **Cocos Creator 2.x / `cc.` global JS.** `cc.Class({ extends: cc.Component, properties: {...} })`, `cc.find`, `cc.loader.loadRes`, `cc.director.getPhysicsManager().enabled = true`, `cc.systemEvent` are 2.x. 3.x: ES module imports from `'cc'`, `@ccclass` classes, `resources.load`, `PhysicsSystem2D.instance`, `input`.
2. **Node size/color/opacity on the node.** `node.width`, `node.height`, `node.anchorX`, `node.color`, `node.opacity` were 2.x. 3.x: `UITransform` (`setContentSize`, `anchorX`), color on `Sprite`/`Label`, opacity via `UIOpacity`.
3. **`node.x = 5` / `node.position.x = 5`** do not apply. Use `node.setPosition(x, y, z)` (position getter is read-only). Same for `setScale`, `setRotationFromEuler`, `node.angle` for 2D rotation.
4. **`zIndex` removed** in 3.x. Use `node.setSiblingIndex(i)`; `UITransform.priority` was deprecated in 3.1.
5. **`systemEvent` deprecated since 3.4.0.** Use `input.on(Input.EventType.KEY_DOWN, cb, this)` and remove in `onDestroy` with `input.off`.
6. **Action system removed.** `cc.moveTo`, `runAction`, `cc.sequence` are 2.x. Use `tween(node).to(...).start()`; `cc.repeatForever` -> `Tween.repeatForever`.
7. **Physics names.** 2D: `RigidBody2D`, `BoxCollider2D`, `CircleCollider2D`, `PolygonCollider2D`, `Contact2DType`, `PhysicsSystem2D` (not `cc.RigidBody`/`cc.PhysicsBoxCollider`). 3D: `RigidBody`, `BoxCollider` (not `RigidBody3D`/`Collider3D`). 2D collision callbacks are registered (`collider.on(Contact2DType.BEGIN_CONTACT, ...)`), not magic `onBeginContact` methods, and the rigidbody needs **Enabled Contact Listener** (`rigidbody.enabledContactListener = true`).
8. **resources path rules.** No file extension; must be inside `assets/resources`; a texture path returns `ImageAsset` unless you append `/spriteFrame` or `/texture`; `loadRemote` cannot load SpriteFrame/SpriteAtlas.
9. **Do not store contact callback params.** Box2D reuses them; copy values. Do not destroy nodes or change bodies inside a contact callback; defer with `this.scheduleOnce(() => node.destroy(), 0)` (community-standard practice; the docs note objects created in callbacks appear only after the physics step).
10. **Missing `@ccclass` name or duplicated name** breaks serialization; class name strings must be unique across the project. Properties without `@property` are not saved or shown.
11. **Audio:** `cc.audioEngine` removed; use an `AudioSource` component (`playOneShot(clip)`, `clip`, `volume`).
12. **Camera:** `backgroundColor` -> `clearColor`, `cullingMask` -> `visibility`, `getScreenToWorldPoint` -> `screenToWorld`. Node `group` -> `layer` (bitmask).
13. **Global flags:** `CC_EDITOR`, `CC_DEBUG` -> `import { EDITOR, DEBUG } from 'cc/env'`.
14. **Cocos2d-x confusion.** Cocos2d-x (C++/Lua/JS, last 4.0 in 2019) is a different, legacy framework: `cc.Sprite::create`, `Director::getInstance()`, `cc.Layer`, `scheduleUpdate` do not exist in Creator 3.x.
15. **COCOS 4 vs Creator 3.8.** COCOS 4 (Jan 2026, MIT) is the engine successor with headless CLI and new PinK IDE; mini-game support rolls out gradually. Shipping WeChat mini-games today still targets Creator 3.8.x. Check the project's `package.json` `creator.version` before advising.

## Rendering
- 2D: `Sprite` (+ `SpriteFrame`, `SpriteAtlas`), `Label` (TTF/BMFont/system), `RichText`, `Graphics`, `Mask`, `TiledMap`, `ParticleSystem2D`, `Spine` (`sp.Skeleton`; 3.8.6 added Spine 4.2), DragonBones, `UISkew` (3.8.6+).
- 3D: `MeshRenderer`, PBR materials, Effects (custom shaders in `.effect`), custom render pipeline, skeletal animation, shadows, reflection probes, Lightmaps.
- Rendering backends: WebGL (web), Vulkan/Metal/GLES (native) via the GFX layer.
- Layers & cameras: node `layer` bitmask must match the camera `visibility` or nothing renders.

## Physics
- **2D:** choose Box2D (full: rigid bodies, joints) or Builtin (collision detection only, BEGIN/END contact only) in Project Settings -> Feature Cropping. Components `RigidBody2D` (`type: ERigidBody2DType.Static|Dynamic|Kinematic|Animated`, `linearVelocity: Vec2`, `gravityScale`, `fixedRotation`, `bullet`, `enabledContactListener`), colliders `BoxCollider2D`, `CircleCollider2D`, `PolygonCollider2D`. Global: `PhysicsSystem2D.instance` (`gravity`, `debugDrawFlags`). 3.8.6 added Box2D on native.
- **3D:** backends Bullet (ammo.js wasm), PhysX, cannon.js, builtin. Components `RigidBody`, `BoxCollider`, `SphereCollider`, `CapsuleCollider`, `MeshCollider`, `CharacterController` (3.8+). Events `collider.on('onCollisionEnter', ...)`/`'onTriggerEnter'`. Raycast: `PhysicsSystem.instance.raycastClosest(ray)`.

## Input
- Global: `input.on(Input.EventType.KEY_DOWN | KEY_UP | KEY_PRESSING | TOUCH_START | TOUCH_MOVE | TOUCH_END | MOUSE_DOWN | MOUSE_WHEEL ..., cb, this)`; keys via `KeyCode.KEY_A`, `KeyCode.ARROW_LEFT`, `KeyCode.SPACE`.
- Node-level (hit-tested on UI): `node.on(Node.EventType.TOUCH_START, cb, this)` (needs `UITransform`).
- Gamepad and handle input: `Input.EventType.GAMEPAD_INPUT`, `HANDLE_INPUT` (XR) (names from 3.x input docs; verify for your version).

## UI
- UI = 2D nodes under `Canvas` with `UITransform`. Components: `Button` (click events wired in Inspector or `node.on(Button.EventType.CLICK, ...)`), `Label`, `EditBox`, `ScrollView`, `PageView`, `ProgressBar`, `Slider`, `Toggle`, `Layout`, `Widget` (anchoring/stretch to screen edges), `SafeArea`, `BlockInputEvents`.
- Resolution policy in Project Settings (design resolution, fit width/height).

## Networking and multiplayer
No built-in multiplayer. `WebSocket` and `XMLHttpRequest`/`fetch` available on web and native (native implements WebSocket); mini-game platforms use their own socket APIs through the adapter. Community: Colyseus, Nakama, Photon SDKs. COCOS 4 roadmap mentions real-time multiplayer networking (planned, not shipped as of this research).

## Save data
`import { sys } from 'cc'; sys.localStorage.setItem('save', JSON.stringify(data)); JSON.parse(sys.localStorage.getItem('save') ?? '{}')`. Web: Web Storage; native: sqlite on disk. Mini-games: platform storage via adapter. Cloud save: platform SDK or your backend.

## Performance
- Draw calls: put UI sprites in the same atlas (Auto Atlas / SpriteAtlas), avoid interleaving Labels between Sprites, use BMFont or Label cache mode (`CacheMode.CHAR` for changing numbers).
- Static batching for 3D (`BatchingUtility`), GPU instancing on materials.
- Object pooling: `NodePool` (`pool.get()`, `pool.put(node)`) instead of `instantiate`/`destroy` each frame.
- Reuse `Vec3` temporaries; avoid `new Vec3()` in `update`.
- Feature Cropping in Project Settings strips unused modules (important for mini-game package size limits).
- Release dynamically loaded assets: `assetManager.releaseAsset(asset)` / `asset.decRef()` (see Release of Assets docs).
- Profiler: `Show FPS` in preview, `profiler.showStats()`.

## Build and export
- Editor: Project -> Build, choose platform, Build then Make/Run. Output in `build/<platform>`.
- Native needs Android Studio/NDK, Xcode, or Visual Studio; HarmonyOS needs DevEco Studio.
- Mini-games: build to `build/wechatgame` etc., open in the platform devtool (WeChat DevTools). Subpackages = Asset Bundles marked as mini-game subpackage; WeChat subpackages cannot be remote. Large assets as remote bundles with a resource server address.
- Command-line builds exist ("Publish from the Command Line" docs page): `CocosCreator --project <path> --build "platform=web-mobile;debug=false"` (format from docs pattern; verify flags for your version).

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `Cannot find name 'cc'` / `cc is not defined` | 2.x global style in 3.x | `import { ... } from 'cc'` |
| Position change ignored | Wrote `node.position.x` | `node.setPosition(...)` |
| Sprite not visible | Not under Canvas, layer not in camera visibility, or missing SpriteFrame | Parent under Canvas; set layer `UI_2D`; assign frame |
| `resources.load` returns ImageAsset / type error | Missing `/spriteFrame` sub-path | `'path/name/spriteFrame', SpriteFrame` |
| `resources.load` 404 | Asset not under `assets/resources` or extension in path | Move asset; drop extension |
| Contact callbacks never fire | Enabled Contact Listener off, or Builtin vs Box2D mismatch, or registered too late | Enable on RigidBody2D; register in `onLoad`/`start` |
| Crash when destroying in contact callback | Modifying physics world mid-step | Defer with `scheduleOnce(..., 0)` |
| Input keeps firing after scene change | `input.on` not removed | `input.off` in `onDestroy` |
| Property missing in Inspector | No `@property`, or class lacks `@ccclass` | Add decorators; recompile |
| Mini-game package too big | Everything in main bundle | Feature Cropping, subpackages, remote bundles |

## Mapping from Roblox
| Roblox | Cocos Creator | Notes |
|---|---|---|
| Workspace / Instance tree | Scene node tree (Hierarchy panel) | Nodes + components, like Instances + children |
| Part | Node + `Sprite` (2D) / `MeshRenderer` + `BoxCollider` (3D) | |
| Model | Parent `Node` or Prefab | Prefab = reusable model asset |
| Script (server) | No equivalent | Client engine; server is yours |
| LocalScript | `@ccclass` Component on a node | |
| ModuleScript | TS module (`export`) | Imported with ES import |
| RemoteEvent | WebSocket message | Not built in |
| DataStore | `sys.localStorage` / backend | |
| Players | Not applicable | Platform SDK for user identity |
| Humanoid | Your controller + `RigidBody2D` or `CharacterController` (3D) | |
| RunService.Heartbeat / RenderStepped | `update(deltaTime)` / `lateUpdate(deltaTime)` | seconds |
| TweenService | `tween(node).to(...).start()` | |
| CollectionService tags | Node names, `layer`, groups, or your registry; components as tags | |
| Attributes | `@property` fields | Inspector-editable |
| ScreenGui | `Canvas` with UI nodes + `Widget` | |
| UserInputService | `input` + `Input.EventType`, node touch events | |
| task.wait | `this.scheduleOnce(fn, sec)` or `await` a Promise | |
| Studio playtest | Editor Preview (browser or simulator) | |
| Publishing | Project -> Build for a platform | |

## Minimal example
2D: move with A/D/W/S, collect coins on contact, update a Label (Cocos Creator 3.8, TypeScript). Setup in editor: Player node with `Sprite`, `RigidBody2D` (Dynamic, gravity scale 0, Enabled Contact Listener on), `BoxCollider2D`, this script; coin nodes with `BoxCollider2D` (sensor) and name `Coin`; a `Label` node assigned to `scoreLabel`. Physics engine: Box2D.
```ts
import {
  _decorator, Component, Label, RigidBody2D, Collider2D, Contact2DType, IPhysics2DContact,
  Vec2, input, Input, EventKeyboard, KeyCode,
} from 'cc';
const { ccclass, property } = _decorator;

@ccclass('CoinCollector')
export class CoinCollector extends Component {
  @property(Label)
  scoreLabel: Label | null = null;

  @property
  speed = 8;

  private body: RigidBody2D | null = null;
  private move = new Vec2();
  private score = 0;

  onLoad() {
    this.body = this.getComponent(RigidBody2D);
    input.on(Input.EventType.KEY_DOWN, this.onKey, this);
    input.on(Input.EventType.KEY_UP, this.onKey, this);
    const col = this.getComponent(Collider2D);
    col?.on(Contact2DType.BEGIN_CONTACT, this.onBeginContact, this);
  }

  onDestroy() {
    input.off(Input.EventType.KEY_DOWN, this.onKey, this);
    input.off(Input.EventType.KEY_UP, this.onKey, this);
  }

  private onKey(e: EventKeyboard) {
    const down = e.type === Input.EventType.KEY_DOWN ? 1 : 0;
    switch (e.keyCode) {
      case KeyCode.KEY_A: this.move.x = -down; break;
      case KeyCode.KEY_D: this.move.x = down; break;
      case KeyCode.KEY_W: this.move.y = down; break;
      case KeyCode.KEY_S: this.move.y = -down; break;
    }
  }

  update(deltaTime: number) {
    if (this.body) {
      this.body.linearVelocity = new Vec2(this.move.x * this.speed, this.move.y * this.speed);
    }
  }

  private onBeginContact(self: Collider2D, other: Collider2D, contact: IPhysics2DContact | null) {
    if (other.node.name !== 'Coin') return;
    const coin = other.node;
    this.scheduleOnce(() => { if (coin.isValid) coin.destroy(); }, 0); // never destroy inside the callback
    this.score += 1;
    if (this.scoreLabel) this.scoreLabel.string = `Score: ${this.score}`;
  }
}
```

## Sources
- https://github.com/cocos/cocos-engine/releases (3.8.8 latest, 16 Dec; 3.8.7 22 Aug; 3.8.6 27 Mar)
- https://github.com/cocos/cocos-engine/releases/tag/3.8.8 (3.8.8 release entry)
- https://www.cocos.com/en/post/f539c7888e620701228458d6b89b80c7 (3.8.6 release: Spine 4.2, UISkew, Box2D native, HarmonyOS Next; via search summary)
- https://github.com/cocos/cocos4 (COCOS 4 engine repo, v4.0.0 tag, MIT, C++ core + TS API)
- https://technode.global/prnasia/cocos-4-is-here-fully-open-source/ (COCOS 4 press release 2026-01-05: MIT, headless CLI, PinK IDE, SemVer + 6-month deprecation)
- https://itsfoss.com/news/cocos-4-game-engine/ (secondary: COCOS 4 context, SUD acquisition Nov 2025)
- https://dev.to/pht1991/cocos-4-is-open-source-but-is-it-time-to-leave-cocos-creator-38-577m (community: stay on 3.8 for WeChat mini-games; PinK alpha)
- https://docs.cocos.com/creator/manual/en/scripting/life-cycle-callbacks.html (lifecycle order and semantics)
- https://docs.cocos.com/creator/manual/en/scripting/decorator.html (ccclass, property, integer, executeInEditMode, requireComponent, executionOrder, menu)
- https://docs.cocos.com/creator/manual/en/asset/dynamic-load-resources.html (resources.load rules, /spriteFrame sub-path, loadRemote limits)
- https://docs.cocos.com/creator/manual/en/asset/bundle.html (assetManager.loadBundle, built-in bundles, mini-game remote/subpackage rules)
- https://docs.cocos.com/creator/manual/en/physics-2d/physics-2d-contact-callback.html (Contact2DType callbacks, contact listener, do not store params)
- https://docs.cocos.com/creator/3.8/manual/en/physics-2d/physics-2d-rigid-body.html (ERigidBody2DType, linearVelocity, enabledContactListener, fixedRotation)
- https://docs.cocos.com/creator/manual/en/engine/event/event-input.html (input.on, KeyCode, systemEvent deprecated since 3.4.0)
- https://docs.cocos.com/creator/manual/en/release-notes/upgrade-guide-v3.0.html (2.x -> 3.x renames: UITransform, UIOpacity, zIndex, tween, physics, camera, audio, CC_* flags)
- https://docs.cocos.com/creator/manual/en/tween/tween-example.html (tween to/call/union/repeat/stopAllByTarget)
- https://docs.cocos.com/creator/manual/en/editor/publish/ (platform list)
- https://docs.cocos.com/creator/3.8/manual/en/advanced-topics/data-storage.html (sys.localStorage; web storage vs sqlite)

## Confidence and gaps
- High: 3.8.x lifecycle, decorators, resources/bundles, 2D physics callbacks, input, 2.x -> 3.x renames, release list.
- Medium: 3.8.8 year (GitHub omits year; FileHorse lists 2025-12-16; sequence after 3.8.7 Aug 2025 fits).
- Unclear: docs.cocos.com default manual is now labeled "Cocos Creator 4.0 (LTS)" with no release notes; press calls the product "COCOS 4" (engine) + PinK IDE. Whether a Dashboard-installable "Creator 4.0" editor is GA could not be confirmed.
- Unverified: command-line build flag syntax, 3D CharacterController version, gamepad event names, mini-game package size limits (check each platform's docs).
