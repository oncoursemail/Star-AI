# Trending Unity alternatives in 2026 (beyond Unity/Unreal/Godot): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: see the per-engine table (Fyrox 1.0.x 2026-03; Ebitengine 2.10.5 2026-10-09; Macroquad 0.4.16 2026-07; GDevelop 5.6.283 2026-09-29; KAPLAY 3001.0.19 2025-06-15; Excalibur 0.32.0 2025-12-23; Wicked Engine 0.72.120 2026-10-02; HYTOPIA SDK 0.15.2 2026-02-13).** All free; mostly MIT/Apache/Zlib/BSD open source; HYTOPIA SDK is proprietary-licensed on a hosted platform.

Scope note: Unity, Unreal and Godot are covered elsewhere. Bevy, LÖVE, Defold, Phaser, PixiJS, raylib, SDL3, GameMaker, Cocos Creator and Solar2D have their own docs in this folder; they appear here only as one-line context. This doc covers the next tier that people actually adopted after the Unity Runtime Fee episode.

## At a glance
| | |
|---|---|
| Best for | Choosing a non-Big-3 engine by language and genre: Rust 3D with editor (Fyrox), Go 2D (Ebitengine), Rust 2D quick (Macroquad), no-code (GDevelop), JS beginner 2D (KAPLAY), TS 2D structured (Excalibur), C++ high-end 3D (Wicked Engine), Roblox-like hosted multiplayer in TS (HYTOPIA) |
| Weak at | Each is narrower than Unity: smaller asset stores, fewer console ports, thinner docs; most have no built-in networking |
| Language(s) | Rust, Go, JavaScript/TypeScript, C++/Lua, visual events |
| Editor / tooling | Fyrox (FyroxEd + project manager), GDevelop (full editor), Wicked (editor app); others are code-only libraries |
| Platforms (export) | Desktop for all; web for Ebitengine/Macroquad/GDevelop/KAPLAY/Excalibur/HYTOPIA; mobile for Ebitengine/Macroquad/GDevelop; consoles: Ebitengine (Switch via third parties), Wicked (Xbox Series, PS5 with private files) |
| License / cost | Free; see table below |
| Roblox-likeness | low for most; medium for GDevelop (editor + one-click web/multiplayer features); high for HYTOPIA (hosted, server-authoritative, player events, browser play) |

### Context: why this list exists
- Unity announced a per-install Runtime Fee in September 2023, then cancelled it for games on 2024-09-12 (Unity blog); it raised Unity Pro 8% to $2,200/seat (2025-01-01) and doubled the Personal threshold to $200k. Trust damage drove jam and indie migration mostly to Godot, with a long tail to the engines below.
- GMTK Game Jam engine share (organizer survey, reported by Game World Observer 2026-07-29): Godot 16% (2022), 19% (2023), 37% (2024), 39% (2025), 47% (2026); 2026 Unity 34%, GameMaker 5%, Unreal 3%. Everything else, including all engines in this doc, shares the remaining ~11%.
- Redot (Godot fork, MIT, forked Sept 2024): latest `redot-26.2-stable` on 2026-06-30, 6.1k GitHub stars. API is Godot's; use Godot knowledge and check fork-specific changes.

### Evidence table (pulled 2026-10-13)
| Engine | Lang | Latest stable (date) | GitHub stars | Other adoption signal | License |
|---|---|---|---|---|---|
| GDevelop | events + JS | 5.6.283 (2026-09-29) | 27.5k | itch.io "made with GDevelop": 19,208 games | MIT (repo shows custom notice; engine MIT) |
| Ebitengine | Go | 2.10.5 (2026-10-09; 2.10.0 2026-09-08) | 13.6k | Steam/Switch shipped titles in showcase | Apache-2.0 |
| Fyrox | Rust | 1.0.0 (2026-03-29 GitHub; crate 1.0.1) | 9.6k | first 1.0 after 7 years | MIT |
| Wicked Engine | C++/Lua | v0.72.120 (2026-10-02) | 7.3k | editor on Steam, consoles | MIT |
| Redot | GDScript/C# | 26.2 (2026-06-30) | 6.1k | Godot fork | MIT |
| Macroquad | Rust | 0.4.16 (crates.io, 2026-07-30) | 4.7k | 1.86M crate downloads | MIT/Apache-2.0 |
| Armory3D | Haxe (Blender) | 26.02 (2026-02-16) | 3.3k | Blender add-on | Zlib |
| Excalibur.js | TypeScript | 0.32.0 (2025-12-23; 0.33 in alpha) | 2.35k | | BSD-2-Clause |
| KAPLAY | JS/TS | 3001.0.19 (2025-06-15); 4000 alpha.27.1 (2026-05-12) | 1.8k | Kaboom.js successor | MIT |
| UPBGE | Python (Blender) | 0.50 (2026-01-04) | 1.8k | Blender Game Engine fork | GPL (Blender) |
| HYTOPIA SDK | TS/JS | 0.15.2 npm (2026-02-13), alpha | n/a (SDK repo) | browser voxel platform | proprietary (LICENSE.md) |
| raylib (context) | C + 70 bindings | 6.0 (2026-04-23) | 35.2k | Odin ships `vendor:raylib` (6.0) | Zlib |

