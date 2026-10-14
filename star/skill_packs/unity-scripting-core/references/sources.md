# Sources for unity-scripting-core

Checked against official Unity documentation (Unity 6.6 / 6000.6 manual and scripting reference, package docs) on 2026-10-13. The guidance is written in STAR's own words; Unity documentation is licensed CC BY-NC-ND, so no text is copied.

| Claim in the skill | Documentation page |
|---|---|
| Lifecycle order Awake, OnEnable, Start, FixedUpdate, Update, LateUpdate, OnDisable, OnDestroy | https://docs.unity3d.com/Manual/execution-order.html |
| Fields serialize when public or [SerializeField], not static/const/readonly; properties are not serialized, [field: SerializeField] serializes the backing field; [SerializeReference] for polymorphism and null | https://docs.unity3d.com/Manual/script-serialization-rules.html |
| Unity's == also checks the native object, so destroyed objects compare equal to null | https://docs.unity3d.com/ScriptReference/Object-operator_eq.html |
| linearVelocity is the Unity 6 property; prefer AddForce over setting it every step; no effect on kinematic bodies | https://docs.unity3d.com/ScriptReference/Rigidbody-linearVelocity.html |
| Interpolation smooths the fixed-step/frame mismatch; enable it on the main character; use the Rigidbody, not the Transform | https://docs.unity3d.com/ScriptReference/Rigidbody-interpolation.html |
| FindObjectsByType, FindFirstObjectByType, FindAnyObjectByType; sort-mode overloads obsolete in 6.6 | https://docs.unity3d.com/ScriptReference/Object.FindObjectsByType.html |
| Trigger events need one trigger collider and a Rigidbody or ArticulationBody on one of the objects | https://docs.unity3d.com/Manual/collider-interactions-other-events.html |
| Awaitable methods, pooling, await only once | https://docs.unity3d.com/Manual/async-awaitable-introduction.html |
| Enter Play Mode options and resetting statics without domain reload | https://docs.unity3d.com/Manual/configurable-enter-play-mode.html and https://docs.unity3d.com/Manual/domain-reloading.html |
| Input System package, actions workflow | https://docs.unity3d.com/Packages/com.unity.inputsystem@6.7/manual/index.html |
| uGUI vs UI Toolkit | https://docs.unity3d.com/Manual/UI-system-compare.html |

API names verified against the official reference on 2026-10-13: Rigidbody.linearVelocity, Rigidbody.interpolation, Physics.SyncTransforms, Object.FindObjectsByType, Object.FindFirstObjectByType, Object.FindAnyObjectByType, FindObjectsInactive, Awaitable.NextFrameAsync, Awaitable.WaitForSecondsAsync, Awaitable.FixedUpdateAsync, SerializeField, SerializeReference. Not re-fetched (long-standing names): DefaultExecutionOrder, FormerlySerializedAs, destroyCancellationToken, InputSystemUIInputModule, InputAction.WasPressedThisFrame, linearDamping, angularDamping.
