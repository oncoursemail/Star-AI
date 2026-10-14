Those lines are Godot 3 syntax. Godot 4 renamed the class and changed the API:

- `KinematicBody` is now `CharacterBody3D`. It has a built-in `velocity` property: set `velocity`, then call `move_and_slide()` with no arguments. The up direction is the `up_direction` property, not an argument.
- `yield` is gone. Use `await get_tree().create_timer(0.5).timeout`.

```gdscript
extends CharacterBody3D
func _physics_process(delta: float) -> void:
    velocity.y -= 9.8 * delta
    move_and_slide()
```

I have not run this in the editor; open the script in Godot 4 and check that the parse errors are gone.