Other mentions: Stencyl (itch "made with" 283 games; legacy, low activity), Bitsy (12,078 itch games; tiny narrative tool, not a general engine), Odin + raylib and Zig + raylib (community bindings; raylib API applies), LÖVE 11.5 (2023-12-03, still current stable), Bevy 0.20 (2026-10-08; see bevy.md), Defold 1.14.0 (2026-10-12; see defold.md), Phaser 4.2.1 (see phaser.md).

## Architecture and lifecycle
**Fyrox 1.0 (Rust, editor-first)**
- A game is a `Plugin` (crate `game`) loaded by both the editor (`editor` crate) and per-platform executors. Project manager (`cargo install fyrox-project-manager`) creates the workspace; `fyrox-template script --name MyScript` scaffolds scripts.
- Scripts implement `ScriptTrait` on nodes: `on_init`, `on_start`, `on_update`, `on_os_event`, `on_message`, `on_deinit`, all returning `GameResult` in 1.0. Context gives `ctx.scene`, `ctx.handle`, `ctx.dt`, `ctx.input_state`, `ctx.resource_manager`.
- Scripts are registered in `Plugin::register` via `context.serialization_context.script_constructors.add::<MyScript>("My Script")`. Derives needed: `Visit, Reflect, Default, Debug, Clone, TypeUuidProvider, ComponentProvider` plus `#[type_uuid(id = "...")]`.
- Scene graph with handles (`Handle<Node>`) into `scene.graph`; editor-authored scenes (`.rgs`).

**Ebitengine 2.10 (Go)**
- Implement `ebiten.Game`: `Update() error` (fixed 60 TPS by default), `Draw(screen *ebiten.Image)`, `Layout(outsideWidth, outsideHeight int) (int, int)` for logical resolution; start with `ebiten.RunGame(g)`. 2.10: pure Go on desktop (no Cgo on macOS/Linux), Go 1.25+ required, experimental VM guest mode for headless automated tests.

**Macroquad 0.4 (Rust)**
- Immediate-mode. `#[macroquad::main("Title")] async fn main() { loop { ...; next_frame().await } }`. The async loop exists so the same code runs on WASM/Android. Globals like `is_key_down(KeyCode::Left)`, `get_frame_time()`, `draw_rectangle`, `draw_text`.

**GDevelop 5.6 (no-code events)**
- Scenes contain objects (Sprite, Text, Tiled Sprite, 3D Box/Model...), behaviors (Platformer character, Top-down movement, Physics 2/3, Pathfinding, Multiplayer object) and an event sheet (conditions -> actions) evaluated every frame top to bottom. Extensions add custom actions/behaviors; JavaScript code events are an escape hatch (`runtimeScene`, `objects` array, `gdjs.evtTools`). Recent: navmesh pathfinding (5.6.278), gameplay tests (experimental), AI agent that edits extensions (5.6.283).

**KAPLAY 3001 (JS/TS)**
- Call `kaplay({...})` once; it installs global functions (unless `global: false`). Game objects are component lists: `add([sprite("bean"), pos(80, 40), area(), body(), "player"])`. Events: `onUpdate`, `onKeyDown`, `onKeyPress`, `obj.onCollide("tag", fn)`, `scene()`/`go()`. Successor of Kaboom.js.

