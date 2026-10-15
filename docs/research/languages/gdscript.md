# GDScript (Godot 4.x) for STAR (research, checked 2026-10-13)

Status: verified on godotengine.org on 2026-10-13. The current stable release is **Godot 4.7.2** (18 Aug 2026), and 4.8 is in development (4.8-dev7, 29 Sep 2026) [1]. Godot 3.6.3 is a maintained legacy line. The latest docs are 4.7 ("stable") [2].
Language features verified as stable:
- typed `Array[T]`, since 4.0
- typed `Dictionary[K, V]`, 4.4 [5]
- `@export_tool_button`, 4.4
- variadic functions `...args: Array` and `@abstract` classes/methods, 4.5 [3]
- script backtracing in release builds, 4.5 [3]
- a new GDScript profiler, 4.6 [4]

In 4.7 [6][7]:
- `AwaitTweener` (`tween.tween_await(signal)`)
- improved constant expressions
- packed-array element writes no longer call the whole property's setter
- overrides inherit typed returns

Unverified as of 2026-10-13:
- **traits**: still a proposal/PR. No stable release ships `trait`, and none of the 4.5–4.7 release notes checked list it.
- **structs**: same as traits.
- **JIT/AOT compilation of GDScript**: the docs call it "planned".

---

## 1. Mental model

- GDScript is Godot's built-in, Python-looking, indentation-scoped language. It is tightly integrated with the engine's object model (`Object` → `RefCounted`/`Node` → ...), the scene tree and the editor.
- **One script file = one class.** A `.gd` file implicitly defines an anonymous class that `extends` an engine or script class. `class_name Player` registers it globally (the editor shows it in "Create Node"). Inner classes use `class Foo:`.
- A script is attached to a node in a scene (`.tscn`). Behaviour comes from **callbacks** the engine calls: `_init()`, `_enter_tree()`, `_ready()`, `_process(delta)`, `_physics_process(delta)`, `_input(event)`, `_unhandled_input(event)`, `_exit_tree()`, `_notification(what)`.
- Communication: call down (parent calls child methods), **signal up** (child emits, parent connects). Groups (`add_to_group`, `get_tree().call_group`) and autoload singletons (Project Settings > Globals) provide global access.
- **Memory**: `RefCounted` (and `Resource`) objects are reference counted and freed automatically. `Node`s are **not**: they are freed with their scene tree or with `queue_free()` (deferred to the end of the frame) or `free()`. An orphan node that never entered the tree leaks.
- `Variant` is the universal dynamic value (nil, bool, int (64-bit), float (64-bit), String, StringName, NodePath, Vector2/3/4(i), Color, Rect2, Transform2D/3D, Basis, Quaternion, Array, Dictionary, Packed*Array, Object, Callable, Signal, RID...). Untyped variables hold Variants.
- Value vs reference: **Arrays, Dictionaries and Objects are passed by reference**. Vectors, Colors, Transforms, Strings and Packed*Arrays are copy-on-write values (assigning a PackedArray to a new variable makes a shared copy that diverges on write).

## 2. Type system

Gradual static typing [2]:

```gdscript
var speed: float = 200.0         # explicit
var dir := Vector2.ZERO          # inferred (Vector2)
const MAX_HP := 100              # constant
var anything                     # Variant
var enemies: Array[Enemy] = []   # typed array
var costs: Dictionary[String, int] = {"sword": 10}  # typed dictionary (4.4+)

func damage(amount: int, crit := false) -> int:
    return amount * (2 if crit else 1)

func _ready() -> void:
    var sprite := $Sprite2D as Sprite2D   # `as` returns null on mismatch (no error)
    if body is CharacterBody2D:            # `is` narrows for the editor's safe-line analysis
        (body as CharacterBody2D).velocity = Vector2.ZERO
```

