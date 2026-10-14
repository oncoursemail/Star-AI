---
name: godot-migration-and-pitfalls
description: Godot 4 syntax versus Godot 3, node lifecycle order, shared resources, collision layers and masks, C# rules and Roblox equivalents. Use when Godot 4 code fails after porting, a node or signal misbehaves, or a Roblox developer asks how something maps to Godot.
---
# Godot 4 essentials and the mistakes that break code
Assume current stable Godot 4 (4.7). Write Godot 4 syntax only.
- Godot 3 to 4: yield(x, "s") becomes await x.s; connect("s", self, "f") becomes s.connect(f); export/onready/tool become @export/@onready/@tool; KinematicBody becomes CharacterBody3D: set the built-in velocity property, then call move_and_slide() with no arguments; Spatial is Node3D; instance() is instantiate(); remote/master/puppet become @rpc; File/Directory become FileAccess/DirAccess.
- Order: _init (not in tree), _enter_tree (parent first), _ready (children first, once). Use @onready or %UniqueName, never get_node in _init. Free with queue_free(); check is_instance_valid() before using a node that may be gone.
- Physics in _physics_process, visuals in _process. Turn on physics interpolation against jitter. Inside body_entered or other physics callbacks change shapes with set_deferred.
- collision_layer is what a body is; collision_mask is what it detects. An Area3D sees a body only when the body's layer is in the area's mask, monitoring is on and it has a CollisionShape3D child.
- Loaded resources are shared: duplicate() or resource_local_to_scene before changing one instance's material or data.
- A Control with mouse_filter STOP eats clicks; overlays need MOUSE_FILTER_IGNORE.
- Type everything (var hp: int, -> void); := cannot infer from a Variant. Typed dictionaries need 4.4+, @abstract 4.5+. New 3D projects use Jolt since 4.6.
- @tool scripts run in the editor: guard with Engine.is_editor_hint().
- C#: partial classes, [Export], [Signal] delegates named ...EventHandler, .NET 8+; C# cannot export to the web.
- Roblox map: Script and LocalScript become one script that checks is_multiplayer_authority(); ModuleScript is a class_name script or autoload; BindableEvent is a signal; CollectionService tags are groups; TweenService is create_tween(); Heartbeat is _process; Humanoid is CharacterBody3D plus your own movement; ScreenGui is CanvasLayer with Controls; anchors are Scale, offsets are Offset.
- Say which Godot version an answer assumes; never claim it ran in the editor.
