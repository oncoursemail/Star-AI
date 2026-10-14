---
name: unity-scripting-core
description: Unity 6 C# gameplay scripting: MonoBehaviour lifecycle, serialization, prefabs and ScriptableObjects, physics timing, Input System, UI, coroutines and Awaitable, null pitfalls. Use for writing or debugging Unity scripts.
---
# Unity 6 scripting core (C#, MonoBehaviour)
Ask the editor version first: Unity 6 renamed APIs that 2022.3 still uses.
- Lifecycle: Awake (own setup, cache GetComponent) -> OnEnable (subscribe) -> Start (cross-object links) -> FixedUpdate -> Update -> LateUpdate -> OnDisable (unsubscribe) -> OnDestroy. No order between scripts' Awake unless [DefaultExecutionOrder].
- Serialize with [SerializeField] private fields; properties are not saved (use [field: SerializeField]). Not static, const or readonly. Polymorphic or nullable data needs [SerializeReference]. Rename with [FormerlySerializedAs].
- ScriptableObject = shared data asset; play-mode edits persist in the editor, never use it as a save file. Edit prefabs in Prefab Mode or apply overrides.
- Destroyed objects compare == null, but ?. ?? and "is null" bypass that check: use `if (obj != null)` for anything deriving from UnityEngine.Object.
- Physics: forces, linearVelocity and MovePosition in FixedUpdate; read input in Update and latch it. Turn on Rigidbody.interpolation for the body the camera follows and move the camera in LateUpdate. Never move a Rigidbody via transform.position.
- Unity 6 names: Rigidbody.linearVelocity / linearDamping / angularDamping (velocity and drag are obsolete); FindObjectsByType, FindFirstObjectByType, FindAnyObjectByType (FindObjectsOfType is obsolete). Never call Find* per frame.
- OnTriggerEnter(Collider) needs one collider with Is Trigger and a Rigidbody (kinematic is fine) on one of the two objects, plus layers enabled in the collision matrix. 2D uses OnTriggerEnter2D.
- Input System: if Active Input Handling is the new package only, UnityEngine.Input throws InvalidOperationException. Use actions (InputAction.ReadValue, WasPressedThisFrame), enable them, and use InputSystemUIInputModule on the EventSystem.
- UI clicks need an EventSystem, a GraphicRaycaster on the Canvas, Raycast Target on the target and nothing covering it. UI Toolkit: UIDocument, query elements in OnEnable.
- Coroutines stop when the object is disabled. Awaitable (NextFrameAsync, WaitForSecondsAsync) is pooled: await each one once and pass destroyCancellationToken.
- Domain reload may be off: reset statics and static events on play mode entry.
- Roblox map: Heartbeat -> Update, Stepped -> FixedUpdate, Touched -> OnTriggerEnter/OnCollisionEnter, ModuleScript -> C# class in an asmdef, TweenService -> coroutine, Awaitable or a tween library.
