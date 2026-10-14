# O3DE (Open 3D Engine): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 26.05.0 (May 27, 2026).** Free and open source (Apache-2.0 OR MIT dual license), no royalties.

## At a glance
| | |
|---|---|
| Best for | Large 3D simulations and games where you own the C++ code; robotics/digital twins (ROS 2 gems); teams who want an AAA-style modular engine without royalties |
| Weak at | Fast prototyping, small teams, mobile/web, beginners; long C++ build times; smaller community and fewer tutorials than Unity/Unreal/Godot |
| Language(s) | C++20 (engine, gems, components), Lua (Lua Script component), Script Canvas (visual scripting), Python (editor automation) |
| Editor / tooling | O3DE Editor, Project Manager, Asset Processor, Script Canvas editor, Lua Editor, `o3de.bat`/`o3de.sh` CLI, CMake (bundled since 26.05) |
| Platforms (export) | Windows, Linux, Android, iOS, macOS (support varies by gem; prebuilt installers for Windows 10+ and Ubuntu 22.04) |
| License / cost | Apache-2.0 OR MIT, free, source on GitHub |
| Roblox-likeness | low: no built-in avatars, accounts, hosting or publishing service; the Lua component is the only familiar part, and its API is EBus calls, not an Instance tree |

## Architecture and lifecycle
- Built from the Lumberyard codebase (which came from CryEngine). Most CryEngine code (`CryCommon`, `gEnv`) is legacy and is being deprecated; the 26.05 notes list a CryCommon clean-up.
- **Entity-Component system (AZ framework).** An *entity* is an ID plus a list of *components*. Components derive from `AZ::Component` and implement `Init()` (optional, once), `Activate()` and `Deactivate()`. Entities can be deactivated and reactivated without being destroyed, so `Deactivate()` must undo everything `Activate()` did.
- **Services**: components declare provided, required, dependent and incompatible services (`GetProvidedServices`, `GetRequiredServices`, ...). Activation order follows these dependencies.
- **Reflection**: each component has a static `Reflect(AZ::ReflectContext*)` that registers fields with the `SerializeContext` (save/load), the `EditContext` (Inspector UI) and the `BehaviorContext` (exposes methods and EBuses to Lua and Script Canvas). Anything not reflected to the BehaviorContext cannot be used from script.
- **EBus** (event bus) is the messaging system. *Request* buses are called by other code (`TransformBus::Event(entityId, &TransformInterface::SetWorldTM, tm)`); *notification* buses are listened to by handlers that `BusConnect()` and `BusDisconnect()`. Newer code also uses `AZ::Event` and `AZ::Interface`.
- **Tick**: per-frame work comes from `AZ::TickBus`. A handler implements `OnTick(float deltaTime, AZ::ScriptTimePoint time)` and should only stay connected while it needs ticks. `GetTickOrder()` returns presets such as `TICK_DEFAULT` (1000), `TICK_PHYSICS` (200) and `TICK_UI` (2000).
- **Gems** are modules (code + assets) enabled per project. Physics (PhysX5), Atom renderer gems, LyShine (UI), Multiplayer, ScriptCanvas, SaveData, Open Particle System (experimental, 26.05) and SkyAtmosphere (its own gem since 26.05) are all gems.
- **Prefabs** (`.prefab`, JSON) replaced Lumberyard *slices*. Levels are prefabs too. Spawning at runtime uses spawnables (`SpawnableScriptAssetRef` in Script Canvas).
- **Entity activation (26.05 change)**: the Inspector again has an initial Active/Inactive state per entity, and the state now **propagates to all descendants**, controlled by an Active State bitmask. The Transform component is now always active for the entity's lifetime.
- Lua components activate **after** all C++ components on the entity. The order between several Lua components on one entity is not guaranteed.

