---
name: engine-stride
description: Stride (ex-Xenko) 4.4 C# engine on .NET 10. Use for SyncScript/AsyncScript/StartupScript, entities/components, Bepu physics, Game Studio, Stride UI and input.
---
# engine-stride
## Scope
Stride 4.4.0 (released Oct 9, 2026; 4.3 was Nov 2025), C# 14 on .NET 10, MIT. Check the project's Stride package version and whether it references `Stride.BepuPhysics` or `Stride.Physics` (Bullet) first.

## Core model
- Scene -> Entity (TransformComponent) -> EntityComponents; processors are the ECS systems.
- Scripts are components: `StartupScript` (Start/Cancel), `SyncScript` (+ `Update()`), `AsyncScript` (`async Task Execute()` looping on `await Script.NextFrame()`).
- Entities are never truly destroyed; Start/Cancel can run again, so Cancel undoes Start.
- Bepu is the developed physics engine; Bullet is being phased out.

## Idioms
- Public properties are serialized and editable in Game Studio; hide with `[DataMemberIgnore]`; custom data classes need `[DataContract]`.
- Frame time: `(float)Game.UpdateTime.WarpElapsed.TotalSeconds` (respects the pause/time factor; `Elapsed` does not).
- Keys: `Input.IsKeyDown(Keys.W)`, `IsKeyPressed`, `IsKeyReleased`; `Input.MouseDelta`.
- Components: `Entity.Get<T>()`; prefer typed `public required T X { get; set; }` references.
- Prefabs: `var list = prefab.Instantiate(); Entity.Scene.Entities.AddRange(list);`.
- Bepu: `CharacterComponent.Move(Vector3)` (local to Orientation; +Z forward, +X left), `TryJump()`, `BodyComponent`, `StaticComponent`; physics-step code via `ISimulationUpdate`.
- Triggers: implement `IContactHandler` with `NoContactResponse => true` and `OnStartedTouching<TManifold>(Contacts<TManifold> contacts)`.
- UI: `Entity.Get<UIComponent>().Page.RootElement.FindVisualChildOfType<TextBlock>("Name")`; `Button.Click += ...`.

## Pitfalls
1. Xenko-era names (`Xenko.*`, `SiliconStudio.*`, `.xk*` files) are gone; use `Stride.*`.
2. `CharacterComponent` exists in both physics stacks: Bullet (`Stride.Physics`: SetVelocity/Jump/Teleport) vs Bepu (`Stride.BepuPhysics`: Move/TryJump/Position). Match the project.
3. Bullet triggers (`PhysicsComponent.NewCollision()`, `ProcessCollisions`) do not apply to Bepu; use `IContactHandler`.
4. 4.4 reworked the Bepu CharacterComponent (breaking): re-check properties and behavior.
5. 4.4 renames: `GameSettings.Configuration.Get<T>` -> `GameSettings.GetOrCreateConfiguration<T>`; `Utilities.AllocateMemory/FreeMemory` -> `MemoryUtilities.Allocate/Free`.
6. 4.4 removed OpenGL, dropped 32-bit, needs Vulkan 1.3 and D3D12 Enhanced Barriers; the new SDSL compiler may break custom shaders.
7. Target .NET 10 (4.3+), not net6.0/net8.0.
8. Never `Task.Run` engine work; it leaves the main thread. Use `Script.AddTask`.
9. Unity-isms (`MonoBehaviour`, `void Update()` without override, `Time.deltaTime`, `KeyCode`) do not compile.
10. No built-in multiplayer; use community libraries or your own sockets.
11. String asset URLs break on rename; 4.4 has a generated `Assets` class: `Content.Load(Assets.Models.Player)`.

## Roblox to Stride
- Workspace tree -> Scene entity hierarchy
- Part -> Entity + ModelComponent + Bepu StaticComponent/BodyComponent
- Model -> Prefab (`Instantiate()`)
- Script/LocalScript -> SyncScript / AsyncScript (all local)
- RemoteEvent -> not built in
- DataStore -> your own JSON files
- Humanoid -> Bepu CharacterComponent
- Heartbeat -> `Update()`; physics step -> `ISimulationUpdate`
- task.wait -> `await Task.Delay(ms)` / `Script.NextFrame()`
- ScreenGui -> UIComponent + UI page
- UserInputService -> `Input`

## Skeleton
```csharp
using Stride.BepuPhysics;
using Stride.Core.Mathematics;
using Stride.Engine;
using Stride.Input;

public class PlayerController : SyncScript
{
    public required CharacterComponent Character { get; set; }
    public float Speed { get; set; } = 6f;

    public override void Update()
    {
        var move = Vector3.Zero;
        if (Input.IsKeyDown(Keys.W)) move.Z += 1;
        if (Input.IsKeyDown(Keys.S)) move.Z -= 1;
        if (Input.IsKeyDown(Keys.A)) move.X += 1;
        if (Input.IsKeyDown(Keys.D)) move.X -= 1;
        if (move != Vector3.Zero) move.Normalize();

        Character.Speed = Speed;
        Character.Move(move);
        if (Input.IsKeyPressed(Keys.Space)) Character.TryJump();
    }
}
```

## Verification
- Build the game project (`dotnet build` on the platform project, or Game Studio Build) and fix compile errors first.
- Run with Game Studio Play (F5) and watch the Output/Log panel.
- If nothing was built or run, say so; do not claim it works.
