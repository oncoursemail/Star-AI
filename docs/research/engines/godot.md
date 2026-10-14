# Godot 4 — engine reference for STAR

**Researched 2026-10-13.** Written for STAR (strongest at Roblox/Luau) so it can answer Godot questions correctly and
translate Roblox habits into Godot ones. Text is STAR's own wording. The Godot documentation is CC BY 3.0 (the class
reference is MIT); every section ends with the official pages it was checked against. Claims that could not be checked
against an official page are marked *(unverified)*.

Scope: Godot 4.x with GDScript 2.0 first, C#/.NET second, GDExtension last. Godot 3 syntax is covered only as a
"this is why your old code breaks" migration table.

---

## 1. Versions and release cadence (as of October 2026)

| Version | When | What matters for code |
|---|---|---|
| 4.0 | 2023-03 | GDScript 2.0, Vulkan renderers, new multiplayer API (`@rpc`, `MultiplayerSpawner`, `MultiplayerSynchronizer`), `CharacterBody`, Callable-based signals. |
| 4.2 | 2023-11 | C# on desktop is stable (Android/iOS C# arrive later as experimental). |
| 4.3 | 2024-08 | 2D physics interpolation, `TileMapLayer` replaces `TileMap`, runtime FBX loading (`FBXDocument`). |
| 4.4 | 2025-03 | `.uid` sidecar files, typed dictionaries, Jolt Physics built in (experimental, opt-in), 3D physics interpolation, embedded game window, ubershaders against shader stutter, `@export_tool_button`, C# targets .NET 8. |
| 4.5 | 2025-09 | GDScript variadic arguments and `@abstract` classes/methods, script backtraces in release builds (opt-in setting), custom loggers, stencil buffer, shader baker at export, AccessKit screen-reader support (experimental), dedicated 2D navigation server, 3D physics interpolation moved into `SceneTree`. |
| 4.6 | early 2026 | Jolt becomes the **default 3D physics engine for new projects** (existing projects keep their setting), new editor theme and docking, unique internal node IDs so references survive renames, LibGodot (embed the engine), rewritten SSR. |
| 4.7 | 2026-06 | `AreaLight3D`, HDR output, Asset Store replaces the Asset Library, transformable `Control` offsets, built-in `VirtualJoystick`, stable Android build environment, Mobile renderer recommended for XR. Maintenance releases 4.7.1 and 4.7.2 (Aug 2026) followed. |

Cadence: roughly two feature releases a year, each followed by `x.y.1`, `x.y.2` maintenance releases. Always read the
official migration guide ("Upgrading from Godot 4.N to 4.N+1") before bumping a project; minor versions do break things
(e.g. `TileMap` → `TileMapLayer`, `.uid` files, Jolt default).

**Rule for STAR:** when a user does not say a version, assume current stable (4.7) syntax, and say so when an answer
depends on a 4.4+/4.5+ feature (typed dictionaries, `@abstract`, variadic args, Jolt default).

Sources: https://godotengine.org/releases/4.7/ · https://godotengine.org/releases/4.6/ · https://godotengine.org/releases/4.5/ ·
https://godotengine.org/releases/4.4/ · https://godotengine.org/article/maintenance-release-godot-4-7-1/

### 1.1 Godot 3 → Godot 4 breaking changes (the most common source of "my code doesn't work")

| Godot 3 | Godot 4 |
|---|---|
| `yield(obj, "signal")` | `await obj.signal` |
| `yield(get_tree().create_timer(1), "timeout")` | `await get_tree().create_timer(1.0).timeout` |
| `connect("pressed", self, "_on_pressed")` | `pressed.connect(_on_pressed)` (Callable) |
| `emit_signal("hit", 5)` | `hit.emit(5)` (old form still works) |
| `export var speed = 10` | `@export var speed := 10.0` |
| `onready var label = $Label` | `@onready var label: Label = $Label` |
| `tool` | `@tool` |
| `remote`, `master`, `puppet`, `remotesync`, `rset` | `@rpc(...)` annotation; property sync via `MultiplayerSynchronizer` |
| `KinematicBody` / `KinematicBody2D` | `CharacterBody3D` / `CharacterBody2D` |
| `move_and_slide(velocity, Vector3.UP)` returns velocity | set the built-in `velocity` property, call `move_and_slide()` with **no arguments**; `up_direction` is a property |
| `Spatial` | `Node3D` |
| `PackedScene.instance()` | `PackedScene.instantiate()` |
| `File.new().open(...)` | `FileAccess.open(path, FileAccess.WRITE)` (static, returns `null` on failure) |
| `Directory` | `DirAccess` |
| `setget` | inline `var x: int: set(value): ...  get: ...` |
| `OS.get_ticks_msec()` | `Time.get_ticks_msec()` |
| `rand_range()` | `randf_range()` / `randi_range()` |
| `PoolStringArray` etc. | `PackedStringArray` etc. |
| `BUTTON_LEFT` | `MOUSE_BUTTON_LEFT` |
| `RigidBody` modes | `freeze` + `freeze_mode` |
| `Navigation` node | `NavigationServer3D` / `NavigationAgent3D` |
| `.instance_from_id` / `funcref()` | `instance_from_id()` / `Callable(obj, "method")` |
| `GLES2/GLES3` | Forward+, Mobile, Compatibility renderers |

Sources: https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html

---

## 2. Architecture

### 2.1 Object model
- **`Object`** — base of everything; manual memory (`free()`), has properties, signals, metadata.
- **`RefCounted`** — reference counted; freed automatically when the last reference goes. `Resource` derives from it.
- **`Resource`** — data container that can be saved (`.tres` text, `.res` binary). Loaded resources are **cached and
  shared**: two `load("res://x.tres")` calls return the same instance.
- **`Node`** — the building block of scenes. Lives in a tree, receives callbacks (`_ready`, `_process`, ...). Nodes are
  **not** reference counted: remove them with `queue_free()` (deferred, safe) rather than `free()`.
- **Scene** — a saved tree of nodes (`.tscn`), loaded as a `PackedScene` and instanced with `instantiate()`. A scene
  is the Godot unit of reuse (prefab in Unity terms, a Model in `ReplicatedStorage` in Roblox terms).