## Project layout
Typical project created by Project Manager or `o3de.bat create-project`:
```
MyProject/
  project.json            # project name, engine, enabled gems ("gem_names")
  CMakeLists.txt
  Gem/ (or Code/)         # project gem: Source/, Include/, *_files.cmake, module class
  Assets/                 # source assets (fbx, png, .lua, .scriptcanvas, .inputbindings)
  Levels/<Level>/<Level>.prefab
  Registry/*.setreg       # settings registry (JSON)
  ShaderLib/, Passes/     # optional Atom overrides
  Cache/<platform>/       # Asset Processor output (do not edit or commit)
  build/                  # CMake build tree (do not commit)
  user/                   # per-user settings, logs
```
- New C++ components: in 26.05 use **File > New Component** in the Editor (creates header/source and registers them with CMake), or the CLI template `scripts/o3de.bat create-from-template -dp <dir> -dn <Name> -tn DefaultComponent -kr -r ${GemName} <GemName>` (in PowerShell quote `'${GemName}'`). Register `MyComponent::CreateDescriptor()` in the gem module's `m_descriptors`.
- Lua `require` uses dotted, extension-less paths relative to the assets root: `require("Scripts.MyLibraryFile")`.

## Scripting idioms
### Lua Script component
A Lua script returns a table. `Properties` appear in the Inspector; `self.entityId` is the owning entity.
```lua
-- Scripts/Spinner.lua
local Spinner = {
    Properties = {
        DegreesPerSecond = { default = 90.0, suffix = "deg/s", description = "Spin speed" },
        Target = { default = EntityId(), description = "Optional other entity" },
    }
}

function Spinner:OnActivate()
    self.radPerSec = Math.DegToRad(self.Properties.DegreesPerSecond)
    self.tickBusHandler = TickBus.Connect(self)        -- start receiving OnTick
end

function Spinner:OnTick(deltaTime, timePoint)
    TransformBus.Event.RotateAroundLocalZ(self.entityId, self.radPerSec * deltaTime)
end

function Spinner:OnDeactivate()
    if self.tickBusHandler then
        self.tickBusHandler:Disconnect()               -- always disconnect handlers
        self.tickBusHandler = nil
    end
end

return Spinner
```
- Call request buses with `Bus.Event.Method(entityId, ...)` (one entity) or `Bus.Broadcast.Method(...)` (all handlers). Connect handlers with `Bus.Connect(self, busId)` and keep the returned handle to `Disconnect()`.
- To read another entity, wait for it: `self.h = EntityBus.Connect(self, otherId)` then do the work in `function X:OnEntityActivated()`. Querying too early returns nil.
- Logging: `Debug.Log("text")`.
- Math types are reflected: `Vector3(x, y, z)`, `Transform.CreateIdentity()`, `Math.DegToRad`.

### Input (Lua)
Input is mapped in an **Input Bindings** asset (`.inputbindings`, created in Asset Editor) referenced by an **Input** component. Scripts listen to named events:
```lua
function Mover:OnActivate()
    self.moveX = InputEventNotificationBus.Connect(self, InputEventNotificationId("MoveX"))
end
function Mover:OnHeld(value)       -- also OnPressed(value), OnReleased(value)
    -- value already includes the binding's "Event value multiplier" (e.g. A = -1, D = +1)
end
function Mover:OnDeactivate() self.moveX:Disconnect() end
```
With several inputs, `InputEventNotificationBus.GetCurrentBusId()` tells you which one fired (pattern used in the StartingPointInput gem scripts; check your version).

### C++ component skeleton
```cpp
#pragma once
#include <AzCore/Component/Component.h>
#include <AzCore/Component/TickBus.h>

namespace MyGem
{
    class SpinComponent
        : public AZ::Component
        , public AZ::TickBus::Handler
    {
    public:
        AZ_COMPONENT(MyGem::SpinComponent, "{0C09F774-DECA-40C4-8B54-3A93033EC381}");
        static void Reflect(AZ::ReflectContext* context);

    protected:
        void Activate() override { AZ::TickBus::Handler::BusConnect(); }
        void Deactivate() override { AZ::TickBus::Handler::BusDisconnect(); }
        void OnTick(float deltaTime, AZ::ScriptTimePoint time) override;

        float m_speed = 1.0f;
    };
}
```
`Reflect` registers `m_speed` with `SerializeContext` (`->Field("Speed", &SpinComponent::m_speed)`) and `EditContext` (`->DataElement(...)`). Generate a fresh UUID for every new component type.

