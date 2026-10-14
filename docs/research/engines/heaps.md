# Heaps (Haxe): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Heaps 2.1.1 (2025-06-07) on Haxe 4.3.7 (2025-05-09); HashLink 1.16 (2026-08-03).** Free, open source (GitHub reports MIT; haxelib.json says "BSD"); Hide editor is BSD-2-Clause.

## At a glance
| | |
|---|---|
| Best for | Code-first 2D and 3D games by programmers who want a fast, portable GPU framework (Dead Cells, Northgard, Evoland, Darksburg are made with it, per heaps.io showcase) |
| Weak at | Beginner onboarding, documentation depth, editor polish, ready-made gameplay systems (no built-in rigid-body physics, no built-in UI designer outside Hide/DomKit) |
| Language(s) | Haxe 4.x (statically typed, compiles to HashLink bytecode, HL/C native, or JavaScript); HxSL for shaders |
| Editor / tooling | No mandatory editor. VS Code + Haxe Extension Pack is the documented workflow. Hide (Heaps IDE, NW.js app, nightly builds) for levels, prefabs, particles, CastleDB |
| Platforms (export) | Windows/macOS/Linux via HashLink (SDL/OpenGL `hlsdl`, DirectX `hldx`, DX12 via `-D dx12`), HTML5/WebGL via JS target, mobile via community HL/C setups, consoles (Switch, PS, Xbox) for registered devs via the Haxe team |
| License / cost | Free, open source |
| Roblox-likeness | low: no hosted multiplayer, no instance/property editor by default, no services; it is a framework where you write the game loop yourself |

## Architecture and lifecycle
- A game is a class extending `hxd.App`. Construction (`new Main()` in `static function main()`) sets up the engine, then calls your overridden `init()` once, then `update(dt:Float)` every frame. `dt` is in **seconds** (changed in Heaps 1.5; older answers multiply by 60).
- `hxd.App` exposes `engine : h3d.Engine`, `s2d : h2d.Scene` (2D scene graph), `s3d : h3d.scene.Scene` (3D scene graph) and `sevents : hxd.SceneEvents`. Both scenes render each frame: 3D first, then 2D on top.
- Other overridable hooks (package-private, override with `override function`): `onResize()`, `loadAssets(onLoaded)`, `dispose()`. Public: `setScene(scene, disposePrevious = true)` to switch to a new `h2d.Scene` or `h3d.scene.Scene`.
- Scene graph: `h2d.Object` is the 2D base class (renamed from `h2d.Sprite` in 1.5). Children are added by passing the parent as the last constructor argument (`new h2d.Bitmap(tile, s2d)`) or with `parent.addChild(obj)`; remove with `obj.remove()`.
- 3D: `h3d.scene.Object` base; `h3d.scene.Mesh(primitive, ?material, ?parent)`; lights such as `h3d.scene.fwd.DirLight` (forward renderer) or PBR lights; camera at `s3d.camera`.
- Resources: `hxd.Res` is a macro-generated typed tree of the `res/` folder. You must initialize a loader (`hxd.Res.initEmbed()`, `initLocal()` or `initPak()`) before touching `hxd.Res.*`. Usually done in `main()` before `new Main()`, or in an overridden `loadAssets`.
- Time: `hxd.Timer` (static `update()`, `fps()`, `skip()`, `reset()`); input: `hxd.Key` static functions, `hxd.Pad` for gamepads.

## Project layout
```
mygame/
  compile.hxml        # or build.hxml; any name, passed to `haxe`
  src/Main.hx
  res/                # hxd.Res root (change with -D resourcesPath=assets)
    hero.png          # -> hxd.Res.hero.toTile()
    sfx/jump.wav      # -> hxd.Res.sfx.jump.play()
  .vscode/launch.json # F5 builds + runs (Haxe extension)
  index.html          # only for the JS target, loads hello.js
```
JS target hxml (from the official Hello World):
```
-cp src
-lib heaps
-js hello.js
-main Main
-debug
```
HashLink target hxml:
```
-cp src
-lib heaps
-lib hlsdl          # or: -lib hldx   (DirectX 11)   or: -lib hldx -D dx12
-hl hello.hl
-main Main
```
Run with `hl hello.hl`. For HL/C native: `-hl out/main.c`, then compile the C with a native compiler and link against the HashLink runtime.

