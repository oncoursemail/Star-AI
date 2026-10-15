# GameMaker (GML): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: LTS 2026.0.0 (2026-05-21; Minor Update 1 on 2026-05-27, IDE 16 / GMS2 Runtime 23).** Free for non-commercial use; Professional one-time $99.99 for commercial; Enterprise subscription for consoles.

## At a glance
| | |
|---|---|
| Best for | 2D games of any genre (platformers, top-down, RPG, roguelites), fast prototyping, solo/indie teams |
| Weak at | 3D (low-level only), large codebases without discipline, engine-source access (Enterprise only), true multiplayer replication |
| Language(s) | GML Code (C/JS-like scripting) and GML Visual (drag-and-drop blocks); GMRT (new runtime, beta) plans JavaScript (Q2 2026), TypeScript (Q3), C# preview (Q4) per roadmap |
| Editor / tooling | GameMaker IDE (room editor, sprite editor, sequences, particle editor, Feather linting, Code Editor 2 beta), Igor CLI builds (paid tiers) |
| Platforms (export) | Windows (incl. ARM64 in 2026.0), macOS, Ubuntu, Android, iOS, tvOS, HTML5, GX.games, Reddit (Devvit), consoles (Switch, Switch 2, PlayStation, Xbox) with Enterprise |
| License / cost | Free non-commercial; Professional $99.99 one-time (commercial, desktop/web/mobile); Enterprise monthly/yearly (consoles, source access) |
| Roblox-likeness | medium: object/instance model with events and a room editor feels familiar, but no client/server split and no Luau |

## Architecture and lifecycle
- **Objects** are templates (with events and Variable Definitions); **instances** are runtime copies placed in **rooms** (levels) on **layers** (Instance, Asset, Tile, Background, Effect, UI layers).
- Each instance runs **events**. Order per step: Begin Step -> (alarms, input events) -> Step -> (collisions) -> End Step -> Draw events (Pre-Draw, Draw Begin, Draw, Draw End, Post-Draw) -> Draw GUI Begin/Draw GUI/Draw GUI End. Other events: Create, Destroy, Clean Up, Alarm 0-11, Collision, Keyboard/Mouse, Async (HTTP, Networking, Save/Load, Social), Room Start/End, Game Start/End, Animation End.
- **Create** runs when the instance is created (after Variable Definitions and after any struct passed to `instance_create_layer/depth`).
- **Draw**: if you add a Draw event you must call `draw_self()` or the sprite is not drawn. **Draw GUI** is screen-space (HUD), unaffected by camera.
- **Clean Up** event: free dynamic resources (`ds_*`, surfaces, buffers) here; runs on destroy and room end for non-persistent instances.
- Rooms: `room_goto(rm_level2)`, `room_restart()`; persistent instances/rooms survive changes.
- **Scripts** (since 2.3): script assets hold named functions declared with `function name(args) {}`; they run once at game start to define globals.
- **Sequences**: timeline assets of sprites/instances/sounds/keyframes, created on layers (`layer_sequence_create(layer, x, y, seq)`).
- **Runtimes**: "GMS2 VM" (interpreted) and "GMS2 YYC" (compiled C++) - renamed in 2026.0. **GMRT** (new runtime) is in beta (0.22, September 2026) with "GMRT" and "GMRT VM" targets on some platforms; GMS2 runtime is declared feature complete in LTS26 (SDK updates and critical fixes until at least Q1 2028).
- **Release channels** (as of Oct 2026): LTS 2026.0 is the recommended version; old monthly 2024.x (last 2024.14.x, Oct 2025+) were "replaced by LTS2026.0"; beta 2026.100 (July 2026+). Next LTS update 2026.1 planned for Q4 2026.

## Project layout
```
MyGame/
  MyGame.yyp                  -- project file (JSON-like); 2026.0 tile storage bumps project version to 1.6
  objects/obj_player/obj_player.yy, Create_0.gml, Step_0.gml, Draw_0.gml, Draw_64.gml (Draw GUI)
  scripts/scr_utils/scr_utils.gml
  sprites/spr_player/...
  rooms/rm_main/rm_main.yy
  sequences/, sounds/, fonts/, shaders/, extensions/, datafiles/ (Included Files)
  options/ (per-platform Game Options)
```
- Asset names are global identifiers in GML (`obj_player`, `spr_coin`, `rm_main`). Naming prefixes are a convention, not required.
- Included Files go to `datafiles/` and are read-only at runtime from the bundle; writes go to the sandboxed save area.

