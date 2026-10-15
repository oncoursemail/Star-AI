# Construct 3: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: r495.2 (5 Aug 2026; r495 stable line started 21 Jul 2026). LTS: r449.5 (12 Aug 2026). Latest beta seen: r502 (16 Sep 2026).** Proprietary, browser-based editor sold as a subscription (Personal / Business / Education seats); a free edition exists with hard limits (50 events, 2 layers).

## At a glance
| | |
|---|---|
| Best for | 2D (and light 3D) games built with event sheets, fast prototyping, education, web/HTML5 games, mobile and desktop exports from a browser |
| Weak at | Large codebases without discipline, heavy 3D, native-code extensions, very large open worlds; editor requires an online account/subscription for full features |
| Language(s) | Event sheets (visual conditions/actions); JavaScript or TypeScript (script files and inline script actions/blocks) |
| Editor / tooling | Browser editor at editor.construct.net (also installable web app; desktop build). Built-in code editor, debugger (Inspect/Watch/CPU/GPU profiler), external-editor workflow with TypeScript definitions |
| Platforms (export) | Web (HTML5), Android and iOS (Cordova-based build service), Windows / macOS / Linux desktop wrappers, Xbox (UWP), Scirra Arcade, Instant Games |
| License / cost | Subscription per seat (Personal, Business, Education plans). Free edition: max 50 events, 2 layers; personal licence not for businesses over the stated revenue/asset thresholds |
| Roblox-likeness | low-medium: object/instance/behavior model and per-instance variables feel familiar, but there is no client/server split, no hosted multiplayer world, and the main programming surface is event sheets |

## Architecture and lifecycle
- **Project -> Layouts -> Layers -> Instances.** A layout is a level/scene; each layout has an event sheet attached. Layers hold instances (draw order, parallax, HTML layers).
- **Object types (plugins) and instances.** Each object type is created from a plugin (Sprite, Text, Tiled Background, Tilemap, 3D shape, Keyboard, Audio...). Object types have instance variables, behaviors (Platform, 8 Direction, Bullet, Solid, Physics, Tween, Timer, Pathfinding...) and effects. Families group object types.
- **Event sheets** run top to bottom **every tick**. Each event = conditions + actions + optional sub-events. Conditions pick instances (the "SOL", selected object list); actions apply to picked instances. Triggers (green arrow, e.g. `On start of layout`, `On key pressed`) run only when fired.
- **Tick order** (official IRuntime docs): `"pretick"` fires -> behaviors tick -> `"tick"` fires -> event sheets run -> `"tick2"` fires. Use `runtime.dt` (seconds) for frame-rate independence. Default `maxDt` = 1/30, so below 30 FPS the game slows down rather than tunnelling.
- **Script lifecycle.** The main script (Purpose = Main script) is loaded as a JS module before the loading screen. `runOnStartup(async runtime => {...})` runs once the runtime exists but **before any objects exist**. Interact with objects in the `"beforeprojectstart"` event (all first-layout instances created; handler may be async and is awaited).
- **Worker mode.** Project property *Use worker* can run the runtime in a Web Worker; then `window`/`document` (and `localStorage`) are unavailable. Input arrives as runtime events (`"keydown"`, `"pointerdown"`...). `runtime.isInWorker` tells you which.
- **Release channels:** beta (about weekly), stable (every 2-3 months, with .2/.3 patches), LTS (r449 line, supported until end of 2026; next LTS announced as r495).