- **`SceneTree`** — the `MainLoop` that runs the game: owns the root `Window`, groups, timers, pausing, the current scene,
  and the default `MultiplayerAPI`.
- **Servers** — low-level singletons (`RenderingServer`, `PhysicsServer3D`, `NavigationServer3D`, `AudioServer`). Nodes
  are friendly wrappers over them; for thousands of objects you can talk to servers directly with RIDs.

### 2.2 Composition, groups and singletons
- Behaviour is composed by child nodes (a `Player` scene with `CollisionShape3D`, `AnimationPlayer`, `Camera3D`
  children). One script per node; reuse logic with child "component" nodes or `class_name` base classes.
- **Groups** tag nodes (`add_to_group("enemies")`, `get_tree().get_nodes_in_group("enemies")`,
  `get_tree().call_group(...)`). This is Godot's `CollectionService`.
- **Autoloads** (Project Settings → Globals → Autoload) are nodes instanced at startup under `/root` and reachable by
  name from every script. Use them sparingly for truly global services (save manager, event bus, audio).
- **Signals** are the observer pattern: declare `signal health_changed(new_value: int)`, emit with
  `health_changed.emit(hp)`, connect with `health_changed.connect(_on_health_changed)`. Rule of thumb:
  *call down, signal up* — parents call methods on children; children emit signals the parent listens to.

### 2.3 Ownership and freeing
- `queue_free()` deletes at the end of the frame. `free()` deletes now and can crash code still iterating.
- After a node is freed, any variable still pointing to it is a "previously freed" instance. Test with
  `is_instance_valid(node)`; better, disconnect/clear the reference when `tree_exiting` fires.
- `owner` matters when saving scenes from code (`PackedScene.pack`): only nodes whose `owner` is the scene root are saved.

Sources: https://docs.godotengine.org/en/stable/getting_started/step_by_step/nodes_and_scenes.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/singletons_autoload.html ·
https://docs.godotengine.org/en/stable/getting_started/step_by_step/signals.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/groups.html ·
https://docs.godotengine.org/en/stable/classes/class_node.html

---

## 3. Lifecycle

Order when a scene is added to the tree:

1. `_init()` — constructor; the node is **not** in the tree; no children available from the scene file yet.
2. `_enter_tree()` — called parent first, then children (top-down).
3. `_ready()` — called **children first, then parent** (bottom-up), once per node the first time it enters the tree.
   `@onready` variables are assigned just before `_ready()`. Call `request_ready()` to get `_ready()` again after
   re-adding.
4. Every frame: `_process(delta)` (render frame, variable delta) and `_physics_process(delta)` (fixed tick,
   default 60 Hz, `Engine.physics_ticks_per_second`).
5. Input: `_input(event)` → GUI (`Control._gui_input`) → `_shortcut_input` → `_unhandled_key_input` →
   `_unhandled_input(event)`. Use `_unhandled_input` for gameplay so UI can consume clicks first; call
   `get_viewport().set_input_as_handled()` to stop propagation.
6. `_exit_tree()` — on removal (children first? no: exit is called child-first after parent notification; do not rely on
   sibling state here). `tree_exiting`/`tree_exited` signals are safer hooks.
7. `NOTIFICATION_PREDELETE` — right before the object is destroyed.

Practical rules:
- Move bodies, apply forces and read physics state in `_physics_process`; do camera smoothing/visuals in `_process`.
- With **physics interpolation** enabled (Project Settings → Physics → Common → Physics Interpolation; 2D since 4.3,
  3D since 4.4), move bodies only in `_physics_process` and the renderer interpolates — this removes jitter at high refresh
  rates. Teleports need `reset_physics_interpolation()`.
- `call_deferred("method")` / `set_deferred("prop", v)` run at idle time. Needed when changing the tree or physics state
  inside a physics callback (e.g. disabling a `CollisionShape3D` inside `body_entered` → use
  `shape.set_deferred("disabled", true)`), and for `add_child` during `_ready` of the parent.
- `process_mode` (`PROCESS_MODE_INHERIT`, `PAUSABLE`, `WHEN_PAUSED`, `ALWAYS`, `DISABLED`) controls what keeps running
  while `get_tree().paused = true`. A pause menu needs `PROCESS_MODE_WHEN_PAUSED` or `ALWAYS`.
- `set_process(false)` / `set_physics_process(false)` stop the callbacks for idle nodes (cheap optimisation).

Sources: https://docs.godotengine.org/en/stable/tutorials/scripting/overridable_functions.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/idle_and_physics_processing.html ·
https://docs.godotengine.org/en/stable/tutorials/inputs/inputevent.html ·
https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/index.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/pausing_games.html

---

## 4. Project layout

```
my_game/
  project.godot          # project settings (INI-like text). Commit it.
  export_presets.cfg     # export presets. Commit it, but keep secrets (keystore passwords) out: they go to
                         # .godot/export_credentials.cfg which is not committed.
  icon.svg
  .godot/                # imported asset cache, editor state, UID cache. NEVER commit (in default .gitignore).
  addons/<plugin>/       # editor plugins and GDExtensions; plugin.cfg per plugin
  scenes/ scripts/ assets/ ...   # free-form; group by feature, not by type, in larger projects
  *.import               # import settings next to each source asset. Commit them.
  *.uid                  # (4.4+) UID sidecar for scripts/shaders. Commit them, move them together with the file.
```

- Paths: `res://` = project folder, **read-only in an exported game**. `user://` = per-user writable data folder
  (Windows `%APPDATA%\Godot\app_userdata\<project>` or a custom dir if `application/config/use_custom_user_dir`).
  Save games, settings and logs go to `user://`.
- `.tscn`/`.tres` are text and merge reasonably in Git; `.scn`/`.res` are binary.
- Move/rename files **inside the editor's FileSystem dock** so references and `.uid` files are updated.
- Godot's default `.gitignore` is `.godot/` and `/android/`.
- Editor plugins: `addons/x/plugin.cfg` + an `EditorPlugin` `@tool` script; enable in Project Settings → Plugins.