## Scripting idioms
- Variables: instance (`hp = 3`), local (`var _i = 0`), global (`global.score = 0`). Use `var` for temporaries.
- Movement + collision with `move_and_collide` (2022.x+):
```gml
// Step event
var _h = keyboard_check(vk_right) - keyboard_check(vk_left);
var _v = keyboard_check(vk_down) - keyboard_check(vk_up);
move_and_collide(_h * spd, _v * spd, obj_wall);
```
- Spawning:
```gml
var _b = instance_create_layer(x, y, "Instances", obj_bullet, { direction: image_angle, speed: 8 });
// or by depth
var _fx = instance_create_depth(x, y, -100, obj_spark);
```
- `with (obj_enemy) { hp -= 1; }` iterates all instances of an object; inside `with`, `other` is the calling instance.
- Structs and constructors (2.3+):
```gml
function Item(_name, _value) constructor {
    name = _name;
    value = _value;
    static describe = function() { return name + " (" + string(value) + ")"; };
}
inventory = [];
array_push(inventory, new Item("Sword", 10));
show_debug_message(inventory[0].describe());
show_debug_message(array_length(inventory));
```
- Method variables: `on_hit = function(_dmg) { hp -= _dmg; };` and `method(struct_or_instance, func)` to bind scope.
- Arrays are first-class (`array_push`, `array_delete`, `array_filter`, `array_foreach`, `array_sort`); prefer arrays/structs over `ds_list`/`ds_map` (which need manual `ds_*_destroy`).
- JSON: `json_stringify(struct)` / `json_parse(string)` (structs/arrays) instead of old `json_encode`/`json_decode` (ds_map based).
- String templates: `$"Score: {score}"`.
- Timing: alarms (`alarm[0] = game_get_speed(gamespeed_fps) * 2;`) or Time Sources (`time_source_create(time_source_game, 2, time_source_units_seconds, func)` + `time_source_start`); `delta_time` is microseconds.
- Exceptions: `try { } catch (_e) { show_debug_message(_e.message); } finally { }`.
- Enums + state machine (common platformer/RPG pattern):
```gml
// Create
enum PState { idle, run, jump }
state = PState.idle;

// Step
switch (state) {
    case PState.idle:
        if (keyboard_check(vk_left) || keyboard_check(vk_right)) state = PState.run;
        break;
    case PState.run:
        if (!keyboard_check(vk_left) && !keyboard_check(vk_right)) state = PState.idle;
        break;
}
```
- Object parents give inheritance: `obj_enemy_slime` with parent `obj_enemy` inherits events; call `event_inherited();` inside an overridden event to run the parent version. `place_meeting(x, y, obj_enemy)` also matches children.
- Camera follow (room editor viewport 0 enabled):
```gml
// obj_camera End Step
var _cam = view_camera[0];
var _w = camera_get_view_width(_cam), _h = camera_get_view_height(_cam);
camera_set_view_pos(_cam,
    clamp(obj_player.x - _w / 2, 0, room_width - _w),
    clamp(obj_player.y - _h / 2, 0, room_height - _h));
```
- Alarm example: `alarm[0] = 60;` in Create, then the Alarm 0 event runs after 60 steps (it does not repeat unless re-set).
- Static methods on constructors are shared (one copy), instance methods declared without `static` are copied per struct.
- `is_struct`, `is_array`, `is_undefined`, `variable_struct_exists` (or `struct_exists` in newer releases, unverified) guard dynamic data.