## Project layout
Construct projects are a single `.c3p` file (zip) or a **folder project** (needed for external-editor workflows). Project Bar folders:
```
Layouts/            Layout 1, Level2 ...
Event sheets/       Event sheet 1 ...
Object types/       Player (Sprite), Coin (Sprite), ScoreText (Text), Keyboard ...
Families/
Scripts/            main.js | main.ts (Purpose: Main script), other modules (Purpose: none),
                    importsForEvents.js (Purpose: Imports for events), *.d.ts
Sounds/ Music/ Videos/ Fonts/ Icons/
Files/              arbitrary files copied as-is (workers, JSON data)
Timelines/ Flowcharts/
```
- Only the main script runs automatically. Other script files must be `import`ed from it ("./globals.js"). Imports even in TypeScript use the `.js` extension.
- Files needing an un-processed URL (Web Worker scripts) go in **Files**, not **Scripts** (Scripts are moved/minified on export).
- Since r450 the export file structure is always "folders" mode (case-preserving paths, `myfolder/Hello.txt`), the legacy lowercase flat mode is gone.

## Scripting idioms
**Main script (JavaScript):**
```js
// main.js  (Purpose: Main script)
import { Globals } from "./globals.js";

runOnStartup(async runtime => {
  // No instances exist yet here. Preload/async init only.
  runtime.addEventListener("beforeprojectstart", () => onBeforeProjectStart(runtime));
});

async function onBeforeProjectStart(runtime) {
  runtime.addEventListener("tick", () => tick(runtime));
}

function tick(runtime) {
  const player = runtime.objects.Player.getFirstInstance();   // IObjectClass -> instance or null
  if (!player) return;
  player.x += 100 * runtime.dt;                                // px per second
}
```
**Inline script in an event sheet** (action or block): code runs inside an async function with `runtime` (and `localVars`) passed in. No `import`/`export` there; use a script file with Purpose *Imports for events*.
```js
// Script action under "Player: On collision with Coin"
runtime.globalVars.Score += 1;
```
**Common instance API (verified in manual):**
- Object classes: `runtime.objects.Sprite` (IObjectType / IFamily), `getAllInstances()` (array), `getFirstInstance()`, `instances()` (iterator), `getPickedInstances()`, `createInstance(layerNameOrIndex, x, y, createHierarchy, template)` (IObjectType only), `setInstanceClass(Class)` (only in runOnStartup).
- IInstance: `uid`, `instVars.health`, `behaviors.Platform`, `destroy()`, `hasTag(tag)`, `setAllTags(tags)`, `signal(tag)` / `waitForSignal(tag)`, `dt`, `timeScale`.
- IWorldInstance: `x`, `y`, `setPosition`, `width`, `height`, `angle` (**radians**), `angleDegrees`, `opacity`, `isVisible`, `zElevation`, `layer`, `moveToTop()`, `moveToLayer(layer)`, `testOverlap(wi)`, `testOverlapSolid()`, `containsPoint(x, y)`, `addChild(wi, opts)`, `getParent()`.
- IRuntime: `objects`, `globalVars`, `keyboard`, `mouse`, `touch`, `layout`, `goToLayout(name)`, `getInstanceByUid(uid)`, `callFunction(name, ...params)` (calls an event-sheet function), `setReturnValue(v)`, `storage` (IStorage), `assets`, `random()`, `destroyMultiple(iterable)`, `sortZOrder(iterable, cmp)`, `timeScale`, `gameTime`, `dt`, `dtRaw`, `minDt`/`maxDt`.
- Keyboard: `runtime.keyboard.isKeyDown("ArrowLeft")` uses `KeyboardEvent.code` strings; numeric codes are deprecated.
- Platform behavior: `inst.behaviors.Platform.simulateControl("left" | "right" | "jump")`, `isOnFloor`, `isJumping`, `vectorX`, `maxSpeed`, `isDefaultControls`.
- Text: `textInst.text = "Score: 3"`.

**TypeScript:** each object type gets a generated class in `InstanceType` (e.g. `InstanceType.Player`). Annotate `runtime: IRuntime`. `getFirstInstance()` can return `null`, so use `!` or a guard. Generic form `getFirstInstance<GoblinInstance>()` returns a subclass type.
```ts
async function onBeforeProjectStart(runtime: IRuntime) {
  const p: InstanceType.Player = runtime.objects.Player.getFirstInstance()!;
  p.instVars.health = 3;
}
```
**Subclassing instances:**
```js
class PlayerInstance extends globalThis.ISpriteInstance {
  constructor() { super(); this.coins = 0; }
}
runOnStartup(async runtime => {
  runtime.objects.Player.setInstanceClass(PlayerInstance);
});
```
(Base class name `ISpriteInstance` follows the manual's subclassing guide; confirm the plugin's interface name in the scripting reference for non-Sprite objects.)

