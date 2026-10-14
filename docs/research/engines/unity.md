# Unity engine reference for STAR (checked 2026-10-13)

Scope: Unity 6 (editor versions `6000.x`) as it stands in October 2026, written for a coding assistant whose home turf is
Roblox/Luau. Everything is paraphrased in STAR's own words; Unity's documentation is licensed CC BY-NC-ND, so no doc
text is copied. Short API names are quoted because they are facts, not prose. Anything that could not be confirmed
against an official page on 2026-10-13 is marked **(unverified)**.

How to read this file: each section ends with the official pages it was checked against. The concept map from
Roblox is in section 17; the list of common bugs is in section 16.

---

## 1. Versions and release cadence (as of October 2026)

Unity switched from year-named releases (2021.3, 2022.3, 2023.x) to **Unity 6** in 2024. Internally every Unity 6
editor is numbered `6000.<minor>.<patch>`, so Unity 6.3 is `6000.3.x`, Unity 6.6 is `6000.6.x`.

The cadence since 2025:

- **LTS (Long Term Support)** releases get about two years of fixes (an extra year for Enterprise/Industry).
  - Unity 6.0 LTS (`6000.0`, Oct 2024). Its support ends around October 2026 (per Unity's regional release page).
  - Unity 6.3 LTS (`6000.3`, announced 4 Dec 2025). Unity's release page lists support until December 2027. This is
    the safest pick for a project shipping in the next year.
- **Supported Update** releases between LTS versions ship new features and are supported until the next one
  replaces them:
  - Unity 6.4 (shipped around March 2026, date from a third-party roadmap: **(unverified)** exact date).
  - Unity 6.5 (beta June 2026, release thread dated August 2026).
  - Unity 6.6 (release thread dated 3 Sep 2026). The online Scripting Reference and Manual currently default to
    6000.6, so the API pages cited below were read in their 6.6 form.
- **Unity 6.7 LTS** is expected in Q4 2026 (reported by press, **(unverified)**). The Manual already says the
  Built-in Render Pipeline will stay supported through the 6.7 LTS lifecycle, which confirms 6.7 is the next LTS.
- **Unity 7**: a public alpha thread ("Unity 7.0 Alpha is now available") was posted in early October 2026, and
  unity.com/releases/unity-7 says "coming early 2027". Headline change is the move to the **CoreCLR** runtime. Unity
  says Unity 6 projects should upgrade without a rewrite, but obsolete APIs become errors as usual.

Package versions that the docs' `@latest` redirects pointed to on 2026-10-13:

| Package | Name | Latest docs version |
|---|---|---|
| Universal Render Pipeline | `com.unity.render-pipelines.universal` | 17.7 |
| Entities (ECS) | `com.unity.entities` | 6.7 (now versioned in step with the editor) |
| Netcode for GameObjects | `com.unity.netcode.gameobjects` | 3.1 |
| Netcode for Entities | `com.unity.netcode` | 7.1 |
| Input System | `com.unity.inputsystem` | 6.7 |
| Addressables | `com.unity.addressables` | 4.1 |
| Burst | `com.unity.burst` | 1.8 |
| Unity Test Framework | `com.unity.test-framework` | 1.9 |

Rules of thumb for STAR:

- Ask which editor version the user runs before naming APIs; 2022.3 projects still exist and lack `Awaitable`,
  `linearVelocity`, Build Profiles and Render Graph.
- Package versions are pinned per project in `Packages/manifest.json`; the latest docs are not necessarily what the
  user has. The package version picker on docs.unity3d.com shows older manuals.
- "Unity 6" alone is ambiguous: 6.0 LTS and 6.3 LTS differ (Render Graph default, Build Profiles maturity, Box2D v3 in
  6.3 for 2D, the Built-in RP deprecation notice in later 6.x).

Sources: https://unity.com/releases/unity-6-releases, https://unity.com/blog/unity-6-3-lts-is-now-available,
https://unity.com/en/releases/unity-7, https://discussions.unity.com/t/unity-7-0-alpha-is-now-available/1738310,
https://docs.unity.com/en-us/engine/6000.6/manual

---

## 2. Architecture, the player loop and the MonoBehaviour lifecycle

### 2.1 Objects

- A **Scene** holds a hierarchy of **GameObjects**. A GameObject is only a container: a name, a tag, a layer, an
  active flag and a list of **Components**. Every GameObject has exactly one `Transform` (or `RectTransform` in UI).
- Behaviour comes from components. Your scripts are classes deriving from `MonoBehaviour` attached to GameObjects.
- Assets (meshes, materials, prefabs, ScriptableObjects, audio) live in the project, not in the scene. Scenes
  reference them.
- `UnityEngine.Object` is the base for everything Unity owns (GameObject, Component, assets). Each has a native C++
  half and a managed C# wrapper. This split causes the "fake null" behaviour (section 4.4).

### 2.2 Lifecycle order (single MonoBehaviour)

When a scene loads or an object is instantiated, then each frame, Unity calls these message methods if they exist
(they are found by name, not through an interface or override):

1. `Awake()` once, when the script instance is loaded, even if the component is disabled (but only if the
   GameObject is active). Use it to set up the object's own state and cache its own components.
2. `OnEnable()` each time the component becomes enabled and active. Subscribe to events here.
3. `Start()` once, before the first `Update` of that script, only if it is enabled. Use it for setup that needs
   other objects' `Awake` to have run.
4. `FixedUpdate()` zero, one or several times per frame, on the fixed physics timestep (default 0.02 s, set in
   Project Settings > Time). Physics forces and Rigidbody moves belong here.
5. Internal physics step, then trigger/collision callbacks (`OnTriggerEnter`, `OnCollisionEnter`, ...).
6. `Update()` once per frame. Input reading, gameplay timers, non-physics movement.
7. Coroutines resume after `Update` (`yield return null`) and Animation/Animator update.
8. `LateUpdate()` once per frame after all `Update` calls. Cameras that follow something go here.
9. Rendering, then `yield return new WaitForEndOfFrame()` continuations.
10. `OnDisable()` when disabled or before destroy. Unsubscribe here.
11. `OnDestroy()` when the object is destroyed or the scene unloads.
12. `OnApplicationQuit()` before the app quits (not reliable on mobile, where the OS may kill the process; use
    `OnApplicationPause(true)` to save there).

Important details:

- `Awake` of all objects in a freshly loaded scene runs before any `Start`, but there is **no guaranteed order between
  two different scripts' `Awake`** unless you set it.
- An object instantiated at runtime gets `Awake` and `OnEnable` immediately inside the `Instantiate` call; `Start`
  waits until just before its first `Update`.
- `Destroy(obj)` is deferred to the end of the current frame; the object still exists until then (but compares equal to
  null after the frame). `DestroyImmediate` is for editor code only.
- Disabled components still receive `Awake` (if the GameObject is active) but not `Update`. Collision and trigger
  messages are also delivered to disabled MonoBehaviours so they can re-enable themselves **(unverified)** in 6.6.

### 2.3 Script execution order

- Project Settings > Script Execution Order lets you set an integer order per script; lower runs first for each event.
- The attribute `[DefaultExecutionOrder(-100)]` does the same in code and is easier to keep in version control.
- Prefer designing so order does not matter: own state in `Awake`, cross-object links in `Start`, or explicit
  initialisation from a bootstrap object.

### 2.4 The player loop

The low-level `UnityEngine.LowLevel.PlayerLoop` API exposes the ordered list of subsystems (Initialization,
EarlyUpdate, FixedUpdate, PreUpdate, Update, PreLateUpdate, PostLateUpdate). Libraries (UniTask, ECS) insert their own
systems there. Most game code never touches it.

### 2.5 Domain reload and Enter Play Mode options

- C# code lives in a .NET "domain". Recompiling or entering Play mode with **domain reload** throws away all static
  state, which is slow in large projects.
- Project Settings > Editor > Enter Play Mode Settings offers: reload domain and scene, reload scene only, reload
  domain only, or neither. The 6.6 Manual lists "Reload Scene only" (domain reload off) as the default, and Unity 6.6
  enables fast Enter Play Mode by default for new projects. Unity frames this as preparation for CoreCLR, which has no
  domain reload concept.
- With domain reload off, **static fields and static event subscriptions survive between Play sessions**. Bugs that
  look like "my singleton is already set" or "event fires twice on second play" come from this.
- Fixes:
  - Classic: a static method with `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]`
    that resets statics.
  - Unity 6.6 Manual: `[OnEnteringPlayMode]` / `[OnExitingPlayMode]` reset methods and `[AutoStaticsCleanup]` on a
    field of a `partial` type (with `[NoAutoStaticsCleanup]` to opt out). Static constructors do **not** re-run.
- Always unsubscribe static events in `OnDisable`/`OnDestroy`.

Sources: https://docs.unity3d.com/Manual/execution-order.html (unverified fetch, standard page),
https://docs.unity3d.com/Manual/configurable-enter-play-mode.html, https://docs.unity3d.com/Manual/domain-reloading.html

---

## 3. Project layout and version control

### 3.1 Folders

| Folder | What it is | In git? |
|---|---|---|
| `Assets/` | All your content and scripts. Every file and folder has a sibling `.meta` file. | Yes, with `.meta` |
| `Packages/` | `manifest.json` (dependencies) and `packages-lock.json`; embedded/local packages as subfolders. | Yes |
| `ProjectSettings/` | All project settings as YAML assets (`ProjectSettings.asset`, `TagManager.asset`, `DynamicsManager.asset`...). | Yes |
| `UserSettings/` | Per-user editor settings. | No |
| `Library/` | Import cache, compiled assemblies, artifact database. Rebuilt automatically. | **No** |
| `Temp/`, `Obj/`, `Logs/`, `Build/`, `Builds/` | Transient output. | No |
| `*.csproj`, `*.sln` | Generated by the IDE integration package. | No |

### 3.2 `.meta` files and GUIDs

- Each asset's `.meta` file holds a **GUID** and import settings. Scenes and prefabs reference other assets by GUID +
  file ID, not by path.
- If you move or rename files outside the Editor and lose or regenerate the `.meta`, every reference to that asset
  breaks (missing scripts, pink materials). Move files inside the Editor, or move the `.meta` with the file.
- Committing an asset without its `.meta` (or vice versa) is the most common team bug. Treat them as one unit.

### 3.3 Serialization mode and merging

- Project Settings > Editor > Asset Serialization Mode should be **Force Text** (the default in modern versions), so
  scenes and prefabs are YAML and can be diffed.
- Version Control mode: "Visible Meta Files".
- Unity ships **UnityYAMLMerge** ("Smart Merge") in the editor install folder (`Editor/Data/Tools`); configure it as the
  merge tool for `.unity`, `.prefab` and `.asset` files in git. It understands the YAML object structure.
- Large binary files (textures, audio, FBX) should go through Git LFS. Unity Version Control (formerly Plastic SCM) is
  Unity's own option and handles large binaries and locking.
- Reduce conflicts: split scenes into prefabs and additive scenes so two people rarely edit the same file.

### 3.4 Assembly definitions (`.asmdef`)

- Without asmdefs, all runtime scripts compile into `Assembly-CSharp.dll` and editor scripts into
  `Assembly-CSharp-Editor.dll`; any change recompiles everything.
- An `.asmdef` file in a folder makes that folder (and subfolders) its own assembly. Benefits: faster iteration,
  enforced dependency direction, test assemblies.
- References are explicit: assembly A can use B only if A's asmdef lists B. Cycles are not allowed.
- Editor-only code goes in an asmdef with only the Editor platform enabled, or in a folder named `Editor`.
- Test assemblies reference `UnityEngine.TestRunner` and `UnityEditor.TestRunner` and the NUnit precompiled reference.
- "Auto Referenced" off on a library asmdef keeps `Assembly-CSharp` from seeing it unless asked.

### 3.5 Packages

- Add via Package Manager window or edit `Packages/manifest.json` (`"com.unity.inputsystem": "<version>"`). Git URLs and
  scoped registries (OpenUPM) are allowed.
- Some packages are "core" and ship with the editor version; their version moves with the editor.

Sources: https://docs.unity3d.com/Manual/SpecialFolders.html, https://docs.unity3d.com/Manual/SmartMerge.html,
https://docs.unity3d.com/Manual/ScriptCompilationAssemblyDefinitionFiles.html (standard Manual pages; contents
summarised from long-standing documentation, not re-fetched on 2026-10-13: **(unverified)** for exact wording)