### Script Canvas
Visual graphs attached through the Script Canvas component. Typical entry nodes: **On Graph Start**, **Input Handler** (event name), **On Tick**, **Lerp Between**, **Spawn** (with `SpawnableScriptAssetRef`). Variables with "Initial Value Source: From Component" become per-entity properties.

## Pitfalls (what AI answers get wrong)
1. **Lumberyard/CryEngine APIs**: `gEnv`, `CryLog`, `IEntitySystem`, `ISystem`, `CryCommon` headers, `.slice` files, `GameplayNotificationBus` cookbook code from 2017. Slices are gone (prefabs replaced them); CryCommon is being deprecated (26.05).
2. **PhysX 4 vs 5**: since 26.05 new projects use the **PhysX5** gem by default and PhysX 4 is deprecated, to be removed in the next release. Migrate with `<engine>/scripts/o3de.bat upgrade-physx-gem --project-path <project>`. Do not tell users to enable `PhysX` (4) for new projects.
3. **SkyAtmosphere moved to its own gem (26.05)**: projects using it must add that gem in project settings. Old references are redirected automatically.
4. **Activation semantics changed (26.05)**: Active/Inactive now cascades to children. Code that turned a parent off and expected children to stay active behaves differently.
5. **Lua timing**: Lua components activate after C++ components, and other entities may not be active yet. Use `EntityBus` + `OnEntityActivated`.
6. **Never leave handlers connected**: every `X.Connect(...)` in `OnActivate` needs a `:Disconnect()` in `OnDeactivate`. In C++, `BusDisconnect()` in `Deactivate()`. Leaked TickBus handlers keep ticking after deactivation.
7. **Coordinate system**: O3DE is **Z-up** (X right, Y forward) in meters. Code ported from Y-up engines points things the wrong way.
8. **Script access needs reflection**: a C++ method or bus not reflected to `BehaviorContext` does not exist in Lua or Script Canvas, whatever the docs for C++ say.
9. **Version-specific build facts**: C++20 is the default (since 25.10); fast math is disabled on all platforms (26.05); bundled CMake 4.2.3 is used by default (26.05); minimum Clang is still 14 but will become 18 in the next release; VS 2026 supported from 25.10.1.
10. **`AZ::Colors` named colors are now `AZ::u8`** (26.05), not float. `AZ::RHI::GeometryView` lost its default constructor (26.05).
11. **Script Canvas process**: 25.10.0 ran Script Canvas as a separate tool; 25.10.1 temporarily moved it back into the main editor. Do not give version-agnostic instructions about where it opens.
12. **Open Particle System is experimental** (26.05). Do not recommend it for production; PopcornFX is a separate third-party gem.
13. Using `OnTick` to poll state that an EBus notification could give you (official guidance: event-driven first, tick only while needed).

## Rendering
- **Atom** renderer: PBR, forward+ with deferred options, multi-backend RHI (DirectX 12, Vulkan, Metal). Windows backend (DX12/Vulkan) and validation mode are selectable in Platform Settings (26.05).
- Components: Mesh, Material, Directional/Point/Area Light, Global Skylight (IBL), HDRi Skybox, Reflection Probe, Diffuse Probe Grid (GI), PostFX Layer, Display Mapper (ACES, and in 26.05 AgX ×4 and Khronos PBR Neutral), SSAO, Bloom, Depth of Field.
- New in 26.05: Unlit material type, automatic missing-LOD generation in the FBX importer (opt-in), Deferred Materials feature processor (off by default, CVAR), Alternate Frame Rendering.
- Shaders are AZSL (`.azsl`, `.azsli`); material types `.materialtype`, materials `.material`.

