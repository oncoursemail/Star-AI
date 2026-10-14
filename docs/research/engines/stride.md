# Stride: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 4.4.0 (October 9, 2026; previous 4.3.0.2507 on November 14, 2025).** Free and open source (MIT), no royalties.

## At a glance
| | |
|---|---|
| Best for | C#/.NET developers who want a full 3D editor with engine source; PC 3D games, VR (OpenXR), tools and simulations |
| Weak at | Small community, few tutorials, no built-in high-level networking, Game Studio editor is Windows-only (Linux via Proton since 4.4), docs lag behind code |
| Language(s) | C# 14 on .NET 10; SDSL shader language (`.sdsl`, `.sdfx`) |
| Editor / tooling | Game Studio (Windows; Avalonia rewrite in progress), Stride Launcher (Avalonia since 4.4), `stride` CLI (4.4), `dotnet new stride-game`, Visual Studio / Rider / VS Code |
| Platforms (export) | Windows, Linux, macOS, Android, iOS (UWP/Xbox historically); 4.4 brought all platforms "back into shape" and allows building from Linux/macOS; 64-bit only since 4.4 |
| License / cost | MIT, free |
| Roblox-likeness | low: plain C# engine, scene/entity editor; no hosting, avatars, data stores or replication |

## Architecture and lifecycle
- Renamed from **Xenko** (Silicon Studio) to Stride in 2020 (4.0). Namespaces are `Stride.*`. `Xenko.*` and `SiliconStudio.*` are gone.
- **Entity-Component-System**: `Scene` → `Entity` (has a `TransformComponent`) → `EntityComponent`s. Systems are **processors** (`EntityProcessor<TComponent, TData>`). 4.3 added a "flexible processing" API that can process components by interface.
- **Scripts** are components that derive from one of three types:
  - `StartupScript`: `Start()` when added to the scene, `Cancel()` when removed.
  - `SyncScript`: adds `Update()` every frame.
  - `AsyncScript`: `async Task Execute()` that loops with `await Script.NextFrame()`; `Script.AddTask(...)` runs parallel tasks on the main thread.
