`collision_layer` is what an object *is*; `collision_mask` is what it *detects*. The Area3D only reports bodies whose layer is inside the area's mask. Your coin is on layer 3, but its `collision_mask` must include layer 1 (the player's layer), otherwise `body_entered` never fires.

Also check:
- `monitoring` is true on the Area3D (it is by default, but code or the inspector may have turned it off).
- The Area3D has a `CollisionShape3D` child with a shape resource assigned.
- The signal is connected to your handler.

Not run in Godot; verify by walking through the coin and printing in the handler.