**Excalibur 0.32 (TypeScript)**
- `new ex.Engine({ width, height, displayMode })`, `ex.Actor` with `onInitialize(engine)`, `onPreUpdate(engine, elapsed)`, `onPostUpdate`; `ex.Scene`; `engine.add(actor)`; `engine.start(loader)`. ECS underneath; physics bodies with `collisionType` (`ex.CollisionType.Active/Fixed/Passive`).

**Wicked Engine (C++/Lua)**
- `wi::Application` owns the loop; you `ActivatePath(&renderPath)` where `wi::RenderPath3D`/`RenderPath2D` subclasses override `Start()`, `Update(float dt)`, `Render()`. ECS scene (`wi::scene::GetScene()`, `Component_GetTransform(entity)`). Lua scripts run from the backlog console, `startup.lua`, or `dofile`.

**HYTOPIA (TS, hosted server-authoritative)**
- Server-only game code: `startServer(world => { ... })`. `world.loadMap(map)`, `world.on(PlayerEvent.JOINED_WORLD, ({ player }) => new DefaultPlayerEntity({ player, name }).spawn(world, { x, y, z }))`, `player.ui.load('ui/index.html')`. Client is the HYTOPIA web client; physics, networking, prediction handled by the platform.

## Project layout
- Fyrox: workspace `Cargo.toml`, `data/scene.rgs`, `game/src/lib.rs` (plugin + scripts), `editor/`, `executor/`, `executor-wasm/`, `executor-android/`, `export-cli/` (1.0).
- Ebitengine: `go.mod` (`github.com/hajimehoshi/ebiten/v2`), `main.go`, assets via `embed`.
- Macroquad: `Cargo.toml` (`macroquad = "0.4"`), `src/main.rs`, `assets/`.
- GDevelop: `game.json` project + `assets/`; events stored in JSON (diff-unfriendly).
- KAPLAY: `npx create-kaplay my-game` gives Vite project with `src/main.js`; or one HTML file with the script from a CDN.
- Excalibur: `npm create excalibur@latest` (Vite templates), `src/main.ts`, `src/resources.ts` (ImageSource, Loader).
- Wicked: clone repo, `WickedEngine.sln` or CMake; `Samples/Template_*` as starting point; `.wiscene` files.
- HYTOPIA: `npx hytopia init` style boilerplate (check docs), `index.ts`, `assets/map.json` (built on build.hytopia.com), `assets/ui/`.

## Scripting idioms
```go
// Ebitengine: input + draw (2.9+ names)
func (g *Game) Update() error {
    if ebiten.IsKeyPressed(ebiten.KeyArrowRight) { g.x += 2 }
    if inpututil.IsKeyJustPressed(ebiten.KeySpace) { g.jump() }
    return nil
}
func (g *Game) Draw(screen *ebiten.Image) {
    vector.FillRect(screen, float32(g.x), float32(g.y), 16, 16, color.RGBA{0x30, 0x80, 0xff, 0xff}, false)
    op := &ebiten.DrawImageOptions{}
    op.GeoM.Translate(g.x, g.y)          // transform via GeoM, not x/y args
    screen.DrawImage(g.sprite, op)
}
```
```rust
// Macroquad: frame-rate independent movement
let dt = get_frame_time();
if is_key_down(KeyCode::Right) { x += 200.0 * dt; }
if is_key_pressed(KeyCode::Space) { /* jump */ }
let hit = Rect::new(x, y, 16., 16.).overlaps(&Rect::new(cx, cy, 8., 8.));
```
```js
// KAPLAY: components + tags
const player = add([rect(24, 24), pos(40, 40), area(), body(), "player"]);
onKeyDown("right", () => player.move(200, 0));   // move() is pixels/second
player.onCollide("coin", (c) => { destroy(c); score.value++; });
```
```ts
// Excalibur: keyboard in an Actor
class Player extends ex.Actor {
  onPreUpdate(engine: ex.Engine, elapsed: number) {
    this.vel = ex.vec(0, 0);
    if (engine.input.keyboard.isHeld(ex.Keys.Right)) this.vel.x = 150;
  }
}
```
```rust
// Fyrox 1.0 script
impl ScriptTrait for Player {
    fn on_update(&mut self, ctx: &mut ScriptContext) -> GameResult {
        if ctx.input_state.is_key_down(KeyCode::KeyD) {
            ctx.scene.graph[ctx.handle].local_transform_mut().offset(Vector3::new(5.0 * ctx.dt, 0.0, 0.0));
        }
        Ok(())
    }
}
```
```js
// GDevelop JavaScript code event (objects passed as array)
for (const o of objects) {
  o.setX(o.getX() + 100 * o.getElapsedTime(runtimeScene) / 1000); // elapsed time is ms
}
```

