---
name: lang-gdscript-verse
description: GDScript for Godot 4.x (4.7 stable) and Verse for UEFN/Fortnite. Use when writing, porting from Luau or debugging Godot scripts or Verse devices.
---
# GDScript (Godot 4) and Verse (UEFN)
## GDScript
- Target Godot 4 unless the user says 3.x (4.7.2 is stable; 4.8 is in development). Use the Godot 4 names: `await` (not `yield`), `@export`, `@onready`, `@tool`, `instantiate()` (not `instance()`), `CharacterBody2D/3D` (not `KinematicBody`), `Node3D` (not `Spatial`), `sig.connect(callable)` and `sig.emit(args)`, inline `set(value):` setters (not `setget`), `create_tween()` (not the Tween node), `randf_range`, `PackedStringArray`.
- `move_and_slide()` takes no arguments. Set `velocity` first and call it from `_physics_process(delta)`.
- Type everything: `var hp: int = 100`, `var dir := Vector2.ZERO`, `func f(a: int) -> void:`, `Array[Enemy]`, `Dictionary[String, int]` (4.4+). Nested typed collections are not supported. `:=` cannot infer from a Variant (an untyped dict lookup or `get()`), so write the type. `as` returns null silently on a mismatch; check with `is`.
- 4.5+ adds `@abstract` classes and methods (no body) and variadic `func f(a, ...rest: Array)`. 4.7: typed overrides need an explicit `return`, and `tween.tween_await(signal)` exists. Do not emit `trait` or `struct` syntax: neither is in a stable release.
- Indexing is 0-based. `null`, `0`, `""` and empty containers are falsy. `5 / 2 == 2` (int division), so use `5 / 2.0`. Arrays, Dictionaries and Objects are references; resources loaded from disk are shared, so `duplicate()` before mutating.
- Get nodes with `@onready var s: Sprite2D = $Sprite2D` or `%UniqueName`, never in `_init`. Check freed nodes with `is_instance_valid()`. `queue_free()` frees at the end of the frame. Nodes are not reference-counted, so remove orphans.
- Async: a function that contains `await` is a coroutine, and callers that skip `await` continue immediately. Wait with `await get_tree().create_timer(t).timeout`. Change physics or tree state from physics callbacks with `call_deferred` or `set_deferred`. The scene tree is main-thread only; use `WorkerThreadPool` plus `call_deferred` for background work.
- Errors: there is no try/except. Use `assert`, `push_error` and `Error` return codes (`if err != OK`).
- Security: never `load()` untrusted .tres, .res or .tscn files, because they can embed scripts. Use JSON or ConfigFile for saves and mods. Keep `bytes_to_var` without objects. Validate every `@rpc("any_peer")` on the server with `multiplayer.get_remote_sender_id()`.
- Tests: GUT (`extends GutTest`) or gdUnit4, run headless with `godot --headless`.
## Verse
- Failure drives control flow, not booleans. A failable expression (`Arr[I]`, `Map[K]`, `X > 0`, `Opt?`, a call to a `<decides>` function) must sit in a failure context: an `if (...)` condition, a `for (...)` filter, a `<decides>` body, or the left side of `or`. Call `<decides>` functions with square brackets `F[x]`; all other calls use `()`.
- Mark user failable functions `<transacts><decides>`. A failed context rolls back every `set` made inside it.
- `<suspends>` and `<decides>` cannot be combined. `Sleep`, `Await`, `sync`, `race`, `rush` and `branch` need a `<suspends>` caller. `Subscribe` handlers are immediate, so start async work with `spawn{ Work() }`; spawn requires a `<suspends>` call. `race` cancels the losers, while `rush` lets them keep running.
- Values are immutable by default. Mutable state needs `var Name:type = value` with an explicit type (`var X := 1` is an error), and updates use `set X = ...`. `set Map[K] = V` is failable, so wrap it: `if (set Scores[Agent] = S) {}`.
- Integer `/` is failable and returns a `rational`, so use `Floor(R)`. Float-to-int conversion is failable: `Floor[F]`, `Int[F]`. Arrays are 0-based and immutable values (`array{}`, `.Length`, `+`). Strings join with `+` and interpolate with `"{X}"`. Equality is `=`, inequality is `<>`, comments use `#`.
- `Err()` is an uncatchable runtime error. Use failure for expected cases.
- Persistence uses a module-scoped `var Data:weak_map(player, t) = map{}`, where `t` is `class<final><persistable>` with no `var` fields, no superclass or interface, and no function calls in initializers. Replace whole records, add a `Version` field, and keep integers within 64 bits.
- Devices: `my_device := class(creative_device):`, `@editable` references assigned in the editor, `OnBegin<override>()<suspends>:void`, and `using { /Fortnite.com/Devices }`. Take exact signatures from the digest files and never invent device APIs. Live variables (`set live`, `when`) are documented but unreleased. UE6 plans are announcements only.