## Physics
- **PhysX 5** gem (default for new projects in 26.05). Components: PhysX Static Rigid Body, PhysX Dynamic Rigid Body, PhysX Collider / Shape Collider / Mesh Collider / Heightfield Collider, PhysX Character Controller (kinematic; does not apply gravity by itself), Character Gameplay, joints (Ball, Hinge, Fixed, Prismatic), Ragdoll, Force Region, Cloth.
- Collision layers and groups are configured in the PhysX Configuration tool.
- Scene queries (Lua), as documented:
```lua
local physicsSystem = GetPhysicsSystem()
local sceneHandle = physicsSystem:GetSceneHandle(DefaultPhysicsSceneName)
local scene = physicsSystem:GetScene(sceneHandle)
local request = RayCastRequest()
request.Start = Vector3(5.0, 0.0, 5.0)
request.Direction = Vector3(0.0, 0.0, -1.0)
request.Distance = 10.0
local hits = scene:QueryScene(request)
local numHits = hits.HitArray:Size()
```
- Per-body raycast: `SimulatedBodyComponentRequestBus.Event.RayCast(entityId, request)`.
- Script Canvas has nodes for Raycast (World/Local Space), trigger and collision events. Collision and trigger events for Lua go through the simulated-body event system; check the API reference for your version (not confirmed in this pass).
- 26.05: the VHACD convex decomposition budget defaults to 8 hulls. The `RigidBody` component can force a new transform without disabling simulation.

## Input
- Input Bindings asset → Input component → `InputEventNotificationBus` (`OnPressed`, `OnHeld`, `OnReleased`, all with a float value). Input contexts: `InputRequestBus.Broadcast.PushContext("name")` / `PopContext()`.
- Raw device input is available in C++ through `AzFramework::InputChannelEventListener` (C++ only).
- Device names look like `keyboard_key_alphanumeric_W`, `mouse_button_left`, `gamepad_button_a`.