**Event-sheet idioms:** use built-in Functions (not the legacy Function plugin), groups to enable/disable logic, `Every X seconds`, `Trigger once while true`, families + family instance variables for shared logic, templates for prefab-like spawning, `Wait` / `Wait for signal` for sequencing.

## Pitfalls (what AI answers get wrong)
1. **Touching objects inside `runOnStartup`.** No instances exist then. Use `"beforeprojectstart"` (or `"afteranylayoutstart"` for each layout).
2. **Treating the object class as an instance.** `runtime.objects.Sprite.x` is wrong; use `runtime.objects.Sprite.getFirstInstance().x` or iterate `instances()`.
3. **Construct 2 / C2 SDK code.** `cr.plugins_`, `cr.behaviors`, `this.runtime.tickcount`, `instanceProto`, `.capx`-era JS SDK patterns are C2 and do not work. Construct 2 was retired July 2021; C3 runtime replaced the C2 runtime.
4. **SDK v1 addons removed in r450+ (2025).** Projects with SDK v1 third-party addons will not open in current stable; only r449.x LTS (supported to end of 2026) can open them. Same for the NW.js exporter (removed; use Windows/macOS/Linux exporters + Browser/File System plugins, Steamworks instead of Greenworks) and Cordova `file:` scheme (removed; changing scheme wipes app storage).
5. **Classic scripts.** Scripts are ES modules since 2020/2021; top-level functions in one file are not global in another. Use `import`/`export`, or explicit `globalThis.x`.
6. **Own game loop.** Do not use `requestAnimationFrame`/`setInterval` for game logic; listen to the runtime `"tick"` event and scale with `runtime.dt`.
7. **`angle` is radians** in script; event sheets use degrees. Use `angleDegrees` when porting event logic.
8. **Numeric key codes** (`isKeyDown(37)`) are deprecated; use `"ArrowLeft"`, `"KeyW"`, `"Space"`.
9. **`localStorage` / `window` in worker mode.** Use `runtime.storage.getItem/setItem` (async, shared with the Local Storage plugin) and runtime input events.
10. **Mixing .ts and .js with the same name**: Construct uses the .js and ignores the .ts. Choose one workflow (all .ts in editor, or external tsc and only .js imported).
11. **Inline scripts and `await`:** the rest of the event's actions continue while a script awaits; add System *Wait for previous actions to complete* if order matters.
12. **Destroy while iterating:** `instances()` is a live iterator; collect with `getAllInstances()` before destroying many, or use `runtime.destroyMultiple()`.
13. **Physics defaults:** C3 Physics defaults to framerate-independent stepping (C2 was fixed 60 Hz), so imported C2 projects differ.
14. **Legacy Function plugin** is deprecated; use built-in functions (`runtime.callFunction("name", ...)`).

## Rendering
WebGL 2 / WebGPU renderer (WebGPU on supported browsers; r476.3 notes a WebGPU Android driver workaround). 2D sprites with animations editor, meshes/distortion, effects (shaders per instance/layer/layout), blend modes, `zElevation` and 3D shape / 3D model objects (official 3D model plugin added around r476; r495 adds 3D rotation for 3D shapes and 2D objects incl. Sprite, Text, Tiled Background). Sampling can be set per instance/layer/layout ("dynamic sampling", r476). Scripted drawing via `IRenderer` only in layer `"beforedraw"`/`"afterdraw"` events. Integer-scale fullscreen modes exist since r476.