## Scripting idioms
```haxe
class Main extends hxd.App {
    var hero : h2d.Bitmap;

    override function init() {
        // 2D scaling: fixed virtual resolution with letterboxing
        s2d.scaleMode = LetterBox(320, 180);
        hero = new h2d.Bitmap(hxd.Res.hero.toTile().center(), s2d);
        hero.setPosition(160, 90);
    }

    override function update(dt : Float) {
        if (hxd.Key.isDown(hxd.Key.RIGHT)) hero.x += 120 * dt;     // dt is seconds
        if (hxd.Key.isPressed(hxd.Key.SPACE)) jump();              // edge-triggered
    }

    function jump() {}

    static function main() {
        hxd.Res.initEmbed();   // must run before any hxd.Res access
        new Main();
    }
}
```
- Tiles: `h2d.Tile.fromColor(0xFF0000, w, h)`, `tile.sub(x, y, w, h)`, `tile.split(frames)`, `tile.grid(size)`, `tile.center()`. Spritesheet animation: `new h2d.Anim(frames, speed = 15, parent)`.
- Text: `new h2d.Text(hxd.res.DefaultFont.get(), s2d)`; set `.text`. Bitmap fonts via `hxd.Res.font.toFont()`.
- Vector drawing: `h2d.Graphics` with `beginFill(color, alpha)`, `drawRect`, `drawCircle`.
- Mouse/touch: `var i = new h2d.Interactive(w, h, parent); i.onClick = function(e) {...}` (dynamic callback fields: `onOver`, `onOut`, `onPush`, `onRelease`, `onMove`, `onWheel`).
- Layout: `h2d.Flow` (box layout, padding, `layout = Vertical`), optional DomKit for CSS-like UI.
- Sound: `hxd.Res.sfx.jump.play()` (`play(?loop = false, ?volume = 1.)`). Files must be supported by the target (wav/ogg/mp3).
- 3D: 
```haxe
var prim = new h3d.prim.Cube(1, 1, 1, true);
prim.unindex(); prim.addNormals(); prim.addUVs();
var mesh = new h3d.scene.Mesh(prim, s3d);
mesh.material.color.setColor(0xFFB280);
new h3d.scene.fwd.DirLight(new h3d.Vector(0.5, 0.5, -0.5), s3d);
s3d.camera.pos.set(4, 4, 3);       // Z is up in Heaps
s3d.camera.target.set(0, 0, 0);
```
Note: on current master `h3d.scene.CameraController` is declared `abstract class` with `OrbitCameraController` as a subtype in the same module; older samples doing `new h3d.scene.CameraController(s3d)` may no longer compile. Check the source of your pinned Heaps version.
- Save: `hxd.Save.save(data, "slot1")` / `hxd.Save.load(defaultValue, "slot1")` (Haxe serializer; optional checksum flag).

## Pitfalls (what AI answers get wrong)
1. **Heaps 2.0 changed `h3d.Vector` to 3 components** (alias of `h3d.col.Point`) and added `h3d.Vector4`. Code doing `new h3d.Vector(x, y, z, w)` or reading `.w` must use `h3d.Vector4` now. Colors that used Vector with alpha also go through `Vector4`.
2. **`h2d.Sprite` is gone** (renamed `h2d.Object` in 1.5); `hxd.Stage` is now `hxd.Window` (`hxd.Window.getInstance()`).
3. **`update(dt)` is in seconds**, not frames (1.5+). Use `x += speed * dt` with speed in pixels per second. Old code using `hxd.Timer.tmod` is legacy.
4. **Forgetting `hxd.Res.initEmbed()`** (or `initLocal`) gives a null loader crash on first resource access. `initLocal` does not work in the browser; use `initEmbed` for JS.
5. **`hxd.Res` paths are compile-time fields**: `hxd.Res.load("hero.png")` exists for dynamic paths, but files with names that are not valid Haxe identifiers (spaces, leading digits, dashes) do not get typed fields. Rename assets.
6. **Z-up coordinate system** in 3D. FBX exported Y-up is auto-converted since 1.9, but hand-written camera/physics code that assumes Y-up is wrong.
7. **Buffers were unified in 2.0** into `h3d.Buffer` with a format; old `h3d.Indexes`/`ManagedBuffer`-style low-level code from 1.x tutorials will not compile. `DepthBuffer` was unified with `Texture`.
8. **`h2d.Object.move(dx, dy)` moves along the object's rotation** (fixed to local movement in 2.0.1); use `x += ...` for world-axis movement.
9. **HashLink library names**: you need `-lib hlsdl` or `-lib hldx` in the hxml, plus the matching native libs shipped with HashLink. Missing them gives "missing driver" or link errors. DX12 needs `-lib hldx -D dx12` and HL 1.13+.
10. **Haxe version**: Heaps 1.9+ requires Haxe 4.2.1+; current dev targets Haxe 4.3.x. Haxe 5 exists only as `5.0.0-preview.1` (2025-07-04); do not claim Heaps is on Haxe 5.
11. **Installing**: the docs recommend `haxelib git heaps https://github.com/HeapsIO/heaps.git` (the haxelib release lags master). Mixing haxelib heaps with git hlsdl versions can mismatch.
12. **`init`/`update` are not public**: override with `override function init()` (not `public override`), otherwise Haxe reports a visibility mismatch.