- `:=` infers from the right-hand side. It fails when the right side is a Variant (e.g. `dict["k"]` on an untyped dict, or `get("x")`). Then write the type explicitly.
- Typed arrays: `Array[int]`, `Array[Node]`, `Array[PackedScene]`. **Nested typed collections are not supported** (`Array[Array[int]]` is an error). Assigning an untyped `[]` literal to a typed variable works (the literal is typed by the context), but assigning an existing untyped Array variable fails at runtime ("Trying to assign an array of type 'Array' to a variable of type 'Array[int]'"). Use `Array[int](untyped)` or `.assign()`.
- Typed dictionaries (4.4+): `Dictionary[KeyType, ValueType]`, with the same no-nesting rule [2][5].
- Enums: `enum State { IDLE, RUN, JUMP }`. The values are ints, and `State.keys()` lists the names. Named enum types can be used as types: `var s: State = State.IDLE`.
- Casting: `as` gives `null` for objects on mismatch (silently), while a failed cast to a built-in type raises an error. `is`/`is not` tests the type. Use `is_instance_of(v, T)` when `T` is a variable.
- Nullability: object-typed variables can be `null`. There is no non-null type. `is_instance_valid(obj)` checks for freed objects (a freed object is not equal to `null`).
- Warnings (Project Settings > Debug > GDScript, Advanced): `UNTYPED_DECLARATION` and `INFERRED_DECLARATION` are off by default. `UNSAFE_PROPERTY_ACCESS`, `UNSAFE_METHOD_ACCESS`, `UNSAFE_CAST` and `UNSAFE_CALL_ARGUMENT` exist. Each can be set to warn or error to enforce a typed codebase [2].
- Typed code runs faster because the VM emits typed opcodes when types are known at compile time [2].
- **Abstract** (4.5+) [3]:

```gdscript
@abstract
class_name Animal extends Node

@abstract
func cry() -> void            # no body; subclasses must implement

# cat.gd
class_name Cat extends Animal
func cry() -> void:
    print("Meow!")
```

- **Variadic functions** (4.5+): `func sum(first: float, ...rest: Array) -> float:`. The rest parameter must be `Array` and comes last [3].
- Static members: `static var count := 0`, `static func make() -> Player:`. A `static func _static_init()` runs once per class.
- Callables and lambdas: `var add := func(a, b): return a + b` and `add.call(1, 2)`. Lambdas capture locals **by value at creation time** (rebinding the outer variable later is not seen inside the lambda, but mutating a shared Array/Dictionary is). `bind()`/`unbind()` adjust arguments.

## 3. Runtime, concurrency and async model

- Scripts run on the main thread, driven by the `SceneTree` main loop. `_process(delta)` runs once per rendered frame (variable rate). `_physics_process(delta)` runs at the fixed physics tick (default 60 Hz, Project Settings > Physics > Common > Physics Ticks Per Second). Put movement/physics in `_physics_process`.
- **Signals** are first-class:

```gdscript
signal health_changed(old: int, new: int)
signal died

func take_damage(n: int) -> void:
    var old := hp
    hp = max(hp - n, 0)
    health_changed.emit(old, hp)
    if hp == 0:
        died.emit()

func _ready() -> void:
    $Enemy.died.connect(_on_enemy_died)                    # Godot 4 style
    $Button.pressed.connect(func(): print("clicked"))
    $Enemy.died.connect(_on_enemy_died, CONNECT_ONE_SHOT)  # flags
```

- **`await`** (Godot 4; replaces `yield` from 3.x) suspends the current function until a signal fires or a coroutine function returns:

```gdscript
func flash() -> void:
    modulate = Color.RED
    await get_tree().create_timer(0.1).timeout    # SceneTreeTimer
    modulate = Color.WHITE

func attack() -> void:
    $Anim.play("swing")
    await $Anim.animation_finished
    await flash()                                  # awaiting a coroutine
```

  A function containing `await` becomes a coroutine. Callers that do not `await` it continue immediately. If the node is freed while a coroutine is suspended, the coroutine is dropped, so check `is_inside_tree()` after awaits in long sequences.
- `call_deferred("method")`, `set_deferred("prop", v)` and `Callable.call_deferred()` run at the end of the frame (idle time). They are required when changing physics state or the scene tree inside physics callbacks ("Can't change this state while flushing queries").
- **Threads**: `Thread`, `Mutex`, `Semaphore`, and `WorkerThreadPool.add_task(callable)`. The scene tree is **not thread-safe**: touch nodes in the tree only from the main thread (use `call_deferred` to hand results back). Godot 4.1+ has per-node thread groups (`process_thread_group`) for advanced use.
- 4.7 adds `AwaitTweener` (`tween.tween_await(signal)`) to sequence tweens on signals [7].