Sources: https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html ·
https://docs.godotengine.org/en/stable/tutorials/best_practices/project_organization.html ·
https://docs.godotengine.org/en/stable/tutorials/best_practices/version_control_systems.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/scene_unique_nodes.html

---

## 5. GDScript 2.0 idioms and pitfalls

### 5.1 Typing
- Use static types: `var speed: float = 5.0`, inferred `var speed := 5.0`, typed returns `func hit(dmg: int) -> void:`.
  Typed code is faster (typed instructions) and the editor catches errors. Turn on warnings like
  `untyped_declaration` in Project Settings → Debug → GDScript for strictness (closest thing to Luau `--!strict`).
- Typed arrays `Array[Enemy]`, typed dictionaries (4.4+) `Dictionary[String, int]`.
- `class_name Enemy` registers a global type usable in type hints and `is` checks. `extends CharacterBody3D` picks the base.
- 4.5+: `@abstract class_name Weapon` and `@abstract func fire() -> void` for base classes; variadic
  `func log(...args: Array)`.
- `:=` cannot infer from a `Variant` (e.g. `var x := dict["k"]` errors) — give an explicit type.

### 5.2 Annotations
- `@export var hp := 100`, `@export_range(0, 100, 1) var pct: int`, `@export_enum("A","B") var mode: int`,
  `@export_node_path`, `@export var target: Node3D` (node export, 4.0+), `@export_group("Movement")`,
  `@export_file("*.json")`, `@export_flags_3d_physics var mask: int`.
- `@onready var anim: AnimationPlayer = $AnimationPlayer` — resolved right before `_ready`.
- `@tool` runs the script **in the editor** too — guard gameplay code with `if Engine.is_editor_hint(): return`.
- `@export_tool_button("Bake") var bake_btn = bake` (4.4+) puts a button in the inspector.
- `@warning_ignore("unused_parameter")`, `@static_unload`, `@icon("res://icon.svg")`.

### 5.3 Nodes and paths
- `$Path/To/Node` is `get_node("Path/To/Node")`. It fails (null + error) if called before the node is in the tree or
  if the path is wrong. Prefer **scene-unique names**: mark a node "Access as Unique Name" and use `%HealthBar` —
  survives re-parenting inside the scene.
- Prefer `@export var target: Node` over hard-coded paths for cross-scene references.
- `get_node_or_null()` when absence is legal.

### 5.4 Signals, await, Callables
- `signal died` / `died.emit()` / `died.connect(_on_died)` / `died.disconnect(_on_died)`.
- Connecting twice raises an error — check `is_connected` or use `CONNECT_ONE_SHOT` where suitable.
- Bind extra arguments: `button.pressed.connect(_on_pressed.bind(item_id))`.
- Lambdas: `timer.timeout.connect(func(): print("done"))`. A lambda capturing `self` keeps working only while `self` lives.
- `await some_signal` suspends the function (coroutine). The caller does not wait unless it also `await`s the call.
  If the node is freed while awaiting, the coroutine is dropped — re-check `is_instance_valid(self)` after long awaits.

### 5.5 Resources
- `preload("res://x.tscn")` at parse time (constant path, cheaper), `load()` at runtime, `ResourceLoader.load_threaded_request()` for background loading.
- Resources are **shared**: modifying `material.albedo_color` on a loaded material changes every user. Use
  `resource.duplicate()` or enable **Local to Scene** (`resource_local_to_scene = true`) for per-instance copies.