## UI
- **LyShine** gem: UI Canvas assets (`.uicanvas`) edited in the UI Editor, loaded with the UI Canvas Asset Ref component. Elements carry components such as Text, Image, Button, Layout and Mask. Scripts talk to elements through buses such as `UiCanvasBus`, `UiElementBus`, `UiTextBus` (names are from the LyShine API; confirm the exact methods in your version's API reference).
- LyShine has a tweener system with Lua examples.
- ImGui gem for debug tools.

## Networking and multiplayer
- **Multiplayer Gem** on top of **AzNetworking** (reliable UDP, delta replication). It is server-authoritative with local prediction and backward reconciliation ("rollback").
- Multiplayer components are **auto-components**: XML files named `*.AutoComponent.xml` that AzAutoGen turns into C++ at build time. The XML defines:
  - `NetworkProperty` with `ReplicateFrom` (Authority/Autonomous) and `ReplicateTo` (Client/Autonomous/Server/Authority), plus `IsRewindable`, `IsPredictable`, `ExposeToScript` and `GenerateEventBindings`;
  - `RemoteProcedure` with `InvokeFrom` and `HandleOn` (for example Autonomous→Authority or Authority→Client) and `IsReliable`;
  - `NetworkInput` (player input per network tick), which needs `CreateInput` and `ProcessInput` implemented on the controller;
  - `ArchetypeProperty` (edit-time only).
- Roles: `NetEntityRole::Authority`, `Autonomous` (locally controlled, can predict), `Client` (read-only proxy), `Server` (non-authoritative server in multi-server setups).
- Multiplayer components are the only built-in way for networked entities to talk, because two entities may not be authoritative on the same host.
- Required pieces: Network Transform component, Network Binding, and a player spawner (`SimpleNetworkPlayerSpawner` component). Test in the editor with the multiplayer play mode (the console variable `editorsv_enabled` starts a local server; check the "Test in Editor" docs for your version).
- Reference project: `o3de/o3de-multiplayersample`.

## Save data
- **SaveData gem**: `SaveData::SaveDataRequestBus::Broadcast(&SaveData::SaveDataRequests::SaveDataBuffer, params)` / `LoadDataBuffer`, or `SaveOrLoadObjectParams<T>` for reflected objects. Everything is asynchronous with callbacks on the main thread. Data can be per local user (`AzFramework::LocalUserIdNone` for global). This is C++. Lua access to SaveData was not confirmed.
- JSON serialization of reflected classes is available through `AZ::JsonSerialization`.

## Performance
- Prefer event-driven code; connect to `TickBus` only while needed.
- Profile with the built-in profiler (ImGui) and PIX/RenderDoc for Atom. Use LODs (26.05 can auto-generate missing ones), occlusion culling planes and instancing.
- Avoid calling `SetMaterialProperties` every frame. It was slow before a 26.05 fix and is still costly.
- Asset Processor builds products in the background; on a first open, wait for critical assets (26.05 shows a progress overlay).
- Use monolithic release builds for shipping performance.

## Build and export
- Build with CMake (bundled since 26.05) or from Project Manager ("Build Project"). Example: `cmake -B build/windows -S . -G "Visual Studio 17"` then `cmake --build build/windows --target MyProject.GameLauncher --config profile`.
- Export: Project Manager **Export** or the CLI `o3de.bat export-project` with an export script (for example `ExportScripts/export_source_built_project.py`). Confirm the script name for your engine install; the 25.10.2 fix concerned bundling GI assets during export.
- Asset bundling: Asset Bundler / seed lists. In 26.05, Generic Asset types can opt into automatic bundling.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Lua `TransformBus.Event.GetWorldTM(other)` returns nil | Target entity not activated yet | Connect `EntityBus` to the target and work in `OnEntityActivated` |
| Script keeps running after entity disabled | Handler never disconnected | `self.handler:Disconnect()` in `OnDeactivate` |
| Method missing in Lua / Script Canvas | Not reflected to BehaviorContext | Add `BehaviorContext` reflection (`->Class<>()->Method(...)` or `->EBus<>()`) and rebuild |
| Component not in Add Component menu | Descriptor not registered or no EditContext | Add `CreateDescriptor()` to the module's `m_descriptors`; reflect with `EditContext` and `AppearsInAddComponentMenu` |
| Sky disappeared after upgrading to 26.05 | SkyAtmosphere is a separate gem now | Enable the SkyAtmosphere gem in project settings |
| PhysX deprecation warning / build errors | Project still uses the PhysX 4 gem | Run `upgrade-physx-gem` and switch to PhysX5 |
| Character falls through or floats | PhysX Character Controller is kinematic, no gravity | Apply gravity yourself or use the Character Gameplay component |
| Editor stuck "processing assets" | Asset Processor still compiling critical assets | Wait for the progress overlay; check the Asset Processor window for failed jobs |
| Build uses the wrong CMake | System CMake conflicts | Use the bundled CMake (26.05 default) or set it explicitly |
| Object faces the wrong way | Y-up assumptions | O3DE is Z-up; forward is +Y |

## Mapping from Roblox
| Roblox | O3DE | Notes |
|---|---|---|
| Workspace / Instance tree | Level prefab with entity hierarchy (Entity Outliner) | Entities hold components; no class inheritance per object |
| Part | Entity + Mesh + Material + PhysX Collider (+ Rigid Body) | Shapes come from mesh assets or shape components |
| Model | Prefab (`.prefab`) or parent entity | Prefabs are spawnables at runtime |
| Script (server) | Multiplayer component logic on Authority role, or a C++ component | No implicit server/client split unless you use Multiplayer gem roles |
| LocalScript | Lua/Script Canvas on Autonomous/Client entities, or local-only components | |
| ModuleScript | Lua `require("Scripts.Module")` or C++ gem code | |
| RemoteEvent | `RemoteProcedure` in an AutoComponent XML | `InvokeFrom` / `HandleOn` define direction |
| DataStore | SaveData gem (local files per user) | No cloud store; bring your own backend |
| Players | Multiplayer connections + spawned player entities (`SimpleNetworkPlayerSpawner`) | |
| Humanoid | PhysX Character Controller + EMotionFX Actor/AnimGraph | Gravity and jumping are yours to code |
| RunService.Heartbeat / RenderStepped | `TickBus` `OnTick(deltaTime, timePoint)` with tick order | Physics has its own fixed step |
| TweenService | Script Canvas **Lerp Between** node, LyShine tweener (UI) | No general tween service |
| CollectionService tags | **Tag** component (LmbrCentaur Tag gem) + tag buses | Verify gem name in your version |
| Attributes | Lua `Properties`, reflected component fields, Script Canvas component variables | |
| ScreenGui | LyShine UI Canvas | |
| UserInputService | Input Bindings asset + `InputEventNotificationBus` | |
| task.wait | Count time in `OnTick`, or Script Canvas Delay/TimeDelay nodes | No coroutine wait in O3DE Lua |
| Studio playtest | Editor Game Mode (Ctrl+G); multiplayer test in editor | Esc exits |
| Publishing | Export project + your own distribution (Steam etc.) | No hosted platform |

## Minimal example
Lua component: move an entity with W/A/S/D through two Input Bindings events (`MoveX`, `MoveY` with multipliers -1/+1). When it gets within 1 m of a target entity, add a point and log the score.
```lua
-- Scripts/PlayerMover.lua  (entity needs: Input component with bindings MoveX/MoveY, this Lua Script component)
local PlayerMover = {
    Properties = {
        Speed = { default = 5.0, suffix = "m/s" },
        Coin = { default = EntityId(), description = "Entity to collect" },
    }
}

function PlayerMover:OnActivate()
    self.axis = { x = 0.0, y = 0.0 }
    self.score = 0
    self.xBus = InputEventNotificationBus.Connect(self, InputEventNotificationId("MoveX"))
    self.yBus = InputEventNotificationBus.Connect(self, InputEventNotificationId("MoveY"))
    self.tickBusHandler = TickBus.Connect(self)
end

function PlayerMover:SetAxis(value, released)
    local id = InputEventNotificationBus.GetCurrentBusId()
    local v = released and 0.0 or value
    if id == InputEventNotificationId("MoveX") then self.axis.x = v else self.axis.y = v end
end

function PlayerMover:OnPressed(value)  self:SetAxis(value, false) end
function PlayerMover:OnHeld(value)     self:SetAxis(value, false) end
function PlayerMover:OnReleased(value) self:SetAxis(value, true) end

function PlayerMover:OnTick(deltaTime, timePoint)
    local pos = TransformBus.Event.GetWorldTranslation(self.entityId)
    local step = Vector3(self.axis.x, self.axis.y, 0.0) * (self.Properties.Speed * deltaTime)
    TransformBus.Event.SetWorldTranslation(self.entityId, pos + step)

    local coin = self.Properties.Coin
    if coin:IsValid() then
        local coinPos = TransformBus.Event.GetWorldTranslation(coin)
        if coinPos ~= nil and (coinPos - (pos + step)):GetLength() < 1.0 then
            self.score = self.score + 1
            Debug.Log("Score: " .. tostring(self.score))
            TransformBus.Event.SetWorldTranslation(coin, coinPos + Vector3(0.0, 10.0, 0.0)) -- move coin away
        end
    end
end

function PlayerMover:OnDeactivate()
    if self.tickBusHandler then self.tickBusHandler:Disconnect() end
    if self.xBus then self.xBus:Disconnect() end
    if self.yBus then self.yBus:Disconnect() end
end

return PlayerMover
```
Notes: `GetCurrentBusId()` and `GetWorldTranslation`/`SetWorldTranslation` are commonly used reflected names. The tutorials confirmed `TransformBus.Event.GetLocalTM/SetLocalTM/RotateAroundLocalZ`, so check the other two in the Lua Editor's class reference. For real collisions use a PhysX trigger collider and Script Canvas trigger nodes.

## Sources
- https://docs.o3de.org/docs/release-notes/ (latest is 26.05.0, May 27 2026; history of 25.10.x)
- https://docs.o3de.org/docs/release-notes/2605-0-release-notes/ (PhysX 4 deprecation and upgrade-physx-gem, SkyAtmosphere gem, activation propagation, File > New Component, bundled CMake, Clang/VS notes, AZ::Colors u8, fast math)
- https://docs.o3de.org/docs/release-notes/2510-0-release-notes (C++20, installer changes, 25.10.1/25.10.2 fixes)
- https://github.com/o3de/o3de/releases (tag dates 2605.0, 2510.2, 2510.1, 2510.0)
- https://docs.o3de.org/docs/user-guide/scripting/lua/basic-lua-script/ (Script Table, Properties, OnActivate/OnDeactivate, entityId)
- https://docs.o3de.org/docs/user-guide/scripting/lua/ebus/ (Lua activation order, Event/Broadcast, EntityBus/OnEntityActivated)
- https://docs.o3de.org/docs/user-guide/scripting/lua/properties/ (Properties table types)
- https://docs.o3de.org/docs/user-guide/scripting/lua/debugging-tutorial/ (TickBus.Connect(self), OnTick(deltaTime, timePoint), Disconnect)
- https://docs.o3de.org/docs/user-guide/scripting/lua/environment/ (require path format)
- https://docs.o3de.org/docs/user-guide/programming/components/tick/ (TickBus, OnTick signature, tick order presets)
- https://docs.o3de.org/docs/user-guide/programming/components/create-component/ (AZ_COMPONENT, Activate/Deactivate, Reflect, services, create-from-template)
- https://docs.o3de.org/docs/user-guide/components/reference/gameplay/input-event-bus-interface/ (InputEventNotificationBus, OnPressed/OnHeld/OnReleased, InputRequestBus contexts)
- https://docs.o3de.org/docs/learning-guide/tutorials/input-and-movement/grid-based-movement/ (Input Bindings asset, Script Canvas input nodes, Ctrl+G game mode)
- https://docs.o3de.org/docs/user-guide/networking/multiplayer/overview/ (roles, delta replication, RPC reliability)
- https://docs.o3de.org/docs/user-guide/networking/multiplayer/autocomponents/ (AutoComponent XML, NetworkProperty, RemoteProcedure, NetworkInput)
- https://docs.o3de.org/docs/user-guide/gems/reference/utility/save-data/ (SaveDataRequestBus API)
- https://docs.o3de.org/docs/user-guide/interactivity/physics/nvidia-physx/scene-queries/ (Lua raycast example)
- https://docs.o3de.org/docs/user-guide/components/reference/physx/character-controller/ (kinematic, no gravity)
- https://docs.o3de.org/docs/learning-guide/tutorials/entities-and-prefabs/spawn-a-prefab/ (SpawnableScriptAssetRef)

## Confidence and gaps
- High: version/date, 26.05 changes, Lua component pattern, TickBus, EBus Lua syntax, input bus, multiplayer auto-component model, SaveData C++ API.
- Medium: LyShine bus method names, `GetWorldTranslation`/`SetWorldTranslation` and `GetCurrentBusId` in Lua (widely used, not re-read in this pass), export CLI script name, Tag gem name, editor multiplayer CVAR.
- Not verified: Lua access to PhysX collision/trigger events, Lua access to SaveData, current macOS/iOS export maturity.
- The docs site (docs.o3de.org) timed out from this machine; content was read from the official `o3de/o3de.org` GitHub docs source, which is what the site renders.