---

## 4. Scripting idioms and pitfalls

### 4.1 Serialization rules (what shows in the Inspector and gets saved)

Checked against the Unity 6.6 Manual:

- A field is serialized when it is `public` or has `[SerializeField]`, and is not `static`, `const` or `readonly`.
- Supported types: primitives, enums (up to 32-bit), Unity types (`Vector3`, `Color`, `AnimationCurve`...),
  `[Serializable]` plain classes and structs, references to `UnityEngine.Object` (assets, components, GameObjects),
  and arrays / `List<T>` of these.
- **Properties are not serialized.** Use `[field: SerializeField]` on an auto-property to serialize its backing field.
- Multidimensional arrays, jagged arrays and lists of lists are not supported: wrap the inner list in a
  `[Serializable]` class.
- The 6.6 Manual states `Dictionary<TKey,TValue>` is serialized when marked `[SerializeField]`. This is new; in older
  versions (6.3 and before) dictionaries were not serialized and people used two lists or
  `ISerializationCallbackReceiver`. Check the user's version before relying on it.
- Plain `[Serializable]` classes are stored **inline by value**: no null (you get a default instance), no shared
  references, no polymorphism (a field of type `Weapon` holding a `Sword` saves only `Weapon` fields).
- `[SerializeReference]` stores managed references: null, shared references, polymorphism and cycles. Reference types
  only.
- Inline nesting depth: indirect cycles stop after 10 levels with a warning.
- Prefer `[SerializeField] private` over `public` for inspector fields: keeps encapsulation.
- Renaming a serialized field loses saved values; add `[FormerlySerializedAs("oldName")]` to migrate.
- `[NonSerialized]` hides a public field from serialization; `[HideInInspector]` keeps it serialized but hidden.
- Unity calls the default constructor and field initializers during deserialization, often off the main thread:
  never call Unity APIs in constructors or field initializers of MonoBehaviours.

### 4.2 ScriptableObject

- A `ScriptableObject` is a data asset (create via `[CreateAssetMenu]`). Use it for item definitions, tuning
  tables, shared config, enemy stats. Many prefabs referencing one SO share one copy of the data in memory.
- Changes made to a ScriptableObject in Play mode **persist in the Editor** (the asset is modified), but in a build
  they reset on restart. Do not use SOs as save files.
- Runtime instances: `ScriptableObject.CreateInstance<T>()`.

### 4.3 Prefabs and variants

- A **prefab** is a saved GameObject hierarchy asset. Instances in scenes keep a link and store only **overrides**.
- **Nested prefabs**: a prefab can contain prefab instances.
- **Prefab variants** inherit from a base prefab and add overrides (e.g. `Enemy` -> `Enemy_Fast`).
- Editing an instance in a scene changes only that instance until you use Overrides > Apply. Edit the asset in Prefab
  Mode (double click) to change all instances.
- In editor scripts, after changing a prefab or scene object, call `EditorUtility.SetDirty` / use `Undo.RecordObject`
  and `PrefabUtility.RecordPrefabInstancePropertyModifications`, otherwise changes are not saved.
- `Instantiate(prefab, position, rotation, parent)` clones at runtime. Unity 6 also has `InstantiateAsync`
  (since 2022.3.20 / Unity 6) for spreading large instantiations over frames.

### 4.4 Null checks and "fake null"

- `UnityEngine.Object` overrides `==` so that a destroyed object (native side gone) compares equal to `null`, even
  though the C# reference is not null. The 6.6 Scripting Reference describes `==` as also checking the native pointer.
- C#'s `?.`, `??`, `??=` and `is null` / pattern matching **do not use that overload**. They check the raw C#
  reference, so `destroyedThing?.DoStuff()` still calls into a dead object and throws `MissingReferenceException`.
  Rider and the Unity analyzers warn about this (UNT0007/UNT0008 **(unverified)** rule IDs).
- Rule: for anything deriving from `UnityEngine.Object`, use `if (thing != null)` or `if (thing)` (implicit bool),
  never `?.` or `??`.
- `MissingReferenceException` = you kept a reference to an object after `Destroy`. `UnassignedReferenceException` =
  a serialized field was never assigned in the Inspector. `NullReferenceException` = a plain C# null.

### 4.5 Coroutines vs async/await vs Awaitable

- **Coroutines**: `IEnumerator` methods started with `StartCoroutine`. They yield `null` (next frame),
  `new WaitForSeconds(t)`, `new WaitForFixedUpdate()`, `new WaitUntil(...)`, `AsyncOperation`. They stop when the
  GameObject is deactivated or destroyed, or via `StopCoroutine`. They cannot return values and allocate for many
  yield instructions (cache `WaitForSeconds` instances).
- **Awaitable** (Unity 2023.1+ / Unity 6): `async Awaitable` methods with `await Awaitable.NextFrameAsync()`,
  `WaitForSecondsAsync`, `FixedUpdateAsync`, `EndOfFrameAsync`, and thread hopping `BackgroundThreadAsync()` /
  `MainThreadAsync()`. Instances are pooled, so they allocate little, but **each Awaitable may be awaited only once**.
  `AsyncOperation` subclasses (scene loads, asset bundle loads) can be awaited directly.
- Awaitables do **not** stop automatically when the object is destroyed. Pass `destroyCancellationToken` (a
  MonoBehaviour property since 2022.2) to the wait calls and handle `OperationCanceledException`. Application-wide:
  `Application.exitCancellationToken`.