- Custom data assets: `class_name ItemData extends Resource` with `@export` fields → create `.tres` files in the editor
  (Godot's ScriptableObject).

### 5.6 Other pitfalls
- Integer division: `5 / 2 == 2`. Use `5 / 2.0`.
- `==` between `int` and `float` works, but `is` checks types exactly.
- Dictionaries/arrays are passed by reference; `duplicate(true)` for deep copies.
- `print_debug`, `push_error`, `push_warning`, `assert()` (asserts are stripped from release builds).
- Use `StringName` (`&"jump"`) for hot-path action names to avoid string hashing.

Sources: https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/static_typing.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_exports.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/warning_system.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html ·
https://docs.godotengine.org/en/stable/tutorials/plugins/running_code_in_the_editor.html

---

## 6. C# in Godot

- Use the **.NET build** of the editor. Since 4.4 projects target **.NET 8** (upgraded automatically). Android needs
  .NET 9+ for 16 KB page support (4.5 notes).
- Platforms: Windows/macOS/Linux stable; **Android and iOS experimental**; **web export is not supported for C#** in
  Godot 4 (docs suggest Godot 3 if C# on web is mandatory).
- Classes must be `partial` and derive from a Godot type: `public partial class Player : CharacterBody3D`.
  Source generators produce the glue — without `partial`, exports/signals fail to register.
- `[Export] public float Speed { get; set; } = 5f;`
- Signals: `[Signal] public delegate void HealthChangedEventHandler(int value);` (name **must end in `EventHandler`**),
  emit with `EmitSignal(SignalName.HealthChanged, hp)`, subscribe with `HealthChanged += OnHealthChanged;`.
- Godot API is PascalCase (`GetNode<Label>("Label")`, `_Ready()`, `_PhysicsProcess(double delta)`; delta is `double`).
- Build before running (the editor builds automatically); after renaming a class make sure the file name matches the class.
- Mixing: GDScript can call C# and vice versa via `Call()`/`Get()`, but keep one language per subsystem.
- Disconnect C# event subscriptions to Godot signals with `-=` when the subscriber can outlive the emitter; for lambdas
  use `Connect(..., Callable.From(...))` and Godot tracks it.

Sources: https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/index.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_basics.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_signals.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_exports.html

---

## 7. Rendering

### 7.1 Renderers
| Renderer | Backend | Use for |
|---|---|---|
| **Forward+** | Vulkan / D3D12 / Metal | Desktop 3D with all features (SDFGI, VoxelGI, volumetric fog, SSR, clustered lights). |
| **Mobile** | Vulkan / D3D12 / Metal | Mobile and XR (recommended for new XR projects in 4.7); fewer per-object lights, cheaper passes. |
| **Compatibility** | OpenGL 3.3 / OpenGL ES 3.0 / WebGL 2 | Web export, old/low-end hardware, simple 2D. Missing many advanced 3D effects. |

The renderer is a project setting (`rendering/renderer/rendering_method`, with `.mobile` override). Web exports use
Compatibility.

### 7.2 Lighting and GI
- `WorldEnvironment` + `Environment` resource: sky, ambient light, tonemapping, glow, fog, SSAO, SSR, SSIL, adjustments.
- Global illumination options: **LightmapGI** (baked, cheapest at runtime, static), **VoxelGI** (baked probe volume,
  semi-dynamic objects), **SDFGI** (real-time, large open worlds, Forward+ only), ReflectionProbe for reflections.
- Lights: `DirectionalLight3D` (sun, shadow cascades), `OmniLight3D`, `SpotLight3D`, `AreaLight3D` (4.7). 2D:
  `PointLight2D`, `DirectionalLight2D`, `LightOccluder2D`.
- Stencil buffer (4.5) for x-ray/outline effects.

### 7.3 Materials and shaders
- `StandardMaterial3D` (PBR) / `ORMMaterial3D`; `ShaderMaterial` with `.gdshader` files (GLSL-like language,
  `shader_type spatial;` / `canvas_item;` / `particles;` / `sky;` / `fog;`), or the Visual Shader editor.
- Shader stutter: 4.4 ubershaders + 4.5 shader baker (precompile on export) reduce first-use hitches.

### 7.4 Scale tools
- LOD: automatic mesh LOD on import; `visibility_range_*` (HLOD) on `GeometryInstance3D`.
- Occlusion culling: `OccluderInstance3D` + bake; enable in Project Settings.
- `MultiMeshInstance3D` for thousands of identical meshes (grass, crowds); `GPUParticles3D`/`CPUParticles3D`.
- 2D: `CanvasItem` batching is automatic in Compatibility and improved in RD renderers; use `TileMapLayer`.

Sources: https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html ·
https://docs.godotengine.org/en/stable/tutorials/3d/global_illumination/index.html ·
https://docs.godotengine.org/en/stable/tutorials/3d/environment_and_post_processing.html ·
https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html ·
https://docs.godotengine.org/en/stable/tutorials/performance/using_multimesh.html ·
https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html

---

## 8. Physics

### 8.1 Engines
- 3D: **Jolt** is built in since 4.4 and **the default for new projects since 4.6**; GodotPhysics3D remains selectable
  (Project Settings → Physics → 3D → Physics Engine, then restart). Existing projects are not switched automatically and
  behaviour differs (joint soft limits unsupported, single-body joints attach to `node_b`, kinematic contacts opt-in,
  ray-cast `face_index` opt-in, smaller `WorldBoundaryShape3D`).
- 2D: GodotPhysics2D.

### 8.2 Bodies
| Node | Use |
|---|---|
| `StaticBody3D` | Never moves (or moves via `constant_linear_velocity` for conveyors). |
| `AnimatableBody3D` | Moved by code/animation, pushes others (moving platforms). |
| `RigidBody3D` | Simulated. Do not set `position` every frame; apply `apply_central_impulse`, `apply_force`, or edit state in `_integrate_forces(state)`. `freeze` + `freeze_mode` for kinematic/static modes. |
| `CharacterBody3D` | Code-driven characters. Set `velocity`, call `move_and_slide()`; read `is_on_floor()`, `get_slide_collision()`. `up_direction`, `floor_max_angle`, `floor_snap_length` are properties. `move_and_collide(motion)` for custom response. |
| `Area3D` | Overlap detection, gravity/damping zones. Signals `body_entered`, `area_entered`. Needs `monitoring = true` and a `CollisionShape3D` child. |

Every body needs at least one `CollisionShape3D`/`CollisionPolygon3D` **direct child** with a shape resource.

### 8.3 Layers and masks
- `collision_layer` = **what I am**; `collision_mask` = **what I look for/collide with**. An `Area3D` detects a body
  only if the body's layer is in the area's mask (and the area is monitoring); a body is detected by areas whose mask
  includes its layer. Name layers in Project Settings → Layer Names.
- Set in code with `set_collision_layer_value(3, true)` (1-based layer numbers) or bit masks.

### 8.4 Queries
- Node: `RayCast3D` (`is_colliding()`, `get_collider()`, `force_raycast_update()`), `ShapeCast3D`.
- Immediate: `var space := get_world_3d().direct_space_state; var q := PhysicsRayQueryParameters3D.create(from, to, mask, [self.get_rid()]); var hit := space.intersect_ray(q)` — dictionary with `position`, `normal`, `collider`. Only valid inside `_physics_process`.

### 8.5 Gotchas
- Moving `CharacterBody3D` with `position +=` skips collision. Use `move_and_slide()`.
- Scaling collision shapes non-uniformly breaks physics — change the shape's size instead.
- Changing physics state in a signal callback → `set_deferred`.
- Tunnelling at high speed → `continuous_cd` on `RigidBody3D`, or ray/shape casts.

Sources: https://docs.godotengine.org/en/stable/tutorials/physics/physics_introduction.html ·
https://docs.godotengine.org/en/stable/tutorials/physics/using_character_body_2d.html ·
https://docs.godotengine.org/en/stable/tutorials/physics/ray-casting.html ·
https://docs.godotengine.org/en/stable/tutorials/physics/using_jolt_physics.html ·
https://docs.godotengine.org/en/stable/classes/class_characterbody3d.html

---

## 9. Animation

- **`AnimationPlayer`** — keyframes any property of any node (position, modulate, shader params, method calls).
  `play("run")`, `queue()`, `animation_finished` signal, `speed_scale`, blend time.
- **`AnimationTree`** — state machines (`AnimationNodeStateMachine`, travel with
  `$AnimationTree["parameters/playback"].travel("jump")`), blend spaces (`BlendSpace1D/2D`), blend trees,
  one-shot nodes; parameters via `set("parameters/blend_position", v)`. Both inherit `AnimationMixer` (4.2+).
- Root motion: `AnimationTree.root_motion_track` + `get_root_motion_position()`.
- Animation libraries: animations live in `AnimationLibrary` resources ("" is the default library; `"lib/anim"` otherwise).
- Skeletons: `Skeleton3D`, `SkeletonModifier3D` subclasses for IK/look-at (`LookAtModifier3D`, `SkeletonIK3D` legacy) *(exact IK node set varies by version — check the class reference for your version)*.
- Retargeting on import with `BoneMap`/`SkeletonProfileHumanoid`.
- **Tweens**: `var t := create_tween(); t.tween_property(node, "position", target, 0.3).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)`;
  `t.parallel()`, `t.tween_callback(f)`, `t.set_loops()`. Tweens created with `create_tween()` on a node die with it. Kill a
  previous tween (`if tween: tween.kill()`) before starting a new one on the same property. This is TweenService.

Sources: https://docs.godotengine.org/en/stable/tutorials/animation/introduction.html ·
https://docs.godotengine.org/en/stable/tutorials/animation/animation_tree.html ·
https://docs.godotengine.org/en/stable/classes/class_tween.html ·
https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html

---

## 10. UI

- `Control` nodes; layout by **anchors** (0–1 fractions of parent, like Roblox Scale) plus **offsets** (pixels, like
  Offset). Layout presets ("Full Rect", "Center") in the toolbar.
- **Containers** own their children's layout: `VBoxContainer`, `HBoxContainer`, `GridContainer`, `MarginContainer`,
  `CenterContainer`, `ScrollContainer`, `PanelContainer`. Children use **size flags** (`SIZE_EXPAND_FILL`) and
  `custom_minimum_size` instead of manual positions (UIListLayout/UIGridLayout/UIPadding equivalents).
- **Themes** (`Theme` resource) style many controls at once; per-control overrides via `add_theme_*_override`.
- `CanvasLayer` draws UI above the 3D/2D world independent of the camera (ScreenGui).
- Input blocking: every `Control` has `mouse_filter` — `STOP` (default for most; eats the click), `PASS` (handles and
  passes up to parents), `IGNORE` (invisible to the mouse). A full-screen `Control`/`ColorRect` overlay with `STOP`
  silently blocks clicks to everything behind it and to `_unhandled_input`.
- Focus/gamepad: `focus_mode`, `focus_neighbor_*`, `grab_focus()`.
- Multi-resolution: Project Settings → Display → Window → Stretch (`mode = canvas_items`, `aspect = expand`) and design
  at a base resolution.
- 4.5 adds screen-reader support through AccessKit (experimental); 4.7 adds transformable control offsets.

Sources: https://docs.godotengine.org/en/stable/tutorials/ui/size_and_anchors.html ·
https://docs.godotengine.org/en/stable/tutorials/ui/gui_containers.html ·
https://docs.godotengine.org/en/stable/tutorials/ui/gui_skinning.html ·
https://docs.godotengine.org/en/stable/classes/class_control.html ·
https://docs.godotengine.org/en/stable/tutorials/rendering/multiple_resolutions.html

---

## 11. Input

- Define actions in Project Settings → Input Map (`jump`, `move_left`...). Read with `Input.is_action_pressed("jump")`,
  `Input.is_action_just_pressed`, `Input.get_vector("left","right","up","down")` (dead-zone aware, normalised).
- Event callbacks: `_unhandled_input(event)` → `event.is_action_pressed("jump")`. `InputEventKey`,
  `InputEventMouseButton`, `InputEventMouseMotion` (`relative` for mouse look), `InputEventJoypadMotion`,
  `InputEventScreenTouch`.
- Mouse capture: `Input.mouse_mode = Input.MOUSE_MODE_CAPTURED`.
- Rebinding at runtime: `InputMap.action_erase_events` / `action_add_event`; persist with `ConfigFile`.
- 4.7: built-in `VirtualJoystick` node for touch, gyro aiming, per-device keyboard/mouse IDs.

Sources: https://docs.godotengine.org/en/stable/tutorials/inputs/input_examples.html ·
https://docs.godotengine.org/en/stable/tutorials/inputs/inputevent.html ·
https://docs.godotengine.org/en/stable/classes/class_input.html

---

## 12. Networking and multiplayer

### 12.1 Model
- The **high-level multiplayer API** (`MultiplayerAPI`, default implementation `SceneMultiplayer`) is per `SceneTree`
  (`multiplayer` property on every node). Transports (`MultiplayerPeer`): **`ENetMultiplayerPeer`** (UDP, default),
  `WebSocketMultiplayerPeer` (web), `WebRTCMultiplayerPeer` (P2P/browser), `OfflineMultiplayerPeer` (default, no network).
- Server peer ID is always **1**. Clients get random IDs. `multiplayer.get_unique_id()`, `multiplayer.is_server()`.
- Host: `var peer := ENetMultiplayerPeer.new(); peer.create_server(PORT, MAX_CLIENTS); multiplayer.multiplayer_peer = peer`.
  Client: `peer.create_client(ADDRESS, PORT)`. Check the returned `Error`.
- Signals: `peer_connected(id)`, `peer_disconnected(id)` (all peers); `connected_to_server`, `connection_failed`,
  `server_disconnected` (clients). Optional authentication: `auth_callback`, `send_auth`, `complete_auth`.
- UDP only for ENet: port-forward UDP. Godot has no built-in relay/matchmaking; use your own server, WebRTC signalling,
  or a third-party service.

### 12.2 RPCs
- `@rpc(mode, sync, transfer_mode, channel)` — default `@rpc("authority", "call_remote", "reliable", 0)`. First three
  arguments in any order, channel last.
  - mode `"authority"`: only the node's multiplayer authority may call it remotely. `"any_peer"`: any peer may (needed
    for client → server requests).
  - sync `"call_remote"` (default) doesn't run locally; `"call_local"` also runs on the caller (use when the host is also
    a player).
  - transfer `"reliable"`, `"unreliable"`, `"unreliable_ordered"`.