## Rendering
- GPU-accelerated 2D and 3D, drivers: OpenGL/WebGL, DirectX 11, DirectX 12 (production-ready since 2.0), compute shaders on GL/DX12 (2.1).
- Shaders are written in HxSL (Haxe-embedded shader language) by extending `hxsl.Shader` with a `static var SRC = { ... }` block; added to materials via `material.mainPass.addShader(s)` or to 2D objects via `obj.addShader(s)`.
- 3D renderer: PBR renderer with cascade shadow maps (2.1), MeshBatch instancing, HMD model format (convert FBX), LOD (2.1), GPU particles.
- 2D: `h2d.SpriteBatch`, `h2d.TileGroup` for many sprites in one draw call, filters (`h2d.filter.Blur`, `Glow`, `DropShadow`), `h2d.Camera` (multiple cameras since 1.6).
- `s2d.scaleMode`: `Resize` (default), `Stretch(w,h)`, `LetterBox(w,h,?integerScale,...)`, `Fixed(w,h,zoom,...)`, `Zoom(level)`, `AutoZoom(minW,minH,?integerScaling)`, `Custom(...)`.

## Physics
No built-in rigid-body physics. Heaps ships collision math only:
- 2D: `h2d.col.Bounds` (`intersects`, `contains`), `Circle`, `Polygon`, `Point`, `h2d.col.Collider` for `h2d.Interactive` shapes.
- 3D: `h3d.col.Bounds`, `Ray`, `Sphere`, `Capsule`, `Plane`; mesh ray picking via `h3d.scene.Interactive`.
Studios typically write their own grid/AABB platformer physics (Dead Cells style) or bind a C library (e.g. via HashLink natives). Mark third-party Haxe physics libraries as community.

## Input
- Keyboard: `hxd.Key.isDown(code)`, `isPressed(code)` (this frame), `isReleased(code)`; constants `hxd.Key.LEFT`, `SPACE`, `A`..`Z`, `NUMBER_0`, `F1`, `ESCAPE`; also `"W".code`.
- Mouse: `s2d.mouseX/mouseY`, `h2d.Interactive` callbacks, or `hxd.Window.getInstance().addEventTarget(onEvent)` with `hxd.Event` (`EPush`, `ERelease`, `EMove`, `EWheel`, `EKeyDown`...).
- Gamepad: `hxd.Pad.wait(function(pad) {...})` then `pad.xAxis`, `pad.isDown(pad.config.A)` (`PadConfig` has an `A` field; mappings differ per backend).

## UI
- Code-built: `h2d.Flow`, `h2d.Text`, `h2d.HtmlText`, `h2d.TextInput`, `h2d.Interactive`, `h2d.ScaleGrid` (9-slice).
- DomKit (separate haxelib `domkit`): CSS + markup components compiled by macros; Heaps has an inspector for it.
- No drag-and-drop UI designer in Heaps itself.

## Networking and multiplayer
- `hxd.net.Socket` / `hxd.net.SocketHost` (TCP) plus the separate `hxbit` library for serialization and replication: classes `implements hxbit.NetworkSerializable`, replicated fields tagged `@:s`, remote calls tagged `@:rpc`, permission check via `networkAllow(op, propId, client)` (see `samples/Network.hx`).
- No hosted servers, matchmaking or relays. Northgard's multiplayer is studio-built on this stack.

## Save data
- `hxd.Save.save(value, ?name = "save", checkSum = false)` and `hxd.Save.load<T>(?defValue, ?name, checkSum)`: Haxe-serialized, local file on HL, `localStorage` on JS. `load` merges missing fields from `defValue`, which helps versioned saves.
- For larger data use `sys.io.File` (HL only) or CastleDB (`cdb`) for designer data.

