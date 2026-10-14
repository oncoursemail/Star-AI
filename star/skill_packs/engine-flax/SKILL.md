---
name: engine-flax
description: Flax Engine 1.12 (C#/C++/Visual Scripting). Use for Flax Script lifecycle, Actors, CharacterController, triggers, UIControl, NetworkReplicator/NetworkRpc and Game Cooker builds.
---
# engine-flax
## Scope
Flax Engine 1.12 (build 1.12.6912, May 2026; 1.13 in development). Editor needs .NET SDK 10, C# 14. Check the `.flaxproj` engine version first. Free; 4% royalty above $250k gross per calendar quarter.

## Core model
- Scene tree of typed Actors (StaticModel, Camera, lights, colliders, RigidBody, CharacterController, UICanvas).
- Scripts (`FlaxEngine.Script`) attach to actors; many per actor; lifetime follows the actor.
- Events: OnAwake, OnStart, OnEnable, OnUpdate, OnLateUpdate, OnFixedUpdate, OnLateFixedUpdate, OnDisable, OnDestroy (override; no base call needed).
- JSON serialization: public members or `[Serialize]` are saved; `[NoSerialize]` opts out.
- Units are centimeters; Y-up.

## Idioms
- `Actor` is the owner; `Actor.Position`, `Actor.Orientation`, `Actor.LocalPosition`; cast with `Actor.As<CharacterController>()`.
- Find: `Actor.GetScript<T>()`, `Actor.AddScript<T>()`, `Level.FindScript<T>()`; typed public fields for references.
- Spawn/destroy: `PrefabManager.SpawnPrefab(prefab, parent)`, `Destroy(obj)` / `Destroy(obj, seconds)`.
- Time: `Time.DeltaTime`. Log: `Debug.Log`.
- Input: `Input.GetKey(KeyboardKeys.W)`, `GetKeyDown`, `GetKeyUp`; virtual `Input.GetAction("Fire")`, `Input.GetAxis("Horizontal")`, `InputEvent`/`InputAxis` (Dispose them).
- Character: `CharacterController.Move(displacement)` / `SimpleMove(speed)`, `IsGrounded`, `Velocity`.
- Triggers: collider actor with Is Trigger; subscribe `TriggerEnter += Handler` in OnEnable, `-=` in OnDisable; handler takes `PhysicsColliderActor`.
- UI: `UIControl.Get<Label>().Text = "..."`; `button.Clicked += ...`.
- Networking: `NetworkManager.StartHost()/StartServer()/StartClient()`; `NetworkReplicator.AddObject(this)` in OnEnable; `[NetworkReplicated]` fields; `[NetworkRpc(Server = true)]` / `[NetworkRpc(Client = true)]`.
- Save: `JsonSerializer.Serialize(obj)` + files under `Globals.ProductLocalFolder`.

## Pitfalls
1. Unity-isms fail: `MonoBehaviour`, `void Update()`, `transform`, `GetComponent`, `Time.deltaTime`, `KeyCode`. Use `Script`, `public override void OnUpdate()`, `Actor`, `GetScript`, `Time.DeltaTime`, `KeyboardKeys`.
2. No magic `OnTriggerEnter(Collider)` override; subscribe to the collider's `TriggerEnter` event.
3. Colliders are actors, not components; mesh colliders cannot be triggers.
4. Units are cm: speeds around 300-800, gravity about -981.
5. `Vector3` uses Real (double with large worlds); use `Float3` for float-only data.
6. Networking needs `Tags["Network"]` in the module `*.Build.cs` and `NetworkReplicator.AddObject`; otherwise RPCs do nothing.
7. 1.12 added a `Gamma Color Space` setting; linear workflow migration needs sRGB reimport and post-FX retune.
8. 1.12 renames: `GPUContext::ClearState` -> `ResetState`; `IsRegularWindow` -> `WindowType`; `GPUTimerQuery` deprecated.
9. 1.11: 24-bit depth + stencil; `ISceneRenderingListener` no longer mutex-guarded.
10. Web export (1.12) is experimental and has no C# support.
11. C++ scripts must set `_tickUpdate = true` to receive OnUpdate.

## Roblox to Flax
- Workspace tree -> Scene actor hierarchy
- Part -> StaticModel + BoxCollider (RigidBody parent for dynamic)
- Model -> Prefab
- Script/LocalScript -> Script (check `NetworkManager.IsServer` / ownership)
- RemoteEvent -> `[NetworkRpc]`
- DataStore -> JSON in `Globals.ProductLocalFolder`
- Humanoid -> CharacterController + AnimatedModel
- Heartbeat -> OnUpdate; physics -> OnFixedUpdate
- CollectionService tags -> Actor Tags
- ScreenGui -> UICanvas + UIControl
- UserInputService -> Input + Input Settings

## Skeleton
```csharp
using FlaxEngine;

public class PlayerMove : Script
{
    public float Speed = 600.0f; // cm/s
    private CharacterController _controller;

    public override void OnStart()
    {
        _controller = Actor.As<CharacterController>();
    }

    public override void OnUpdate()
    {
        var input = new Vector3(
            (Input.GetKey(KeyboardKeys.D) ? 1 : 0) - (Input.GetKey(KeyboardKeys.A) ? 1 : 0),
            0,
            (Input.GetKey(KeyboardKeys.W) ? 1 : 0) - (Input.GetKey(KeyboardKeys.S) ? 1 : 0));
        if (input.LengthSquared > 1) input.Normalize();
        _controller.SimpleMove(input * Speed);
    }
}
```

## Verification
- Save the script; the Flax Editor hot-reloads C#. Fix errors in the Output Log first.
- Attach the script to the actor, press Play in the editor, and test in the Game window.
- Build with Game Cooker. Report only what actually compiled or ran.