## Physics
Two options: **movement behaviors** (Platform, 8 Direction, Car, Bullet, Tile movement, Jump-thru, Solid) which are kinematic and collision-polygon based, and the **Physics behavior** (Box2D-based) for rigid bodies with joints and forces. Do not mix Physics with movement behaviors on the same object. Collision checks from script: `testOverlap`, `testOverlapSolid`, `runtime.collisions` (ICollisionEngine). Collision polygons are edited per animation frame.

## Input
Plugins: Keyboard, Mouse, Touch (covers mouse too), Gamepad. Event sheet: `Keyboard: On key pressed`, `Is key down`. Script: `runtime.keyboard.isKeyDown(code)`, runtime events `"keydown"`, `"keyup"`, `"pointerdown"`, `"pointermove"`, `"pointerup"`, `"wheel"`. Platform/8 Direction have default controls (arrow keys) unless *Default controls* is disabled; then use `simulateControl`.

## UI
No widget tree like ScreenGui; UI is instances on a dedicated layer with *Parallax 0,0* and scale rate 0 (stays fixed to screen). Objects: Text, SpriteFont, 9-patch, Button, Text input, List, Slider bar, Progress bar, HTML Element; HTML layers let DOM content interleave with canvas layers. Anchor behavior pins UI to screen edges. Timelines and the Tween behavior animate UI.

## Networking and multiplayer
**Multiplayer plugin**: WebRTC DataChannels, peer-to-peer with an authoritative host, Scirra-hosted signalling and TURN servers, interpolation, local input prediction, LAN support. Script interface `IMultiplayerObjectType`. Plus AJAX and WebSocket plugins for custom servers, and **Construct Game Services** (leaderboards, cloud saves, multiplayer services; free CGS plan with paid plans). No server-authoritative cloud runtime like Roblox; the "server" is a player's browser acting as host unless you build your own backend.

## Save data
- **Savegame system**: System `Save`/`Load` actions snapshot the whole game state into slots (browser storage). Behaviors `No save` and `Persist` control what is included. Script hooks: runtime `"save"`/`"load"` events with `e.saveData` (JSON only) for custom script state.
- **Key/value**: Local Storage plugin, or script `await runtime.storage.setItem(key, value)` / `getItem(key)` (getItem resolves `null` on missing; setItem can reject on quota, wrap in try/catch).
- **Cloud**: Construct Game Services cloud save, or your own backend via AJAX.
- Browser storage is per-origin; changing the hosting URL (or mobile scheme) loses saves.

## Performance
Official tips: avoid creating thousands of objects, keep collision checks narrow (use `Is overlapping` after cheap picking, collision cells are automatic), minimize effects/large transparent overdraw, prefer tile maps and Tiled Background over many sprites, avoid `Every tick` heavy loops, use `destroyMultiple`, profile with the debugger CPU/GPU tabs. Images are packed into spritesheets on export; enable *Deduplicate images*, *Optimize images* and *Minify script* (Advanced minification can break scripts that access object properties by string, use Simple mode or the documented patterns). `maxDt` caps slow frames.

## Build and export
Menu > Project > Export. Common options: deduplicate images, lossless/lossy formats, optimize images, minify script (cloud service, needs Internet), offline support for web. Targets: Web (HTML5), Scirra Arcade, Android/iOS (Cordova; build service can produce APK/AAB/IPA with signing), Windows (WebView2 wrapper), macOS (WKWebView), Linux (CEF), Xbox UWP, Instant Games. Export Manager re-downloads recent builds. Never ship from a beta release.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `Cannot read properties of null (reading 'x')` at startup | Accessing instances inside `runOnStartup` or object not on first layout | Move code into `"beforeprojectstart"` handler; null-check `getFirstInstance()` |
| Function in one script file "is not defined" in another | Scripts are modules | `export` it and `import` it in main script; for event scripts use an *Imports for events* file |
| Game runs at different speeds on 60 vs 144 Hz | Fixed per-tick movement | Multiply by `runtime.dt` (or `self.dt` in events) |
| Project will not open after updating Construct | SDK v1 third-party addon (r450+) | Update the addon to SDK v2 or stay on r449.x LTS |
| Saves lost after app update | Cordova scheme changed or hosting URL changed | Keep the same scheme/origin; r449 LTS for legacy `file:` apps |
| Script works in preview, breaks after export | Advanced minification renaming property names | Use Simple minify or dot-access documented APIs |
| `localStorage is not defined` | Worker mode | Use `runtime.storage` |
| Sprite rotates wildly from script | Using degrees with `angle` | Use `angleDegrees` or convert to radians |
| Newly created object invisible for a moment | Images not loaded yet (object not on any layout) | Place one instance in the layout and destroy it on start, or preload |
| TypeScript error "possibly null" | `getFirstInstance()` returns `T | null` | Guard or use `!` |