## Pitfalls (what AI answers get wrong)
1. **Ebitengine v1 APIs are gone**: `ebiten.Run(update, w, h, scale, title)` is v1; v2 needs the `Game` interface + `ebiten.RunGame`. Import path must be `github.com/hajimehoshi/ebiten/v2`.
2. **Ebitengine deprecations**: `ebitenutil.DrawRect` (deprecated 2.5) -> `vector.DrawFilledRect` (itself deprecated 2.9) -> `vector.FillRect(dst, x, y, w, h, clr, antialias)`. `(*Image).Size()` -> `Bounds()` (2.5). `Dispose` -> `Deallocate` (2.7). Old `text` package -> `text/v2` (2.7). `audio.Player.Seek` -> `SetPosition` (2.6). Go 1.25+ needed for 2.10.
3. **Fyrox 1.0 script methods return `GameResult`** (`Ok(())`); pre-1.0 examples return `()` and do not compile. `AsyncSceneLoader` was removed in 1.0 (use `PluginContext` scene-loading helpers), default root renamed `__ROOT__` -> `SceneRoot`. Forgetting `script_constructors.add::<T>()` makes scripts invisible in the editor.
4. **Macroquad loop must `next_frame().await`** each iteration; a missing await freezes the window. `#[macroquad::main]` requires `async fn main`. Use `macroquad::rand::gen_range`, not the `rand` crate (WASM). Macroquad's `draw_text` takes `font_size` then `Color`.
5. **KAPLAY is not Kaboom**: call `kaplay()` (the `kaboom()` global and `kaboom` package are the abandoned predecessor). 3001 is stable; 4000 is alpha with breaking changes (`z()` global, layers global, primitive UVs, sprite frame coordinates in pixels). Pin the version.
6. **Excalibur 0.30 removed `ex.Input.*`**: use `ex.Keys.Left`, not `ex.Input.Keys.Left`. Also removed: `engine.goto` -> `goToScene`, `GraphicsComponent.show` -> `use`, `ex.Physics.*` statics -> `new ex.Engine({ physics: ... })`, event `delta` -> `elapsedMs`. 0.32: realistic-solver bodies sleep by default.
7. **GDevelop JS events: elapsed time is in milliseconds** (`getElapsedTime(runtimeScene) / 1000`); the docs recommend extensions over raw JS events; `objects` contains only the picked instances.
8. **Wicked Engine version scheme** is `0.<major>.<build>` (e.g. 0.72.120) with frequent API churn; console builds need private extension files. Use the `wi::` namespaces (`wi::Application`, `wi::RenderPath3D`, `wi::input::Press`), older tutorials use pre-namespace names.
9. **HYTOPIA SDK is alpha**: breaking changes between minor versions; server-authoritative only (no client scripting of physics). Code that assumes client-side LocalScripts does not apply.
10. **raylib 6.0 breaking changes** (if using via Odin/Zig/C): `DrawCircleGradient` takes a `Vector2` center, `DrawModelPoints*` removed, pan range now -1..1, `utils` module merged into core, shader loading names changed.
11. **Redot is a Godot fork**, not a new engine: answer with Godot 4 APIs and note any Redot-specific differences only if verified.
12. **Armory3D/UPBGE run inside Blender**: Armory uses Haxe traits (`iron.Trait`), UPBGE uses Python `bge` logic; answers mixing Blender `bpy` editor scripting with runtime game logic are wrong.

## Rendering
- Fyrox: deferred PBR 3D, 2D scenes, GI-lite features, editor material editor; OpenGL-based renderer (1.0).
- Ebitengine: 2D only, GPU batched `DrawImage`/`DrawTriangles`, Kage shaders (Go-like), shader precompilation (2.10 experimental).
- Macroquad: 2D immediate API on miniquad (GL/Metal/WebGL), basic 3D (`draw_cube`, `set_camera(&Camera3D{..})`), `material` shaders.
- GDevelop: PixiJS 2D + Three.js 3D, effects, lights.
- KAPLAY / Excalibur: WebGL 2D; Excalibur has `ex.Sprite`, `ex.SpriteSheet`, `ex.Animation`, post-processors.
- Wicked: high-end DX12/Vulkan/Metal renderer (path tracing, DDGI, volumetrics, ocean, terrain).
- HYTOPIA: platform client (Three.js-based voxel renderer); you provide GLTF models and block textures.

