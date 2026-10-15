# Defold: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 1.14.0 (2026-10-12).** Free, Defold License (Apache 2.0 derived), no royalties; console targets (Switch, PlayStation, Xbox since 1.14.0) need platform-holder approval.

## At a glance
| | |
|---|---|
| Best for | Small, fast 2D (and light 3D) games for mobile, web (HTML5/wasm), desktop and consoles; tiny build sizes |
| Weak at | Heavy 3D, big open worlds, visual scripting (none), beginners who expect an Inspector-driven OOP workflow |
| Language(s) | Lua 5.1 (LuaJIT on most platforms) for game logic; C/C++ (also C#, experimental) in native extensions |
| Editor / tooling | Defold editor (scene/collection/atlas/GUI editors, debugger, profiler), `bob.jar` command-line builder, cloud build server for native extensions, editor scripts + editor HTTP API |
| Platforms (export) | Windows (x86_64 only since 1.14.0), macOS, Linux, iOS, Android, HTML5 (wasm-web; asm.js removed in 1.13.0), Nintendo Switch, PlayStation 4/5, Xbox (1.14.0) |
| License / cost | Free, source available on GitHub, Defold License |
| Roblox-likeness | medium: has a game-object hierarchy and an editor, but logic communicates by asynchronous message passing and addresses (URLs), not direct object references |

## Architecture and lifecycle
- **Collection** (`.collection`): a file that contains game objects and nested collections; the "main collection" (set in `game.project` -> bootstrap) is loaded at start. Collections are the scene/prefab unit.
- **Game object** (`.go` or embedded): has id, position/rotation/scale, can parent other game objects; holds **components**.
- **Components**: script (`.script`), sprite, collision object, factory, collection factory, collection proxy, GUI (`.gui` + `.gui_script`), label, tilemap, model, particlefx, sound, camera, mesh, light (new in 1.13.1).
- **Addressing**: every component has a URL `[socket:]/path#fragment`, e.g. `main:/player#script`. Shorthands `"."` = this game object, `"#"` = this component, `"#sprite"` = sprite on this game object. Ids are hashes at runtime.
- **Message passing**: `msg.post(receiver, message_id, [message_table])` queues a message; it is delivered later the same frame via `on_message`. Message tables are limited to 2 KB, no functions.
- **Script lifecycle** (game object scripts):
  - `init(self)` - component created.
  - `fixed_update(self, dt)` - 0..N times per frame, only if fixed timestep is enabled (Physics > Use Fixed Timestep, Engine > Fixed Update Frequency > 0).
  - `update(self, dt)` - once per frame (after all `fixed_update` calls).
  - `late_update(self, dt)` - once per frame after all `update`, before render (added in the 1.12 series).
  - `on_message(self, message_id, message, sender)` - message_id arrives **hashed**.
  - `on_input(self, action_id, action)` - only if this component acquired input focus.
  - `on_reload(self)` - hot reload.
  - `final(self)` - deleted; clean up spawned objects.
- `self` is userdata per script instance; store state on it (`self.speed = 200`). It cannot be iterated with `pairs` or printed with `pprint`.
- Since 1.14.0 all script types (`.script`, `.gui_script`, `.render_script`) always share one Lua state; globals and required modules are shared between them.
- **Render script** (`.render_script`) controls the render pipeline (predicates, cameras). Default one is fine for most 2D games.
- **Worlds**: each collection proxy loads a separate world (own physics). Collection factories spawn into the current world.

## Project layout
```
game.project            -- project settings (INI-like): bootstrap main collection, display, physics, input binding, dependencies
input/game.input_binding
main/main.collection
main/player.go          -- or embedded game objects in the collection
main/player.script
main/hud.gui
main/hud.gui_script
main/bullet.go + bullet.factory referenced by a factory component
assets/sprites.atlas    -- atlas of images; sprites reference animations in the atlas
modules/util.lua        -- require("modules.util")
```
- Library dependencies: URLs of zip archives (GitHub releases) listed in `game.project` -> Project -> Dependencies, then Project > Fetch Libraries.
- Native extensions: folder with `ext.manifest` + `src/*.cpp`; built on the Defold build server automatically.
- `.defignore` / `.defunload` support wildcards since 1.14.0.

## Scripting idioms
- Compare hashes, not strings. Pre-hash constants at file top:
```lua
local MSG_SCORE = hash("score")
local ACT_LEFT = hash("left")
```
- Script properties (editable in the editor, overridable per instance and at spawn time). Must be at file top level, literal defaults only:
```lua
go.property("speed", 200)
go.property("target", msg.url())
go.property("tint", vmath.vector4(1, 1, 1, 1))
go.property("atlas", resource.atlas("/assets/sprites.atlas"))
```
  Read as `self.speed`. From another script: `go.get(url, "speed")`, `go.set(url, "speed", 300)`. Since 1.13.2 a string default creates a text property.
- Positions: `go.get_position()`, `go.set_position(vmath.vector3(x, y, 0))`, `go.get_world_position()`. With no id these act on the current game object.
- Animation/tween: `go.animate(url, property, playback, to, easing, duration, [delay], [complete_function])`, e.g. `go.animate(".", "position.y", go.PLAYBACK_LOOP_PINGPONG, 200, go.EASING_INOUTSINE, 1)`.
- Spawn: `local id = factory.create("#bulletfactory", pos, rot, { speed = 500 }, scale)` returns a hash id. `go.delete(id)` to remove.
- Delays: `timer.delay(seconds, repeating, function(self, handle, time_elapsed) ... end)`; cancel with `timer.cancel(handle)`.
- Sprite flipbook: `sprite.play_flipbook("#sprite", hash("run"))`; flip: `sprite.set_hflip("#sprite", true)`.
- Shared state between scripts: a Lua module table (`require`) - allowed but message passing is the idiomatic decoupled path.
- Input focus:
```lua
function init(self)
    msg.post(".", "acquire_input_focus")
end
```

## Pitfalls (what AI answers get wrong)
1. **message_id and action_id are hashes.** `if message_id == "hit"` is always false. Use `message_id == hash("hit")`.
```lua
-- WRONG
if action_id == "jump" then ... end
-- RIGHT
if action_id == hash("jump") and action.pressed then ... end
```
2. **Forgetting `acquire_input_focus`** -> `on_input` never called. Also input bindings must exist in `game.input_binding` (key name like `KEY_LEFT` mapped to action "left").
3. **`go.property` inside a function** or with an expression default (`3 + 6`) fails; properties are parsed at build time and must be top-level literals.
4. **Messages are async**: state set in a message is not visible until the receiver processes it. `msg.post` then reading the result on the next line is a bug. Message tables > 2 KB error.
5. **Removed in 1.13.0**: `js-web`/asm.js target (use `wasm-web`), Collada `.dae` models (use glTF/GLB), old LiveUpdate format and auto-mount, and long-deprecated Lua functions/constants (Defold ships a Python checker script). Component winding order unified to counter-clockwise.
6. **Breaking in 1.14.0**: 32-bit Windows removed (use `x86_64-win32` in bob scripts); separate Lua states option (`script.shared_state`) removed - globals are now shared between `.script`, `.gui_script` and render scripts; accelerometer input disabled by default; generational game-object handles for native extensions (rebuild prebuilt dmSDK libs).
7. **1.13.1 behavior changes**: desktop fullscreen is borderless windowed by default; SDL gamepad database on by default (`input.gamepad_deadzone` setting).
8. **GUI vs game objects**: `.gui_script` uses the `gui.*` API (`gui.get_node("score")`, `gui.set_text(node, "...")`), not `go.*`. GUI nodes are not game objects and cannot be addressed by `go.set_position`.
9. **`go.delete()` with no argument** deletes the current game object; to delete a spawned one pass its id. Deleting during collision handling is fine, but references to the id become invalid.
10. **Collision messages**: physics sends `collision_response`, `contact_point_response`, `trigger_response` to scripts on the game object owning the collision object. Groups/masks in the collision object must include each other or nothing is reported. Kinematic objects need manual separation using `contact_point_response` (normal * distance).
11. **Collection proxy vs factory**: proxies load a separate world (`load`/`async_load` -> `proxy_loaded` -> `init`/`enable`); collection name must be unique among loaded worlds. Factories spawn into the current world.
12. **`self` is not a table**: `for k, v in pairs(self)` errors.

## Rendering
- Sprites draw from atlases or tile sources; z order via position.z (default render script draws -1..1 for 2D; values outside are culled).
- Camera component (`camera`) plus render script; 1.12 added camera/world-screen helpers (blog summary; exact names not verified here).
- Materials and shaders (GLSL, cross-compiled; Vulkan default on Android since 1.13.0, Metal default on macOS since 1.14.0). 1.13.0 added `graphics`, `material`, `compute` script modules (exact function names not verified).
- Particles: particlefx component, `particlefx.play("#fx")`.
- Labels for world text; GUI scenes for HUD (separate render predicate).
- Models: glTF/GLB (Collada removed 1.13.0), morph targets via `model.set_blend_weights()` (1.13.0); Light components (ambient, directional, point, spot) in 1.13.1 (not on WebGL 1/GLES2).

## Physics
- Box2D for 2D (V2 and V3 supported per 1.13.0 notes) and Bullet for 3D. Collision object component: type dynamic/kinematic/static/trigger, shapes, group, mask.
- Collision messages:
```lua
function on_message(self, message_id, message, sender)
    if message_id == hash("trigger_response") and message.enter then
        print("entered", message.other_id, message.other_group)
    elseif message_id == hash("collision_response") then
        print("hit", message.other_id)
    end
end
```
- Forces/velocity on dynamic bodies: `msg.post("#collisionobject", "apply_force", { force = vmath.vector3(0, 500, 0), position = go.get_world_position() })`; linear velocity is a component property: `go.set("#collisionobject", "linear_velocity", vmath.vector3(...))`.
- Raycasts: `physics.raycast(from, to, groups)`.
- 1.13.0 added extensive Box2D scripting (joints of all types, fixture/shape editing) under the `b2d` namespaces; 1.14.0 added `b2d.get_gameobject_id()`. Check the b2d reference before using exact names.
- Scale: game.project physics scale (default 0.02 in 2D templates).

## Input
- Input bindings file maps triggers to actions: `KEY_SPACE -> jump`, `MOUSE_BUTTON_LEFT -> touch`, gamepad/touch triggers.
- `on_input(self, action_id, action)`: `action.pressed`, `action.released`, `action.repeated`, `action.value`, mouse/touch `action.x`, `action.y`, `action.screen_x`, `action.screen_y`. `action_id` is nil for mouse movement.
- Return `true` from `on_input` to consume the input (stops propagation down the input stack).
- Input stack: the most recently focused component gets input first; collection proxies have their own stack.

## UI
- GUI component: `.gui` scene (box, text, pie, template, particlefx nodes) + `.gui_script` with the same lifecycle callbacks.
```lua
-- hud.gui_script
function init(self)
    self.score_node = gui.get_node("score")
end
function on_message(self, message_id, message, sender)
    if message_id == hash("set_score") then
        gui.set_text(self.score_node, "Score: " .. message.score)
    end
end
```
- Hit test: `gui.pick_node(node, action.x, action.y)` inside `on_input` (needs input focus in GUI script too).
- Layouts for orientation/aspect; adjust modes (fit/zoom/stretch); safe-area support improved in 1.12/1.14.
- Community UI libs (Druid, unofficial) are common.

## Networking and multiplayer
- `http.request(url, method, callback, [headers], [post_data], [options])` built in.
- WebSocket and other transports via official/community extensions (extension-websocket). LuaSocket is bundled (`socket` module) for TCP/UDP.
- No built-in replication. Multiplayer usually via Nakama, Colyseus or custom servers through extensions (third-party).

## Save data
```lua
local path = sys.get_save_file("my_game", "save")
local data = sys.load(path)            -- returns empty table if missing
data.best = math.max(data.best or 0, self.score)
if not sys.save(path, data) then print("save failed") end
```
- `sys.save` serializes a Lua table (no functions/userdata). On HTML5 it maps to IndexedDB-backed storage. Size limits apply (check sys reference).

## Performance
- Very small engine (~few MB builds); the Lua side is the usual bottleneck. Avoid per-frame `hash("...")` calls and `vmath` allocations in hot loops; precompute.
- Prefer `go.animate` over per-frame Lua tweening; prefer factories with pooling for bullets only when profiling shows spawn cost.
- Built-in profiler (Debug > Toggle Profiler, web profiler at engine port). Engine throttling (`sys.set_engine_throttle`, 1.12) for idle apps.
- Component counts are capped by `game.project` max counts (e.g. `sprite.max_count`, `collection.max_instances`) - "buffer full" errors mean raise these.
- Frustum culling of particle FX (1.13.0).

## Build and export
- Editor: Project > Build (run locally, hot reload with Ctrl/Cmd+R), Project > Bundle > platform.
- CLI: `java -jar bob.jar --platform x86_64-win32 --archive --bundle-output build/win resolve build bundle` (platform ids like `x86_64-linux`, `arm64-macos`, `arm64-android`, `arm64-ios`, `wasm-web`).
- Native extensions build on Defold's cloud build server (or self-hosted extender).
- HTML5: bundle `wasm-web`; asm.js gone since 1.13.0.
- Consoles: request access via platform programs (Xbox via Microsoft middleware portal, free for approved devs since 1.14.0).

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `on_input` never fires | No input focus | `msg.post(".", "acquire_input_focus")` in `init` |
| Message handler never matches | Comparing hash to string | `message_id == hash("name")` |
| "Could not send message" error | Wrong URL/fragment id | Check ids in the collection; use `msg.url()` to print |
| Sprite invisible | z outside -1..1 in default render | Keep z in range or change render script |
| No collision messages | Group/mask mismatch or both static | Set group/mask lists to include each other |
| Spawn fails "buffer is full" | max count in game.project | Raise `collection.max_instances` / component max counts |
| `go.property` error at build | Expression default or not top-level | Literal default at top of file |
| HTML5 bundle missing js-web option | Removed in 1.13.0 | Use `wasm-web` |
| Win32 build script fails after 1.14 | 32-bit Windows removed | Use `x86_64-win32` |
| Globals collide between GUI and game scripts after 1.14 | Shared Lua state always on | Use locals/modules; avoid globals |

## Mapping from Roblox
| Roblox | Defold | Notes |
|---|---|---|
| Workspace / Instance tree | Collection with game objects (and child game objects) | Address by URL, not by object reference |
| Part | Game object + sprite + collision object | |
| Model | Collection (prefab) spawned with collection factory | |
| Script / LocalScript | `.script` component | Everything runs on the client; no server |
| ModuleScript | Lua module (`require("folder.module")`) | |
| RemoteEvent | `msg.post` (local only) | Network requires extensions |
| DataStore | `sys.save` / `sys.load` with `sys.get_save_file` | Local device storage |
| Players | Not applicable | |
| Humanoid | Not applicable; write a controller with kinematic collision + `contact_point_response` | |
| RunService.Heartbeat | `update(self, dt)` / `fixed_update` | |
| RunService.RenderStepped | `late_update(self, dt)` (1.12+) | Before render |
| TweenService | `go.animate` / `gui.animate` | Easing constants `go.EASING_*`, `gui.EASING_*` |
| CollectionService tags | Collision groups, or a Lua module registry | No tag system |
| Attributes | `go.property` | Editor-visible, per instance |
| ScreenGui | GUI component (`.gui` + `.gui_script`) | |
| UserInputService | Input bindings + `on_input` | |
| task.wait | `timer.delay` | |
| Studio playtest | Project > Build (Ctrl/Cmd+B) | Hot reload |
| Publishing | Project > Bundle / bob.jar | |

## Minimal example
```lua
-- player.script (attached to "player" game object with sprite + kinematic collision object, group "player", mask "coin")
-- input/game.input_binding maps KEY_LEFT->left, KEY_RIGHT->right, KEY_UP->up, KEY_DOWN->down
go.property("speed", 200)

local LEFT, RIGHT, UP, DOWN = hash("left"), hash("right"), hash("up"), hash("down")
local TRIGGER = hash("trigger_response")

function init(self)
    msg.post(".", "acquire_input_focus")
    self.dir = vmath.vector3()
    self.score = 0
end

function update(self, dt)
    if vmath.length_sqr(self.dir) > 0 then
        local pos = go.get_position()
        go.set_position(pos + vmath.normalize(self.dir) * self.speed * dt)
    end
    self.dir = vmath.vector3()
end

function on_input(self, action_id, action)
    if action_id == LEFT then self.dir.x = -1
    elseif action_id == RIGHT then self.dir.x = 1
    elseif action_id == UP then self.dir.y = 1
    elseif action_id == DOWN then self.dir.y = -1
    end
end

function on_message(self, message_id, message, sender)
    if message_id == TRIGGER and message.enter then
        go.delete(message.other_id)          -- coin game object (trigger collision object, group "coin")
        self.score = self.score + 1
        msg.post("/hud#hud", "set_score", { score = self.score })
    end
end
```

## Sources
- https://github.com/defold/defold/releases (1.14.0 stable 2026-10-12; 1.13.2 2026-09-29; 1.13.1 2026-08-17; confirmed via GitHub API releases/latest)
- https://forum.defold.com/t/defold-1-14-0-has-been-released/83348 (1.14.0 breaking changes: generational handles, shared Lua state, win32 removal, accelerometer off, b2d.get_gameobject_id)
- https://forum.defold.com/t/removing-32-bit-windows-support-and-separate-lua-states/83211 (script.shared_state removal details)
- https://forum.defold.com/t/defold-now-officially-supports-xbox/83350 (Xbox support from 1.14.0)
- https://defold.com/2026/06/22/Defold-1-13-0/ (asm.js, Collada, LiveUpdate, deprecated Lua APIs removed; winding order; Vulkan Android; model.set_blend_weights)
- https://defold.com/2026/08/17/Defold-1-13-1/ (Light components, borderless fullscreen, SDL gamepads, collectionproxy async load progress)
- https://defold.com/manuals/script/ (lifecycle incl. fixed_update, late_update, self userdata)
- https://defold.com/manuals/message-passing/ (msg.post signature, URL shorthands, hashed ids, 2 KB limit, dispatch passes)
- https://defold.com/manuals/script-properties/ (go.property types, top-level literal rule, text properties since 1.13.2, factory property overrides)
- https://defold.com/manuals/collection-proxy/ (load/async_load/enable/unload, proxy_loaded, set_time_step)
- https://defold.com/ref/factory/ (factory.create signature, ref for 1.14.0)
- https://defold.com/manuals/physics-messages/ (collision_response, contact_point_response fields)
- https://defold.com/ref/sys/ (sys.get_save_file, sys.save, sys.load)
- https://defold.com/license/ (Defold License, Apache 2.0 derived)

## Confidence and gaps
- High: versions/dates, lifecycle, message passing, properties, factory, save, 1.13/1.14 breaking changes.
- Medium: exact physics message for `apply_force` and `linear_velocity` property name, bob.jar platform ids for macOS/iOS (from memory of manuals), render z-range default.
- Not verified: exact names in new `graphics`/`material`/`compute`/`b2d` modules and 1.12 camera helpers (left unnamed or marked); C# extension support status.