## Mapping from Roblox
| Roblox | Construct 3 | Notes |
|---|---|---|
| Workspace / Instance tree | Layout + layers + instances; scene-graph hierarchy via `addChild` | Flat instance lists per object type, optional hierarchy |
| Part | Sprite / Tiled Background / 3D shape instance | Collision polygon per frame |
| Model | Hierarchy, Container, or Template | Templates spawn prefab-like copies |
| Script | Event sheet or main script `"tick"` handler | All logic runs in one runtime |
| LocalScript | Same as above (everything is client) | No client/server split |
| ModuleScript | Script file with Purpose none + `export`/`import` | ES modules |
| RemoteEvent | Multiplayer plugin messages (host/peer) | Peer-to-peer WebRTC |
| DataStore | `runtime.storage` / Local Storage plugin / CGS cloud save | Local unless cloud service |
| Players | Multiplayer peers (`myId`, peer list) | No accounts by default |
| Humanoid | Platform / 8 Direction behavior | Movement only, no health/animation rig |
| RunService.Heartbeat | runtime `"tick"` event or `Every tick` | `runtime.dt` seconds |
| RunService.RenderStepped | `"tick"` / layer `"beforedraw"` | Draw only in draw events |
| TweenService | Tween behavior (`behaviors.Tween`) / Timelines | Easing editor |
| CollectionService tags | Instance tags `hasTag`/`setAllTags`, families | Families also share variables/behaviors |
| Attributes | Instance variables `instVars` | Typed in TS via `InstanceType` |
| ScreenGui | UI layer (parallax 0) + Text/Button/9-patch, HTML layers | Anchor behavior for layout |
| UserInputService | Keyboard / Mouse / Touch / Gamepad plugins, runtime input events | `isKeyDown("KeyW")` |
| task.wait | System `Wait` action; `await` a promise in script; `waitForSignal` | Script `setTimeout` ignores time scale |
| Studio playtest | Preview (F5), Debug preview | Remote preview to devices |
| Publishing | Export (Web/Android/iOS/Desktop) | Host on itch.io, own site, stores |

## Minimal example
Main script (JavaScript). Project contains Sprite objects `Player` and `Coin` (several Coin instances), a Text object `ScoreText`, and the Keyboard plugin.
```js
// main.js  Purpose: Main script
const SPEED = 240; // pixels per second
let score = 0;

runOnStartup(async runtime => {
  runtime.addEventListener("beforeprojectstart", () => onBeforeProjectStart(runtime));
});

function onBeforeProjectStart(runtime) {
  runtime.addEventListener("tick", () => tick(runtime));
}

function tick(runtime) {
  const player = runtime.objects.Player.getFirstInstance();
  if (!player) return;

  const kb = runtime.keyboard;
  let dx = 0, dy = 0;
  if (kb.isKeyDown("ArrowLeft") || kb.isKeyDown("KeyA")) dx -= 1;
  if (kb.isKeyDown("ArrowRight") || kb.isKeyDown("KeyD")) dx += 1;
  if (kb.isKeyDown("ArrowUp") || kb.isKeyDown("KeyW")) dy -= 1;
  if (kb.isKeyDown("ArrowDown") || kb.isKeyDown("KeyS")) dy += 1;
  const len = Math.hypot(dx, dy) || 1;
  player.x += (dx / len) * SPEED * runtime.dt;
  player.y += (dy / len) * SPEED * runtime.dt;

  // getAllInstances() returns an array copy, safe to destroy while looping
  for (const coin of runtime.objects.Coin.getAllInstances()) {
    if (player.testOverlap(coin)) {
      coin.destroy();
      score += 1;
    }
  }

  const label = runtime.objects.ScoreText.getFirstInstance();
  if (label) label.text = `Score: ${score}`;
}
```
Event-sheet equivalent: `Player: On collision with Coin` -> `Coin: Destroy`, `System: Add 1 to Score`, `ScoreText: Set text to "Score: " & Score`; movement via the 8 Direction behavior.