## Physics
- Fyrox: Rapier-based 2D and 3D rigid bodies, colliders, character controllers.
- Ebitengine / Macroquad: none built in (use resolv/box2d bindings or rapier crates; community).
- GDevelop: Physics 2 (Box2D) and Physics 3D (Jolt) behaviors, platformer/top-down behaviors.
- KAPLAY: `area()` + `body()` components (gravity via `setGravity`), simple solver.
- Excalibur: built-in arcade and realistic solvers (`CollisionType.Active/Fixed/Passive`), islands/sleeping (0.32).
- Wicked: Jolt physics, ragdolls, vehicles (check features.txt).
- HYTOPIA: server-side physics with colliders and rigid bodies (`world.simulation`).

## Input
- Fyrox: `ctx.input_state.is_key_down/is_key_pressed(KeyCode::KeyA)` or `on_os_event` winit events.
- Ebitengine: `ebiten.IsKeyPressed`, `inpututil.IsKeyJustPressed`, gamepads `ebiten.IsStandardGamepadButtonPressed`, touch IDs.
- Macroquad: `is_key_down`, `is_key_pressed`, `mouse_position`, `touches()`.
- GDevelop: conditions (Key pressed, Mouse button), Gamepads extension.
- KAPLAY: `onKeyDown/onKeyPress`, Buttons API (`kaplay({ buttons: { jump: { keyboard: ["space"], gamepad: ["south"] } } })` + `onButtonPress("jump")`, 3001+).
- Excalibur: `engine.input.keyboard.isHeld/wasPressed(ex.Keys.X)`, `engine.input.pointers`, `inputMapper`.
- Wicked: `wi::input::Down/Press(wi::input::KEYBOARD_BUTTON_SPACE)`; Lua `input.Press(...)`.
- HYTOPIA: `DefaultPlayerEntity` maps WASD/mouse automatically; custom via entity controllers and player input on the server.

## UI
- Fyrox: built-in retained UI library (also used by the editor) and UI editor.
- Ebitengine: none built in (community: ebitenui); `text/v2` for text, `exp/textinput` IME.
- Macroquad: immediate `root_ui()` widgets (`macroquad::ui`), egui via `egui-macroquad` (community).
- GDevelop: Text, Button, Slider, Text input, Panel sprite objects.
- KAPLAY: `text()` component, build buttons from `rect`+`area`+`onClick`.
- Excalibur: `ex.Label`, `ex.ScreenElement`, or HTML/CSS overlay (recommended for complex UI).
- Wicked: `wi::gui` widgets.
- HYTOPIA: HTML/CSS/JS overlay per player (`player.ui.load`, `player.ui.sendData`).

## Networking and multiplayer
- Built in: HYTOPIA (core feature, hosted, server-authoritative); GDevelop (Multiplayer extension with lobbies on gd.games); Fyrox has no high-level netcode (use crates).
- None built in: Ebitengine, Macroquad, KAPLAY, Excalibur, Wicked (bring your own WebSocket/ENet/Steam).

## Save data
- Ebitengine/Macroquad/Fyrox/Wicked: write files yourself (`os`, `std::fs`, `serde`); Macroquad on WASM uses `quad-storage` (community). Fyrox scenes/state can use `Visit` serialization.
- GDevelop: Storage actions (Write/Read to storage, JSON), cloud via its backend services.
- KAPLAY: `setData(key, value)` / `getData(key, default)` (localStorage).
- Excalibur: `localStorage` directly.
- HYTOPIA: persisted player data APIs on the platform (`player.getPersistedData()` / `player.setPersistedData(...)`, listed in the 0.15.2 SDK `docs/server.player.md`).

## Performance
- Ebitengine: batch draws by reusing the same source image/atlas; avoid creating `ebiten.Image` per frame; `ebiten.ActualFPS/ActualTPS`.
- Macroquad: immediate draws batched automatically; keep textures in atlases; build `--release`.
- Fyrox: `--release`, use the project manager's release executor; Rust debug builds are slow (set `opt-level` for deps in dev profile).
- KAPLAY/Excalibur: object counts in the low thousands; pool objects; avoid per-frame `add`/`destroy` storms; Excalibur 0.32 profiling via `engine.stats`.
- GDevelop: use object groups, avoid "for each" over large sets, use the profiler (5.6.281 improved).
- Wicked: GPU-heavy by design; tune via graphics options.