## 4. Tooling and package management

- **Editor**: the built-in script editor with LSP. External editors (VS Code `godot-tools`, Neovim, Rider) connect to the editor's language server on port 6005 and the DAP debugger on 6006. In 4.7 the LSP and editor gained join-lines, doc-tooltip-under-caret, and no-replace autocomplete by default [7].
- **Formatter/linter**: `gdtoolkit` (`gdformat`, `gdlint`, community, pip) [12]. The engine has no official formatter. Its static checks come from the warnings system.
- **Packages/addons**: the **Asset Library** (in editor), git submodules, and copying into `res://addons/<name>/` with a `plugin.cfg` + `EditorPlugin`. There is no official package manager; `gd-plug` and the community Asset Store are options.
- **Project layout**: `project.godot`, `res://` paths, `user://` for writable save data. Export presets in `export_presets.cfg`. Headless CLI: `godot --headless --script res://tool.gd`, `godot --headless --export-release "Windows Desktop" out.exe`, `godot --check-only --script file.gd` for parse checks [13].
- **GDExtension** (C/C++/Rust via godot-rust/`gdext`, Swift, etc.): native classes usable from GDScript without recompiling the engine. **C#** is supported through the .NET build (separate editor download). Web export of C# projects is still limited as of 4.x; verify for the target version.
- `@tool` scripts run in the editor. Guard with `Engine.is_editor_hint()`. 4.4 added `@export_tool_button("Label") var b := my_callable` for inspector buttons.

## 5. Testing