- Call: `my_func.rpc(args)` (everyone), `my_func.rpc_id(1, args)` (only the server), `rpc_id(peer_id, ...)`.
- **Paths and signatures must match on every peer**: same `NodePath` (same node names — add nodes with
  `add_child(node, true)` / `force_readable_name`), the same RPC set in the script (a checksum covers all RPCs; declare
  every RPC on both sides). Mismatch errors can point at an unrelated RPC.
- RPC arguments can't be Objects or Callables; send IDs/plain data.
- **Validate on the server**: inside an `any_peer` RPC read `multiplayer.get_remote_sender_id()` and check that this
  peer may do this (owns the character, cooldown, range). Never trust positions/damage from clients — same rule as
  Roblox `OnServerEvent`.

### 12.3 Authority
- Each node has a **multiplayer authority** (default 1 = server). `set_multiplayer_authority(peer_id)` (recursive by
  default) and `is_multiplayer_authority()`. Typical pattern: server spawns a player character named after the peer ID,
  sets authority to that peer for the input node only, and the server stays authoritative for health/score.
- Authority must be set identically on all peers (e.g. in `_enter_tree` from the node name) before RPCs/sync happen.

### 12.4 Spawning and state sync
- **`MultiplayerSpawner`**: set `spawn_path` (a parent node) and the list of spawnable scenes (editor or
  `add_spawnable_scene`). When the **authority** adds an instance of a listed scene as a direct child of `spawn_path`,
  remote peers spawn it too; freeing it despawns. `spawn_function` + `spawn(data)` for custom spawns (return a node not
  yet in the tree; do not `add_child` it yourself). `spawned`/`despawned` signals fire on remote peers.
  Common failures: scene not in the spawnable list; added under a different parent; added on a client; spawner itself not
  present at the same path on clients; `spawn_limit` hit.
