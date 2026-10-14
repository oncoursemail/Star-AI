---
name: engine-sbox
description: s&box (Facepunch, Source 2, C#) scene system 2026. Use for Component/GameObject code, [Sync]/[Rpc.*] networking, Razor PanelComponent UI, input actions, triggers and traces.
---
# engine-sbox
## Scope
s&box on Steam (full release April 28, 2026; rolling weekly updates, no version numbers). C# with hotload; engine code MIT, Source 2 core proprietary. Check the project's last update and the docs page dates first; the API still moves.

## Core model
- Scene -> GameObject (transform, tags, children) -> Component. The old Entity system is gone.
- Component methods: OnLoad (async), OnAwake, OnStart, OnEnabled, OnUpdate, OnPreRender, OnFixedUpdate, OnDisabled, OnDestroy.
- Host + clients. GameObjects have an owner; `IsProxy` is true where you are not the owner.
- Per-scene systems: `GameObjectSystem` with `Listen(Stage.PhysicsStep, ...)`.
- Source units (inches), Z-up.

## Idioms
- `[Property]` exposes to the inspector; `[RequireComponent]` auto-adds a sibling.
- Transforms: `WorldPosition`, `WorldRotation`, `LocalPosition`; `Time.Delta`.
- Components: `AddComponent<T>()`, `GetComponent<T>()`, `GetOrAddComponent<T>()`, `GetComponentInChildren<T>()`.
- Objects: `prefab.Clone(pos)`, `go.Destroy()`, `go.Tags.Add("x")`, `go.IsValid()`.
- Input: `Input.Down("jump")`, `Input.Pressed("attack1")`, `Input.AnalogMove`, `Input.AnalogLook` (action names from Project Settings).
- Async: `await Task.DelaySeconds(1f)`, `await Task.Frame()`; timers `TimeSince`.
- Networking: `go.NetworkSpawn()`, `NetworkMode.Object`, `[Sync]`, `[Sync(SyncFlags.FromHost)]`, `[Change(nameof(OnX))]`, `NetList<T>`, `[Rpc.Broadcast]`, `[Rpc.Owner]`, `[Rpc.Host]`, `NetFlags.Unreliable`, `Rpc.Caller`.
- Triggers: collider IsTrigger + `Component.ITriggerListener` (`OnTriggerEnter(Collider other)`).
- Traces: `Scene.Trace.Ray(start, end).WithoutTags("player").Run()`.
- UI: Razor `@inherits PanelComponent`, values in `BuildHash()`, `StateHasChanged()`.
- Save: `FileSystem.Data.WriteJson(...)`, `Storage.CreateEntry("save")`.

## Pitfalls
1. Legacy entity code (`[Net]`, `[ClientRpc]`, `Entity`, `AnimatedEntity`, `Simulate(IClient)`, `Game.Current`) no longer compiles. Use Component + `[Sync]` + `[Rpc.*]`.
2. Early scene-system `[Broadcast]`/`[Authority]` became `[Rpc.Broadcast]`/`[Rpc.Owner]`/`[Rpc.Host]`.
3. Setting `[Sync]` on a proxy is silently dropped; owner sets it, or use `SyncFlags.FromHost` for host state.
4. `[Sync]` needs `NetworkMode.Object`; the default Snapshot mode syncs once.
5. Changes after `NetworkSpawn()` need `Network.Refresh()`.
6. Missing `if (IsProxy) return;` makes every client drive every player.
7. `[Change]` does not fire on collection edits; use `NetList`/`NetDictionary` `OnChanged`.
8. Razor UI only rebuilds when `BuildHash()` changes.
9. API whitelist: `System.IO`, `Console.WriteLine` give `SB1000`; use `FileSystem.Data`, `Log.Info`.
10. Older code uses `Transform.Position`; current docs use `WorldPosition`.
11. Validate `[Rpc.Host]` calls on the host (`Rpc.Caller`); clients can send anything.
12. Standalone export is preview: needs Valve approval and a Facepunch license; replace Citizen models.

## Roblox to s&box
- Workspace tree -> Scene GameObjects
- Part -> GameObject + ModelRenderer + BoxCollider (+ Rigidbody)
- Model -> prefab (`Clone`)
- Script -> host-side component logic / `[Rpc.Host]`
- LocalScript -> owner-only code behind `IsProxy`
- ModuleScript -> C# classes / GameObjectSystem
- RemoteEvent -> `[Rpc.Host]` / `[Rpc.Broadcast]`
- DataStore -> FileSystem.Data / Storage / stats services
- Humanoid -> PlayerController
- Heartbeat -> OnUpdate / OnFixedUpdate
- CollectionService tags -> GameObject.Tags
- Attributes -> `[Property]` / `[Sync]`
- ScreenGui -> PanelComponent (Razor)
- task.wait -> `await Task.DelaySeconds(n)`
- Studio playtest -> editor Play + extra local clients

## Skeleton
```csharp
using Sandbox;

public sealed class Mover : Component
{
    [Property] public float Speed { get; set; } = 300f;
    [Sync( SyncFlags.FromHost )] public int Score { get; set; }

    protected override void OnFixedUpdate()
    {
        if ( IsProxy ) return;
        var move = Input.AnalogMove;
        if ( !move.IsNearZeroLength )
            WorldPosition += move.Normal * Speed * Time.Delta;
    }

    [Rpc.Host]
    public void AddScore()
    {
        Score++;
    }
}
```

## Verification
- Save the file; the editor hotloads. Check the editor console for compile errors (including SB1000).
- Press Play; for multiplayer, start extra local clients from the editor and check owner vs proxy behavior.
- Report only what you actually ran; otherwise mark the code "not run".