## Performance
- HashLink JIT for development, HL/C (native C compile) for shipping performance; JS target is slower and limited by WebGL.
- Batch sprites (`SpriteBatch`, `TileGroup`), atlas textures, avoid creating `h2d.Text` per frame, avoid allocations in `update` (Haxe GC on HL).
- `engine.drawCalls`, `hxd.Timer.fps()` for quick stats; `-D hl-profile` / HL profiler for CPU.
- `MeshBatch` for 3D instancing; LOD and mesh optimization in 2.1.

## Build and export
- Desktop: build `.hl` and ship with the HashLink VM (`hl.exe` + `.hdll` libs), or compile HL/C to a native binary.
- Web: `-js game.js`, host with an `index.html` containing a `<canvas id="webgl">`. Use `hxd.Res.initEmbed()`.
- Resource packing: `hxd.fmt.pak.Build` creates `res.pak`; load with `hxd.Res.initPak()`.
- Consoles: available to registered developers through the Haxe Foundation / Shiro Games tooling, not public.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `Null access` / crash on first `hxd.Res.x` | Loader not initialized | Call `hxd.Res.initEmbed()` (or `initLocal`) before `new Main()` |
| `h3d.Vector has no field w` / wrong constructor arity | Heaps 2.0 made Vector 3D | Use `h3d.Vector4` for 4 components |
| `Type not found : h2d.Sprite` | Renamed in 1.5 | Use `h2d.Object` |
| Movement 60x too fast | Treating `dt` as frames | Multiply by speed in units per second |
| Black window on HL, "no driver" | Missing `-lib hlsdl`/`-lib hldx` or missing `.hdll` | Add the lib to hxml and install the native libs with HashLink |
| `initLocal` fails in browser | Local FS unsupported on JS | Use `initEmbed` for JS |
| Resource field missing on `hxd.Res` | Invalid identifier in file name or file added without recompiling | Rename file; rebuild (macro runs at compile time) |
| 3D model lies on its side | Y-up assumptions | Heaps is Z-up; rotate or rely on FBX auto-convert |
| `Field init has different visibility` | Declared `public override function init` | Use `override function init()` |

## Mapping from Roblox
| Roblox | Heaps | Notes |
|---|---|---|
| Workspace / Instance tree | `s3d` (`h3d.scene.Scene`) and `s2d` (`h2d.Scene`) object trees | Parent passed in constructor or `addChild` |
| Part | `h3d.scene.Mesh` with `h3d.prim.Cube` | No physics properties built in |
| Model | `h3d.scene.Object` container, or loaded `hxd.Res.x.toModel()` via `h3d.prim.ModelCache` | |
| Script / LocalScript | Haxe classes in `src/`; all code runs in one process | No client/server split unless you build one |
| ModuleScript | Haxe class/module + `import` | Static typing, compile-time |
| RemoteEvent | `hxbit` `@:rpc` methods over `hxd.net.Socket` | Self-hosted |
| DataStore | `hxd.Save` (local only) | No cloud storage |
| Players | Not applicable | Build your own player list |
| Humanoid | Not applicable | Write your own controller |
| RunService.Heartbeat / RenderStepped | `override function update(dt)` | One callback; dt in seconds |
| TweenService | No built-in; use `h2d.Anim` for frames, lerp in `update`, or a tween lib (community) | |
| CollectionService tags | Your own arrays / `Map<String, Array<Object>>` | |
| Attributes | Class fields | |
| ScreenGui | `s2d` with `h2d.Flow`/`h2d.Text` | 2D scene draws over 3D |
| UserInputService | `hxd.Key`, `hxd.Pad`, `h2d.Interactive`, `hxd.Window` events | |
| task.wait | No coroutine scheduler; use timers accumulated in `update` or `haxe.Timer.delay` | |
| Studio playtest | F5 in VS Code (build + run HL or JS) | |
| Publishing | Ship HL build or JS bundle yourself (Steam, itch.io) | |

