---
name: engine-alternatives-2026
description: 2026 Unity alternatives beyond Godot/Unreal: Fyrox 1.0, Ebitengine 2.10, Macroquad 0.4, GDevelop 5.6, KAPLAY, Excalibur 0.32, Wicked, HYTOPIA. Use for their APIs and traps.
---
# engine-alternatives-2026
## Scope
Fyrox 1.0 (Rust), Ebitengine 2.10 (Go), Macroquad 0.4 (Rust), GDevelop 5.6 (events/JS), KAPLAY 3001 (JS/TS; 4000 is alpha), Excalibur 0.32 (TS), Wicked Engine 0.72 (C++/Lua), HYTOPIA SDK 0.15 (TS, alpha). Redot is a Godot fork (use Godot 4 APIs). Check the project's version first (go.mod, Cargo.toml, package.json).

## Core model
- Ebitengine: implement `Update() error`, `Draw(screen *ebiten.Image)`, `Layout(w, h int) (int, int)`; run `ebiten.RunGame(g)`; 60 ticks per second.
- Macroquad: `async fn main()` loop ending in `next_frame().await`.
- Fyrox: game is a `Plugin`; node scripts implement `ScriptTrait` (`on_update` returns `GameResult`) and are registered in `Plugin::register`.
- KAPLAY: `kaplay()` then `add([components..., "tag"])`. Excalibur: `ex.Actor` subclasses with `onPreUpdate`.
- HYTOPIA: server-only `startServer(world => ...)`; the platform runs clients.

## Idioms
- Ebitengine: `inpututil.IsKeyJustPressed`, `DrawImageOptions.GeoM.Translate`.
- Macroquad: `is_key_down(KeyCode::Left)`, `get_frame_time()`, `Rect::overlaps`, `macroquad::rand::gen_range`.
- Fyrox: `ctx.input_state.is_key_down(KeyCode::KeyA)`, `ctx.scene.graph[ctx.handle]`, `ctx.dt`.
- KAPLAY: `onKeyDown("left", ...)`, `obj.onCollide("coin", ...)`, `obj.move(px_per_sec, 0)`, `wait(1)`.
- Excalibur: `engine.input.keyboard.isHeld(ex.Keys.Left)`, `actor.vel`, `CollisionType.Active/Fixed`.
- GDevelop: prefer events and extensions; JS events get `runtimeScene` and `objects`; `getElapsedTime` is ms.
- HYTOPIA: `world.on(PlayerEvent.JOINED_WORLD, ({ player }) => ...)`, `new DefaultPlayerEntity({ player, name }).spawn(world, pos)`, `player.ui.load(...)`.

## Pitfalls
1. Ebitengine v1 `ebiten.Run(update, w, h, scale, title)` is gone; use v2 `Game` + `RunGame`, import `github.com/hajimehoshi/ebiten/v2`.
2. Ebitengine: `ebitenutil.DrawRect` and `vector.DrawFilledRect` are deprecated; use `vector.FillRect` (2.9+). `Image.Size()` -> `Bounds()`; `Dispose` -> `Deallocate`. 2.10 needs Go 1.25+.
3. Fyrox 1.0 script callbacks return `GameResult` (`Ok(())`); pre-1.0 code returning `()` fails. `AsyncSceneLoader` was removed.
4. Fyrox scripts must be registered with `script_constructors.add::<T>("Name")` or the editor cannot see them.
5. Macroquad freezes without `next_frame().await`; use its own `rand` (not the `rand` crate) on WASM.
6. KAPLAY replaces Kaboom: call `kaplay()`, not `kaboom()`. 4000 alpha has breaking changes vs 3001; match docs to the installed version.
7. Excalibur 0.30 removed `ex.Input.*` (use `ex.Keys`), `engine.goto` (use `goToScene`), `GraphicsComponent.show` (use `use`); events use `elapsedMs`.
8. GDevelop JS: `getElapsedTime(runtimeScene)` is milliseconds; divide by 1000.
9. HYTOPIA SDK is alpha with breaking changes; pin the version. Logic is server-authoritative; no LocalScript equivalent.
10. Wicked Engine APIs live in `wi::` namespaces and change often.
11. raylib 6.0 (also via Odin/Zig) takes a Vector2 center in `DrawCircleGradient`; `DrawModelPoints` was removed.

## Roblox to Alternatives
- Workspace tree -> Fyrox scene graph, Excalibur Scene, HYTOPIA world
- Script -> HYTOPIA server TS (closest), Fyrox ScriptTrait, GDevelop events
- Players and PlayerAdded -> HYTOPIA `PlayerEvent.JOINED_WORLD`
- Humanoid -> HYTOPIA `DefaultPlayerEntity`, GDevelop character behaviors
- RunService.Heartbeat -> `Update()`, `on_update`, `onUpdate`
- CollectionService tags -> KAPLAY tags, GDevelop object groups
- task.wait -> KAPLAY `wait()`, GDevelop Wait action
- DataStore -> HYTOPIA persisted player data; others local files

## Skeleton
```go
package main

import (
	"image/color"
	"log"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/vector"
)

type Game struct{ x, y float64 }

func (g *Game) Update() error {
	if ebiten.IsKeyPressed(ebiten.KeyArrowLeft) { g.x -= 2 }
	if ebiten.IsKeyPressed(ebiten.KeyArrowRight) { g.x += 2 }
	return nil
}

func (g *Game) Draw(screen *ebiten.Image) {
	vector.FillRect(screen, float32(g.x), float32(g.y), 16, 16, color.White, false)
}

func (g *Game) Layout(w, h int) (int, int) { return 320, 240 }

func main() {
	if err := ebiten.RunGame(&Game{x: 40, y: 40}); err != nil {
		log.Fatal(err)
	}
}
```

## Verification
Run `go run .` (Ebitengine), `cargo run` (Macroquad/Fyrox), `npm run dev` (KAPLAY/Excalibur/HYTOPIA), or GDevelop Preview. Quote compiler output; never claim a run that did not happen.