- `System.Threading.Tasks.Task` works too but allocates each call and resumes via the synchronization context
  (Unity's runs on the main thread). Use Task when you need several awaiters or `WhenAll`.
- Never touch most Unity APIs (Transform, GameObject, Instantiate) from a background thread.
- `async void` swallows nothing: exceptions go to the console but the caller cannot catch them. Prefer
  `async Awaitable` and await it.

### 4.6 Events

- C# `event Action<T>` for code-to-code; `UnityEvent` for inspector-wired callbacks (slower, but designers can bind).
- Subscribe in `OnEnable`, unsubscribe in `OnDisable`, or you leak delegates holding destroyed objects (the handler
  then throws `MissingReferenceException`).
- ScriptableObject "event channels" are a common pattern for decoupled messaging.

### 4.7 `GetComponent` and caching

- `GetComponent<T>()` is a lookup on the GameObject; cheap but not free. Cache results in `Awake` into
  `[SerializeField]` or private fields rather than calling it every `Update`.
- `TryGetComponent(out T c)` avoids an editor-only allocation when the component is missing.
- `[RequireComponent(typeof(Rigidbody))]` makes Unity add the dependency automatically.
- `GetComponentInChildren` / `InParent` search the hierarchy; cost grows with size.

### 4.8 `Find*` cost

- `GameObject.Find(name)` and `FindWithTag` scan the scene. Never call them per frame.
- `FindObjectOfType` / `FindObjectsOfType` are obsolete in Unity 6. Use `FindObjectsByType<T>()`,
  `FindFirstObjectByType<T>()` or `FindAnyObjectByType<T>()` (the last is fastest when any instance will do).
- In 6.6 the overloads that take `FindObjectsSortMode` are themselves marked obsolete (the InstanceID sort order cannot
  be kept); use the overloads with only `FindObjectsInactive`.
- Better: register instances in a static list in `OnEnable`/`OnDisable`, or pass references explicitly.

### 4.9 Other idioms

- `Time.deltaTime` in `Update`, `Time.fixedDeltaTime` in `FixedUpdate` (reading `Time.deltaTime` inside `FixedUpdate`
  returns the fixed step anyway).
- Compare tags with `CompareTag("Enemy")`, not `tag == "Enemy"` (no allocation).
- `transform.position` writes are relatively expensive when the object has many children; batch them.
- Singletons: `static Instance` set in `Awake`, destroy duplicates, `DontDestroyOnLoad` for persistent managers. Reset
  the static when domain reload is off.

Sources: https://docs.unity3d.com/Manual/script-serialization-rules.html,
https://docs.unity3d.com/ScriptReference/Object-operator_eq.html,
https://docs.unity3d.com/Manual/async-awaitable-introduction.html,
https://docs.unity3d.com/ScriptReference/Object.FindObjectsByType.html

---

## 5. Rendering

### 5.1 Pipelines

| Pipeline | Status in Unity 6.6 | Use for |
|---|---|---|
| **URP** (Universal) | Default for new projects, actively developed (package 17.x). | Almost everything: mobile, console, PC, XR, WebGL, stylised and mid-high realism. |
| **HDRP** (High Definition) | Supported; for high-end PC/console. The 6.6 Manual pipeline overview does not call it deprecated. Unity 7 marketing describes a "single renderer" goal **(unverified)** what that means for HDRP. | Photoreal, physically based lighting on high-end hardware only. |
| **Built-in RP** | **Deprecated**: the 6.6 Manual says it will become obsolete in a future release, supported (fixes) through the 6.7 LTS lifecycle. | Legacy projects only; migrate to URP. |

Shaders are not portable between pipelines: Built-in surface shaders do not work in URP/HDRP. Use Shader Graph or
URP's HLSL templates. Materials need conversion (Render Pipeline Converter in URP).

### 5.2 SRP Batcher

- In URP/HDRP the **SRP Batcher** reduces CPU cost of draw calls by keeping per-material data in persistent GPU
  buffers. It batches by shader variant, not by material, so many materials using the same shader are cheap.
- A shader is compatible when its per-material properties live in a `UnityPerMaterial` CBUFFER. Shader Graph and URP
  Lit are compatible. `MaterialPropertyBlock` breaks SRP Batcher compatibility for that renderer.
- Check in the Frame Debugger ("SRP Batch" entries) or the shader's Inspector.

### 5.3 GPU Resident Drawer (Unity 6)

- Draws GameObjects through the `BatchRendererGroup` API with GPU instancing, cutting CPU time for big scenes of
  repeated meshes.
- Requirements from the 6.6 URP Manual: Forward+ or Deferred+ rendering path, compute shader support (not OpenGL ES),
  SRP Batcher on, Graphics settings "BatchRendererGroup Variants" set to Keep All, GPU Resident Drawer set to
  Instanced Drawing on the URP asset. Objects with `MaterialPropertyBlock`, `OnBecameVisible`/`OnWillRenderObject`
  scripts, or under an Animator fall back to normal drawing.
- Comes with GPU occlusion culling. Build time increases because more shader variants are compiled.

### 5.4 Render Graph

- URP 17 (Unity 6) moved custom passes to the **Render Graph** API: a `ScriptableRenderPass` declares its resources
  and work in `RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)` using builders such as
  `AddRasterRenderPass`. The graph culls unused passes and merges passes for tile-based GPUs.
- Old `Execute`-based passes ran in "Compatibility Mode" in 6.0; that mode was deprecated, and later 6.x versions
  removed or hid it **(unverified)** exact version. New code should target Render Graph only.
- The Render Graph Viewer window shows passes and resource lifetimes.

### 5.5 Shader Graph, VFX Graph

- Shader Graph: node-based shaders for URP/HDRP. Sub Graphs for reuse; Custom Function node for HLSL.
- VFX Graph: GPU particles (compute), needs compute support. The older Particle System (Shuriken) is CPU-based and
  works everywhere.

### 5.6 Lighting

- Realtime lights cost per pixel; URP Forward+ removes the per-object light limit.
- **Baked** lighting (Progressive Lightmapper) stores indirect light in lightmaps for static objects; mark static
  geometry "Contribute GI". Dynamic objects get indirect light from **Light Probes** or **Adaptive Probe Volumes**
  (APV, URP/HDRP in Unity 6).
- Mixed lights: baked indirect plus realtime direct.
- Enlighten realtime GI is legacy and blocks the GPU Resident Drawer.
- Reflection Probes for reflections; Screen Space options in HDRP.

### 5.7 LOD and culling

- `LODGroup` swaps meshes by screen size; last level can cull. Mesh LOD (automatic LOD generation) was added in
  Unity 6.2 **(unverified)**.
- Occlusion Culling (baked Umbra) for static scenes; GPU occlusion culling with the GPU Resident Drawer.
- Camera far clip and layer cull distances reduce work.

Sources: https://docs.unity3d.com/Manual/render-pipelines-overview.html,
https://docs.unity3d.com/Manual/urp/gpu-resident-drawer.html, https://docs.unity3d.com/Manual/urp/render-graph.html,
https://docs.unity3d.com/Manual/SRPBatcher.html

---

## 6. Physics

### 6.1 Engines

- 3D physics: **NVIDIA PhysX** integration ("built-in 3D physics"). Components: `Rigidbody`, colliders
  (`BoxCollider`, `SphereCollider`, `CapsuleCollider`, `MeshCollider`), joints, `CharacterController`,
  `ArticulationBody` for robotics chains.
- 2D physics: Box2D (`Rigidbody2D`, `Collider2D`); Unity 6.3 integrated **Box2D v3** with a new low-level API.
  2D and 3D never interact.
- DOTS: **Unity Physics** (`com.unity.physics`, stateless, deterministic-friendly) and Havok Physics for Unity.

### 6.2 Rigidbody basics and Unity 6 renames

- Unity 6 renamed `Rigidbody.velocity` to **`linearVelocity`**, `drag` to **`linearDamping`**, `angularDrag` to
  **`angularDamping`**. The old names are obsolete (the API updater rewrites them). Same for `Rigidbody2D`.
- The 6.6 reference warns against setting `linearVelocity` every step; prefer `AddForce`, except for instant changes
  like a jump. Setting velocity on a **kinematic** body has no effect.
- **Dynamic** bodies are moved by forces (`AddForce`, `AddTorque`, `linearVelocity`). **Kinematic** bodies
  (`isKinematic = true`) are moved by you, via `Rigidbody.MovePosition` / `MoveRotation` in `FixedUpdate` so the
  physics engine sweeps them and pushes dynamic bodies.
- Setting `transform.position` on a Rigidbody object teleports it and skips interpolation and collision.
- Collision Detection mode: Discrete (default), Continuous / Continuous Dynamic / Continuous Speculative for fast
  objects that tunnel through thin colliders.

### 6.3 FixedUpdate and interpolation (jitter)

- Physics simulates at fixed steps (Time > Fixed Timestep, 0.02 s default = 50 Hz); rendering runs at a variable rate.
  A frame can contain zero or several physics steps, so a Rigidbody rendered directly from its simulated pose
  stutters.
- Put forces and `MovePosition` in `FixedUpdate`. Read input in `Update` (input events are per frame), store it, and
  apply in `FixedUpdate`. One-shot inputs read in `FixedUpdate` can be missed or doubled.
- Set `Rigidbody.interpolation = RigidbodyInterpolation.Interpolate` (or `Extrapolate`) on the object the camera
  follows. The 6.6 docs recommend interpolation on the main character and not on everything else. With
  interpolation on, set position through the Rigidbody, not the Transform (or call `Physics.SyncTransforms`).
- Move the follow camera in `LateUpdate` (or let Cinemachine do it), reading the interpolated transform. A camera
  moved in `FixedUpdate` or a target moved in `Update` with a camera in `Update` causes the classic jitter.
- `Physics.simulationMode` (`SimulationMode.FixedUpdate` default, `Update`, `Script`) replaces the old
  `Physics.autoSimulation`.

### 6.4 Layers and the collision matrix

- 32 layers (Tags and Layers settings). Project Settings > Physics > Layer Collision Matrix says which layers can
  collide at all. A missing collision often is just an unchecked box.
- Raycasts take a `LayerMask`: `Physics.Raycast(origin, dir, out RaycastHit hit, maxDistance, layerMask)`. Use
  `LayerMask.GetMask("Ground")` or a serialized `LayerMask` field. A raycast starting inside a collider does not hit
  it.
- `QueryTriggerInteraction` decides whether queries hit triggers (default follows Physics settings).
- Non-allocating variants: `Physics.RaycastNonAlloc`, `OverlapSphereNonAlloc`, or the `RaycastCommand` batch job API.

### 6.5 Triggers vs collisions

- **Collision** events (`OnCollisionEnter/Stay/Exit(Collision)`): both colliders non-trigger and at least one dynamic
  Rigidbody involved.
- **Trigger** events (`OnTriggerEnter/Stay/Exit(Collider)`): at least one collider has **Is Trigger**, and at least one
  of the two objects has a **Rigidbody** (kinematic is fine) or ArticulationBody. Two static colliders never report
  anything.
- Method names and signatures must match exactly; `OnTriggerEnter(Collision c)` or `ontriggerenter` silently never
  runs. 2D needs `OnTriggerEnter2D(Collider2D)` and 2D components.
- Messages go to scripts on the GameObject with the collider and to the Rigidbody's GameObject (compound colliders).
- Layers must be allowed to interact in the collision matrix.

### 6.6 CharacterController

- A capsule mover without a Rigidbody. Call `Move(Vector3 motion)` (you apply gravity yourself) or `SimpleMove`
  (applies gravity, ignores Y). `isGrounded` is only valid after a `Move` that pushed down.
- Does not respond to forces; pushing rigidbodies needs `OnControllerColliderHit`.
- Setting `transform.position` while the controller is enabled may be overwritten; disable it, set, re-enable (or call
  `Physics.SyncTransforms`).
- Usually moved in `Update` (it is not simulated by the physics step).

### 6.7 DOTS physics

- Unity Physics works on entities: `PhysicsCollider`, `PhysicsVelocity`, `PhysicsMass` components, baked from
  regular Rigidbody/Collider authoring components in SubScenes. Queries go through `PhysicsWorldSingleton`
  (**(unverified)** exact naming in the 2026 package).

Sources: https://docs.unity3d.com/ScriptReference/Rigidbody-linearVelocity.html,
https://docs.unity3d.com/ScriptReference/Rigidbody-interpolation.html,
https://docs.unity3d.com/Manual/collider-interactions-other-events.html,
https://docs.unity3d.com/Manual/PhysicsSection.html

---

## 7. Animation

- **Mecanim**: an `Animator` component plays an **Animator Controller** asset (a state machine of animation clips).
  Script control is through parameters: `animator.SetFloat("Speed", v)`, `SetBool`, `SetTrigger`, `SetInteger`. Cache
  parameter hashes with `Animator.StringToHash("Speed")`.
- **States and transitions**: transitions have conditions, exit time and blend duration. "Has Exit Time" on by default
  makes transitions wait for the clip; turn it off for responsive input-driven transitions.
- **Layers** with avatar masks (upper body attack over lower body run), additive or override.
- **Blend trees**: 1D (speed) and 2D (directional movement) blending of clips by parameters.
- **Humanoid vs Generic** rigs: Humanoid uses an Avatar for retargeting between characters and IK; Generic keeps exact
  bone curves.
- **Root motion**: "Apply Root Motion" moves the GameObject from the animation's root curves. With a Rigidbody or
  CharacterController, implement `OnAnimatorMove()` and apply `animator.deltaPosition` yourself. Animator "Update Mode"
  can be "Animate Physics" so it runs in the physics step.
- **Animation events** call methods by name at clip times; **StateMachineBehaviour** scripts run on state enter/exit.
- **Animation Rigging** package: runtime constraints (Two Bone IK, Multi-Aim, damped transforms) on a Rig Builder.
- **Timeline**: sequenced cutscenes and scripted events (`PlayableDirector`), tracks for animation, audio,
  activation, Cinemachine shots, signals.
- The legacy `Animation` component still exists for simple cases.
- `Animator` makes objects ineligible for the GPU Resident Drawer; many animated characters use GPU skinning or
  baked vertex animation for crowds.

Sources: https://docs.unity3d.com/Manual/AnimationOverview.html,
https://docs.unity3d.com/Packages/com.unity.animation.rigging@latest/,
https://docs.unity3d.com/Packages/com.unity.timeline@latest/ (overview pages; specific wording **(unverified)**)

---

## 8. UI

### 8.1 Two systems

| | **UI Toolkit** | **uGUI** (Unity UI, Canvas) |
|---|---|---|
| Model | Retained-mode visual tree, web-like: UXML (structure), USS (styles), C# queries | GameObjects with `RectTransform` under a `Canvas` |
| Runtime entry | `UIDocument` component + Panel Settings asset | `Canvas` + `CanvasScaler` + `GraphicRaycaster` |
| Editor tooling | UI Builder; also the system for custom editors/inspectors | Scene view editing |
| Strengths | Menus, HUDs, data-heavy screens, styling, data binding (Unity 6 runtime binding) | World-space UI, particle/animation-heavy UI, mature ecosystem, TextMeshPro |
| Gaps | World-space UI support is newer (Unity 6.2+ **(unverified)**), custom shaders limited | Layout rebuild cost, harder theming |

Unity recommends UI Toolkit for new runtime UI where it has the features you need; uGUI is not deprecated.

### 8.2 uGUI essentials

- Every Canvas renders its children; any change to a child marks the whole Canvas dirty and rebuilds its batch. Split
  static and frequently changing UI into separate Canvases.
- **Canvas Scaler**: "Scale With Screen Size" with a reference resolution and Match width/height is the usual
  responsive setup (similar to Roblox Scale vs Offset thinking).
- **EventSystem**: exactly one per scene, with an input module. With the Input System package use
  `InputSystemUIInputModule`, not the old `StandaloneInputModule` (which uses the legacy Input class and errors when
  only the new system is active).
- Clicks need: an EventSystem, a `GraphicRaycaster` on the Canvas, the target `Image`/`Text` with **Raycast Target**
  on, and nothing invisible with Raycast Target on above it. A `CanvasGroup` with `blocksRaycasts = false` or
  `interactable = false` disables children.
- Turn off Raycast Target on decorative images and text: fewer raycasts.
- Text: TextMeshPro (`TMP_Text`, `TextMeshProUGUI`) is the standard; legacy `Text` is outdated. In Unity 6, TMP
  is merged into the uGUI package.
- World-space canvases need an Event Camera.

### 8.3 UI Toolkit essentials

- `var root = GetComponent<UIDocument>().rootVisualElement; var btn = root.Q<Button>("play"); btn.clicked += OnPlay;`
- Query after the document is enabled (in `OnEnable`), since the tree is rebuilt when the UIDocument is re-enabled.
- USS supports flexbox layout, classes, pseudo-states, transitions and variables.
- UI Toolkit has its own event system for runtime panels; it works with the Input System through the EventSystem when
  one exists.

Sources: https://docs.unity3d.com/Manual/UI-system-compare.html, https://docs.unity3d.com/Manual/UIElements.html,
https://docs.unity3d.com/Packages/com.unity.ugui@latest/ (summarised; **(unverified)** wording on world-space UI
Toolkit version)