## Sources
- https://editor.construct.net/ (live editor title: Construct 3 r495.2)
- https://www.construct.net/en/make-games/releases (release list: Stable r495.2 5 Aug 2026, LTS r449.5 12 Aug 2026, Beta r502 16 Sep 2026; read via Internet Archive copy because construct.net blocked direct fetch)
- https://editor.construct.net/r449-5/ and search snippet of r449.5 notes (r495 named next LTS)
- https://www.construct.net/en/make-games/releases/stable/r495 (search snippet: published 21 Jul 2026, 3D rotation highlight)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/iruntime (events, tick order, all IRuntime members)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/using-scripting/script-files (runOnStartup, beforeprojectstart, modules, Files folder)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/using-scripting/scripts-in-event-sheets (inline scripts, await behaviour, no imports)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/using-scripting/typescript-construct (InstanceType, IRuntime annotation, .ts/.js priority, generics)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/object-interfaces/iobjectclass (getAllInstances, getFirstInstance, class vs instance mistake)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/object-interfaces/iobjecttype (createInstance signature, setInstanceClass)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/object-interfaces/iinstance (instVars, behaviors, tags, destroy)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/object-interfaces/iworldinstance (angle radians, testOverlap, hierarchy)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/plugin-interfaces/keyboard (isKeyDown code strings, numeric deprecated)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/behavior-interfaces/platform (simulateControl, isOnFloor)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/interfaces/istorage (async getItem/setItem)
- https://www.construct.net/en/make-games/manuals/construct-3/scripting/scripting-reference/plugin-interfaces/text (text property)
- https://www.construct.net/en/make-games/manuals/construct-3/tips-and-guides/deprecated-features (SDK v1, flat mode, file: scheme, NW.js removed r450+; classic scripts; Function plugin)
- https://www.construct.net/en/make-games/manuals/construct-3/tips-and-guides/importing-c2-projects (C2 retired July 2021, Physics stepping, C3 runtime)
- https://www.construct.net/en/make-games/manuals/construct-3/tips-and-guides/release-channels (beta/stable/LTS cadence)
- https://www.construct.net/en/make-games/manuals/construct-3/overview/publishing-projects (export options)
- https://www.construct.net/en/make-games/manuals/construct-3/plugin-reference/multiplayer (WebRTC, host model, signalling)
- https://www.construct.net/en/make-games/buy-construct (plans; free edition 50 events / 2 layers)
- https://editor.construct.net/r476-3/ (search snippet: r476 10 Mar 2026, r476.3 30 Mar 2026, WebGPU Android workaround, 3D model plugin, dynamic sampling)

## Confidence and gaps
- High: scripting API names above (read from the official manual, entries last updated Dec 2025), deprecations in r450+, release numbers/dates from the release list snapshot and live editor title.
- Medium: exact export target list (Xbox UWP, Instant Games, Linux CEF) is from general manual navigation, not each exporter page. Pricing amounts were not captured (page lists plans but numbers rendered client-side).
- Not verified: `ISpriteInstance` base class name for subclassing (from memory of the subclassing guide, not fetched); whether r495 has already been promoted to LTS (announced as "soon" in Aug 2026). construct.net was behind Cloudflare; manual pages were read through Internet Archive copies.