- **`MultiplayerSynchronizer`**: replicates properties listed in its `replication_config` (`SceneReplicationConfig`)
  from the synchronizer's authority to others; per-property *spawn* (sent once on spawn) and *sync/watch* modes;
  `replication_interval`, `delta_interval`, visibility filters (`public_visibility`, `add_visibility_filter`,
  `set_visibility_for`) for interest management. Its authority decides direction — a client-authoritative input
  synchronizer + server-authoritative state synchronizer is a common split.
- Dedicated server: export with the "Dedicated Server" option / run with `--headless`; check
  `OS.has_feature("dedicated_server")`.
- Network profiler in the debugger shows RPC and sync bandwidth.

Sources: https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html ·
https://docs.godotengine.org/en/stable/classes/class_multiplayerspawner.html ·
https://docs.godotengine.org/en/stable/classes/class_multiplayersynchronizer.html ·
https://docs.godotengine.org/en/stable/classes/class_enetmultiplayerpeer.html ·
https://docs.godotengine.org/en/stable/classes/class_multiplayerapi.html ·
https://godotengine.org/article/multiplayer-in-godot-4-0-scene-replication/

---

## 13. Save data

- Write to `user://`. `res://` is read-only in exports.
- **JSON**: `JSON.stringify(dict)` / `JSON.parse_string(text)` with `FileAccess.open(path, FileAccess.WRITE)` /
  `store_string` / `get_as_text`. Human-readable, safe to parse, but numbers come back as `float` and Vector types must
  be encoded by hand.
- **Binary variants**: `store_var(value)` / `get_var()`. Smaller, keeps Godot types. **Leave `allow_objects` false** —
  the docs warn deserialized objects can contain code that gets executed (remote code execution with untrusted files).
- **`ConfigFile`** for settings (sections/keys, INI-like), `save("user://settings.cfg")`.
- **Resources** (`ResourceSaver.save(res, "user://save.tres")`, `ResourceLoader.load`) are convenient but a `.tres`/`.res`
  can embed a script that runs on load — treat any save file a player can edit or download (shared saves, mods, cloud
  sync) as untrusted and use JSON/`ConfigFile`/`get_var()` without objects instead *(the risk is documented by the
  `FileAccess.get_var` warning and widely reported by the community for resources; the resource-loading pages
  themselves do not carry a warning)*.
- `FileAccess.open` returns `null` on failure → check `FileAccess.get_open_error()`. Create folders first with
  `DirAccess.make_dir_recursive_absolute()`.
- Write to a temp file then rename (`DirAccess.rename_absolute`) for crash-safe saves; version your format
  (`{"version": 2, ...}`) and migrate on load.
- `FileAccess.open_encrypted_with_pass` deters casual editing (the key ships with the game — not real security).
- Online saves: there is no DataStoreService equivalent; you need your own backend or a service.

Sources: https://docs.godotengine.org/en/stable/tutorials/io/saving_games.html ·
https://docs.godotengine.org/en/stable/classes/class_fileaccess.html ·
https://docs.godotengine.org/en/stable/classes/class_configfile.html ·
https://docs.godotengine.org/en/stable/classes/class_json.html ·
https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html ·
https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html

---

## 14. GDExtension

- Native code (C++ via **godot-cpp**, also Rust via godot-rust, Swift, etc.) loaded at runtime as a shared library
  without recompiling the engine. Alternative to engine **modules** (compiled into the engine) and to C#.
- A `.gdextension` file (INI) declares `entry_symbol`, `compatibility_minimum` (oldest Godot version supported) and
  per-platform library paths under `[libraries]`.
- godot-cpp branch/tag must match the targeted Godot API version; build with SCons or CMake; register classes in the
  initializer (`GDREGISTER_CLASS(MyNode)`), bind methods in `_bind_methods()` with `ClassDB::bind_method`.
- Extensions are forward-compatible within 4.x from their `compatibility_minimum` *(minor exceptions happen; check the
  release notes)*. 4.7 lists GDExtensions in Project Settings.
- Use it for hot loops (pathfinding, procedural generation, physics helpers) or binding third-party C/C++ libraries.

Sources: https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/what_is_gdextension.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/cpp/gdextension_cpp_example.html ·
https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/gdextension_file.html

---

## 15. Performance and profiling

- **Debugger → Profiler** (script functions, frame time), **Visual Profiler** (CPU/GPU per render pass), **Monitors**
  (FPS, objects, nodes, draw calls, video memory, physics), **Network Profiler**, **Video RAM** tab. `Performance.get_monitor()`
  from code; custom monitors with `Performance.add_custom_monitor`.
