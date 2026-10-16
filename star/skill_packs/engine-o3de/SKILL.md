---
name: engine-o3de
description: O3DE (Open 3D Engine) 26.05 C++/Lua/Script Canvas. Use for O3DE components, EBus, TickBus, Lua Script component, PhysX5, LyShine, Multiplayer gem.
---
# engine-o3de
## Scope
O3DE (Open 3D Engine) 26.05.0 (May 2026; previous 25.10.x). Check the project's engine version first (`project.json`).

## Core model
- Entity = ID + components. C++ components derive `AZ::Component` with `Init()`, `Activate()`, `Deactivate()`; entities can re-activate, so Deactivate undoes Activate.
- EBus messaging: request buses (`Bus.Event(id, ...)`, `Bus.Broadcast(...)`) and notification handlers (`BusConnect`/`BusDisconnect`).
- Per-frame: `AZ::TickBus`, `OnTick(float deltaTime, AZ::ScriptTimePoint time)`; connect only while needed.
- Static `Reflect()` registers Serialize/Edit/Behavior contexts; only BehaviorContext items reach Lua and Script Canvas.
- Gems = modules (PhysX5, Atom, LyShine, Multiplayer). Levels/prefabs are `.prefab` JSON.

## Idioms
- Lua component: `local X = { Properties = {...} }`, `function X:OnActivate()`, `function X:OnDeactivate()`, `return X`; `self.entityId`.
- Ticks in Lua: `self.tick = TickBus.Connect(self)`, `function X:OnTick(deltaTime, timePoint)`, `self.tick:Disconnect()`.
- Calls: `TransformBus.Event.GetLocalTM(self.entityId)`; `Debug.Log("...")`.
- Input: Input Bindings asset + Input component; `InputEventNotificationBus.Connect(self, InputEventNotificationId("MoveX"))`, handlers `OnPressed/OnHeld/OnReleased(value)`.
- Other entity data: `EntityBus.Connect(self, otherId)` then work in `OnEntityActivated`.
- New C++ component: Editor File > New Component (26.05) or `o3de.bat create-from-template ... -tn DefaultComponent`; add `CreateDescriptor()` to the gem module; unique UUID in `AZ_COMPONENT`.
- Multiplayer: `*.AutoComponent.xml` with NetworkProperty (ReplicateFrom/To), RemoteProcedure (InvokeFrom/HandleOn), NetworkInput (CreateInput/ProcessInput). Roles Authority, Autonomous, Client, Server.
- Save: SaveData gem (`SaveDataRequestBus`, async callbacks).

## Pitfalls
1. Lumberyard/CryEngine APIs (`gEnv`, `CryLog`, `IEntitySystem`, slices) are legacy or removed; use AZ components, EBus and prefabs.
2. 26.05 makes PhysX5 the default and deprecates PhysX 4 (removed next release); migrate with `o3de.bat upgrade-physx-gem --project-path <dir>`.
3. 26.05 moved SkyAtmosphere into its own gem; enable it.
4. 26.05 entity Active/Inactive now propagates to all children; Transform stays active.
5. Lua components activate after all C++ components; other entities may be inactive. Use `EntityBus` + `OnEntityActivated`.
6. Every `Connect` needs a `Disconnect` in `OnDeactivate` (C++: `BusDisconnect()` in `Deactivate()`).
7. There is no `Update()`/`Start()` callback in O3DE Lua; use `OnActivate` and `OnTick`.
8. O3DE is Z-up with +Y forward; ported Y-up math breaks.
9. Methods not reflected to BehaviorContext do not exist in Lua or Script Canvas.
10. PhysX Character Controller is kinematic: no gravity unless you add it.
11. 26.05: `AZ::Colors` named colors are `AZ::u8`; fast math off; bundled CMake default; C++20 default since 25.10.

## Roblox to O3DE
- Workspace tree -> level prefab + entity hierarchy
- Part -> entity + Mesh + PhysX Collider (+ Rigid Body)
- Script/LocalScript -> Lua, Script Canvas or C++ components
- RemoteEvent -> AutoComponent RemoteProcedure
- DataStore -> SaveData gem (local)
- Heartbeat -> TickBus OnTick
- UserInputService -> Input Bindings + InputEventNotificationBus
- ScreenGui -> LyShine UI Canvas
- Studio playtest -> Editor Game Mode (Ctrl+G)

## Skeleton
```lua
-- Scripts/Spinner.lua (attach with a Lua Script component)
local Spinner = {
    Properties = {
        DegreesPerSecond = { default = 90.0, suffix = "deg/s" },
    }
}

function Spinner:OnActivate()
    self.radPerSec = Math.DegToRad(self.Properties.DegreesPerSecond)
    self.tickBusHandler = TickBus.Connect(self)
end

function Spinner:OnTick(deltaTime, timePoint)
    TransformBus.Event.RotateAroundLocalZ(self.entityId, self.radPerSec * deltaTime)
end

function Spinner:OnDeactivate()
    if self.tickBusHandler then
        self.tickBusHandler:Disconnect()
        self.tickBusHandler = nil
    end
end

return Spinner
```

## Verification
- Lua: attach the script to an entity, enter Game Mode (Ctrl+G), and watch the Console for `Debug.Log` output and errors.
- C++: build the project (Project Manager Build, or `cmake --build build/<platform> --target <Project>.GameLauncher --config profile`). The component must appear in Add Component.
- Say what you actually ran. Without an editor or build run, mark the code "not run".
