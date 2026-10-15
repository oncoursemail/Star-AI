---
name: engine-defold
description: Defold 1.14 (Lua): collections, game objects, components, msg.post message passing, go.property, factories, GUI scripts. Use for any Defold game code or project question.
---
# engine-defold
## Scope
Defold 1.14.0 (stable 2026-10-12; 1.13.x earlier in 2026). Check the project's version first (editor Help > About, or the bob.jar used): 1.13.0 and 1.14.0 both had breaking changes.

## Core model
- Collections (`.collection`) contain game objects; game objects hold components (script, sprite, collision object, factory, GUI, label, sound, camera, collection proxy).
- Everything is addressed by URL `[socket:]/path#component`; `"."` = this game object, `"#"` = this component. Ids are hashes.
- Scripts talk by async messages: `msg.post(url, "id", {table})` -> receiver's `on_message`.
- Script callbacks: `init`, `fixed_update`, `update`, `late_update` (1.12+), `on_message`, `on_input`, `on_reload`, `final`. State lives on `self`.

## Idioms
- Pre-hash ids at file top: `local JUMP = hash("jump")`; compare `action_id == JUMP`.
- `msg.post(".", "acquire_input_focus")` in `init` before expecting `on_input`.
- `go.property("speed", 200)` at top level with a literal default; read `self.speed`; other scripts use `go.get`/`go.set`.
- Move: `go.set_position(go.get_position() + v * dt)`; tween with `go.animate`.
- Spawn: `factory.create("#enemyfactory", pos, nil, { hp = 3 })` returns an id hash; remove with `go.delete(id)`.
- Delays: `timer.delay(1.0, false, fn)`.
- HUD in a `.gui_script`: `gui.get_node("score")`, `gui.set_text(node, "...")`.
- Collisions arrive as messages: `collision_response`, `contact_point_response`, `trigger_response` (`message.enter`).
- Saves: `sys.save(sys.get_save_file("game", "save"), tbl)` and `sys.load(path)`.

## Pitfalls
1. `message_id` and `action_id` are hashes; comparing to a plain string is always false.
2. No `acquire_input_focus` -> `on_input` never runs. Actions must exist in `game.input_binding`.
3. `go.property` must be top level with a literal default; no expressions, not inside `init`.
4. `msg.post` is queued, not a function call; results are not available on the next line. Message tables max 2 KB, no functions.
5. 1.13.0 removed asm.js (`js-web`; use `wasm-web`), Collada `.dae` (use glTF/GLB), old LiveUpdate format, and long-deprecated Lua functions.
6. 1.14.0 removed 32-bit Windows (`x86_64-win32` only) and the separate Lua state option: game, GUI and render scripts now always share globals.
7. 1.14.0 disables accelerometer input by default; 1.13.1 made desktop fullscreen borderless and SDL gamepad mappings default.
8. GUI nodes are not game objects: use `gui.*` in `.gui_script`, not `go.set_position`.
9. Collision group/mask must list each other or no messages are sent; kinematic bodies need manual separation from `contact_point_response`.
10. Collection proxies load a separate world (`load` -> `proxy_loaded` -> `enable`) with a unique collection name; factories spawn into the current world.

## Roblox to Defold
- Workspace/Instance tree -> collection of game objects
- Part -> game object with sprite + collision object
- Model -> collection spawned by a collection factory
- Script/LocalScript -> `.script` component; ModuleScript -> Lua module via `require`
- RemoteEvent -> `msg.post` (local only; networking needs extensions)
- Attributes -> `go.property`
- RunService.Heartbeat -> `update`; RenderStepped -> `late_update`
- TweenService -> `go.animate` / `gui.animate`
- ScreenGui -> GUI component + `.gui_script`
- UserInputService -> input bindings + `on_input`
- DataStore -> `sys.save`/`sys.load` (local)
- task.wait -> `timer.delay`
- Studio playtest -> Project > Build; shipping -> Project > Bundle or bob.jar

## Skeleton
```lua
-- player.script
go.property("speed", 200)

local LEFT, RIGHT = hash("left"), hash("right")
local TRIGGER = hash("trigger_response")

function init(self)
    msg.post(".", "acquire_input_focus")
    self.dir = 0
    self.score = 0
end

function update(self, dt)
    local p = go.get_position()
    p.x = p.x + self.dir * self.speed * dt
    go.set_position(p)
    self.dir = 0
end

function on_input(self, action_id, action)
    if action_id == LEFT then self.dir = -1
    elseif action_id == RIGHT then self.dir = 1 end
end

function on_message(self, message_id, message, sender)
    if message_id == TRIGGER and message.enter then
        self.score = self.score + 1
        go.delete(message.other_id)
        msg.post("/hud#hud", "set_score", { score = self.score })
    end
end
```

## Verification
Build in the editor (Project > Build) and read the Console, or run bob.jar `resolve build`. If neither ran, say the code is unverified.
