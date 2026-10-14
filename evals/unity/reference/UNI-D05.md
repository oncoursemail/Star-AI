Three separate Unity 6 changes:

1. Physics property rename. In Unity 6 the Rigidbody velocity property is `Rigidbody.linearVelocity` (drag became `linearDamping`, angular drag `angularDamping`). The old name is obsolete; replace `rb.velocity` with `rb.linearVelocity` or accept the API Updater.

2. Object lookup. `Object.FindObjectsOfType` is obsolete. Use `Object.FindObjectsByType<T>()` when you need all instances, `FindFirstObjectByType<T>()` when you need a stable first match, or `FindAnyObjectByType<T>()` when any instance will do (fastest). Pass `FindObjectsInactive.Include` if you need inactive objects. Better still, cache references instead of searching.

3. Input. The exception means Project Settings > Player > Active Input Handling is set to the Input System package only, so the legacy `UnityEngine.Input` class is disabled. Port the code to the Input System: create an `InputAction` (or use the project-wide actions asset) named Move bound to the keyboard and gamepad, and read `move.ReadValue<Vector2>()` each frame, or read `Keyboard.current` directly for quick tests. Also swap any `StandaloneInputModule` on the EventSystem for `InputSystemUIInputModule`. As a temporary bridge you can set Active Input Handling to Both.