## Minimal example
Move a square with arrows/WASD, collect coins, show score. Heaps 2.1, Haxe 4.3, no external assets.
```haxe
// src/Main.hx   build: haxe compile.hxml   (with -lib heaps -lib hlsdl -hl game.hl -main Main)
class Main extends hxd.App {
    static inline var SPEED = 160.0;      // pixels per second
    var player : h2d.Bitmap;
    var coin : h2d.Bitmap;
    var label : h2d.Text;
    var score = 0;

    override function init() {
        s2d.scaleMode = LetterBox(320, 180);
        player = new h2d.Bitmap(h2d.Tile.fromColor(0x3080FF, 12, 12), s2d);
        player.setPosition(40, 40);
        coin = new h2d.Bitmap(h2d.Tile.fromColor(0xFFD020, 6, 6), s2d);
        placeCoin();
        label = new h2d.Text(hxd.res.DefaultFont.get(), s2d);
        label.setPosition(4, 4);
        refresh();
    }

    override function update(dt : Float) {
        var dx = 0.0, dy = 0.0;
        if (hxd.Key.isDown(hxd.Key.LEFT) || hxd.Key.isDown(hxd.Key.A)) dx -= 1;
        if (hxd.Key.isDown(hxd.Key.RIGHT) || hxd.Key.isDown(hxd.Key.D)) dx += 1;
        if (hxd.Key.isDown(hxd.Key.UP) || hxd.Key.isDown(hxd.Key.W)) dy -= 1;
        if (hxd.Key.isDown(hxd.Key.DOWN) || hxd.Key.isDown(hxd.Key.S)) dy += 1;
        player.x = hxd.Math.clamp(player.x + dx * SPEED * dt, 0, s2d.width - 12);
        player.y = hxd.Math.clamp(player.y + dy * SPEED * dt, 0, s2d.height - 12);

        if (player.getBounds().intersects(coin.getBounds())) {
            score++;
            refresh();
            placeCoin();
        }
    }

    function placeCoin() {
        coin.setPosition(Std.random(s2d.width - 6), Std.random(s2d.height - 6));
    }

    function refresh() {
        label.text = 'Score: $score';
    }

    static function main() {
        new Main();
    }
}
```

## Sources
- https://github.com/HeapsIO/heaps/releases (2.1.1 2025-06-07 latest, 2.1 2025-03-23, 2.0 2024-01-01)
- https://raw.githubusercontent.com/HeapsIO/heaps/master/CHANGELOG.md (2.0 Vector/Vector4 and buffer unification, 2.0.1 `move` fix, 1.9 Haxe 4.2.1 requirement, 1.5 renames and dt in seconds)
- https://raw.githubusercontent.com/HeapsIO/heaps/master/hxd/App.hx (fields engine/s3d/s2d/sevents; init/update/onResize/loadAssets/dispose/setScene)
- https://raw.githubusercontent.com/HeapsIO/heaps/master/hxd/Key.hx, hxd/Save.hx, h2d/Scene.hx (ScaleMode values), h2d/Interactive.hx, h2d/Tile.hx, h2d/Anim.hx, h2d/Object.hx, h3d/Vector.hx, h3d/prim/Cube.hx, h3d/scene/Mesh.hx (signatures)
- https://raw.githubusercontent.com/HeapsIO/heaps/master/samples/Base3D.hx and samples/Network.hx (3D setup, hxbit replication)
- https://heaps.io/documentation/hello-world.html (compile.hxml for JS, DefaultFont text)
- https://heaps.io/documentation/hello-hashlink.html (hlsdl / hldx / dx12, `hl hello.hl`, HL/C)
- https://heaps.io/documentation/installation.html (haxelib install / git, HashLink libs)
- https://heaps.io/documentation/resource-management.html (initEmbed/initLocal/initPak, resourcesPath, live update)
- https://heaps.io/documentation/h2d-introduction.html (h2d basics)
- https://heaps.io/ (showcase: Dead Cells, Northgard, Evoland, Darksburg; console logos)
- https://github.com/HeapsIO/hide (Hide editor, NW.js, nightly builds)
- https://haxe.org/download/ and https://github.com/HaxeFoundation/haxe/releases (Haxe 4.3.7 2025-05-09; 5.0.0-preview.1 2025-07-04)
- https://github.com/HaxeFoundation/hashlink/releases (HL 1.16, 2026-08-03)

## Confidence and gaps
- High: lifecycle, App fields, ScaleMode, Key/Save/Interactive/Tile signatures, version numbers (read from source and GitHub API).
- Medium: hxbit usage beyond the sample; `hxd.Pad` config field names (check source); Hide workflow (README only, no run).
- Not verified: console export process, exact HL/C build commands per platform, whether a Heaps release newer than 2.1.1 is imminent (master is active as of 2026-10-13). Heaps master may require a newer HashLink than 1.14; pin versions per project.
- Wartales / Dune: Spice Wars as Heaps titles are widely reported but not on heaps.io; not claimed above.