## Build and export
- Fyrox: `cargo run --package export-cli -- --destination_folder ... --build-target ...` (1.0; flag spelling inconsistent in the blog, check `--help`), or the editor's export window. Targets: Windows/Linux/macOS/WASM/Android.
- Ebitengine: `go build`; WASM via `GOOS=js GOARCH=wasm go build -o game.wasm` + `wasm_exec.js`; mobile via `ebitenmobile bind`; Steam docs on ebitengine.org.
- Macroquad: `cargo build --release`; WASM `--target wasm32-unknown-unknown` + `mq_js_bundle.js`; Android via `cargo-quad-apk` (docker).
- GDevelop: one-click web (gd.games), Android/iOS/desktop builds (cloud build quotas on free tier), HTML5 export.
- KAPLAY/Excalibur: `npm run build` (Vite) -> static site; desktop via Electron/Tauri (community).
- Wicked: Visual Studio / CMake / Xcode builds.
- HYTOPIA: deploy through the HYTOPIA platform tooling (see dev.hytopia.com).

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `undefined: ebiten.Run` | v1 API | Implement `Game` and call `ebiten.RunGame` |
| `vector.DrawFilledRect is deprecated` warning | 2.9 rename | `vector.FillRect(screen, x, y, w, h, clr, false)` |
| Go build error on Ebitengine 2.10 | Old Go toolchain | Go 1.25+ |
| Fyrox script `expected GameResult, found ()` | Pre-1.0 example | Return `Ok(())` |
| Fyrox script not in editor list | Not registered | `script_constructors.add::<T>("Name")` in `Plugin::register` |
| Macroquad window frozen/white | Missing `next_frame().await` | Await at the end of every loop |
| `kaboom is not defined` | Using old Kaboom API | `import kaplay from "kaplay"; kaplay();` |
| KAPLAY code from 4000 docs fails on 3001 | Alpha API | Match docs to installed version |
| `Cannot read properties of undefined (reading 'Keys')` | `ex.Input.Keys` removed in 0.30 | `ex.Keys` |
| `engine.goto is not a function` | Removed 0.30 | `engine.goToScene("name")` |
| GDevelop object moves 1000x too fast | Treating `getElapsedTime` as seconds | Divide by 1000 |
| HYTOPIA game breaks after `npm update` | Alpha SDK breaking change | Pin `hytopia` version; read release notes |

## Mapping from Roblox
| Roblox | Closest equivalent | Notes |
|---|---|---|
| Workspace / Instance tree | Fyrox `scene.graph`; GDevelop scene objects; KAPLAY object tree (`add`, `getTreeRoot()`); Excalibur `Scene`; HYTOPIA `world` entities | Ebitengine/Macroquad have no tree |
| Part | Fyrox mesh node + rigid body; GDevelop 3D Box; HYTOPIA blocks/`Entity` | |
| Model | Fyrox prefab (`.rgs`), GDevelop custom object, HYTOPIA GLTF entity | |
| Script / LocalScript | Fyrox `ScriptTrait`; GDevelop events; HYTOPIA server TS (no client scripts) | HYTOPIA is closest to server Scripts |
| ModuleScript | Rust/Go/TS modules | |
| RemoteEvent | HYTOPIA `player.ui.sendData` / UI `hytopia.sendData`; GDevelop multiplayer messages | Others: none |
| DataStore | HYTOPIA persisted data; GDevelop storage/cloud; others local files | |
| Players | HYTOPIA `PlayerEvent.JOINED_WORLD`, `player` objects; GDevelop multiplayer players | |
| Humanoid | HYTOPIA `DefaultPlayerEntity`; GDevelop Platformer/3D character behaviors; Fyrox character controller | |
| RunService.Heartbeat | `Update()` / `on_update` / `onUpdate` / `onPreUpdate` / events sheet | |
| TweenService | GDevelop Tween behavior; KAPLAY `tween()`; Excalibur `actor.actions` | Others manual |
| CollectionService tags | KAPLAY string tags; GDevelop object groups; Excalibur `addTag`/`query` | |
| Attributes | Struct fields; GDevelop object variables | |
| ScreenGui | HYTOPIA HTML UI; GDevelop UI layer; Excalibur `ScreenElement` | |
| UserInputService | per-engine input APIs above | |
| task.wait | KAPLAY `wait(sec)` / `await wait()`; GDevelop "Wait X seconds"; Rust/Go timers | |
| Studio playtest | Fyrox editor Play; GDevelop Preview; `go run .`; `cargo run`; `npm run dev`; `npm run dev` + HYTOPIA web client | |
| Publishing | gd.games, itch.io, Steam, HYTOPIA platform | |

