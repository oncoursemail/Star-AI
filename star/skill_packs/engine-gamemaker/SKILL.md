---
name: engine-gamemaker
description: GameMaker LTS 2026.0 (GML Code): objects/instances, events, rooms/layers, structs and constructors, current vs removed functions. Use for any GameMaker/GML question.
---
# engine-gamemaker
## Scope
GameMaker LTS 2026.0 (May 2026, GMS2 runtime 23; beta 2026.100; GMRT runtime in beta). Old monthly 2024.x releases were replaced by LTS 2026.0. Check the project's IDE/runtime version first (Help > About); GML before 2.3 (2020) is a different language style.

## Core model
- Objects are templates with events; instances live in rooms on layers.
- Events: Create, Step (Begin/End), Draw, Draw GUI, Alarm, Collision, Async, Destroy, Clean Up.
- Script assets hold named `function` declarations (global); structs via `constructor` and `new`.
- Runtimes: GMS2 VM (fast iteration), GMS2 YYC (compiled), GMRT (new, beta).

## Idioms
- Spawn with `instance_create_layer(x, y, "Instances", obj_bullet, { speed: 8 })` or `instance_create_depth(x, y, depth, obj)`.
- Movement + walls: `move_and_collide(dx, dy, obj_wall)`; checks with `place_meeting` / `instance_place` (returns `noone` on miss).
- Input: `keyboard_check(vk_left)`, `keyboard_check_pressed(ord("Z"))`, `mouse_check_button_pressed(mb_left)`.
- Use `var` for locals, `global.` for globals, `with (obj) {}` to iterate instances (`other` = caller).
- Structs: `function Item(_n) constructor { name = _n; static info = function() { return name; }; }` then `new Item("Sword")`.
- Arrays: `array_push`, `array_length`, `array_delete`, `array_foreach`; prefer arrays/structs over `ds_*`.
- JSON: `json_stringify(struct)` / `json_parse(str)`; save via buffers or `ini_*`.
- HUD in Draw GUI: `draw_text(16, 16, $"Score: {global.score}")`.
- Timers: alarms or Time Sources; `delta_time` is microseconds.

## Pitfalls
1. `instance_create(x, y, obj)` is GMS1 and does not exist; use `instance_create_layer` or `instance_create_depth`.
2. `array_length_1d`, `array_length_2d`, `array_height_2d` are deprecated since 2.3; use `array_length` and nested arrays.
3. `argument0`/`argument[0]` one-function-per-script style is legacy; declare `function name(a, b)`.
4. LTS 2026.0 deprecates `instance_change` and `position_change` (in-game error unless the Game Option is enabled).
5. 2026.0: calls to overridable functions need `self.` or a method; new projects default to copy-on-write arrays off.
6. Adding a Draw event replaces default drawing; call `draw_self()`.
7. HUD in Draw moves with the camera; use Draw GUI.
8. `ds_list`/`ds_map`/surfaces/buffers must be freed (Clean Up event); surfaces can be lost, check `surface_exists`.
9. `json_decode` returns a ds_map (legacy); use `json_parse` for structs.
10. GMS1 view variables (`view_xview`) are gone; use `camera_set_view_pos(view_camera[0], x, y)`.
11. `room_speed` is legacy; use `game_get_speed(gamespeed_fps)`.
12. Licensing: free is non-commercial only; commercial needs Professional (one-time) or Enterprise; consoles need Enterprise.

## Roblox to GameMaker
- Workspace/Instance tree -> room with layers and instances
- Part -> instance of an object with sprite + collision mask
- Model -> parent object / spawned group of instances, or a Sequence
- Script/LocalScript -> object events; ModuleScript -> script asset functions
- RunService.Heartbeat -> Step event; RenderStepped -> Draw/Draw GUI
- TweenService -> Sequences or animation curves
- CollectionService tags -> asset tags or object parents
- Attributes -> Variable Definitions
- ScreenGui -> Draw GUI or UI Layers
- UserInputService -> `keyboard_check`, `mouse_*`, `gamepad_*`
- DataStore -> local JSON/INI/buffer files
- RemoteEvent -> `network_send_packet` + Async Networking event
- task.wait -> alarms or Time Sources
- Studio playtest -> Run (F5); shipping -> Create Executable

## Skeleton
```gml
/// obj_player Create
spd = 4;
global.score = 0;

/// obj_player Step
var _h = keyboard_check(vk_right) - keyboard_check(vk_left);
var _v = keyboard_check(vk_down) - keyboard_check(vk_up);
move_and_collide(_h * spd, _v * spd, obj_wall);
var _coin = instance_place(x, y, obj_coin);
if (_coin != noone) {
    global.score += 1;
    instance_destroy(_coin);
    instance_create_layer(irandom(room_width), irandom(room_height), "Instances", obj_coin);
}

/// obj_player Draw GUI
draw_text(16, 16, $"Score: {global.score}");
```

## Verification
Run the project in the IDE (F5) on the GMS2 VM target and read the Output window; enable Feather to catch deprecated calls. Without an IDE run, say the code is unverified.
