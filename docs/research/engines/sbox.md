# s&box (Source 2, Facepunch): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Steam release (launched April 28, 2026; rolling updates, no numbered versions; native Linux client since September 2026).** s&box costs $10 on Steam. The C# engine/editor is MIT-licensed (open-sourced Nov 2025); the Source 2 native core is proprietary prebuilt binaries. Facepunch takes no engine royalties on standalone exports.

## At a glance
| | |
|---|---|
| Best for | Multiplayer sandbox/party/shooter games for the s&box platform (sbox.game); Garry's Mod-style creations; quick C# iteration with hotload; the closest thing on this list to Roblox |
| Weak at | Mobile, console and web (PC only); standalone export is in preview and needs Valve approval plus a Facepunch license; API still changes often; code whitelist on the platform |
| Language(s) | C# (.NET 10 SDK for engine source builds), Razor (`.razor`) + SCSS for UI, ActionGraph (visual scripting), HLSL-style shaders and Shader Graph |
| Editor / tooling | s&box editor (`sbox-dev.exe`), Scene and Mapping tools, ModelDoc, AnimGraph, Movie Maker, Shader Graph; Visual Studio 2026 / Rider / VS Code; editor MCP server |
| Platforms (export) | Windows (primary), Linux (native Steam client 2026), macOS Apple Silicon (engine from source); standalone PC export in preview; no console or mobile |
| License / cost | $10 game; engine code MIT; Play Fund revenue share on the platform; no royalties for approved standalone games (Steam's normal cut applies) |
| Roblox-likeness | high: hosted platform with discovery, built-in multiplayer with host/owner model, player accounts, Play Fund monetization, server browser; C# instead of Luau |

## Architecture and lifecycle
- **Scene system** (similar to Unity/Godot): `Scene` → `GameObject` (transform, tags, children) → `Component`s. The old entity system (`Entity`, `[Net]`, `[ClientRpc]`, `Simulate(IClient)`, `Game.Current`) was replaced in 2023-24 and **is gone**.
- **Component** methods (override in your `Component` subclass):
  - `OnLoad()` (async; runs during the loading screen, even when inactive).
  - `OnAwake()` (once, when created and the GameObject is enabled).
  - `OnStart()` (first enable, before first `OnFixedUpdate`).
  - `OnEnabled()` / `OnDisabled()`.
  - `OnUpdate()` (every frame), `OnPreRender()` (not on dedicated servers), `OnFixedUpdate()` (fixed timestep; use it for movement).
  - `OnDestroy()` (always called).
- A component is only active if its GameObject and all ancestors are enabled.
- **GameObjectSystem**: per-scene systems derived from `GameObjectSystem` (or `GameObjectSystem<T>` with `T.Current`) that hook frame stages with `Listen(Stage.PhysicsStep, order, Method, "name")`. Access with `Scene.Get<T>()`.
- **Scene events**: interfaces such as `Component.ITriggerListener`, `Component.INetworkListener`, `IScenePhysicsEvents` (`PrePhysicsStep`/`PostPhysicsStep`), `ISceneStartup`, `PlayerController.IEvents`.
- **Hotload**: code changes recompile and swap in milliseconds while the game runs.
- **Async**: tasks run on the main thread like coroutines: `await Task.DelaySeconds(1f)`, `await Task.Frame()`, `Task.DelayRealtimeSeconds`. Use `TimeSince`/`TimeUntil` structs for timers.
- Under the hood: Source 2 rendering, resources, physics and audio (the same engine family as CS2, Half-Life: Alyx and Dota 2).

## Project layout
```
mygame/
  mygame.sbproj          # project config (type: game or addon), package ident, input actions, collision rules
  Assets/                # scenes (.scene), prefabs (.prefab), models (.vmdl), materials (.vmat), sounds, maps
  Code/                  # C# components, .razor UI, .scss styles  -> compiled into the game assembly
  Editor/                # editor-only code (no whitelist)
  Libraries/             # libraries pulled from sbox.game
  ProjectSettings/       # Input, Collision, etc. (also edited via Project Settings)
```
- Project types: **game** (has a startup scene) and **addon** (content for other games).
- Packages live on **sbox.game** (`org.ident`). There is no Workshop install step: players stream content on demand.

## Scripting idioms
```csharp
using Sandbox;

public sealed class Spinner : Component
{
    [Property] public float DegreesPerSecond { get; set; } = 90f;   // shown in inspector
    [Property] public GameObject Target { get; set; }

    protected override void OnUpdate()
    {
        WorldRotation *= Rotation.FromYaw( DegreesPerSecond * Time.Delta );
    }
}
```
- Transforms: `WorldPosition`, `WorldRotation`, `WorldScale`, `LocalPosition`, `LocalRotation` on both `GameObject` and `Component`. Older code used `Transform.Position` / `GameObject.Transform.Position`; current docs use `WorldPosition`.
- Components: `AddComponent<T>()`, `GetOrAddComponent<T>()`, `GetComponent<T>()`, `GetComponentInChildren<T>()`, `GetComponentsInParent<T>()`, `Components.Get<T>( FindMode.EnabledInSelfAndDescendants )`; `[RequireComponent] ModelRenderer Body { get; set; }` auto-creates a sibling.
- GameObjects: `new GameObject()`, `go.Clone()` (prefab instantiate: `prefabGo.Clone( position )`), `go.Destroy()`, `DestroyGameObject()`, `go.Enabled = false`, `go.Tags.Add("player")`, `Scene.Directory.FindByName("Cube")`, `Scene.GetAll<CameraComponent>()`.
- Validity: always `go.IsValid()` / `component.IsValid()` before using stored references.
- Logging and debug: `Log.Info(...)`, `DebugOverlay.ScreenText(...)`, `Assert.NotNull(...)`.
- Console variables: `[ConVar]`; commands: `[ConCmd]`.
- **API whitelist**: platform games cannot use `System.IO`, `Console.WriteLine`, reflection-heavy or unsafe APIs (`SB1000` compiler error). Use `FileSystem.Data`, `Log.Info`, `Http.RequestStringAsync`. Editor code and approved standalone games may opt out.

## Pitfalls (what AI answers get wrong)
1. **Legacy entity-system code**: `public partial class Player : AnimatedEntity`, `[Net] public int Score { get; set; }`, `[ClientRpc]`, `[ServerCmd]`, `Simulate( IClient cl )`, `Game.Current`, `Sandbox.Game` base class, `Entity.All`, `BaseNetworkable`. None of this exists in the scene system. Use `Component`, `[Sync]`, `[Rpc.Broadcast]`/`[Rpc.Owner]`/`[Rpc.Host]`, `OnFixedUpdate`, `Scene.GetAll<T>()`.
2. **`[Broadcast]` / `[Authority]` attributes** from early scene-system builds became `[Rpc.Broadcast]`, `[Rpc.Owner]`, `[Rpc.Host]` with `NetFlags` (`NetFlags.Unreliable`, `NetFlags.HostOnly`, `NetFlags.OwnerOnly`, `SendImmediate`, `DiscardOnDelay`).
3. **`[Sync]` is owner-controlled**: setting it while `IsProxy` is true is silently discarded. Host-owned shared state needs `[Sync( SyncFlags.FromHost )]`. `[Sync]` only works on `NetworkMode.Object` GameObjects (the default is `NetworkMode.Snapshot`). It guarantees the latest value, not every intermediate value.
4. **`[Change]` does not fire on collection edits**: use `NetList<T>` / `NetDictionary<K,V>` and their `OnChanged` event.
5. **Network spawn timing**: `go.NetworkSpawn()` sends the hierarchy as it is at that moment. Later added components, children or enabled-state changes need `Network.Refresh()`.
6. **Gate input by ownership**: in `OnUpdate`/`OnFixedUpdate` start with `if ( IsProxy ) return;`. Otherwise every client drives every player.
7. **Input uses action names** from Project Settings: `Input.Down( "jump" )`, `Input.Pressed( "attack1" )`, `Input.AnalogMove`, `Input.AnalogLook`. There is no `Input.GetKey(KeyCode...)`. Raw keyboard access is a separate API (`gameplay/input/raw-input` docs).
8. **Units are Source units (inches)**: player speeds are a few hundred units/s and gravity is large. Z is up; forward is +X (`Vector3.Forward`).
9. **Trigger events from player controllers** fire twice (body capsule + feet box). Deduplicate by GameObject root.
10. **Whitelist**: `System.IO.File`, `Console`, `Thread`, `Task.Run` heavy work and similar will not compile for platform games.
11. **Standalone export** is preview: needs Valve approval and a Facepunch standalone license. Citizen player models and clothing must be replaced before shipping standalone.
12. `PlayerController.IEvents.PostCameraSetup` is now `[Obsolete]`: implement `ICameraModifier` instead.

## Rendering
- Source 2 renderer: PBR (`.vmat` materials), dynamic lights with shadows, indirect light volumes, post-processing stack (`PostProcessVolume`, tone mapping, film grain, custom post-processes), decals (`DecalDefinition`), particle effects, beams/tracers, terrain, sprites.
- Shaders: Source 2 `.shader` files (HLSL-like, FEATURES/COMMON/VS/PS blocks) and **Shader Graph** (custom nodes, subgraphs). Bindless API, GPU instancing, command lists.
- Components: `ModelRenderer`, `SkinnedModelRenderer` (AnimGraph), `CameraComponent`, `PointLight`/`SpotLight`/`DirectionalLight`, `EnvmapProbe`, `SkyBox2D`.
- Movie Maker for cinematics and video export.

## Physics
- Source 2 physics (Rubikon). Components: `Rigidbody`, `BoxCollider`, `SphereCollider`, `CapsuleCollider`, `ModelCollider`, `HullCollider`, `PlaneCollider`, joints, `CharacterController` (simple kinematic mover) and `PlayerController` (physics-based first/third person controller with built-in input, camera and Citizen animator; drive manually via `WishVelocity` and `EyeAngles` in `OnFixedUpdate`).
- Triggers: tick **Is Trigger** on a collider (`box.IsTrigger = true;`) and implement `Component.ITriggerListener` on a component of that GameObject (or a child):
```csharp
public sealed class PickupZone : Component, Component.ITriggerListener
{
    public void OnTriggerEnter( Collider other ) => Log.Info( $"{other.GameObject.Name} entered" );
    public void OnTriggerExit( Collider other ) { }
}
```
  Polling alternative: `collider.Touching`.
- Traces: `Scene.Trace.Ray( start, end ).WithoutTags( "player" ).WithCollisionRules( "bullet" ).Run()` returns `SceneTraceResult` (`Hit`, `EndPosition`, `GameObject`, `Normal`). Also `.Sphere( radius, start, end )`, `.Box(...)`.
- Collision rules (tag-vs-tag matrix) live in Project Settings > Collision.
- Physics hooks: `IScenePhysicsEvents.PrePhysicsStep` / `PostPhysicsStep`; `GameObjectSystem` stage `Stage.PhysicsStep`.

## Input
- `Input.Down( "action" )`, `Input.Pressed(...)`, `Input.Released(...)` (case-insensitive action names defined in Project Settings > Input), `Input.AnalogMove` (Vector3, WASD/stick), `Input.AnalogLook` (Angles, mouse/stick), `Input.EscapePressed` (override pause menu), controller glyphs (`Input.GetGlyph`), raw input API, VR input.
- The `PlayerController` component already reads input for its owner; disable its input tab to drive it yourself.

## UI
- **Razor panels**: a `PanelComponent` (root, added to a GameObject with a `ScreenPanel` or `WorldPanel`) plus child `Panel`s written in `.razor` with SCSS stylesheets (flexbox layout, not a browser).
```razor
@using Sandbox;
@using Sandbox.UI;
@inherits PanelComponent

<root>
    <div class="score">Score: @Score</div>
</root>

@code
{
    [Property] public int Score { get; set; }
    protected override int BuildHash() => System.HashCode.Combine( Score );
}
```
- The panel rebuilds only when `BuildHash()` changes (or on `StateHasChanged()` / pointer events). Forgetting `BuildHash` is the #1 "UI does not update" bug.
- Alternatives: `HudPainter` / painter API for immediate-mode HUD drawing; `VirtualGrid` for long lists; localization tokens.

## Networking and multiplayer
- Built in and peer-hosted: one player (or a dedicated server) is the **host**; others are clients. `NetworkHelper` component can start a server on scene load (`StartServer`) and spawn a `PlayerPrefab` per connection at `SpawnPoint`s.
- `Component.INetworkListener` (`OnActive( Connection channel )` etc.) for custom spawning: clone the prefab, then `go.NetworkSpawn( channel )` to give ownership.
- **Network modes** per GameObject: `NetworkMode.Never`, `NetworkMode.Snapshot` (default; sent once in the join snapshot), `NetworkMode.Object` (own networked object with sync + RPCs).
- **Ownership**: owner sends transform and `[Sync]` values; `IsProxy` is true on everyone who is not the owner. Transform interpolation is on by default (`Network.Interpolation = false`, `Network.ClearInterpolation()` for teleports).
- **Sync**: `[Sync]`, `[Sync( SyncFlags.FromHost )]`, `[Sync( SyncFlags.Interpolate )]`, `SyncFlags.Query`; `[Change( nameof(OnX) )]` callbacks with `(old, new)`; `NetList<T>`, `NetDictionary<K,V>`.
- **RPCs**: `[Rpc.Broadcast]` (everyone), `[Rpc.Owner]` (owner, or host if unowned), `[Rpc.Host]` (host only); static RPCs allowed; `Rpc.Caller` identifies the sender; `Rpc.FilterInclude(...)` / `Rpc.FilterExclude(...)` scopes; arguments use the same types as `[Sync]`.
- Also: host migration, network visibility, connection permissions, dedicated servers (with server-side code), chat, HTTP and WebSockets, custom snapshot data. Test locally by launching extra clients from the editor ("testing multiplayer" docs).
- Security model: clients can call `[Rpc.Host]` methods with arbitrary arguments. Validate on the host exactly as you would a Roblox RemoteEvent (`Rpc.Caller`, ownership, rate limits).

## Save data
- `FileSystem.Data` (per-game data folder): `FileSystem.Data.WriteAllText("player.txt", ...)`, `ReadAllText`, `FileExists`, `WriteJson`/`ReadJson`.
- **Storage (UGC)**: `Storage.CreateEntry( "save" )` → `entry.Files.WriteJson( "data.json", obj )`, `entry.SetMeta(...)`, thumbnails, optional Steam Workshop sharing.
- Platform services: **Stats**, **Leaderboards**, **Achievements**, auth tokens (`sbox.game` backend). There is no Roblox-style server DataStore; persistent per-player data lives on the client or in your own web backend.

## Performance
- Movement and traces in `OnFixedUpdate` (fewer traces than per-frame). Avoid `Scene.GetAll<T>()` every frame in hot paths; cache or use a `GameObjectSystem`.
- Use `NetFlags.Unreliable` for frequent cosmetic RPCs. Keep `[Sync]` properties small and unmanaged. Use `SyncFlags.Interpolate` instead of sending every frame.
- Use prefabs and `NetworkMode.Snapshot` for static map props (no per-object network cost).
- `OnPreRender` is skipped on dedicated servers; do not put gameplay there.

## Build and export
- **Platform release**: Project > upload/release to sbox.game (organization + package ident); players launch it from the s&box menu. Play Fund opt-in under Configure > Edit Features.
- **Standalone** (preview): Project > Export… wizard (icon, splash, Steam App ID) → executable folder. Requires Valve approval (email Facepunch with a Steam store page) and a standalone license. PC only. No whitelist in standalone builds.
- Building the engine from source: clone `Facepunch/sbox-public`, run `Setup.bat` (Windows) or `./Setup.sh` (Linux/macOS Apple Silicon); needs .NET 10 SDK.

## Source 2 modding context (other Valve games)
- **Half-Life: Alyx Workshop Tools**: Hammer (Source 2), ModelDoc, Lua VScript for map logic; addons go to the Steam Workshop.
- **Counter-Strike 2 Workshop Tools**: Hammer for maps; scripting through the `point_script` entity referencing **cs_script** (JavaScript/TypeScript `.vjs`) files, with Valve's "Hello Gordon" tutorial and "script_zoo" example map. Launch with `-tools`.
- **Dota 2 Workshop Tools**: custom games with Lua VScript (server logic) and Panorama UI (XML/CSS/JS), Hammer maps.
- These are separate toolchains from s&box. s&box uses its own scene editor and mapping mode (Hammer-like shortcuts), and can still load Hammer `.vmap` maps through the `MapInstance` component (map entities become GameObjects).

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `[Net]`/`Entity`/`ClientRpc` do not compile | Legacy entity-system code | Port to `Component` + `[Sync]` + `[Rpc.*]` |
| Every client moves every player | No ownership check | `if ( IsProxy ) return;` at the top of input code |
| `[Sync]` value never reaches others | Set on a proxy, or GameObject is `NetworkMode.Snapshot` | Set it on the owner (or `SyncFlags.FromHost` on host); use `NetworkMode.Object` / `NetworkSpawn()` |
| New child/component missing on clients | Added after `NetworkSpawn()` | Call `Network.Refresh()` |
| Razor HUD never updates | `BuildHash()` does not include the changing values | Add them to `BuildHash` or call `StateHasChanged()` |
| `SB1000: 'x' is not allowed` | API whitelist | Use the s&box equivalent (`FileSystem.Data`, `Log.Info`, `Http`) |
| Trigger fires twice for the player | Body + feet colliders | Track by root GameObject or tag |
| Object teleports smoothly instead of snapping | Transform interpolation | `Network.ClearInterpolation()` after setting the position |
| Stored reference crashes after destroy | Object destroyed | Check `IsValid()` |
| Movement jittery or fast on high FPS | Moving in `OnUpdate` with physics | Move in `OnFixedUpdate`, scale by `Time.Delta` |

## Mapping from Roblox
| Roblox | s&box | Notes |
|---|---|---|
| Workspace / Instance tree | `Scene` / `GameObject` hierarchy | |
| Part | GameObject + `ModelRenderer` (box model) + `BoxCollider` (+ `Rigidbody`) | Or mapping-mode meshes |
| Model | Prefab (`.prefab`) / parent GameObject | `prefab.Clone( pos )` |
| Script (server) | Component code run on host (`Networking.IsHost`) or `[Rpc.Host]` handlers | One codebase for host and clients |
| LocalScript | Same component with `if ( IsProxy ) return;` for owner-only logic | |
| ModuleScript | Plain C# classes, static classes, `GameObjectSystem<T>` | |
| RemoteEvent | `[Rpc.Host]` (client→host), `[Rpc.Broadcast]` (host→all), `[Rpc.Owner]` | Validate on host |
| DataStore | `FileSystem.Data` / `Storage` (client-side), Stats/Leaderboards services, or own backend | No server DataStore |
| Players | `Connection.All`, `Connection.Local`, `INetworkListener.OnActive` | |
| Humanoid | `PlayerController` (Citizen) / `CharacterController` | |
| RunService.Heartbeat / RenderStepped | `OnUpdate` / `OnFixedUpdate` / `OnPreRender` | |
| TweenService | `async Task` loops with `Easing` + `TimeSince`, Movie Maker for cutscenes | |
| CollectionService tags | `GameObject.Tags` + `Scene.FindAllWithTag(...)` / trace tag filters | |
| Attributes | `[Property]` (editor), `[Sync]` (networked) | |
| ScreenGui | `PanelComponent` (Razor) on a `ScreenPanel` | |
| UserInputService | `Input` with named actions | |
| task.wait | `await Task.DelaySeconds( n )` | Main thread, like coroutines |
| Studio playtest | Editor Play; extra local clients for multiplayer | |
| Publishing | Release to sbox.game; standalone Steam export (preview, approval) | |

## Minimal example
Networked player that moves with WASD (`Input.AnalogMove`) and collects coins; score is host-authoritative.
```csharp
using Sandbox;

public sealed class Mover : Component
{
    [Property] public float Speed { get; set; } = 300f;              // inches per second
    [Sync( SyncFlags.FromHost )] public int Score { get; set; }      // host owns the score

    protected override void OnFixedUpdate()
    {
        if ( IsProxy ) return;                                       // only the owner drives
        var move = Input.AnalogMove;
        if ( !move.IsNearZeroLength )
            WorldPosition += move.Normal * Speed * Time.Delta;
    }

    [Rpc.Host]
    public void AddScore()
    {
        Score++;                                                     // runs on host; synced to all
    }
}

public sealed class Coin : Component, Component.ITriggerListener
{
    public void OnTriggerEnter( Collider other )
    {
        if ( !Networking.IsHost ) return;                            // host decides
        var mover = other.GameObject.Root.GetComponentInChildren<Mover>();
        if ( !mover.IsValid() ) return;
        mover.AddScore();
        GameObject.Destroy();
    }
}
```
Setup: the Mover GameObject has a collider and is spawned per player by `NetworkHelper` (`NetworkMode.Object`). Coin has a `SphereCollider` with **Is Trigger** on. A Razor `PanelComponent` reads `Score` (include it in `BuildHash`).

## Sources
- https://sbox.game/dev/doc/ and https://github.com/Facepunch/sbox-docs (official docs source; pages below are paths in that repo)
- docs/scene/components/component-methods.md (OnLoad/OnAwake/OnStart/OnEnabled/OnUpdate/OnPreRender/OnFixedUpdate/OnDisabled/OnDestroy)
- docs/scene/components/index.md (AddComponent, GetComponent variants, [Property], [RequireComponent], Destroy)
- docs/scene/components/async.md (Task.DelaySeconds, Task.Frame, main-thread tasks)
- docs/scene/gameobjectsystem.md (GameObjectSystem, Listen(Stage...))
- docs/networking/sync-properties.md ([Sync], [Change], SyncFlags, NetList/NetDictionary, IsProxy discard)
- docs/networking/rpc-messages.md ([Rpc.Broadcast], [Rpc.Owner], [Rpc.Host], NetFlags, Rpc.Caller, filters)
- docs/networking/networked-objects.md (NetworkSpawn, NetworkMode, interpolation, Network.Refresh)
- docs/networking/network-helper.md (NetworkHelper, IsProxy movement, INetworkListener)
- docs/gameplay/input/index.md (Input.Down/Pressed/Released, AnalogMove/AnalogLook, EscapePressed)
- docs/physics/triggers.md, docs/physics/tracing.md, docs/physics/physics-events.md (ITriggerListener, Scene.Trace, IScenePhysicsEvents)
- docs/ui/razor-panels/index.md (PanelComponent, BuildHash, StateHasChanged)
- docs/assets/storage-ugc.md, docs/assets/file-system.md (Storage.CreateEntry, FileSystem.Data)
- docs/code/code-basics/api-whitelist.md, docs/code/code-basics/cheat-sheet.md (whitelist, SB1000, common API)
- docs/exporting/index.md (standalone preview, Valve approval, no royalties, PC only)
- docs/getting-started/index.md, faq.md, monetization.md, system-requirements.md ($10 on Steam, Play Fund, requirements)
- docs/scene/components/reference/player-controller.md (PlayerController, WishVelocity/EyeAngles, IEvents obsolete member)
- https://github.com/Facepunch/sbox-public (MIT engine source, .NET 10 SDK, Setup.bat/Setup.sh, Linux and macOS Apple Silicon)
- https://en.wikipedia.org/wiki/S%26box (full release April 28, 2026; MIT since Nov 2025) [community/secondary]
- https://www.gamingonlinux.com/2026/09/s-box-from-facepunch-now-has-native-linux-support-on-steam/ (native Linux on Steam, Sept 2026) [community]
- https://developer.valvesoftware.com/wiki/Point_script_(Source_2) and https://developer.valvesoftware.com/wiki/Counter-Strike_2_Workshop_Tools/Scripting/Hello_Gordon (CS2 point_script / cs_script)

## Confidence and gaps
- High: scene/component API, networking attributes, input, triggers, traces, Razor UI, storage, export policy (all from current official docs repo, updated 2026).
- Medium: `Networking.IsHost`, `Connection.All`, `Scene.FindAllWithTag`, `GameObject.Root`, `Rotation.FromYaw`, `ScreenPanel` (common API, not re-read this pass); exact Source units and axes (Z-up, +X forward, inches) from Source convention.
- Not verified: HL:Alyx and Dota 2 tool details (general knowledge; check the Valve Developer Community wiki); whether standalone export has left preview after this date.
- s&box has no version numbers; behavior can change between weekly updates. Check the project's last update date and the docs `updated:` field.