- **GUT** (Godot Unit Test; `extends GutTest`, `assert_eq`, `double()`, `stub()`, `watch_signals`, `assert_signal_emitted`). Runs in the editor panel or from the CLI: `godot -d -s --path . addons/gut/gut_cmdln.gd -gdir=res://test -gexit` [10].
- **gdUnit4** (`extends GdUnitTestSuite`, fluent `assert_that(x).is_equal(5)`, scene runner for input simulation, C# support, GitHub Action) [11].
- Headless CI: run the Godot binary with `--headless` and the test runner script. Import the project once first (`godot --headless --import`) so resources and `class_name`s are registered.

```gdscript
# test/test_health.gd (GUT)
extends GutTest

func test_damage_clamps_at_zero() -> void:
    var h := preload("res://health.gd").new()
    add_child_autofree(h)
    watch_signals(h)
    h.take_damage(999)
    assert_eq(h.hp, 0)
    assert_signal_emitted(h, "died")
```

## 6. Idiomatic patterns

```gdscript
class_name Player
extends CharacterBody2D

@export var speed: float = 220.0
@export_range(0, 100, 1) var max_hp: int = 100
@export var bullet_scene: PackedScene
@onready var sprite: Sprite2D = $Sprite2D          # resolved just before _ready
@onready var hitbox := %Hitbox as Area2D           # %Name = scene-unique node

var hp: int = max_hp:
    set(value):                                    # Godot 4 inline setter
        hp = clampi(value, 0, max_hp)
        hp_changed.emit(hp)

signal hp_changed(value: int)

func _physics_process(delta: float) -> void:
    var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
    velocity = input * speed
    move_and_slide()                               # Godot 4: no arguments; uses `velocity`

func shoot() -> void:
    var b := bullet_scene.instantiate() as Bullet  # Godot 4: instantiate(), not instance()
    b.global_position = global_position
    get_tree().current_scene.add_child(b)
```

- **State machine with enum + match**:

```gdscript
enum State { IDLE, RUN, ATTACK }
var state := State.IDLE

func _process(_delta: float) -> void:
    match state:
        State.IDLE:
            if Input.is_action_pressed("move_right"): state = State.RUN
        State.RUN:
            pass
        State.ATTACK, _:
            pass
```

- **Resources as data** (`class_name ItemData extends Resource` + `@export` fields): design data in the inspector and save it as `.tres`. Remember that **resources loaded from disk are shared**, so call `duplicate()` (or set `resource_local_to_scene`) before mutating per-instance.
- **Save games**: `FileAccess.open("user://save.json", FileAccess.WRITE)` + `JSON.stringify(data)`, or `ResourceSaver.save()`. `ConfigFile` for settings. Never `load()` untrusted `.tres`/`.res` (see Security).
- **Autoload singleton** `GameState` holds cross-scene state. **Groups** for broadcast: `get_tree().call_group("enemies", "freeze")`.
- **Tweens** (Godot 4): `var t := create_tween(); t.tween_property(self, "modulate:a", 0.0, 0.3).set_ease(Tween.EASE_OUT); t.tween_callback(queue_free)`. The old `Tween` node is gone.
- String formatting: `"HP: %d/%d" % [hp, max_hp]`, `"Hi {name}".format({"name": n})`, `str(a, b)`. `StringName` literals use `&"name"` and NodePath literals use `^"path"`.

## 7. Top pitfalls and error-message fixes

| Exact error text | Cause | Fix |
|---|---|---|
| `Invalid access to property or key 'x' on a base object of type 'null instance'.` (4.x; older: `Invalid get index 'x' (on base: 'null instance')`) | `$Node` path wrong, or used before `_ready`, or node freed | Use `@onready`, check the path / `%UniqueName`, `if node:` / `is_instance_valid(node)` |
| `Invalid call. Nonexistent function 'instance' in base 'PackedScene'.` | Godot 3 API | `instantiate()` |
| `Too many arguments for "move_and_slide()" call. Expected at most 0 but received 2.` | Godot 3 signature | Set `velocity` then call `move_and_slide()` |
| `"yield" was removed in Godot 4. Use "await" instead.` | Godot 3 coroutine syntax | `await signal_name` / `await obj.signal` |
| `Function "connect" ... ` / `Invalid argument for "connect()"` with string method names | Godot 3 `connect("sig", self, "_on")` | `sig.connect(_on)` / `obj.sig.connect(callable)` |
| `Node not found: "Sprite" (relative to "/root/Main/Player").` | Wrong node path or renamed node | Fix the path, mark as unique (`%`), or `get_node_or_null` |
| `Cannot infer the type of "x" variable because the value doesn't have a set type.` | `:=` on a Variant expression | Give an explicit type: `var x: int = d["k"]` |
| `Trying to assign an array of type "Array" to a variable of type "Array[int]".` | Untyped array assigned to typed | `var a: Array[int] = []; a.assign(src)` or `Array(src, TYPE_INT, "", null)` |
| `Can't change this state while flushing queries. Use call_deferred() or set_deferred() to change monitoring state instead.` | Modifying physics bodies/areas during a physics callback | `call_deferred("add_child", n)`, `set_deferred("monitoring", false)` |
| `Attempt to call function 'x' in base 'previously freed' on a null instance.` / `Invalid access ... 'previously freed'` | Using a node after `queue_free()` | `is_instance_valid()`; disconnect signals; avoid storing raw refs |
| `Parent node is busy setting up children, add_child() failed. Consider using add_child.call_deferred(child) instead.` | Adding children in `_ready` of a parent still being set up | `add_child.call_deferred(child)` |
| `Identifier "Foo" not declared in the current scope.` | Missing `class_name`, typo, or the class cache is stale | Add `class_name`, reload the project / reimport |
| `Could not find type "Enemy" in the current scope.` | Cyclic or unregistered `class_name` (often after a parse error in Enemy.gd) | Fix the parse error in the referenced script; restart the editor |
| `Unexpected "Indent" in class body.` / `Mixed use of tabs and spaces for indentation.` | Indentation | Use one style (the editor default is tabs) |
| `The method "cry" is abstract and must be implemented` (wording varies) | Subclass of an `@abstract` class missing an override (4.5+) | Implement the method |
| `Not all code paths return a value.` (4.7: overrides inherit typed returns) | A typed function with a path lacking `return` | Add the final `return` (4.7 migration guide suggests `return null` for Variant-returning overrides) [6] |
| `Integer division. Decimal part will be discarded.` (warning) | `5 / 2` with ints gives 2 | Use `5 / 2.0` or `float(a) / b` |

## 8. Performance

- Use static types everywhere hot, for typed opcodes [2]. Prefer `Vector2`/`PackedFloat32Array` over Arrays of floats. Typed arrays enable faster element access.
- Cache node references (`@onready`). Do not call `get_node`/`$` every frame. `StringName` (`&"action"`) avoids string hashing in `Input.is_action_pressed`.
- Turn off processing on idle nodes: `set_process(false)`, `set_physics_process(false)`. Use signals instead of polling.
- Pool frequently spawned objects (bullets) instead of `instantiate()`/`queue_free()` every shot. For thousands of instances, use `MultiMeshInstance`, `RenderingServer`/`PhysicsServer` directly, or GDExtension.
- Profiling: the editor Debugger > Profiler / Monitors, the new GDScript profiler support (4.6) [4], and external profilers (Tracy/Perfetto, 4.6+) [4]. Use `Performance.get_monitor()` for in-game stats.
- Heavy math (pathfinding, procedural generation) goes to GDExtension (C++/Rust) or `WorkerThreadPool`. GDScript is an interpreted bytecode VM, roughly comparable to Python speed.

## 9. Security

- **Never load untrusted `.tres`/`.res`/`.tscn` files.** Resources can embed scripts, and loading one can execute arbitrary GDScript. For mods or user saves, use data formats (JSON, ConfigFile with care, custom binary). Treat `ConfigFile` values that deserialize Objects as dangerous, and don't use `str_to_var` on untrusted input with objects (`bytes_to_var` has `allow_objects=false` by default; keep it false).
- **Multiplayer**: `@rpc` annotations (`@rpc("any_peer", "call_remote", "reliable")`). **Server-authoritative**: validate every `any_peer` RPC on the server (`multiplayer.get_remote_sender_id()`), never trust client positions/damage, use `MultiplayerSynchronizer` with authority set per node. Same rule as Roblox remotes.
- Exported games are decompilable (`.pck` can be extracted; GDScript is shipped as tokens or source). Encryption of the PCK requires a custom export template with an encryption key, and it only deters casual extraction. Never ship secrets in client builds.
- `OS.execute`/`OS.shell_open` with user input means command injection. File paths: restrict to `user://`.

## 10. Game-dev usage

- 2D: `CharacterBody2D` + `move_and_slide`, `Area2D` for triggers, `TileMapLayer` (4.3+, replaces `TileMap` layers), `AnimationPlayer`/`AnimationTree`, `AnimatedSprite2D`.
- 3D: `CharacterBody3D`. Jolt Physics is the default for new 3D projects in 4.6 [4]. `NavigationAgent3D`.
- UI: `Control` nodes, containers, themes. Anchors/containers are the analog of Roblox `UDim2` + `UIListLayout`.
- Input: Input Map actions (`Input.is_action_just_pressed("jump")`, `Input.get_vector`).
- Networking: high-level multiplayer (`ENetMultiplayerPeer`, `WebSocketMultiplayerPeer`, `WebRTC`), `MultiplayerSpawner`/`MultiplayerSynchronizer`.

## 11. Cheat sheet vs Luau

| Concept | Luau (Roblox) | GDScript (Godot 4) |
|---|---|---|
| Blocks | `then ... end`, `do ... end` | indentation + `:` |
| Indexing base | 1 | 0 |
| Null | `nil` | `null` |
| Truthiness | only `nil`/`false` falsy | `0`, `0.0`, `""`, empty Array/Dictionary, `null`, `false` are falsy |
| Not-equal | `~=` | `!=` |
| Logic | `and`/`or`/`not` | `and`/`or`/`not` or `&&`/`\|\|`/`!` |
| String concat | `..` | `+` (both Strings), `str(a, b)`, `"%s" % x` |
| Interpolation | `` `HP {hp}` `` | `"HP %d" % hp`, `"HP {hp}".format({"hp": hp})` |
| Tables/maps | `{}` table | `Array` `[]`, `Dictionary` `{}` (separate types) |
| Length | `#t` | `arr.size()` |
| Classes / self | metatables, `function T:m()` / `self` | one file = class; `self` implicit; `class_name` |
| Constructors | `T.new()` | `T.new()` calls `_init()`; scenes: `scene.instantiate()` |
| Closures | `function() end` | `func(): ...` lambdas (capture by value) |
| Events | `RBXScriptSignal:Connect(fn)` | `signal x` / `x.connect(fn)` / `x.emit()` |
| Wait | `task.wait(0.1)` | `await get_tree().create_timer(0.1).timeout` |
| Coroutines vs async | `task.spawn`, `coroutine` | `await` (function becomes a coroutine); `Thread`/`WorkerThreadPool` for parallelism |
| Integer division | `//` | `/` on two ints truncates (warning); `float(a)/b` for real division |
| Error handling | `pcall`, `error()` | no try/catch; `assert()`, `push_error()`, return error codes (`Error` enum, `OK`) |
| Modules | `require(ModuleScript)` | `preload("res://x.gd")`, `load()`, `class_name` global |
| Per-frame loop | `RunService.Heartbeat:Connect` | `_process(delta)` / `_physics_process(delta)` |
| Find child | `script.Parent:FindFirstChild("X")` | `$X`, `get_node_or_null("X")`, `%X` |
| Destroy | `inst:Destroy()` | `node.queue_free()` |
| Typing | `--!strict`, `x: number` | `var x: float`, `:=`, warnings as errors |
| Remotes | `RemoteEvent:FireServer` | `@rpc` functions + `rpc_id()` |
| Persistence | `DataStoreService` | `FileAccess` to `user://` (local), your own backend for online |

## 12. Recent changes and version notes

- **4.4** (Mar 2025): typed dictionaries `Dictionary[K, V]`, `@export_tool_button`, Jolt physics as an option, embedded game window in the editor [5].
- **4.5** (Sep 2025): `@abstract` classes/methods, variadic functions `...args: Array`, script backtracing in release builds (setting *Debug > Settings > GDScript > Always Track Call Stacks*), custom loggers [3].
- **4.6** (Jan 2026): GDScript profiler support, external profilers (Tracy/Perfetto/Instruments), Jolt as the default 3D physics, a new "Modern" editor theme, unique node IDs [4].
- **4.7** (June 2026; 4.7.2 on 18 Aug 2026) [1][6][7]:
  - `AwaitTweener`.
  - Enum metadata kept for all variables in remote debug.
  - Constant-expression improvements.
  - Breaking behaviour changes: packed-array element writes no longer call the property setter, and overrides inherit typed returns, so a `return` is now needed.
  - GDScript can implement Java interfaces on Android.
  - LSP and editor improvements.
- **4.8**: in development (dev7, 29 Sep 2026) [1]. Treat any feature only on master as unreleased.
- **Traits** (`trait`/`uses`) and **structs** are proposals/PRs, **not in a stable release as of 2026-10-13** (unverified beyond the 4.5–4.7 release notes). Do not generate `trait` syntax for users on stable Godot.
- Godot 3 → 4 renames that models still mix up: `KinematicBody2D` → `CharacterBody2D`, `instance()` → `instantiate()`, `yield` → `await`, `export` → `@export`, `onready` → `@onready`, `tool` → `@tool`, `connect("sig", obj, "m")` → `sig.connect(obj.m)`, `Spatial` → `Node3D`, `TileMap` layers → `TileMapLayer` nodes (4.3), `rand_range` → `randf_range`, `PoolStringArray` → `PackedStringArray`, `setget` → inline `set(value):`/`get:`.

## Sources

1. Godot download archive (versions and dates), https://godotengine.org/download/archive/ (accessed 2026-10-13)
2. GDScript static typing (4.7 docs), https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/static_typing.html
3. Godot 4.5 release page (abstract, variadic, backtracing), https://godotengine.org/releases/4.5/
4. Godot 4.6 release page, https://godotengine.org/releases/4.6/
5. Godot 4.4 release page (typed dictionaries, tool button), https://godotengine.org/releases/4.4/
6. Upgrading from Godot 4.6 to 4.7, https://docs.godotengine.org/en/4.7/tutorials/migrating/upgrading_to_godot_4.7.html
7. Dev snapshot: Godot 4.7 beta 1, https://godotengine.org/article/dev-snapshot-godot-4-7-beta-1/
8. GDScript reference, https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html
9. GDScript warning system, https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/warning_system.html
10. GUT (Godot Unit Test), https://gut.readthedocs.io/
11. gdUnit4, https://mikeschulze.github.io/gdUnit4/
12. gdtoolkit (gdformat/gdlint), https://github.com/Scony/godot-gdscript-toolkit
13. Command line tutorial, https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
14. High-level multiplayer, https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html
15. Thread-safe APIs, https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html