- Frame-time hotspots: `get_node()` / `$` in `_process` (cache in `@onready`), string-keyed lookups in hot loops,
  creating/freeing many nodes per frame (pool them: hide + `process_mode = DISABLED`), too many `Area3D` overlaps,
  unneeded `_process` on idle nodes (`set_process(false)`), untyped GDScript in hot loops.
- Many identical objects: `MultiMeshInstance3D`; direct `RenderingServer`/`PhysicsServer3D` RIDs for tens of thousands.
- Threads: `WorkerThreadPool.add_task`, `Thread`, `Mutex`; the scene tree is **not thread-safe** — change nodes via
  `call_deferred`. `ResourceLoader.load_threaded_request` for background loading.
- GPU: draw calls (merge meshes, MultiMesh), overdraw from transparency/particles, shadow cascades and shadow distance,
  SDFGI/volumetric fog cost, use Mobile/Compatibility for low-end.
- Shader stutter: ubershaders (4.4) and shader baker on export (4.5).
- Physics: fewer, simpler shapes (prefer primitives over `ConcavePolygonShape3D`), sleeping bodies, physics ticks.

Sources: https://docs.godotengine.org/en/stable/tutorials/performance/index.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/debug/the_profiler.html ·
https://docs.godotengine.org/en/stable/tutorials/performance/using_servers.html ·
https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html ·
https://docs.godotengine.org/en/stable/tutorials/scripting/debug/debugger_panel.html

---

## 16. Build, export and CI

- Install **export templates** matching the exact editor version (Editor → Manage Export Templates).
- `export_presets.cfg` holds presets (platform, features, include/exclude filters, encryption, embed PCK).
- CLI (no window): `godot --headless --path . --import` (import assets in CI), `godot --headless --path . --export-release "Windows Desktop" build/game.exe`,
  `--export-debug`, `--export-pack` (PCK only). The preset name must match `export_presets.cfg` exactly and the output
  directory must exist.
- Output: executable + `.pck` (or embedded), or `.zip` for some targets. DLC/mods: extra PCK via
  `ProjectSettings.load_resource_pack()`.
