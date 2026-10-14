# Sources for godot-migration-and-pitfalls

Checked against the official Godot documentation (stable = Godot 4.7) on 2026-10-13. The Godot documentation is CC BY 3.0
(class reference MIT); the guidance is written in STAR's own words. Deeper reference: docs/research/engines/godot.md.

| Claim in the skill | Documentation page |
|---|---|
| Godot 3 to 4 renames: await, Callable connect, annotations, CharacterBody, instantiate, FileAccess | https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.html |
| move_and_slide() takes no arguments and uses the velocity property | https://docs.godotengine.org/en/stable/classes/class_characterbody3d.html |
| _enter_tree / _ready order, queue_free, is_instance_valid | https://docs.godotengine.org/en/stable/tutorials/scripting/overridable_functions.html and https://docs.godotengine.org/en/stable/classes/class_node.html |
| _process versus _physics_process; physics interpolation | https://docs.godotengine.org/en/stable/tutorials/scripting/idle_and_physics_processing.html and https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/index.html |
| collision_layer versus collision_mask; Area3D monitoring | https://docs.godotengine.org/en/stable/tutorials/physics/physics_introduction.html |
| Resources are cached and shared; duplicate / local to scene | https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html |
| Control mouse_filter STOP / PASS / IGNORE | https://docs.godotengine.org/en/stable/classes/class_control.html |
| Static typing, typed collections, @tool and Engine.is_editor_hint | https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/static_typing.html and https://docs.godotengine.org/en/stable/tutorials/plugins/running_code_in_the_editor.html |
| C# partial classes, [Signal] EventHandler delegates, no web export, .NET 8 | https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/index.html and https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_signals.html |
| Jolt is the default for new 3D projects since 4.6; typed dictionaries 4.4; @abstract 4.5 | https://godotengine.org/releases/4.6/ , https://godotengine.org/releases/4.4/ , https://godotengine.org/releases/4.5/ |
| Groups, autoloads, signals (Roblox map) | https://docs.godotengine.org/en/stable/tutorials/scripting/groups.html , https://docs.godotengine.org/en/stable/tutorials/scripting/singletons_autoload.html , https://docs.godotengine.org/en/stable/getting_started/step_by_step/signals.html |

API names verified against the official reference on 2026-10-13: CharacterBody3D.velocity, CharacterBody3D.move_and_slide,
Node.queue_free, is_instance_valid, Object.set_deferred, CollisionObject3D.collision_layer, CollisionObject3D.collision_mask,
Area3D.monitoring, Resource.duplicate, Resource.resource_local_to_scene, Control.mouse_filter, Engine.is_editor_hint,
Node.is_multiplayer_authority, Node.create_tween, CanvasLayer.
No live Godot editor run is claimed.