---

## 9. Input System

- Package `com.unity.inputsystem` (docs latest 6.7). The 6.7 package page says the Unity 6.7 editor installs it by
  default for some templates. It replaces the legacy `UnityEngine.Input` / Input Manager.
- **Active Input Handling** (Project Settings > Player > Other Settings): "Input Manager (Old)", "Input System Package
  (New)" or "Both". If set to New only, any call to `Input.GetKey`, `Input.GetAxis`, `Input.mousePosition` or
  the legacy `StandaloneInputModule` throws `InvalidOperationException` saying you are using the Input class while
  the Input System is the active handler. Fix: port the code, swap the UI input module, or set "Both" temporarily.
- Direct device reads (quick, not rebindable): `Keyboard.current.spaceKey.wasPressedThisFrame`,
  `Mouse.current.position.ReadValue()`, `Gamepad.current?.leftStick.ReadValue()` (devices are plain C# objects, so
  `?.` is fine here).
- **Actions** are the recommended path:
  - An **Input Actions asset** (`.inputactions`) holds Action Maps ("Player", "UI"), Actions ("Move", "Jump") and
    Bindings per device, plus Control Schemes. Unity 6 projects get a project-wide actions asset (Project Settings >
    Input System Package).
  - Read in code: `InputAction move = InputSystem.actions.FindAction("Move");` then `move.ReadValue<Vector2>()` each
    frame, `jump.WasPressedThisFrame()`, or subscribe to `performed` / `started` / `canceled`. Actions must be
    enabled (`Enable()`); project-wide actions are enabled automatically.
  - **Generate C# Class** on the asset creates a typed wrapper (`var controls = new PlayerControls();
    controls.Player.Jump.performed += ...; controls.Enable();`). Dispose/disable it in `OnDisable`/`OnDestroy`.
  - **PlayerInput** component: binds an actions asset to a player, picks control scheme by device, and calls your
    code via Send Messages (`OnJump(InputValue v)`), Broadcast, UnityEvents, or C# events. `PlayerInputManager`
    handles local multiplayer joining.
- **Rebinding**: `action.PerformInteractiveRebinding().WithControlsExcluding("Mouse").OnComplete(op => op.Dispose())
  .Start()`; disable the action first. Save with `actions.SaveBindingOverridesAsJson()` and restore with
  `LoadBindingOverridesFromJson`.
- Value vs Button vs Pass-Through action types; interactions (Hold, Tap) and processors (deadzone, normalize).
- Read continuous values in `Update`; apply to physics in `FixedUpdate`. The Input System's update mode can be set to
  fixed update but per-frame is the norm.

Sources: https://docs.unity3d.com/Packages/com.unity.inputsystem@6.7/manual/index.html,
https://docs.unity3d.com/Packages/com.unity.inputsystem@latest/ (Actions, PlayerInput, rebinding pages: API names
from long-standing package docs; **(unverified)** that `InputSystem.actions` and project-wide actions are unchanged
in 6.7)

---

## 10. DOTS / ECS (Entities, Burst, Jobs)

### 10.1 Pieces

- **C# Job System**: schedule `IJob`, `IJobParallelFor`, `IJobFor` structs on worker threads; they work on
  `NativeArray<T>` / `NativeList<T>` and other unmanaged containers. Safety checks (editor) catch races. Always
  `Complete()` handles before reading results, and `Dispose()` native containers (or allocate with
  `Allocator.Temp`/`TempJob` and dispose in time).
- **Burst** (`com.unity.burst` 1.8): compiles a subset of C# ("High-Performance C#") to optimised native code via LLVM.
  Mark jobs and static methods `[BurstCompile]`. Constraints: no managed objects (classes, `string`, managed arrays,
  `List<T>`, delegates) in Burst code, only blittable/unmanaged structs, `Unity.Mathematics` types (`float3`,
  `quaternion`) preferred, exceptions only in a limited way (throwing is supported for checks but try/catch is not
  **(unverified)** current details), static readonly data allowed, no virtual calls on managed objects.
- **Entities** (`com.unity.entities`, docs latest 6.7): data-oriented ECS. Entities are IDs; data is components in
  chunks grouped by **archetype** (the set of component types).

### 10.2 Components

- `IComponentData` struct: unmanaged per-entity data (`struct Speed : IComponentData { public float Value; }`).
- `IBufferElementData`: dynamic buffers per entity. `ISharedComponentData`: groups chunks by value.
  `IEnableableComponent`: toggle without structural change. Tag components (empty structs). Managed
  `class : IComponentData` exists but is slow and not Burst-compatible.

### 10.3 Authoring and baking

- You edit normal GameObjects in a **SubScene**. A `MonoBehaviour` authoring component plus a
  `Baker<TAuthoring>` converts it to entity data at edit/build time:
  `class SpeedBaker : Baker<SpeedAuthoring> { public override void Bake(SpeedAuthoring a) { var e =
  GetEntity(TransformUsageFlags.Dynamic); AddComponent(e, new Speed { Value = a.speed }); } }`.
- SubScenes are streamed as entity data at runtime; GameObjects in them do not exist in the player.

### 10.4 Systems

- `partial struct MySystem : ISystem` with `OnCreate`, `OnUpdate(ref SystemState state)`, `OnDestroy`; mark
  `[BurstCompile]`. `SystemBase` (class) is the managed alternative.
- `SystemAPI.Query<RefRW<LocalTransform>, RefRO<Speed>>()` in a `foreach` for main-thread iteration;
  `SystemAPI.Time.DeltaTime`; `SystemAPI.GetSingleton<T>()`.
- Ordering with `[UpdateInGroup(typeof(SimulationSystemGroup))]`, `[UpdateBefore]`, `[UpdateAfter]`.
- `IJobEntity`: a `partial struct` with an `Execute(ref LocalTransform t, in Speed s)` method; source generators build
  the query. Schedule with `new MoveJob{...}.ScheduleParallel()` (state.Dependency is handled for you in ISystem).

### 10.5 Structural changes and EntityCommandBuffer

- A **structural change** is anything that moves entities between chunks: create/destroy entity, add/remove
  component, change shared component value, `Instantiate`. It invalidates iterators and must happen on the main
  thread through `EntityManager`, never inside a job or while iterating a query.
- Calling `EntityManager.DestroyEntity` or `AddComponent` inside an `IJobEntity` does not compile or throws; inside a
  `SystemAPI.Query` foreach it throws an invalid-operation error about structural changes during iteration.
- Fix: record commands in an **`EntityCommandBuffer`** and play them back later on the main thread:
  - Get a buffer from a built-in ECB system singleton:
    `var ecb = SystemAPI.GetSingleton<EndSimulationEntityCommandBufferSystem.Singleton>().CreateCommandBuffer(state.WorldUnmanaged);`
    The ECB system plays back and disposes it; do not play back or dispose it yourself.
  - Parallel jobs use `ecb.AsParallelWriter()` and pass a sort key (the `[ChunkIndexInQuery] int` parameter of
    `Execute`) to each command so playback is deterministic.
  - Or create `new EntityCommandBuffer(Allocator.Temp)`, record, then `ecb.Playback(state.EntityManager)` and
    `Dispose()` yourself.
- Entities created by an ECB get real data only at playback. Use one ECB per job.
- Prefer `IEnableableComponent` over add/remove for frequent toggles, since enabling is not structural.

### 10.6 Hybrid and when to use DOTS

- Use DOTS for many similar things (thousands of units, projectiles, simulation). Keep UI, audio, cameras and
  one-off gameplay in GameObjects. Rendering of entities via Entities Graphics (`com.unity.entities.graphics`).
- Unity has been bringing entities closer to GameObjects in Unity 6.x ("ECS for all" roadmap, Entities versions now
  numbered with the editor) **(unverified)** what has shipped beyond the version numbering.

Sources: https://docs.unity3d.com/Packages/com.unity.entities@6.7/manual/systems-entity-command-buffers.html,
https://docs.unity3d.com/Packages/com.unity.entities@6.7/manual/systems-entity-command-buffer-automatic-playback.html,
https://docs.unity3d.com/Packages/com.unity.burst@1.8/, https://docs.unity3d.com/Manual/job-system.html

---

## 11. Networking

### 11.1 The landscape

- **Netcode for GameObjects (NGO)**, `com.unity.netcode.gameobjects`, docs latest **3.1**. High-level networking for
  MonoBehaviour games: co-op, casual, small-to-mid player counts.
- **Netcode for Entities**, `com.unity.netcode`, docs latest **7.1**. Server-authoritative with client prediction,
  snapshot interpolation, lag compensation; built on Entities. For competitive/fast action and large counts.
- **Unity Transport** (`com.unity.transport`): the low-level UDP/WebSocket transport under both; `UnityTransport`
  component in NGO.
- **Multiplayer Services SDK** (package believed to be `com.unity.services.multiplayer` **(unverified)**): one API
  ("Sessions") that unifies Lobby, Matchmaker and Relay, replacing their separate SDKs. Relay connects players through
  Unity's servers without port forwarding; Lobby lists/joins rooms. Multiplay Hosting / dedicated servers are
  separate. Session method names such as `MultiplayerService.Instance.CreateSessionAsync` **(unverified)**.
- Third-party: Mirror, Fish-Networking, Photon Fusion/PUN, Normcore. Many users run these; ask which one.

### 11.2 NGO building blocks

- **`NetworkManager`**: one per session; holds the transport, the player prefab, the **Network Prefabs list** and
  settings. Start with `NetworkManager.Singleton.StartHost()`, `StartServer()` or `StartClient()`.
- **`NetworkObject`**: on the root of every networked prefab/scene object. Gives it a `NetworkObjectId`, an owner
  (`OwnerClientId`) and spawn state (`IsSpawned`).
- **`NetworkBehaviour`**: base class instead of `MonoBehaviour` for scripts that use RPCs or NetworkVariables.
  Properties: `IsServer`, `IsClient`, `IsHost`, `IsOwner`, `IsLocalPlayer`, `OwnerClientId`, `NetworkManager`.
  Override `OnNetworkSpawn()` / `OnNetworkDespawn()` for setup and teardown that depends on network state.
- Spawn order (3.1 docs): in-scene objects run `Awake`, `Start`, then `OnNetworkSpawn`; dynamically spawned objects
  run `Awake`, `OnNetworkSpawn`, then `Start`.

### 11.3 Spawning

- In client-server topology, **only the server/host spawns** (`Instantiate` the prefab, then
  `GetComponent<NetworkObject>().Spawn()`, or `NetworkManager.SpawnManager.InstantiateAndSpawn(...)`). A client
  calling `Spawn` fails.
- The prefab must be registered in the NetworkManager's Network Prefabs list (a `NetworkPrefabsList` asset);
  otherwise clients cannot create it and log an error about an unregistered prefab hash.
- `Despawn()` (authority only) destroys by default. Clients must never call `Destroy` on a spawned networked object.
- `SpawnWithOwnership(clientId)`, `ChangeOwnership(clientId)`, `RemoveOwnership()` are server calls in client-server.
- Pooling: implement `INetworkPrefabInstanceHandler` and register it with the NetworkManager's prefab handler.

### 11.4 NetworkVariable

- `NetworkVariable<T>` field on a NetworkBehaviour; synced from the writer to readers. Constructor
  `(T value = default, NetworkVariableReadPermission read = Everyone, NetworkVariableWritePermission write = Server)`.
- **Defaults: everyone reads, only the server writes.** `NetworkVariableWritePermission.Owner` lets the owning client
  write instead (and then the server cannot). There is no "Everyone" write permission.
- A client that writes a server-write variable gets an error (the change is rejected and logged, along the lines of
  "client is not allowed to write to this NetworkVariable" **(unverified)** exact message) and the value never
  replicates. Fix: send an RPC to the server and let the server validate and write.
- Initialise at declaration, in `Awake`, or while spawned; subscribe to `OnValueChanged` (`(T previous, T current)`) in
  `OnNetworkSpawn` and unsubscribe in `OnNetworkDespawn`.
- Supported types: unmanaged primitives, Unity math structs, enums, `INetworkSerializable`,
  `INetworkSerializeByMemcpy` structs, `FixedString32Bytes`...`FixedString4096Bytes`. **Not `string`** (use
  FixedString). `NetworkList<T>` for lists of structs. After mutating a collection inside a NetworkVariable call
  `CheckDirtyState()`.

### 11.5 RPCs

- NGO 1.8 introduced the universal **`[Rpc(SendTo.X)]`** attribute; `[ServerRpc]` and `[ClientRpc]` are legacy (still
  compiled for compatibility in the 1.8/2.x docs; 3.x status **(unverified)**).
- Method name **must end with `Rpc`** (`FireRpc`, `RequestDoorOpenRpc`), otherwise codegen errors.
- `SendTo` targets: `Server`, `NotServer`, `Owner`, `NotOwner`, `Me`, `NotMe`, `Everyone`, `ClientsAndHost`,
  `SpecifiedInParams` (plus runtime `RpcTarget.Single(id, RpcTargetUse.Temp)`, `RpcTarget.Group`, `RpcTarget.Not`).
- Attribute options: `Delivery = RpcDelivery.Reliable` (default) or `Unreliable`; `InvokePermission =
  RpcInvokePermission.Server | Owner | Everyone` (default Everyone in the 3.1 docs); `DeferLocal`;
  `AllowTargetOverride`. The legacy `ServerRpc(RequireOwnership = false)` maps to who may invoke.
- Add `RpcParams rpcParams = default` as the last parameter to read `rpcParams.Receive.SenderClientId` on the server.
  **Validate everything server-side** (the sender, ranges, cooldowns): RPC arguments come from untrusted clients.
- RPCs only work on a **spawned** NetworkObject. Calling one before `OnNetworkSpawn` (e.g. in `Awake`/`Start` of a
  dynamically spawned object, or on an object never spawned) fails with an error about the object not being spawned
  **(unverified)** exact wording. Call from `OnNetworkSpawn` or later.
- Reliable RPCs arrive in order relative to each other; NetworkVariable updates and RPCs are not ordered with each
  other.

### 11.6 Authority and transforms

- Default model is **server authoritative**: the server owns simulation; clients send intent via RPCs.
- **`NetworkTransform`** syncs position/rotation/scale; by default **server authority**. In 3.1 an **Authority Mode**
  setting (Server or Owner) selects owner-authoritative motion for player characters. Older projects used the sample
  `ClientNetworkTransform` (a subclass overriding `OnIsServerAuthoritative()` to return false); the 3.1 docs page
  does not mention it, so treat it as legacy **(unverified)** removal.
- If a non-authority moves a synced transform, the authoritative state overwrites it (the object snaps back). That is
  the usual "my player teleports back" bug: you moved it on the client while NetworkTransform is server authority.
- `NetworkRigidbody` makes the Rigidbody kinematic on non-authorities.
- NetworkTransform interpolation is on by default; options Legacy lerp, Lerp, Smooth dampening.
- **Distributed authority** topology (NGO 2.x+): no host; each client is authority for objects it owns; a "session
  owner" client handles scene management and late joiners (`NetworkManager.IsSessionOwner`); ownership status
  `Distributable`, `SessionOwner`, `None` on NetworkObject. Runs through Unity's distributed authority service
  (Multiplayer Services, free tier). Not suited to competitive games: clients are trusted more and there is no single
  physics simulation.

### 11.7 Scene management

- With `NetworkManager.SceneManager` (Enable Scene Management on), the server loads scenes for everyone:
  `NetworkManager.SceneManager.LoadScene("Arena", LoadSceneMode.Single)`. Do not call `SceneManager.LoadScene` on
  clients in a networked session. Listen to `OnSceneEvent` / `OnLoadEventCompleted`.
- In-scene NetworkObjects are matched by a GlobalObjectIdHash; duplicating them in ways that break the hash causes
  sync errors.

### 11.8 Netcode for Entities (brief)

- Ghosts (`GhostAuthoringComponent`) replicate entities; `[GhostField]` marks replicated fields; client-side
  prediction in `PredictedSimulationSystemGroup`; input via `IInputComponentData`; RPCs via `IRpcCommand`. Client and
  server worlds run in one editor process (thin clients for testing). Use when tick-based prediction matters.
  (Names from long-standing docs; **(unverified)** against 7.1.)

Sources: https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/advanced-topics/message-system/rpc.html,
https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/basics/networkvariable.html,
https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/basics/object-spawning.html,
https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/components/helper/networktransform.html,
https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/terms-concepts/distributed-authority.html,
https://docs.unity.com/ugs/en-us/manual/mps-sdk/manual, https://docs.unity3d.com/Packages/com.unity.netcode@latest/

---

## 12. Save data

- Write files under **`Application.persistentDataPath`** (per-user, writable, survives updates). Never write to
  `Application.dataPath` or `streamingAssetsPath` at runtime (read-only in builds on most platforms).
- Write safely: serialize to a temp file, then replace (`File.Replace` / move) so a crash mid-write does not corrupt
  the only copy. Keep a version number in the save for migrations.
- **`JsonUtility`**: fast, built in, same rules as Unity serialization (fields only, public or `[SerializeField]`,
  `[Serializable]` types). Cannot serialize top-level arrays or primitives (wrap them in a class), properties, or
  polymorphic plain classes. `FromJsonOverwrite` patches an existing object and is required for
  MonoBehaviour/ScriptableObject targets. `ToJson` allocates only the string.
- **Newtonsoft Json.NET**: Unity's package `com.unity.nuget.newtonsoft-json`; handles dictionaries, properties,
  polymorphism (with `TypeNameHandling`: never enable `All`/`Auto` on untrusted input). Under IL2CPP, add `link.xml`
  or `[Preserve]` for reflected types so stripping does not remove them.
- **`PlayerPrefs`**: key-value store of `int`, `float`, `string` only; on Windows it lives in the registry, on the web
  in IndexedDB with a 1 MB limit. Not encrypted. Use for settings (volume, key bindings), not game saves. Call
  `PlayerPrefs.Save()` after important changes (otherwise written on quit, which may not happen on mobile).
- **`BinaryFormatter`**: do not use. Microsoft says it is insecure and cannot be made secure; deserializing a shared
  or downloaded save can run attacker code, and on .NET 9+ it throws. Unity 7's CoreCLR move makes this a likely hard
  break **(unverified)**. Use JSON, `BinaryWriter` with your own format, or MessagePack/MemoryPack.
- Local saves can always be edited by players. Anything that matters competitively (currency, unlocks) must be
  validated on a server you control.
- **UGS Cloud Save**: player data, game data and player files in Unity's cloud, access classes controlling what
  players may read and write, Cloud Code triggers. Needs Unity Services initialised and a signed-in player (Unity
  Authentication). SDK calls are along the lines of `CloudSaveService.Instance.Data.Player.SaveAsync(dict)` /
  `LoadAsync(keys)` **(unverified)** exact signatures. Alternatives: PlayFab, Firebase, Nakama, your own backend.

Sources: https://docs.unity3d.com/Manual/json-serialization.html, https://docs.unity3d.com/ScriptReference/PlayerPrefs.html,
https://docs.unity3d.com/ScriptReference/Application-persistentDataPath.html,
https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide,
https://docs.unity.com/ugs/en-us/manual/cloud-save/manual

---

## 13. Asset management

### 13.1 Options

| | `Resources` folder | AssetBundles | **Addressables** |
|---|---|---|---|
| How | Anything under a folder named `Resources` is built in; `Resources.Load<T>(path)` | Build bundles yourself, load with `AssetBundle.LoadFromFileAsync` | Mark assets addressable, load by address/label/`AssetReference`; the system builds bundles and tracks dependencies |
| Memory | Everything in Resources ships and is indexed at startup; unload via `Resources.UnloadUnusedAssets` | Manual `Unload(bool)` | Reference counted; bundles unload when their count reaches zero |
| Remote content | No | Yes, manual | Yes (remote catalogs, content updates) |
| Advice | Avoid except tiny bootstrap assets | Low level; most should use Addressables | Default for anything loaded on demand |

Unity 6.6 added a **Content Directory** option for local content as an alternative to AssetBundles (reported by press;
the Addressables 4.1 memory page says content-directory assets have per-asset reference counts).

### 13.2 Addressables load and release

- Load: `AsyncOperationHandle<T> h = Addressables.LoadAssetAsync<T>(key); await h.Task;` (or `h.Completed += ...`),
  then use `h.Result`. Field-based: `AssetReference` / `AssetReferenceT<T>` with `LoadAssetAsync<T>()` and
  `ReleaseAsset()`.
- Release: every load must be matched by exactly one release: `h.Release()` or `Addressables.Release(h)` (release by
  the handle or the original loaded asset, never by a runtime clone). Usually in `OnDestroy`.
- Instantiate: `Addressables.InstantiateAsync(key)` creates an instance and counts a reference; destroy it with
  `Addressables.ReleaseInstance(go)`. Plain `Destroy(go)` on such an instance leaks the reference (the bundle stays
  loaded). If you `Instantiate` a loaded prefab yourself, you may `Destroy` the clones but must still release the
  load handle.
- A bundle unloads only when **all** assets loaded from it are released; partial unloads are impossible. One forgotten
  handle keeps the whole bundle (textures and all) in memory: the classic "memory grows every level" leak.
- Releasing and immediately reloading from the same bundle causes churn; keep hot assets loaded.
- Diagnose with the **Addressables Profiler module** (shows loaded bundles and assets, and a "Released" state) and
  `AsyncOperationHandle.ReferenceCount` (0 when invalid or released). The older Event Viewer was replaced by the
  profiler module **(unverified)** exact version.
- Do not release twice or use a released handle (error about an invalid operation handle); check `h.IsValid()`.
- Scenes: `Addressables.LoadSceneAsync` / `Addressables.UnloadSceneAsync`.

Sources: https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/memory-assets.html,
https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/load-assets.html,
https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/MemoryManagement.html (the `InstantiateAsync` /
`ReleaseInstance` / `Addressables.Release` names come from long-standing Addressables docs; the 4.1 page for them
returned 404 on 2026-10-13, so **(unverified)** for 4.1)

---

## 14. Performance and profiling

### 14.1 Tools

- **Profiler** (Window > Analysis > Profiler): CPU (timeline and hierarchy views), GPU, Rendering, Memory, Audio,
  Physics modules. Profile a **development build on the target device**; the editor adds overhead. Deep Profile
  instruments every method (very slow, use briefly). Add markers with `ProfilerMarker` (`using (marker.Auto())`).
- **Memory Profiler** package: snapshots of native and managed memory; compare snapshots to find leaks (textures held
  by forgotten references, Addressables not released).
- **Frame Debugger**: step through draw calls, see why batches break (SRP Batcher reasons).
- **Profile Analyzer**: compare captures. **Rendering Debugger** in URP/HDRP.
- **Project Auditor** (static analysis of code and settings) became an official package in the Unity 6 cycle
  **(unverified)** version.

### 14.2 Garbage collection

- Mono and IL2CPP use the Boehm GC with **incremental GC** on by default (spreads collection across frames). Still,
  per-frame allocations cause spikes. Find them with the CPU Profiler "GC Alloc" column.
- Common per-frame allocators: string concatenation/formatting, LINQ, boxing value types into `object`/interfaces,
  lambdas capturing variables, `GetComponents` returning arrays (use the `List<T>` overloads), `Physics.RaycastAll`
  (use NonAlloc), `new WaitForSeconds` every loop iteration.
- Reuse buffers, cache delegates, use structs, `StringBuilder` for text, `TMP_Text.SetText` with number arguments.

### 14.3 Object pooling

- `UnityEngine.Pool.ObjectPool<T>`: `new ObjectPool<Bullet>(createFunc, actionOnGet, actionOnRelease,
  actionOnDestroy, collectionCheck, defaultCapacity, maxSize)`; `pool.Get()`, `pool.Release(obj)`. Also
  `ListPool<T>`, `DictionaryPool<TKey,TValue>`, `GenericPool<T>`, `LinkedPool<T>`.
- Pool bullets, VFX, damage numbers, enemies. Reset state in `actionOnGet`; deactivate in `actionOnRelease`.
- `collectionCheck: true` catches double release (editor cost).

### 14.4 Scripting backends

- **Mono**: JIT, fast builds, supports runtime code generation.
- **IL2CPP**: converts IL to C++ and compiles ahead of time. Required on iOS, consoles and Web; recommended for Android
  (64-bit store requirement) and release desktop builds. Faster at runtime, slower to build, no
  `System.Reflection.Emit`; generic code reached only via reflection may need hints.
- **Managed code stripping** (Player Settings > Managed Stripping Level: Minimal/Low/Medium/High) removes unused code.
  Reflection-only types (JSON serializers, DI containers) get stripped: keep them with a `link.xml` file or
  `[Preserve]`. Symptom: works in editor, `MissingMethodException` or empty deserialized data in an IL2CPP build.
- Unity 7 moves the runtime to **CoreCLR** (announced; alpha in October 2026).

### 14.5 Common wins

- Fewer `Update` methods: one manager updating many objects beats thousands of `Update` callbacks.
- Cache components and `Transform`s; avoid `Find*` and `SendMessage` in hot paths.
- Disable components that have nothing to do; use events instead of polling.
- Physics: fewer MeshColliders (convex or primitives), sensible fixed timestep, prune the layer matrix.
- Rendering: SRP Batcher-compatible shaders, GPU Resident Drawer for many repeated meshes, texture compression (ASTC
  on mobile), mipmaps, LODs, occlusion culling, fewer realtime shadows.
- UI: split canvases, disable Raycast Target, avoid layout groups on frequently changing content.
- Jobs + Burst for heavy loops; DOTS for very many entities.

Sources: https://docs.unity3d.com/Manual/Profiler.html, https://docs.unity3d.com/Packages/com.unity.memoryprofiler@latest/,
https://docs.unity3d.com/Manual/performance-garbage-collector.html, https://docs.unity3d.com/ScriptReference/Pool.ObjectPool_1.html,
https://docs.unity3d.com/Manual/managed-code-stripping.html (standard pages; content from long-standing docs,
not re-fetched on 2026-10-13)

---

## 15. Build and deploy

### 15.1 Build Profiles (Unity 6)

- File > **Build Profiles** is the build window in Unity 6. **Platform profiles** (one per installed platform) share
  settings such as Development Build and the scene list; **custom build profiles** are assets (version-controllable)
  with their own name and scene list, for example "Windows Demo" or "Android Dev". Create one from a platform with
  "Copy to new profile".
- In new projects the classic platform pane can be hidden (Project Settings > Editor > Build Profiles > Hide Classic
  Platforms).
- Scripting API: `UnityEditor.Build.Profile.BuildProfile`; building with a profile from code uses
  `BuildPipeline.BuildPlayer(new BuildPlayerWithProfileOptions { ... })` **(unverified)** exact member names.

### 15.2 Command line

- `Unity.exe -batchmode -nographics -projectPath <path> -executeMethod BuildScript.BuildAll -logFile - -quit`
- `-executeMethod` runs a static method from an Editor script. Signal failure by throwing (exit code 1) or
  `EditorApplication.Exit(nonZero)`. In batch mode a script exception makes Unity exit with code 1.
- `-buildTarget <win64|android|ios|webgl|...>`; `-activeBuildProfile <path relative to project>` (applies its scripting
  defines before compilation); `-build <path>` builds a player from the active build profile.
- `-nographics` cannot bake GI. `-quit` can hide errors and quits before tests finish: **do not combine `-quit` with
  `-runTests`**.
- Licensing on CI: a Unity license must be activated (serial or license server).

### 15.3 Tests

- **Unity Test Framework** (`com.unity.test-framework`, docs latest 1.9), NUnit-based.
  - **EditMode** tests: run in the editor without entering Play mode; fast; for pure logic and editor code.
  - **PlayMode** tests: `[UnityTest]` returning `IEnumerator` (yield frames); run the player loop.
  - Test assemblies are asmdefs referencing the test runner; EditMode test asmdefs include only the Editor platform.
- CLI: `Unity -batchmode -projectPath . -runTests -testPlatform EditMode -testResults results.xml -logFile -`
  (`-testPlatform PlayMode` for play mode; `-testFilter` and `-testCategory` narrow it). Results are NUnit XML.
  (Flag names from long-standing UTF docs; the 1.9 page path returned 404 on 2026-10-13 **(unverified)** for 1.9.)
- Keep gameplay logic in plain C# classes (no MonoBehaviour) so EditMode tests can cover it.

### 15.4 Platforms and CI

- Platform modules are installed per editor through Unity Hub. Android needs the bundled JDK/SDK/NDK; iOS produces an
  Xcode project that must be built on macOS.
- CI options: Unity Build Automation (cloud), GameCI (GitHub Actions/GitLab with Docker images), Jenkins/TeamCity with
  installed editors. Cache the `Library` folder between runs to save import time.
- Web builds are IL2CPP to WebAssembly; no C# threads by default, PlayerPrefs in IndexedDB, compression settings need
  matching server headers.

Sources: https://docs.unity3d.com/Manual/build-profiles.html, https://docs.unity3d.com/Manual/EditorCommandLineArguments.html,
https://docs.unity3d.com/Packages/com.unity.test-framework@1.9/, https://docs.unity3d.com/Manual/scripting-backends.html

---

## 16. Common bugs and their fixes

1. **`NullReferenceException` / `UnassignedReferenceException` on a serialized field.** The Inspector slot is empty
   (often on a second copy of the component, or a prefab instance whose override was reverted). Assign it, or fetch it
   with `GetComponent` in `Awake` plus `[RequireComponent]`, and validate in `Awake`/`OnValidate` with a clear error.
2. **`MissingReferenceException` after `Destroy`.** Code keeps calling a destroyed object (often via a static event
   handler or `?.`). Unsubscribe in `OnDisable`/`OnDestroy`; check with `!= null` or `if (obj)`, not `?.`.
3. **`?.` / `??` on a destroyed object still runs.** They bypass Unity's `==` override. Use explicit `!= null`.
4. **Jittery camera or player.** Rigidbody moved in `Update` (or via `transform.position`) while physics runs in
   `FixedUpdate`, camera following in `Update`. Move the body with `AddForce`/`linearVelocity`/`MovePosition` in
   `FixedUpdate`, set `Rigidbody.interpolation = RigidbodyInterpolation.Interpolate` on the followed body, move the
   camera in `LateUpdate`.
5. **Jump input sometimes ignored or doubled.** One-shot input read in `FixedUpdate`. Read in `Update`, latch a flag,
   consume it in `FixedUpdate`.
6. **`OnTriggerEnter` never fires.** Neither object has a Rigidbody; no collider has Is Trigger; wrong signature
   (`Collision` instead of `Collider`, or 2D vs 3D mismatch); layers disabled in the collision matrix.
7. **`OnCollisionEnter` never fires.** One collider is a trigger, or no dynamic Rigidbody is involved (kinematic vs
   static reports nothing), or the object is teleported with `transform.position`.
8. **Fast objects pass through walls.** Use Continuous collision detection, thicker colliders, or sweep/raycast ahead.
9. **UI button does not respond.** No `EventSystem` in the scene; Canvas missing `GraphicRaycaster`; an invisible
   image with Raycast Target on covers it; `CanvasGroup.interactable`/`blocksRaycasts` false; wrong input module for
   the active input handling.
10. **`InvalidOperationException` about reading input with the `UnityEngine.Input` class while Active Input Handling is
    set to the Input System package.** Port to the Input System (`Keyboard.current`, actions), replace
    `StandaloneInputModule` with `InputSystemUIInputModule`, or set Active Input Handling to Both.
11. **Input actions return zero.** The action or map is not enabled (`Enable()`), the generated class instance was
    never enabled, or the binding's control scheme does not match the device.
12. **Prefab edits lost.** Edited the scene instance, not the asset, and did not apply overrides; or an editor script
    changed objects without `Undo.RecordObject` / `EditorUtility.SetDirty` /
    `PrefabUtility.RecordPrefabInstancePropertyModifications`.
13. **ScriptableObject keeps play-mode changes in the editor but resets in builds.** SOs are assets. `Instantiate(so)`
    a runtime copy if you mutate it.
14. **Static state survives between plays (event fires twice, singleton already set).** Domain reload is disabled.
    Reset statics with `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]` (or the 6.6
    reset attributes).
15. **Script will not attach.** The MonoBehaviour class name must match the `.cs` file name, and any compile error in
    the project blocks attaching.
16. **Missing script on objects after moving files.** The `.meta` was lost or regenerated, so the GUID changed. Restore
    the `.meta` from version control.
17. **Addressables memory keeps growing.** Handles never released, or `InstantiateAsync` instances destroyed with
    `Destroy` instead of `Addressables.ReleaseInstance`. Pair every load with one release; check the Addressables
    profiler module.
18. **Invalid operation handle error.** Released twice or used after release. Clear the stored handle after releasing;
    test `IsValid()`.
19. **NGO: client writes a NetworkVariable and nothing syncs / permission error.** Default write permission is Server.
    Send an `[Rpc(SendTo.Server)]` and write on the server, or use `NetworkVariableWritePermission.Owner` for
    owner-driven values.
20. **NGO: RPC on a non-spawned object.** Called before `OnNetworkSpawn` or on an object the server never spawned.
    Call from `OnNetworkSpawn` or later; make sure the server spawned it.
21. **NGO: RPC method does not compile / codegen error.** Name lacks the `Rpc` suffix, or a parameter type is not
    network-serializable (use FixedString or `INetworkSerializable`).
22. **NGO: player snaps back after moving on the client.** `NetworkTransform` is server-authoritative; set its
    Authority Mode to Owner for player-driven movement (or the legacy ClientNetworkTransform), or move on the server.
23. **NGO: spawned prefab missing on clients / hash error.** Prefab not in the Network Prefabs list, or spawned by a
    client in client-server topology.
24. **Works in editor, fails in IL2CPP build (missing method, empty JSON load).** Code stripping removed reflected
    types. Add `link.xml`/`[Preserve]`; lower the stripping level to confirm.
25. **ECS: structural change inside a job or during iteration.** Record with an `EntityCommandBuffer` (from an ECB
    system singleton; `AsParallelWriter()` with a `[ChunkIndexInQuery]` sort key) and let it play back on the main
    thread.
26. **Burst compile error about managed types.** A class, `string` or managed array in a `[BurstCompile]` job or
    system. Use unmanaged structs, `NativeArray`, `FixedString`.
27. **Native collection leak warnings.** Dispose `NativeArray`s (`using`, or `Dispose(jobHandle)`); use
    `Allocator.Temp` for frame-local data.
28. **Pink/magenta materials after switching to URP.** Built-in shaders. Run the Render Pipeline Converter or switch
    materials to URP shaders; assign the URP asset in Graphics and Quality settings.
29. **Coroutine stops unexpectedly.** The GameObject running it was deactivated or destroyed, or `StartCoroutine` was
    called on an inactive object. Run it on a persistent object, or use Awaitable with a cancellation token.
30. **`async` code keeps running after the scene unloads and throws.** Awaitables are not tied to object lifetime;
    pass `destroyCancellationToken` and handle `OperationCanceledException`.
31. **Obsolete API warnings/errors after upgrading to Unity 6.** `Rigidbody.velocity` -> `linearVelocity`, `drag` ->
    `linearDamping`, `angularDrag` -> `angularDamping`, `FindObjectsOfType` -> `FindObjectsByType`,
    `FindObjectOfType` -> `FindFirstObjectByType` / `FindAnyObjectByType`. Accept the API Updater or rename by hand.
32. **Animator transition feels delayed.** "Has Exit Time" is on, or the transition duration is long. Disable exit
    time for input-driven transitions.
33. **CharacterController ignores a teleport.** Set the position while the controller is disabled, or call
    `Physics.SyncTransforms` after setting it.

Sources: see sections 4, 6, 8, 9, 10, 11, 13, 14 (all URLs collected in the list at the end).

---

## 17. Roblox -> Unity concept map

| Roblox | Unity | Notes |
|---|---|---|
| DataModel / `game` | The running app: loaded Scenes + project assets | No global tree you query by service name. |
| Workspace | The active Scene's hierarchy (plus additive scenes) | Several scenes can be loaded at once. |
| Part / MeshPart | GameObject + `MeshFilter` + `MeshRenderer` + `Collider` (+ `Rigidbody` if it moves physically) | Anchored part = static collider (no Rigidbody) or kinematic Rigidbody. |
| Model | Parent GameObject / prefab | The root Transform acts as the pivot (no PrimaryPart). |
| Instance properties | Component fields | Serialized fields show in the Inspector. |
| `Instance.new` + Parent | `Instantiate(prefab, parent)` or `new GameObject().AddComponent<T>()` | Prefabs replace "clone a template from ReplicatedStorage". |
| `:Destroy()` | `Destroy(gameObject)` (end of frame) | Destroyed objects compare `== null`; beware `?.`. |
| ReplicatedStorage / ServerStorage templates | Prefabs, ScriptableObjects, Addressables | No server/client storage split: a client build contains everything you put in it. |
| Script (server) | Server-side code in NGO (`if (IsServer)`, server-target RPC handlers) or a dedicated server build | There is no automatic server: you choose host, dedicated server or distributed authority. |
| LocalScript | Ordinary MonoBehaviour on the client (`IsOwner` / `IsLocalPlayer` checks in NGO) | Single-player Unity code is all "local". |
| ModuleScript + `require` | C# class / namespace; assemblies via asmdef | Static classes or ScriptableObject services. |
| RemoteEvent `FireServer` / `OnServerEvent` | `[Rpc(SendTo.Server)]` method; sender from `RpcParams.Receive.SenderClientId` | Validate on the server exactly like Roblox remotes. |
| RemoteEvent `FireClient` / `FireAllClients` | `[Rpc(SendTo.Owner)]` or `RpcTarget.Single(...)`; `[Rpc(SendTo.ClientsAndHost)]` | |
| RemoteFunction | No direct equivalent: request RPC plus reply RPC (or a NetworkVariable) | Avoid blocking round trips. |
| UnreliableRemoteEvent | `[Rpc(..., Delivery = RpcDelivery.Unreliable)]` | |
| Attributes / ValueObjects (replicated) | `NetworkVariable<T>` | Server-write by default, like server-set attributes. |
| Attributes (local config) | `[SerializeField]` fields, ScriptableObjects | |
| `SetNetworkOwner` | NetworkObject ownership (`ChangeOwnership`), NetworkTransform Authority Mode | |
| DataStoreService | UGS Cloud Save, PlayFab, your own backend; local files under `persistentDataPath` | No free built-in per-player cloud storage: you pick and pay. |
| MessagingService | Your backend or UGS services (Cloud Code) **(unverified)** closest UGS equivalent | |
| TweenService | DOTween / PrimeTween / LitMotion (third party), coroutine or Awaitable lerps, Animator, UI Toolkit transitions | No built-in tween library. |
| RunService.Heartbeat | `Update` | In Unity physics runs before Update. |
| RunService.Stepped / PreSimulation | `FixedUpdate` | Fixed timestep (0.02 s default). |
| RunService.RenderStepped / BindToRenderStep | `LateUpdate` for cameras; URP `RenderPipelineManager.beginCameraRendering` for render hooks | |
| `task.wait` / `task.delay` / `task.spawn` | `yield return new WaitForSeconds`, `await Awaitable.WaitForSecondsAsync`, `Invoke`, `StartCoroutine` | |
| Humanoid | `CharacterController` (or Rigidbody controller) + `Animator` + your own health script | Health, jumping, walk speed and states are yours to write. |
| Animator / AnimationTrack | `Animator` + Animator Controller state machine | Parameters drive states instead of `:Play()` calls. |
| CollectionService tags | Marker components (`TryGetComponent<Enemy>`), `CompareTag` (one tag per object), registries | Unity tags are single-valued; prefer components. |
| `Workspace:Raycast` + RaycastParams | `Physics.Raycast` + `LayerMask` + `QueryTriggerInteraction` | |
| `Touched` | `OnCollisionEnter` / `OnTriggerEnter` | Needs a Rigidbody on one side. |
| CollisionGroups | Layers + Layer Collision Matrix | |
| StreamingEnabled | Additive scene loading, Addressables, SubScenes (DOTS), NGO visibility (`NetworkHide`, `CheckObjectVisibility`) | Manual design work. |
| ScreenGui | `Canvas` (uGUI) or `UIDocument` (UI Toolkit) | |
| Frame / TextLabel / TextButton | `Image` / `TMP_Text` / `Button`; or VisualElement / Label / Button | |
| UDim2 Scale vs Offset | `RectTransform` anchors (scale-like) plus offsets; `CanvasScaler` | |
| BillboardGui / SurfaceGui | World-space Canvas | |
| UserInputService / ContextActionService | Input System actions and action maps, `PlayerInput` | |
| Sound | `AudioSource` + `AudioListener` + Audio Mixer | |
| Lighting service | Lighting window, Volume (post-processing) profiles | |
| Players / Teams | Your own code; NGO `ConnectedClients`; Sessions/Lobby for grouping | |
| MarketplaceService | Unity IAP (`com.unity.purchasing`), platform stores | Validate receipts on your server. |
| Places / TeleportService | Scenes; for servers, your own matchmaking and hosting | |
| Play Solo / local test server | Play mode; Multiplayer Play Mode package for several local players | |
| Rojo + git | Native: everything is files; Force Text + Smart Merge | |
| `--!strict` | C# static typing (always on) | |

### Mindset differences to tell a Roblox developer

- **No free servers, no automatic replication.** Roblox hosts authoritative servers and replicates the DataModel for
  you. In Unity you choose a netcode library, a topology (host, dedicated server, distributed authority), hosting
  (Relay, a server provider, your own) and pay for it. Nothing replicates unless you make it a NetworkObject,
  NetworkVariable or RPC.
- **You own the backend.** Saves, purchases, leaderboards, moderation, matchmaking: UGS, another service or your own
  server. Local saves are editable by players.
- **The client build contains everything.** There is no ServerStorage: anything shipped to clients can be extracted.
  Keep secrets and authoritative logic in a server build or backend.
- **Physics order differs.** Unity runs physics at a fixed rate before `Update`; jitter fixes revolve around
  `FixedUpdate`, interpolation and moving cameras in `LateUpdate`.
- **Compile step and types.** C# is compiled; one compile error anywhere blocks Play mode.
- **Asset pipeline.** Imports, `.meta` GUIDs, prefabs and scenes as files.
- **Lifecycle is per component**: Unity calls `Awake`/`Update` on each component instance.
- **Platforms.** One project targets PC, consoles, mobile, web and XR; each needs its own build and testing.

---

## 18. Quick API sanity list

Verified against official pages on 2026-10-13: `Rigidbody.linearVelocity`, `Rigidbody.interpolation`,
`Physics.SyncTransforms`, `Object.FindObjectsByType<T>()`, `FindObjectsInactive`, `FindObjectsSortMode` (its overloads
obsolete in 6.6), `Object.FindFirstObjectByType`, `Object.FindAnyObjectByType`, `Awaitable.NextFrameAsync`,
`Awaitable.WaitForSecondsAsync`, `Awaitable.FixedUpdateAsync`, `Awaitable.EndOfFrameAsync`,
`Awaitable.BackgroundThreadAsync`, `Awaitable.MainThreadAsync`, `PlayerPrefs.Save`, `JsonUtility.FromJsonOverwrite`,
`[SerializeReference]`, `[field: SerializeField]`, `NetworkVariable<T>`, `NetworkVariableReadPermission`,
`NetworkVariableWritePermission`, `CheckDirtyState`, `NetworkList<T>`, `[Rpc(SendTo.Server)]`, `RpcParams`,
`RpcTarget.Single`, `RpcInvokePermission`, `RpcDelivery`, `NetworkObject.Spawn`, `InstantiateAndSpawn`, `Despawn`,
`IsSessionOwner`, `Addressables.LoadAssetAsync`, `AssetReference.ReleaseAsset`, `AsyncOperationHandle.Release`,
`AsyncOperationHandle.ReferenceCount`, `EntityCommandBuffer`, `AsParallelWriter`,
`EndSimulationEntityCommandBufferSystem.Singleton`, `CreateCommandBuffer(state.WorldUnmanaged)`, command-line
`-batchmode -nographics -quit -projectPath -executeMethod -buildTarget -activeBuildProfile -build -logFile`.

Believed correct from long-standing docs but not re-fetched on 2026-10-13: `Addressables.Release`,
`Addressables.InstantiateAsync`, `Addressables.ReleaseInstance`, `InputSystem.actions`, `PerformInteractiveRebinding`,
`SaveBindingOverridesAsJson`, `UnityEngine.Pool.ObjectPool<T>`, `RuntimeInitializeLoadType.SubsystemRegistration`,
`destroyCancellationToken`, `-runTests -testPlatform -testResults`, `BuildPlayerWithProfileOptions`,
`CloudSaveService.Instance.Data.Player.SaveAsync`, `ChunkIndexInQuery`.

---

## Sources

Official Unity (docs.unity3d.com, docs.unity.com, unity.com, discussions.unity.com):

- https://unity.com/releases/unity-6-releases
- https://unity.com/blog/unity-6-3-lts-is-now-available
- https://unity.com/en/releases/unity-7
- https://discussions.unity.com/t/unity-7-0-alpha-is-now-available/1738310
- https://docs.unity.com/en-us/engine/6000.6/manual
- https://docs.unity3d.com/Manual/execution-order.html
- https://docs.unity3d.com/Manual/configurable-enter-play-mode.html
- https://docs.unity3d.com/Manual/domain-reloading.html
- https://docs.unity3d.com/Manual/SpecialFolders.html
- https://docs.unity3d.com/Manual/SmartMerge.html
- https://docs.unity3d.com/Manual/ScriptCompilationAssemblyDefinitionFiles.html
- https://docs.unity3d.com/Manual/script-serialization-rules.html
- https://docs.unity3d.com/ScriptReference/Object-operator_eq.html
- https://docs.unity3d.com/Manual/async-awaitable-introduction.html
- https://docs.unity3d.com/ScriptReference/Object.FindObjectsByType.html
- https://docs.unity3d.com/Manual/render-pipelines-overview.html
- https://docs.unity3d.com/Manual/urp/gpu-resident-drawer.html
- https://docs.unity3d.com/Manual/urp/render-graph.html
- https://docs.unity3d.com/Manual/SRPBatcher.html
- https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@latest/
- https://docs.unity3d.com/ScriptReference/Rigidbody-linearVelocity.html
- https://docs.unity3d.com/ScriptReference/Rigidbody-interpolation.html
- https://docs.unity3d.com/Manual/collider-interactions-other-events.html
- https://docs.unity3d.com/Manual/PhysicsSection.html
- https://docs.unity3d.com/Manual/AnimationOverview.html
- https://docs.unity3d.com/Packages/com.unity.animation.rigging@latest/
- https://docs.unity3d.com/Packages/com.unity.timeline@latest/
- https://docs.unity3d.com/Manual/UI-system-compare.html
- https://docs.unity3d.com/Manual/UIElements.html
- https://docs.unity3d.com/Packages/com.unity.ugui@latest/
- https://docs.unity3d.com/Packages/com.unity.inputsystem@6.7/manual/index.html
- https://docs.unity3d.com/Packages/com.unity.inputsystem@latest/
- https://docs.unity3d.com/Packages/com.unity.entities@latest/
- https://docs.unity3d.com/Packages/com.unity.entities@6.7/manual/systems-entity-command-buffers.html
- https://docs.unity3d.com/Packages/com.unity.entities@6.7/manual/systems-entity-command-buffer-automatic-playback.html
- https://docs.unity3d.com/Packages/com.unity.burst@1.8/
- https://docs.unity3d.com/Manual/job-system.html
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/advanced-topics/message-system/rpc.html
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/basics/networkvariable.html
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/basics/object-spawning.html
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/components/helper/networktransform.html
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/terms-concepts/distributed-authority.html
- https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@2.9/manual/migratingfromUNet.html
- https://docs.unity3d.com/Packages/com.unity.netcode@latest/
- https://docs.unity.com/ugs/en-us/manual/mps-sdk/manual
- https://docs.unity3d.com/Manual/json-serialization.html
- https://docs.unity3d.com/ScriptReference/PlayerPrefs.html
- https://docs.unity3d.com/ScriptReference/Application-persistentDataPath.html
- https://docs.unity.com/ugs/en-us/manual/cloud-save/manual
- https://docs.unity3d.com/Packages/com.unity.addressables@latest/
- https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/MemoryManagement.html
- https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/memory-assets.html
- https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/load-assets.html
- https://docs.unity3d.com/Manual/Profiler.html
- https://docs.unity3d.com/Packages/com.unity.memoryprofiler@latest/
- https://docs.unity3d.com/Manual/performance-garbage-collector.html
- https://docs.unity3d.com/ScriptReference/Pool.ObjectPool_1.html
- https://docs.unity3d.com/Manual/managed-code-stripping.html
- https://docs.unity3d.com/Manual/scripting-backends.html
- https://docs.unity3d.com/Manual/build-profiles.html
- https://docs.unity3d.com/Manual/EditorCommandLineArguments.html
- https://docs.unity3d.com/Packages/com.unity.test-framework@1.9/

Other:

- https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide
- https://github.com/Unity-Technologies/com.unity.netcode.gameobjects/blob/release/1.8.0/com.unity.netcode.gameobjects/CHANGELOG.md
- https://gamefromscratch.com/unity-6-3-released/ (6.3 feature list, secondary)
- https://www.digitaltoday.co.kr/jp/view/99090/unity-releases-unity-6-6-to-improve-development-and-build-speeds (6.6
  release and 6.7 LTS timing, secondary)
