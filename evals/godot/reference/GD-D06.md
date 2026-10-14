1. A `Control` (your `ColorRect`) has `mouse_filter = MOUSE_FILTER_STOP` by default, so the full-screen overlay consumes every click before buttons or `_unhandled_input` see it. Set the overlay's `mouse_filter` to `MOUSE_FILTER_IGNORE` (Mouse > Filter: Ignore).

2. Resources such as materials are shared: every enemy instance points at the same material object. Make a per-instance copy with `material = material.duplicate()` in `_ready()`, or enable Local To Scene (`resource_local_to_scene`) on the material.

Not run in the editor; verify by clicking a button with the overlay visible.