- Encryption of PCK needs custom-compiled templates with the key *(standard templates can't decrypt)*.
- Feature tags: `OS.has_feature("web")`, `"mobile"`, `"dedicated_server"`, custom tags per preset.
- Platform notes: Android needs Android SDK/JDK and a keystore (4.7 has a stable on-device build environment); iOS export
  needs macOS + Xcode; web uses Compatibility renderer and needs cross-origin isolation headers only when using threads
  (4.3+ can export single-threaded web builds).
- Testing: Godot has no built-in game test runner for projects; community GUT or GdUnit4 run headless in CI
  (`godot --headless -s addons/gut/gut_cmdln.gd`) *(third-party)*.
- `@tool` scripts and plugins execute when the project is opened — only open trusted projects.

Sources: https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html ·
https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html ·
https://docs.godotengine.org/en/stable/tutorials/export/feature_tags.html ·
https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html ·
https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

---

## 17. Common bugs and fixes

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | `Node not found: "Player/Sprite"` / `$X` is null | Wrong path, or accessed before the node is in the tree (in `_init`), or the node was renamed | Use `@onready`, scene-unique `%Name`, or `@export var x: Node`; check the path in the Remote scene tree. |
| 2 | `Invalid access to property or key 'x' on a base object of type 'null instance'` | A reference is null (failed `get_node`, missing export assignment) | Assign the export in the inspector; guard with `if node:`; fix path. |
| 3 | `Attempt to call function ... in base 'previously freed'` | Holding a reference to a `queue_free`d node | `is_instance_valid()`, clear references on `tree_exiting`, disconnect signals. |
| 4 | `Signal 'x' is already connected` | `connect` called twice (e.g. in `_ready` of a re-added node) | Check `is_connected`, connect once, or use `CONNECT_ONE_SHOT`. |
| 5 | `yield` / `KinematicBody` / `export var` parse errors | Godot 3 code in Godot 4 | Apply the migration table (section 1.1). |
| 6 | Character doesn't move with `move_and_slide(velocity)` | Godot 4 `move_and_slide()` takes no arguments | Assign `velocity` then call `move_and_slide()`. |
| 7 | Character falls through floor / jitter | Moving with `position +=`, physics in `_process`, or no collision shape | Use `move_and_slide()` in `_physics_process`; add `CollisionShape3D`; enable physics interpolation. |
| 8 | `Area3D.body_entered` never fires | Area's mask does not include the body's layer, `monitoring` off, no shape, or body is not a PhysicsBody (e.g. GridMap/CSG without collision) | Fix layer/mask, enable monitoring, add shape. |
| 9 | Clicks don't reach buttons / `_unhandled_input` | A `Control` overlay with `mouse_filter = STOP` covers them | Set overlay `mouse_filter = IGNORE` (or PASS). |
| 10 | Changing one enemy's material/curve changes all | Shared `Resource` | `duplicate()` or `resource_local_to_scene = true`. |
| 11 | "Can't change this state while flushing queries" | Modifying physics objects inside a physics signal | `set_deferred` / `call_deferred`. |
| 12 | RPC: `The rpc node checksum failed` / `Invalid packet received. Requested node was not found` | Node paths or the RPC set differ between peers | Same scene structure and names on all peers, `add_child(node, true)`, declare every RPC on both sides. |
| 13 | RPC from client ignored | Function is `@rpc` with default `"authority"` mode and the caller isn't the authority | Use `@rpc("any_peer")` for client→server requests and validate `get_remote_sender_id()`. |
| 14 | Host player doesn't see own RPC effect | Default `call_remote` | Add `"call_local"`. |
| 15 | `MultiplayerSpawner` spawns nothing on clients | Scene not in spawnable list, wrong parent, spawned on client, spawner missing on clients | Add scene to the list, add as direct child of `spawn_path` on the server. |
| 16 | `MultiplayerSynchronizer` doesn't sync | Property not in replication config, wrong authority, visibility filter, node spawned without spawner | Configure properties; set authority identically on all peers; spawn through `MultiplayerSpawner`. |
| 17 | Save file not found after export | Saving to `res://` | Use `user://`. |
| 18 | `FileAccess.open` returns null | Folder missing / permission | `DirAccess.make_dir_recursive_absolute`, check `get_open_error()`. |
| 19 | `@tool` script modifies/erases scene in editor | Gameplay code runs in the editor | `if Engine.is_editor_hint(): return`. |
| 20 | Exported variable resets / not shown | Not `@export`, wrong type, or the scene instance overrides value | Check inspector override (revert arrow); type the export. |
| 21 | Pause menu frozen | Menu inherits pausable mode | `process_mode = PROCESS_MODE_WHEN_PAUSED`/`ALWAYS`. |
| 22 | C# signal not found / exports missing | Class not `partial`, delegate name lacks `EventHandler`, project not built | Fix declarations and rebuild. |
| 23 | C# project can't export to web | Not supported in Godot 4 | Use GDScript for web builds. |
| 24 | Shader stutter on first use | Pipeline compilation at runtime | 4.4+ ubershaders, shader baker on export, warm-up scene. |
| 25 | Different physics after upgrading to 4.6 or switching to Jolt | Jolt default/behaviour differences | Re-tune; or switch 3D engine back to GodotPhysics3D in settings. |
| 26 | Integer division gives 0 | `1 / 2` in int | Use floats. |
| 27 | `:=` "cannot infer type" | Value is Variant | Use explicit type. |
| 28 | Broken references after moving files outside the editor | `.uid` / paths not updated | Move files in the FileSystem dock; commit `.uid` files with their scripts. |

---

## 18. Roblox → Godot map

| Roblox | Godot | Notes |
|---|---|---|
| DataModel / `game` | `SceneTree` (`get_tree()`) | |
| Workspace | Current scene / root `Node3D` (`get_tree().current_scene`) | |
| Part | `MeshInstance3D` + `StaticBody3D`/`RigidBody3D` + `CollisionShape3D` | Visual and collision are separate nodes. |
| Model | A scene (`.tscn`) instanced with `instantiate()` | |
| `ReplicatedStorage` assets | `preload()`ed `PackedScene`s / resources | No automatic client/server split. |
| Script (server) / LocalScript (client) | One script, branch with `multiplayer.is_server()` / `is_multiplayer_authority()` | Same code runs on every peer. |
| ModuleScript | `class_name` script, static funcs, or an autoload | `preload("res://x.gd")` = `require`. |
| RemoteEvent | `@rpc("any_peer")` function + `rpc_id(1, ...)` | Validate sender with `get_remote_sender_id()`. |
| RemoteFunction | No direct equivalent | Request RPC + response RPC. |
| BindableEvent | `signal` | |
| Attributes / ValueObjects | `@export` vars, `set_meta`, `MultiplayerSynchronizer` for replication | |
| `CollectionService` tags | Groups | |
| `RunService.Heartbeat` / `Stepped` | `_process(delta)` / `_physics_process(delta)` | |
| `task.wait(t)` | `await get_tree().create_timer(t).timeout` | |
| `TweenService` | `create_tween()` | |
| Humanoid | `CharacterBody3D` + your own movement script + `AnimationTree` | No built-in health/walk logic. |
| `UserInputService` / `ContextActionService` | `Input` / Input Map actions / `_unhandled_input` | |
| ScreenGui | `CanvasLayer` + `Control`s | Anchors ≈ Scale, offsets ≈ Offset. |
| UIListLayout / UIGridLayout / UIPadding | `VBoxContainer` / `GridContainer` / `MarginContainer` | |
| DataStoreService | `user://` files locally; online saves need your own backend | No cloud persistence built in. |
| StreamingEnabled | Manual: visibility ranges, `MultiplayerSynchronizer` visibility, background loading | |
| Players service | `multiplayer.get_peers()`, `peer_connected` | Peer ID 1 = server. |
| Roblox hosting | You host: dedicated server export or listen server | Ports, NAT, matchmaking are your problem. |

Mindset differences: Godot has no implicit replication — nothing syncs unless you add an RPC, spawner or synchronizer.
There is no default character, no cloud data store and no hosted servers. In exchange you control the whole stack, can
read the engine source (MIT) and ship anywhere.

---

## 19. Sources

Official (checked 2026-10-13):
- https://godotengine.org/releases/4.7/
- https://godotengine.org/releases/4.6/
- https://godotengine.org/releases/4.5/
- https://godotengine.org/releases/4.4/
- https://godotengine.org/article/maintenance-release-godot-4-7-1/
- https://godotengine.org/article/multiplayer-in-godot-4-0-scene-replication/
- https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.html
- https://docs.godotengine.org/en/stable/getting_started/step_by_step/nodes_and_scenes.html
- https://docs.godotengine.org/en/stable/getting_started/step_by_step/signals.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/singletons_autoload.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/groups.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/overridable_functions.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/idle_and_physics_processing.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/static_typing.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_exports.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/index.html
- https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_signals.html
- https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html
- https://docs.godotengine.org/en/stable/tutorials/physics/physics_introduction.html
- https://docs.godotengine.org/en/stable/tutorials/physics/using_jolt_physics.html
- https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/index.html
- https://docs.godotengine.org/en/stable/tutorials/animation/animation_tree.html
- https://docs.godotengine.org/en/stable/classes/class_tween.html
- https://docs.godotengine.org/en/stable/tutorials/ui/size_and_anchors.html
- https://docs.godotengine.org/en/stable/classes/class_control.html
- https://docs.godotengine.org/en/stable/tutorials/inputs/inputevent.html
- https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html
- https://docs.godotengine.org/en/stable/classes/class_multiplayerspawner.html
- https://docs.godotengine.org/en/stable/classes/class_multiplayersynchronizer.html
- https://docs.godotengine.org/en/stable/tutorials/io/saving_games.html
- https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html
- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/classes/class_fileaccess.html
- https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/what_is_gdextension.html
- https://docs.godotengine.org/en/stable/tutorials/performance/index.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html
- https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html

Community (marked as such where used):
- https://github.com/derkork/godot-safe-resource-loader — scanner for embedded scripts in `.tres` (third-party; its
  author warns it is new).