## Minimal example
Ebitengine 2.10 (Go): move a square with arrows, collect a coin, show score.
```go
package main

import (
	"fmt"
	"image/color"
	"log"
	"math/rand"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/ebitenutil"
	"github.com/hajimehoshi/ebiten/v2/vector"
)

const W, H = 320, 240

type Game struct {
	px, py, cx, cy float64
	score          int
}

func (g *Game) placeCoin() { g.cx, g.cy = float64(rand.Intn(W-8)), float64(rand.Intn(H-8)) }

func (g *Game) Update() error {
	const speed = 2.0 // per tick (60 TPS)
	if ebiten.IsKeyPressed(ebiten.KeyArrowLeft) { g.px -= speed }
	if ebiten.IsKeyPressed(ebiten.KeyArrowRight) { g.px += speed }
	if ebiten.IsKeyPressed(ebiten.KeyArrowUp) { g.py -= speed }
	if ebiten.IsKeyPressed(ebiten.KeyArrowDown) { g.py += speed }
	if g.px < g.cx+8 && g.px+16 > g.cx && g.py < g.cy+8 && g.py+16 > g.cy {
		g.score++
		g.placeCoin()
	}
	return nil
}

func (g *Game) Draw(screen *ebiten.Image) {
	vector.FillRect(screen, float32(g.px), float32(g.py), 16, 16, color.RGBA{0x30, 0x80, 0xff, 0xff}, false)
	vector.FillRect(screen, float32(g.cx), float32(g.cy), 8, 8, color.RGBA{0xff, 0xd0, 0x20, 0xff}, false)
	ebitenutil.DebugPrint(screen, fmt.Sprintf("Score: %d", g.score))
}

func (g *Game) Layout(outsideWidth, outsideHeight int) (int, int) { return W, H }

func main() {
	g := &Game{px: 40, py: 40}
	g.placeCoin()
	ebiten.SetWindowSize(W*2, H*2)
	ebiten.SetWindowTitle("Coins")
	if err := ebiten.RunGame(g); err != nil {
		log.Fatal(err)
	}
}
```
Macroquad 0.4 equivalent:
```rust
use macroquad::prelude::*;

#[macroquad::main("Coins")]
async fn main() {
    let (mut x, mut y) = (40.0f32, 40.0f32);
    let mut coin = vec2(macroquad::rand::gen_range(0.0, screen_width() - 8.0), macroquad::rand::gen_range(0.0, screen_height() - 8.0));
    let mut score = 0;
    loop {
        let dt = get_frame_time();
        if is_key_down(KeyCode::Left) { x -= 200.0 * dt; }
        if is_key_down(KeyCode::Right) { x += 200.0 * dt; }
        if is_key_down(KeyCode::Up) { y -= 200.0 * dt; }
        if is_key_down(KeyCode::Down) { y += 200.0 * dt; }
        if Rect::new(x, y, 16.0, 16.0).overlaps(&Rect::new(coin.x, coin.y, 8.0, 8.0)) {
            score += 1;
            coin = vec2(macroquad::rand::gen_range(0.0, screen_width() - 8.0), macroquad::rand::gen_range(0.0, screen_height() - 8.0));
        }
        clear_background(DARKBLUE);
        draw_rectangle(x, y, 16.0, 16.0, SKYBLUE);
        draw_rectangle(coin.x, coin.y, 8.0, 8.0, GOLD);
        draw_text(&format!("Score: {score}"), 8.0, 20.0, 24.0, WHITE);
        next_frame().await
    }
}
```
HYTOPIA SDK 0.15 (server entry, from the official boilerplate):
```ts
import { startServer, DefaultPlayerEntity, PlayerEvent } from 'hytopia';
import worldMap from './assets/map.json';

startServer(world => {
  world.loadMap(worldMap);
  world.on(PlayerEvent.JOINED_WORLD, ({ player }) => {
    const entity = new DefaultPlayerEntity({ player, name: 'Player' });
    entity.spawn(world, { x: 0, y: 10, z: 0 });
    player.ui.load('ui/index.html');
  });
  world.on(PlayerEvent.LEFT_WORLD, ({ player }) => {
    world.entityManager.getPlayerEntitiesByPlayer(player).forEach(e => e.despawn());
  });
});
```