## Pitfalls (what AI answers get wrong)
1. **`instance_create(x, y, obj)` is GameMaker 8/Studio 1.** It does not exist in GameMaker Studio 2 and later. Use `instance_create_layer(x, y, layer_id_or_name, obj, [struct])` or `instance_create_depth(x, y, depth, obj, [struct])`.
2. **Array length helpers**: `array_length_1d`, `array_length_2d`, `array_height_2d` were deprecated in 2.3 (arrays became 1D, nested for multi-D). Use `array_length(arr)`; 2D = arrays of arrays (`grid[i][j]`), not `grid[i, j]`-style legacy semantics.
3. **Old pre-2.3 script style** (`argument0`, `argument[0]`, one script = one function named by the asset, `script_execute(scr_x)` for everything) is legacy. Use named `function` declarations with parameters.
4. **2026.0 deprecations**: `instance_change()` and `position_change()` are deprecated; projects using them must enable the matching Game Option or get an in-game error. Marketplace integration and Laptop Mode removed from the IDE.
5. **2026.0 behavior changes**: functions that call overridable functions need `self.` prefix or conversion to a method due to optimized calls; audio final pitch = voice * asset * emitter pitch; new projects default to **copy-on-write arrays OFF** (writing to an array passed into a function modifies the caller's array). Existing projects keep copy-on-write on.
6. **Project format 1.6** (2026.0 tile layer storage) cannot be opened in older IDEs - do not suggest downgrading.
7. **Draw event replaces default drawing**: adding a Draw event without `draw_self()` makes the sprite invisible. HUD belongs in Draw GUI, not Draw (Draw uses room/camera coordinates).
8. **`ds_*` leaks**: `ds_list_create()`/`ds_map_create()` must be destroyed (`ds_list_destroy`). Structs/arrays are garbage collected; prefer them.
9. **`json_decode` returns a ds_map** (legacy); `json_parse` returns structs/arrays. Do not mix.
10. **Old view variables** `view_xview`, `view_yview` (GMS1) were replaced by cameras: `camera_set_view_pos(view_camera[0], x, y)`.
11. **`game_save()`/`game_load()`** are not usable in modern GameMaker (unverified exact status this session; avoid). Save with buffers/JSON/INI.
12. **`room_speed`** is legacy; use `game_get_speed(gamespeed_fps)` / `game_set_speed`.
13. **Licensing claims**: Creator/Indie subscriptions are discontinued; commercial use needs Professional (one-time) or Enterprise; console exports need Enterprise.

## Rendering
- 2D sprites with frames (`sprite_index`, `image_index`, `image_speed`, `image_xscale`, `image_angle`, `image_blend`, `image_alpha`).
- Draw functions: `draw_self()`, `draw_sprite_ext`, `draw_text`, `draw_rectangle`, `draw_set_colour(c_white)` (colors are BGR ints, `make_colour_rgb(r,g,b)` 0-255), `draw_set_alpha`.
- Depth: layer depth (-16000..16000), `depth` variable for instances not on layers.
- Cameras/viewports: room editor "Enable Viewports", `view_camera[0]`, `camera_create_view`.
- Surfaces (`surface_create`, must check `surface_exists` every frame since they can be lost), shaders (GLSL ES / HLSL), Filters and Effects layers, particle systems and the Particle asset editor (2026.0).
- Tilemaps: `tilemap_get_at_pixel`, `layer_tilemap_get_id`.
- 2026.0: SVG support, QOI used for in-game sprites, UI Layers with Flexpanels.
- 3D: vertex buffers, `matrix_*`, `gpu_set_ztestenable` - low level; GMRT roadmap adds 3D functions.

## Physics
- Two options: (a) built-in collision functions (most games): `place_meeting(x, y, obj)`, `instance_place`, `collision_rectangle`, `move_and_collide`, Collision events; (b) Box2D-based physics enabled per room ("Uses Physics") with `phy_*` variables and `physics_apply_force` etc.
- Collision masks are set per sprite (precise or bounding box); `mask_index` can override.
- Do not mix manual `x/y` movement with physics-enabled objects.

## Input
- Keyboard: `keyboard_check(vk_left)`, `keyboard_check_pressed(ord("Z"))`, `keyboard_check_released`.
- Mouse: `mouse_x`, `mouse_y` (room coords), `device_mouse_x_to_gui(0)` for GUI coords, `mouse_check_button_pressed(mb_left)`.
- Gamepad: `gamepad_button_check(0, gp_face1)`, `gamepad_axis_value(0, gp_axislh)`; detect via Async System event.
- Touch: `device_mouse_check_button(i, mb_left)`, virtual keys.

## UI
- Draw GUI event for HUD: `draw_text(16, 16, $"Score: {global.score}")`.
- 2026.0 adds UI Layers and Flexpanels (flexbox-like layout) in the room editor; `flexpanel_*` functions (names beyond prefix not verified here).
- Fonts: font assets + `draw_set_font(fnt_main)`, `draw_set_halign(fa_center)`.
- Many projects build menus as objects with mouse hit tests in GUI space.

## Networking and multiplayer
- Low-level sockets: `network_create_server(network_socket_tcp, port, max)`, `network_create_socket`, `network_connect`, `network_send_packet(socket, buffer, size)`; data arrives in the **Async - Networking** event via `async_load` ds_map.
- HTTP: `http_get`, `http_request` -> Async - HTTP event.
- GX.games had built-in rollback multiplayer (`rollback_*` functions) for that target (verify before use).
- No built-in replication/authority model.

## Save data
```gml
function save_game(_file, _data) {
    var _json = json_stringify(_data);
    var _buf = buffer_create(string_byte_length(_json) + 1, buffer_fixed, 1);
    buffer_write(_buf, buffer_string, _json);
    buffer_save(_buf, _file);
    buffer_delete(_buf);
}
function load_game(_file) {
    if (!file_exists(_file)) return undefined;
    var _buf = buffer_load(_file);
    var _json = buffer_read(_buf, buffer_string);
    buffer_delete(_buf);
    return json_parse(_json);
}
```
- INI: `ini_open("save.ini"); ini_write_real("main", "best", best); ini_close();`.
- Files go to the sandbox (`game_save_id`); HTML5 uses browser storage. Async save/load (`buffer_save_async`) required on consoles.

## Performance
- YYC (compiled) for CPU-heavy logic; VM for fast iteration.
- Avoid huge numbers of instances: use structs/arrays for lightweight entities, tilemaps for static geometry, `instance_deactivate_region` for off-screen.
- Minimize texture swaps (texture groups), batch breaks (`shader_set`, `draw_set_colour` changes are cheap; surface switches are not).
- Debugger + Profiler in the IDE; `show_debug_overlay(true)`.
- Free `ds_*`, surfaces, buffers in Clean Up.

## Build and export
- IDE target selector: platform + runtime (GMS2 VM / GMS2 YYC / GMRT where available) -> Run (F5), Debug (F6), Create Executable.
- 2026.0: sign-in only needed for license-checked actions (building); Runtime Modules dialog to download only needed targets; can exclude unused assets; Ubuntu builds use Steam Runtime.
- Igor command-line builds require paid tiers (Professional/Enterprise).
- GMRT builds: sign-in required, keep Package Manager packages updated.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| "unknown function instance_create" | GMS1 API | `instance_create_layer`/`instance_create_depth` |
| Sprite disappears after adding Draw event | Default draw replaced | Call `draw_self()` |
| HUD moves with camera | Drawn in Draw event | Use Draw GUI |
| Memory grows over time | `ds_*`/surfaces never freed | Destroy in Clean Up |
| Surface errors after alt-tab | Surface lost | Check `surface_exists` and recreate |
| Array changed unexpectedly in caller (new 2026 project) | Copy-on-write arrays off by default | Copy explicitly (`array_copy`) or re-enable in options |
| Override not called after 2026.0 upgrade | Optimized function calls | Prefix `self.` or convert to method |
| In-game error on `instance_change` | Deprecated in 2026.0 | Enable the Game Option or rewrite with destroy + create |
| Project won't open in older IDE | Project format 1.6 | Use LTS 2026.0+ |
| Instance stuck in wall | Moving x/y without collision check | `move_and_collide` or `place_meeting` loop |

## Mapping from Roblox
| Roblox | GameMaker | Notes |
|---|---|---|
| Workspace / Instance tree | Room with layers and instances | Flat per layer; no parent/child instances |
| Part | Instance of an object with a sprite + collision mask | |
| Model | Object with child instances spawned in Create, or a Sequence | Parenting is manual |
| Script / LocalScript | Object events (Create/Step/Draw) | Single client process |
| ModuleScript | Script asset with functions / constructors | Global scope |
| RemoteEvent | `network_send_packet` + Async Networking | Manual protocol |
| DataStore | `buffer_save`/`ini_*`/`json_stringify` to local file | Local |
| Players | Not applicable | |
| Humanoid | Player object with Step movement | Write your own |
| RunService.Heartbeat | Step event | Fixed game speed (default 60) |
| RunService.RenderStepped | Draw / Draw GUI event | |
| TweenService | Sequences / animation curves (`animcurve_*`) | Or lerp in Step |
| CollectionService tags | Asset tags (`tag_get_asset_ids`) or parent objects | Object parenting = inheritance |
| Attributes | Variable Definitions / instance variables | |
| ScreenGui | Draw GUI event / UI Layers (2026.0) | |
| UserInputService | `keyboard_check*`, `mouse_*`, `gamepad_*` | |
| task.wait | Alarms / Time Sources | |
| Studio playtest | Run (F5) | |
| Publishing | Create Executable / platform export | Commercial needs license |

## Minimal example
```gml
/// obj_player - Create event
spd = 4;
global.score = 0;

/// obj_player - Step event
var _h = keyboard_check(vk_right) - keyboard_check(vk_left);
var _v = keyboard_check(vk_down) - keyboard_check(vk_up);
move_and_collide(_h * spd, _v * spd, obj_wall);

var _coin = instance_place(x, y, obj_coin);
if (_coin != noone) {
    global.score += 1;
    instance_destroy(_coin);
    instance_create_layer(irandom(room_width), irandom(room_height), "Instances", obj_coin);
}

/// obj_player - Draw GUI event
draw_set_colour(c_white);
draw_text(16, 16, $"Score: {global.score}");
```

## Sources
- https://releases.gamemaker.io/ (channel overview: LTS2026.0 recommended, monthly 2024.14 replaced, beta 2026.100, GMRT 0.22 Sept 2026)
- https://releases.gamemaker.io/release-notes/2026/0 (2026.0.0 dates, IDE 15/16, Runtime 23, deprecations, behavior changes, new targets, GMRT notes)
- https://gamemaker.io/en/blog/update-spring-2026 (LTS26 roadmap, GMS2 runtime feature complete, GMRT language roadmap)
- https://gamemaker.io/blog/lts-2026-release (LTS 2026 based on latest 2025 release, GMRT beta support; fetch failed, confirmed via search snippet)
- https://gamemaker.io/en/get (Free non-commercial, Professional $99.99 one-time, Enterprise for consoles)
- https://manual.gamemaker.io/monthly/en/GameMaker_Language/GML_Reference/Asset_Management/Instances/instance_create_layer.htm (signature, optional struct)
- https://manual.gamemaker.io/monthly/en/GameMaker_Language/GML_Overview/Structs.htm (struct syntax, scoping)
- https://manual.gamemaker.io/lts/en/GameMaker_Language/GML_Reference/Movement_And_Collisions/Movement/move_and_collide.htm (move_and_collide)
- https://manual.gamemaker.io/lts/en/GameMaker_Language/GML_Reference/Variable_Functions/array_length_1d.htm (deprecated, use array_length)
- https://gamemaker.io/en/blog/gamemaker-studio-2-dot-3-new-gml-features (2.3 functions/structs, array function deprecations)

## Confidence and gaps
- High: LTS 2026.0 facts, channel status, pricing tiers, instance_create_layer, array_length, structs/constructors.
- Medium: event order details, Time Source function names, `json_stringify`/`json_parse`, string templates, `tag_get_asset_ids` (from manual knowledge; not all re-fetched - manual pages returned 403 for some URLs).
- Unverified: exact `game_save` status, `flexpanel_*` function list, GX.games `rollback_*` availability in 2026, GMRT JS/TS shipping status vs roadmap.
