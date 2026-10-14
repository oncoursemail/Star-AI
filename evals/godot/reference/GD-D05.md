Two problems:

1. `res://` is read-only in an exported game, so the save fails there. Write to `user://` (for example `user://save.json`).
2. A `.tres` or `.res` file can embed a script, and loading it with `load()` or `ResourceLoader.load()` can run that code. A shared save is untrusted, so this is a code-execution risk.

Safer: store plain data. Build a Dictionary, write it with `FileAccess.open("user://save.json", FileAccess.WRITE)` and `store_string(JSON.stringify(data))`, read it back with `JSON.parse_string()`, and validate every field. `store_var`/`get_var` also work if you leave `allow_objects` false. Use `ConfigFile` for settings. Check `FileAccess.get_open_error()` when `open` returns null. Not run in Godot.