## Sources
- https://api.github.com/repos/{owner}/{repo} and /releases/latest for FyroxEngine/Fyrox, hajimehoshi/ebiten, not-fl3/macroquad, 4ian/GDevelop, kaplayjs/kaplay, excaliburjs/Excalibur, turanszkij/WickedEngine, armory3d/armory, UPBGE/upbge, raysan5/raylib, Redot-Engine/redot-engine, love2d/love, bevyengine/bevy, defold/defold, phaserjs/phaser (stars, latest tags, dates on 2026-10-13)
- https://crates.io/api/v1/crates/macroquad and /fyrox (0.4.16; 1.0.1; downloads)
- https://registry.npmjs.org/kaplay, /excalibur, /hytopia (dist-tags and dates)
- https://unity.com/blog/unity-is-canceling-the-runtime-fee (2024-09-12 cancellation, Pro $2,200, Personal $200k)
- https://gameworldobserver.com/2026/07/29/unity-is-no-longer-the-leader-godot-has-become-the-most-popular-engine-at-gmtk-game-jam-2026 (GMTK 2022-2026 shares)
- https://itch.io/games/made-with-gdevelop (and made-with-bitsy, -stencyl, -raylib, -pico-8: counts on 2026-10-13)
- https://fyrox.rs/blog/post/fyrox-game-engine-1-0-0/ (1.0 changes, export-cli, removals)
- https://fyrox-book.github.io/scripting/script.html, /input/keyboard.html, /beginning/scripting.html (ScriptTrait with GameResult, input_state, project manager)
- https://ebitengine.org/en/documents/2.10.html, /2.9.html, /2.7.html, /2.5.html (release notes, deprecations, Go 1.25)
- https://pkg.go.dev/github.com/hajimehoshi/ebiten/v2 and /vector, /inpututil (signatures, v2.10.5)
- https://raw.githubusercontent.com/not-fl3/macroquad/master/README.md and https://docs.rs/macroquad/latest/ (main loop, input/draw functions, Rect::overlaps)
- https://wiki.gdevelop.io/gdevelop5/events/js-code/ and https://github.com/4ian/GDevelop/releases (JS events API, 5.6.278-283)
- https://raw.githubusercontent.com/kaplayjs/kaplay/master/README.md and CHANGELOG.md (components, create-kaplay, 3001/4000 breaking changes)
- https://excaliburjs.com/docs/getting-started and https://raw.githubusercontent.com/excaliburjs/Excalibur/main/CHANGELOG.md (0.30 removals, 0.32 sleep)
- https://raw.githubusercontent.com/turanszkij/WickedEngine/master/README.md (platforms, wi::Application, Lua)
- https://cdn.jsdelivr.net/npm/hytopia@0.15.2/README.md and /boilerplate/index.ts (alpha status, startServer, PlayerEvent)
- https://raw.githubusercontent.com/raysan5/raylib/master/CHANGELOG (6.0 2026-04-23 breaking changes)
- https://raw.githubusercontent.com/odin-lang/Odin/master/vendor/raylib/raylib.odin (Odin vendor raylib VERSION "6.0")

## Confidence and gaps
- High: versions/dates/stars (APIs queried 2026-10-13), Ebitengine deprecations, Fyrox script signature, Excalibur 0.30 removals, KAPLAY version split, raylib 6.0 changes.
- Medium: GDevelop license wording (GitHub shows NOASSERTION), HYTOPIA CLI init command (not opened), Wicked physics backend, Fyrox renderer details, Macroquad UI/egui status.
- Not covered in depth: Armory3D and UPBGE APIs, Stencyl, Bitsy, Zig engines (no single trending Zig engine found with strong evidence; raylib-zig bindings are the common path). No itch.io-wide 2026 engine share data exists publicly; GMTK survey is the best proxy.
- No code in this doc was compiled or run.