- Entities and components are **never really destroyed**. They can be removed and re-added any number of times. `Start()`/`Cancel()` can run more than once, so `Cancel()` must undo what `Start()` did.
- Access from scripts: `Entity`, `Game`, `Input`, `Content` (asset loading), `Services` (service registry), `Log`, `SceneSystem`, `Script` (scheduler), `DebugText`.
- Scripts execute in **priority** order (`Priority` property; lower runs first).
- Physics: **Bepu Physics** (`Stride.BepuPhysics`, pure C#) is the documented and actively developed engine. **Bullet** (`Stride.Physics`) is "being phased out". 4.3 notes still say Bullet is the default in templates; check what a 4.4 template references.

## Project layout
```
MyGame/
  MyGame.sln or MyGame.slnx       # .slnx is the default solution format from 4.4
  MyGame.sdpkg                     # asset package
  Assets/                          # .sdscene, .sdprefab, .sdmat, .sdm (models), .sduipage, GameSettings.sdgamesettings
  Resources/                       # raw source files (fbx, png, wav)
  MyGame/                          # game code project (MyGame.csproj, scripts *.cs)
  MyGame.Windows/ (.Linux, .macOS, .Android, .iOS)   # platform executables
  Bin/, obj/                       # build output
```
- From 4.4 a generated `Assets` class provides strongly typed asset URLs: `Content.Load(Assets.Models.Player)` instead of `Content.Load<Model>("Models/Player")`. A renamed asset becomes a build error, not a runtime "content not found".
- Asset paths from external packages are now namespaced (4.4; rewritten automatically on upgrade).
- Create projects with Game Studio, or with `dotnet tool install -g stride.cli`, `stride sdk install`, `stride new <template>`, `stride studio`, or `dotnet new install Stride.Templates` + `dotnet new stride-game -n MyGame` (4.4).

## Scripting idioms
```csharp
using Stride.Core.Mathematics;
using Stride.Engine;
using Stride.Input;

public class Spinner : SyncScript
{
    // Public fields/properties are serialized and appear in Game Studio's Property Grid
    public float DegreesPerSecond { get; set; } = 90f;

    public override void Start() { Log.Info("Spinner ready"); }

    public override void Update()
    {
        float dt = (float)Game.UpdateTime.WarpElapsed.TotalSeconds; // respects time Factor (pause/slow-mo)
        Entity.Transform.Rotation *= Quaternion.RotationY(MathUtil.DegreesToRadians(DegreesPerSecond) * dt);
    }

    public override void Cancel() { /* undo Start side effects */ }
}
```
- `Game.UpdateTime.Elapsed` ignores `GameTime.Factor`; use `WarpElapsed` if pausing or slow motion should affect the script.
- Components: `Entity.Get<T>()`, `Entity.GetOrCreate<T>()`, `Entity.Add(component)`, `Entity.Transform.Position/Rotation/Scale`, `Entity.Transform.WorldMatrix`, `Entity.Transform.Parent`.
- Hard dependencies: prefer a typed public property (`public required MyComponent Target { get; set; }`), which shows in the editor and warns when unset (4.x best-practice docs), over `Entity.Get<T>()` returning null.
- Hide members from the editor with `[DataMemberIgnore]`. Custom data classes need `[DataContract]`. Use `[MemberRequired]` for must-set fields. A `<userdoc>` XML comment becomes the editor tooltip.
- Async waiting: `await Script.NextFrame()`, `await Task.Delay(ms)`. **Do not use `Task.Run`** for engine work: it runs off the main thread.
- Spawning: `var instance = prefab.Instantiate(); Entity.Scene.Entities.AddRange(instance);` (`Prefab` assets have `Instantiate()` returning a list of entities).
- Global systems: `Services.GetOrCreate<T>()`, `Services.AddService(this)` / `Services.RemoveService(this)`.
- `EventKey` / `EventReceiver` broadcast events still exist but the docs now say they are **not recommended**.

## Pitfalls (what AI answers get wrong)
1. **Xenko names**: `using Xenko.Engine;`, `SiliconStudio.Core.Mathematics`, `.xkscene` file extensions. Since 4.0 use `Stride.*` and `.sd*`.
2. **Bullet vs Bepu `CharacterComponent`**: both exist with the **same class name** in different namespaces.
   - Bullet (`using Stride.Physics;`): `character.SetVelocity(v)`, `character.Jump()`, `character.Teleport(p)`, `RigidbodyComponent`, `StaticColliderComponent`, `PhysicsComponent.NewCollision()`, `ProcessCollisions`.
   - Bepu (`using Stride.BepuPhysics;`): `character.Move(Vector3)`, `character.TryJump()`, set `Position` to teleport, `BodyComponent`, `StaticComponent`, `CharacterComponent`, triggers through `IContactHandler`.
   New code should target Bepu unless the project already uses Bullet. Check the project's package references (`Stride.BepuPhysics` vs `Stride.Physics`).
3. **Bepu `CharacterComponent` reworked in 4.4** (breaking): behavior and properties differ from 4.3. `Move()` input is local to the character's `Orientation` (X = local X, Y = local Z/forward). Re-orient through `Orientation` or `SetTargetPose(Quaternion)`.
4. **4.4 API renames** (auto-fixed on upgrade but models still emit the old ones): `GameSettings.Configuration.Get<T>` → `GameSettings.GetOrCreateConfiguration<T>`; `Utilities.AllocateMemory/FreeMemory/Clear/CopyWithAlignmentFallback/IsMemoryAligned/Swap` → `MemoryUtilities.Allocate/Free/Clear/CopyWithAlignmentFallback/IsAligned/Swap`.
5. **4.4 removed OpenGL** (use Vulkan or Direct3D), dropped 32-bit, requires Vulkan 1.3 and D3D12 Enhanced Barriers, removed per-platform Game Settings overrides, and replaced the SDSL compiler (custom shaders may need fixes).
6. **.NET version**: 4.3 and 4.4 run on **.NET 10** (C# 14). 4.2 used .NET 8; older 4.0/4.1 used .NET 6. Do not suggest `net6.0`/`net8.0` target frameworks for a 4.4 project.
7. Using `Game.UpdateTime.Elapsed` and expecting pause (`Factor = 0`) to stop motion. Use `WarpElapsed`.
8. Doing runtime work in property setters. Game Studio calls them at edit time when `Entity` and services are not available.
9. Writing a custom "Destroy()" instead of removing from the scene (`Entity.Scene = null` or `scene.Entities.Remove(e)`) and cleaning up in `Cancel()`.
10. Unity-isms: `MonoBehaviour`, `void Update()` without `override`, `transform.position`, `GetComponent<T>()`, `Time.deltaTime`, `Input.GetKey(KeyCode.W)`. Stride: `SyncScript`, `public override void Update()`, `Entity.Transform.Position`, `Entity.Get<T>()`, `Game.UpdateTime`, `Input.IsKeyDown(Keys.W)`.
11. Assuming a built-in multiplayer layer. There is none; community libraries only.
12. Coordinate system: **Y-up, right-handed**, forward is -Z (`Vector3.UnitZ` points toward the camera in the default view); units are meters.

## Rendering
- PBR materials (`.sdmat`), clustered forward rendering, **Graphics Compositor** asset defines the pipeline (cameras, render stages, post effects).
- Post effects: bloom, ambient occlusion, depth of field, tone mapping, color grading, FXAA/TAA. HDR output on D3D/Windows (4.3).
- Shaders: SDSL with mixins/composition (`.sdsl`), effects (`.sdfx`). 4.4 rewrote the compiler around SPIR-V ("SPIR-S" per-shader modules), which improves D3D12/Vulkan tessellation and compute support.
- Backends: Direct3D 11, Direct3D 12, Vulkan (Metal via SPIRV-Cross). The graphics API is selectable in Game Studio settings and per Windows package (4.4). D3D11 may be removed in the next major release.
- Mesh data access: `VertexBufferHelper` / `IndexBufferHelper` (4.3). Custom gizmos (4.3). Particles, sprites, 2D sprite components, skyboxes, light probes.

## Physics
- **Bepu** setup: add the `Stride.BepuPhysics` dependency (Game Studio: right-click game project > Add dependency), then in `GameSettings` add a **Bepu Configuration** with at least one simulation.
- Collidables: `StaticComponent` (immovable), `BodyComponent` (dynamic or `Kinematic`), `CharacterComponent`. Shapes go in the `Collider` property (box, sphere, capsule, convex hull, mesh; mesh colliders only on statics).
- Collision filtering: `CollisionLayer` + the simulation collision matrix, `CollisionGroup` (`Id`, `IndexA/B/C`), and a **Contact Event Handler**.
- Triggers and contacts: implement `IContactHandler` on a script or component bound as the collidable's contact event handler. `NoContactResponse => true` makes it a trigger.
```csharp
using Stride.BepuPhysics;
using Stride.BepuPhysics.Definitions.Contacts;
using Stride.Engine;

public class CoinTrigger : StartupScript, IContactHandler
{
    public bool NoContactResponse => true;   // pass-through trigger
    void IContactHandler.OnStartedTouching<TManifold>(Contacts<TManifold> contacts)
        => Log.Info($"{contacts.Other.Entity.Name} entered");
    void IContactHandler.OnStoppedTouching<TManifold>(Contacts<TManifold> contacts) { }
}
```
- Per-step hooks: implement `ISimulationUpdate` (`SimulationUpdate(BepuSimulation sim, float simTimeStep)` before the step, `AfterSimulationUpdate(...)` after). Use it for velocity changes and ground checks.
- Queries: raycasts, sweepcasts and overlaps through the `BepuSimulation` (see "Physics queries" docs; method names not re-checked in this pass).
- Custom character controllers: derive from `CharacterComponent` and override `SimulationUpdate(BepuSimulation, float, ref InternalCharacterData, in BodyReference, out bool)`, or start from `CharacterComponentAbstract`.

## Input
- `Input.IsKeyDown(Keys.W)`, `Input.IsKeyPressed(Keys.Space)`, `Input.IsKeyReleased(...)`; collections `Input.DownKeys`, `PressedKeys`, `ReleasedKeys`, `KeyEvents`; `Input.HasKeyboard`.
- Mouse: `Input.MousePosition` (normalized), `Input.MouseDelta`, `Input.IsMouseButtonDown(MouseButton.Left)`, `Input.LockMousePosition()`.
- Gamepads: `Input.DefaultGamePad`, `Input.GamePads`. Virtual buttons map several devices to named actions. Gestures and sensors for mobile.
- No "interpreted keys" (character input) from key state; use text input events for typing.

## UI
- UI assets: **UI pages** (`.sduipage`) and UI libraries, edited in the UI editor. Elements: `Grid`, `StackPanel`, `Canvas`, `Button`, `TextBlock`, `EditText`, `ImageElement`, `ScrollViewer`, `Slider`, `ToggleButton`.
- Show a page through a `UIComponent` on an entity (fullscreen or 3D billboard).
```csharp
var root = Entity.Get<UIComponent>().Page.RootElement;
var score = root.FindVisualChildOfType<TextBlock>("ScoreText");
var ok = root.FindVisualChildOfType<Button>("buttonOk");
ok.Click += (s, e) => score.Text = "Clicked";
```
- 4.4: `ScrollViewer.ScrollOfInternal` is private now.

## Networking and multiplayer
- **No built-in high-level multiplayer.** The docs list community options: Stride.ClientServerSample (headless server), Stride.Networking.Simple, StrideNet, LiteEntitySystem (server-authoritative ECS with rollback), Riptide-based interpolation sample, ET-Stride.
- Plain .NET networking (`System.Net.Sockets`, `HttpClient`, LiteNetLib and similar) works because games are normal .NET apps.
- For a Roblox-style setup you must build: server authority, replication, RPC messages, interest management and player sessions.

## Save data
- No dedicated save-game API. Serialize your own types with `System.Text.Json` (or Stride's YAML/binary serializers) and write to a user folder, for example `Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)`. Stride's virtual file system (`VirtualFileSystem`, `/roaming` and `/local` style roots) also exists; not re-verified in this pass.
- Do not save by mutating assets at runtime (best-practice docs: "Do not Mutate Assets").

## Performance
- Avoid per-frame allocations in `Update()` (LINQ, closures, `new List`). Cache `Entity.Get<T>()` results in `Start()`.
- Use processors (ECS systems) for many similar components instead of thousands of scripts.
- Bepu: keep characters on primitive or convex shapes (never mesh colliders), and use statics for level geometry. See "Fix physics jitter" (interpolation) docs.
- 4.4 has a 2x faster asset build cache, NativeAOT and trimming for smaller, faster-starting builds, and better GPU-hang diagnostics on D3D12/Vulkan.
- Profiling: the in-game profiler (Ctrl+Shift+P toggles it in debug builds) and `DebugText`; Visual Studio / dotnet-trace for CPU.

## Build and export
- Game Studio: choose the platform project and Build/Run. Or build the platform project with `dotnet build` / `dotnet publish` (for example `MyGame.Windows`).
- 4.4: official guide "building the game" (self-contained vs framework-dependent; framework-dependent needs the .NET 10 runtime on the player's PC), NativeAOT support, and building from Linux and macOS works like on Windows.
- Running a game needs DirectX 11/12 or Vulkan and the VC++ runtime.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `The type or namespace 'Xenko' could not be found` | Xenko-era code | Replace with `Stride.*` namespaces |
| `CharacterComponent` has no `SetVelocity` | Project uses Bepu, code written for Bullet | Use Bepu `Move(Vector3)` / `TryJump()`, or reference `Stride.Physics` on purpose |
| `CharacterComponent` has no `Move` | Project uses Bullet | Use `SetVelocity`/`Jump`, or migrate to Bepu |
| Character moves sideways/backwards | Bepu `Move` vector is local to `Orientation` | Build the vector in character space or set `Orientation` |
| Character "ice skates" or is too slow | Mass / `MaximumHorizontalForce` / friction balance | Raise `MaximumHorizontalForce`, adjust mass and surface friction |
| Trigger never fires | No contact handler bound, or layers do not collide | Bind the `IContactHandler`; check the collision matrix |
| Objects do not stop when game paused | `Elapsed` ignores time factor | Use `WarpElapsed` |
| Editor crash when selecting entity | Property setter touches runtime API | Keep setters trivial or add `[DataMemberIgnore]` |
| Custom shader stopped compiling after 4.4 | New SDSL compiler | Adjust the shader; report to the Stride GitHub issues if it is a compiler bug |
| Game will not start after 4.4 upgrade (OpenGL project) | OpenGL removed | Switch the graphics API to Vulkan or Direct3D |
| Content not found at runtime | String asset URL typo or rename | Use the 4.4 generated `Assets` class |

## Mapping from Roblox
| Roblox | Stride | Notes |
|---|---|---|
| Workspace / Instance tree | `Scene` with `Entity` hierarchy (`TransformComponent` parent/children) | Child scenes possible |
| Part | Entity + `ModelComponent` (procedural primitive model) + Bepu `StaticComponent`/`BodyComponent` | |
| Model | Prefab (`.sdprefab`) / parent entity | `prefab.Instantiate()` |
| Script | `SyncScript` / `AsyncScript` component | No server/client split |
| LocalScript | Same scripts; everything is local | |
| ModuleScript | Plain C# classes/services (`Services.GetOrCreate<T>()`) | |
| RemoteEvent | Not built in; community libs or your own sockets | |
| DataStore | Your own files (`System.Text.Json`) | |
| Players | Not built in | |
| Humanoid | Bepu `CharacterComponent` + animation component | |
| RunService.Heartbeat / RenderStepped | `SyncScript.Update()`; `ISimulationUpdate` for physics step | |
| TweenService | No built-in tween; lerp in `Update` or an `AsyncScript` loop; animation curves | |
| CollectionService tags | Components as tags + a processor, or `Entity.Name`/custom component queries | |
| Attributes | Public properties on scripts/components | Serialized, editable |
| ScreenGui | `UIComponent` + UI page | |
| UserInputService | `Input` (`InputManager`) | |
| task.wait | `await Task.Delay(ms)` / `await Script.NextFrame()` in `AsyncScript` | Never `Task.Run` |
| Studio playtest | Game Studio "Play" (F5, runs the platform project) | |
| Publishing | Build/publish platform project; ship on your own store page | |

## Minimal example
Bepu character moved with WASD; picks up coins that use the trigger script above and reports score through a shared service.
```csharp
using Stride.BepuPhysics;
using Stride.Core.Mathematics;
using Stride.Engine;
using Stride.Input;

public class ScoreService { public int Score; }

public class PlayerController : SyncScript
{
    public required CharacterComponent Character { get; set; }  // drag the Bepu CharacterComponent here
    public float Speed { get; set; } = 6f;

    public override void Update()
    {
        var move = Vector3.Zero;
        if (Input.IsKeyDown(Keys.W)) move.Z += 1;   // Bepu Move: local Z = forward
        if (Input.IsKeyDown(Keys.S)) move.Z -= 1;
        if (Input.IsKeyDown(Keys.A)) move.X += 1;   // local +X = left
        if (Input.IsKeyDown(Keys.D)) move.X -= 1;
        if (move != Vector3.Zero) move.Normalize();

        Character.Speed = Speed;
        Character.Move(move);
        if (Input.IsKeyPressed(Keys.Space)) Character.TryJump();

        DebugText.Print($"Score: {Services.GetOrCreate<ScoreService>().Score}", new Int2(10, 10));
    }
}

public class Coin : StartupScript, Stride.BepuPhysics.Definitions.Contacts.IContactHandler
{
    public bool NoContactResponse => true;
    void Stride.BepuPhysics.Definitions.Contacts.IContactHandler.OnStartedTouching<TManifold>(
        Stride.BepuPhysics.Definitions.Contacts.Contacts<TManifold> contacts)
    {
        if (contacts.Other.Entity.Get<PlayerController>() is null) return;
        Services.GetOrCreate<ScoreService>().Score++;
        Entity.Scene = null; // remove coin from the scene
    }
    void Stride.BepuPhysics.Definitions.Contacts.IContactHandler.OnStoppedTouching<TManifold>(
        Stride.BepuPhysics.Definitions.Contacts.Contacts<TManifold> contacts) { }
}
```
Caveat: after the 4.4 `CharacterComponent` rework, whether `Speed` and `Move()` keep these exact semantics was not re-read line by line. Check the Characters page of the 4.4 manual. `Entity.Scene = null` for removal and `contacts.Other` follow the docs' trigger samples.

## Sources
- https://github.com/stride3d/stride/releases (releases/4.4.0 published 2026-10-09; 4.4.0-beta9 2026-10-04)
- https://doc.stride3d.net/latest/en/ReleaseNotes/ and https://github.com/stride3d/stride-docs/blob/master/en/release-notes/4.4.md (4.4 highlights, breaking changes, API renames, CLI, Assets class, Bepu CharacterComponent rework)
- https://doc.stride3d.net/4.3/en/ReleaseNotes/ (4.3 date Nov 14 2025, .NET 10 / C# 14, Bepu integration, Bullet still default)
- https://stride3d.net/blog/announcing-stride-4-3-in-dotnet-10/ (4.3 announcement)
- https://doc.stride3d.net/latest/en/manual/physics/index.html (Bepu is primary, Bullet phased out)
- https://doc.stride3d.net/latest/en/manual/physics/characters.html (Bepu CharacterComponent Move/TryJump/Orientation pitfalls)
- https://doc.stride3d.net/latest/en/manual/physics/triggers.html and script-a-trigger.html (IContactHandler, NoContactResponse)
- https://doc.stride3d.net/latest/en/manual/physics/configuration.html (Stride.BepuPhysics dependency, Bepu Configuration)
- https://doc.stride3d.net/latest/en/manual/physics/physics-update.html (ISimulationUpdate)
- https://doc.stride3d.net/latest/en/manual/physics-bullet/characters.html (Bullet SetVelocity/Jump/Teleport)
- https://doc.stride3d.net/latest/en/manual/scripts/types-of-script/ (SyncScript, AsyncScript, StartupScript, WarpElapsed, Task.Run warning)
- https://doc.stride3d.net/latest/en/manual/scripts/best-practice.html (lifetime, Get<T>, services, required properties)
- https://doc.stride3d.net/latest/en/manual/input/keyboards.html (IsKeyDown/IsKeyPressed/IsKeyReleased)
- https://doc.stride3d.net/latest/en/manual/ui/ (UI pages, FindVisualChildOfType)
- https://doc.stride3d.net/latest/en/manual/install-and-update/requirements.html (.NET 10 runtime for games, Windows editor)
- https://doc.stride3d.net/latest/en/community-resources/networking.html (community networking libraries)

## Confidence and gaps
- High: 4.4.0 release and date (GitHub release API), breaking changes, script types, Bepu vs Bullet names, input API, UI lookup.
- Medium: exact 4.4 Bepu `CharacterComponent` property set (reworked); whether new 4.4 templates default to Bepu; `VirtualFileSystem` roots; profiler hotkey.
- 4.4 is only 4 days old. Docs and samples (samples/4.4.3) are moving, and a 4.4.x patch is likely soon.
