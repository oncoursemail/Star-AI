# Unreal Engine 5 — engine reference for STAR

**Researched 2026-10-13.** Written for STAR (strongest at Roblox/Luau) so it can answer Unreal Engine 5 questions
correctly and translate Roblox habits into Unreal ones. Epic's documentation is not openly licensed, so everything here is
STAR's own wording with links to the official pages (dev.epicgames.com documentation, currently labelled 5.8). Claims
that could not be checked against an official page are marked *(unverified)*.

Scope: UE 5.x C++ and Blueprints, gameplay framework, replication, Gameplay Ability System, Enhanced Input, rendering
(Nanite, Lumen, Virtual Shadow Maps, MegaLights, Substrate), World Partition, profiling, build and packaging.

---

## 1. Versions and release cadence (as of October 2026)

| Version | When | Highlights that change answers |
|---|---|---|
| 5.0 | 2022-04 | Nanite, Lumen, Virtual Shadow Maps, World Partition, Enhanced Input introduced (plugin). |
| 5.1–5.3 | 2022-11 → 2023-09 | Enhanced Input becomes the default input system (legacy action/axis mappings deprecated); C++20 default for new code (5.3) *(unverified exact version)*; Substrate experimental. |
| 5.4 | 2024-04 | Motion Matching, Nanite tessellation (experimental), animation retargeting improvements. |
| 5.5 | 2024-11 | MegaLights (experimental), Mobile Forward renderer improvements. |
| 5.6 | 2025-06 | Performance focus for open worlds; MetaHuman Creator in-engine. |
| 5.7 | 2025-11 | **PCG production-ready**, **Substrate production-ready and on by default**, MegaLights beta, Nanite Foliage (experimental), in-editor AI assistant. |
| 5.8 | 2026-06 (State of Unreal, June 17) | **MegaLights production-ready**, **Lumen Lite** (beta, medium GI using irradiance fields, about twice as fast as Lumen high), Mesh Terrain (experimental), large shader-permutation reductions, experimental MCP plugin to connect AI assistants, SSGI deprecated, World Partition Insights. Epic's announcement lists Iris among production-ready items, but the 5.8 Iris documentation page still labels it Experimental and opt-in — treat it as opt-in. |
| UE6 | Early Access targeted for late 2027 | Epic said 5.8 is the last planned major 5.x release (a 5.9 is not ruled out). |

**Rule for STAR:** assume UE 5.8 unless told otherwise; name the version when an answer depends on 5.7+/5.8 features;
never invent console variables — say "check the cvar name in your version" when unsure.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-7-release-notes ·
https://www.unrealengine.com/news/unreal-engine-5-7-is-now-available ·
https://www.unrealengine.com/news/state-of-unreal-2026-top-news-from-the-show ·
https://tomlooman.com/unreal-engine-5-8-performance-highlights/ (community, used for cvar-level detail)

---

## 2. Architecture

### 2.1 UObject and reflection
- **`UObject`** is the base of engine objects: reflection, serialization, garbage collection, default objects, editor
  integration. Classes are declared with `UCLASS()`, structs with `USTRUCT()`, enums with `UENUM()`, and each needs
  `GENERATED_BODY()` and `#include "MyClass.generated.h"` as the **last** include.
- **Unreal Header Tool (UHT)** parses these macros and generates glue code; **Unreal Build Tool (UBT)** compiles modules.
- **Naming prefixes** are required by UHT: `A` (Actor subclasses), `U` (other UObjects), `F` (structs and plain types),
  `E` (enums), `I` (interfaces), `T` (templates), `S` (Slate widgets), `b` for booleans.
- **`UPROPERTY()`** exposes a member to reflection: editor (`EditAnywhere`, `VisibleAnywhere`, `EditDefaultsOnly`),
  Blueprints (`BlueprintReadOnly/ReadWrite`), replication (`Replicated`, `ReplicatedUsing=OnRep_X`), saving
  (`SaveGame`), and **garbage-collection visibility**.
- **`UFUNCTION()`**: `BlueprintCallable`, `BlueprintPure`, `BlueprintImplementableEvent` (body in Blueprint),
  `BlueprintNativeEvent` (C++ default in `Name_Implementation`, overridable in Blueprint), RPC specifiers
  (`Server`, `Client`, `NetMulticast`, `Reliable`, `WithValidation`), `Exec`, `CallInEditor`.

### 2.2 Garbage collection rules
- UObjects are freed by Unreal's mark-and-sweep GC. A UObject is kept alive only if reachable from the root set
  through **reflected references**: `UPROPERTY()` members (raw pointer or `TObjectPtr<>`), `TArray<TObjectPtr<>>`
  marked `UPROPERTY()`, `AddToRoot()`, or `FGCObject::AddReferencedObjects` for non-UObject owners.
- A raw `UMyObject*` member **without** `UPROPERTY()` is invisible to GC: the object can be collected and the pointer
  dangles (crash some time later, often only in packaged builds or after a GC pass — `obj.collectgarbage` forces one).
- `TObjectPtr<T>` is the UE5 standard for UObject pointer members (editor access tracking, lazy load); it does not keep
  an object alive by itself — `UPROPERTY()` does.
- `TWeakObjectPtr<T>` for non-owning references; check `IsValid()` / `.Get()`.
- `TSoftObjectPtr<T>` / `TSoftClassPtr<T>` reference assets by path without loading them; load with
  `LoadSynchronous()` or the `StreamableManager` asynchronously.
- `IsValid(Obj)` checks non-null **and** not pending kill. Destroyed actors stay non-null until GC.
- Actors are destroyed explicitly with `Destroy()`; components with `DestroyComponent()`.

### 2.3 Actors, components and the gameplay framework
- **`AActor`**: anything placed or spawned in a level. Has a root `USceneComponent` and components
  (`UStaticMeshComponent`, `USkeletalMeshComponent`, `UCapsuleComponent`, `UCameraComponent`, ...). Behaviour reuse is
  via `UActorComponent` subclasses.
- **Gameplay framework** (who exists where in multiplayer):

| Class | Exists on | Purpose |
|---|---|---|
| `AGameModeBase` / `AGameMode` | **Server only** | Rules: spawning, login, match flow (`PostLogin`, `HandleStartingNewPlayer`, `ChoosePlayerStart`). |
| `AGameStateBase` / `AGameState` | Server + all clients | Replicated match state (scores, timer, `PlayerArray`). |
| `APlayerController` | Server + **owning client** only | Player's will: input, HUD/UI, camera; owns the connection. |
| `APlayerState` | Server + all clients | Replicated per-player data (name, score); persists across pawn respawns. |
| `APawn` / `ACharacter` | Server + relevant clients | The body. `ACharacter` adds capsule, skeletal mesh and `UCharacterMovementComponent` (networked movement prediction). |
| `AHUD`, UMG widgets | Owning client | UI. |
| `UGameInstance` | Each process, whole session | Survives level loads; host subsystems here. |

- **Subsystems** (`UGameInstanceSubsystem`, `UWorldSubsystem`, `ULocalPlayerSubsystem`, `UEngineSubsystem`,
  `UEditorSubsystem`): auto-instanced singletons with managed lifetimes; prefer them over global singletons.
- **Class Default Object (CDO)**: every `UCLASS` has a default instance built by running the constructor once at startup.
  Constructors therefore must not touch the world, other actors, or gameplay state; they only set defaults and create
  components with `CreateDefaultSubobject<T>(TEXT("Name"))`.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/objects-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-object-handling-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/ufunctions-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-framework-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/epic-cplusplus-coding-standard-for-unreal-engine

---

## 3. Actor lifecycle

Placed in a level (load): constructor (CDO and instance) → `PostLoad` → `PostActorCreated`/`OnConstruction`
(construction script; also runs in the editor on every move/property change) → `PreInitializeComponents` →
`InitializeComponent` (components with `bWantsInitializeComponent`) → `PostInitializeComponents` → **`BeginPlay`** (when
the world begins play; components' `BeginPlay` too) → `Tick(DeltaSeconds)` each frame → `EndPlay(EEndPlayReason)` →
`BeginDestroy` / `FinishDestroy` (GC).

Spawned at runtime: `GetWorld()->SpawnActor<AMyActor>(Class, Transform, Params)` runs construction and `BeginPlay`
immediately. **Deferred spawn**: `SpawnActorDeferred<T>(...)`, set properties, then `UGameplayStatics::FinishSpawningActor`
(or `Actor->FinishSpawning(Transform)`) so `BeginPlay` sees the values.

Practical rules:
- Constructor: defaults and `CreateDefaultSubobject` only. `BeginPlay`: find other actors, bind delegates, start timers.
- `OnConstruction` runs in the editor — keep it cheap and side-effect free.
- Tick: `PrimaryActorTick.bCanEverTick = false` unless needed; use `SetActorTickInterval`, tick groups
  (`TG_PrePhysics`, `TG_PostPhysics`...), timers (`GetWorldTimerManager().SetTimer`) or events instead of polling.
- `EndPlay` for cleanup (clear timers, unbind delegates); `Destroyed()` is not called on level unload.
- In multiplayer, `BeginPlay` runs on server and every client where the actor exists; guard server logic with
  `HasAuthority()`.
- Pawn possession: `PossessedBy` (server), `OnRep_Controller`/`OnRep_PlayerState` (client) — use these, not `BeginPlay`,
  for anything that needs the controller or PlayerState (e.g. GAS init).

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/spawning-actors-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-ticking-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine

---

## 4. Project layout and build system

```
MyGame/
  MyGame.uproject            # JSON: EngineAssociation, Modules, Plugins
  Config/DefaultEngine.ini   # project config (DefaultGame.ini, DefaultInput.ini, ...)
  Content/                   # .uasset / .umap (binary) — use Git LFS or Perforce with file locking
  Source/
    MyGame.Target.cs         # game target (Type = TargetType.Game)
    MyGameEditor.Target.cs   # editor target
    MyGame/                  # primary module
      MyGame.Build.cs        # module rules: dependencies
      MyGame.cpp/.h          # IMPLEMENT_PRIMARY_GAME_MODULE
      Public/ Private/
  Plugins/<Plugin>/<Plugin>.uplugin + Source/
  Binaries/ Intermediate/ Saved/ DerivedDataCache/   # generated — never commit
```

- **Modules**: each has a `.Build.cs`. Using a class from another module requires adding it to
  `PublicDependencyModuleNames` (needed by your public headers) or `PrivateDependencyModuleNames`. Common ones:
  `Core`, `CoreUObject`, `Engine`, `InputCore`, `EnhancedInput`, `UMG`, `Slate`, `SlateCore`, `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`, `NetCore`, `AIModule`, `NavigationSystem`, `Niagara`.
- Missing dependency ⇒ linker error **LNK2019 "unresolved external symbol"** (or "cannot open include file"). Fix:
  add the module to `.Build.cs`, regenerate project files, rebuild. A class must also be exported (`MYMODULE_API`) to be
  used from another module.
- Plugin modules must be enabled in `.uproject`/`.uplugin` as well as listed in `.Build.cs`.
- **Targets**: `Game`, `Client`, `Server` (dedicated server, needs a source-built engine), `Editor`, `Program`.
- **Build configurations**: `Debug`, `DebugGame` (engine optimized, game debug), `Development` (default), `Test`,
  `Shipping` (no console, no stats, strip logs). `Editor` suffix variants for the editor.
- **Live Coding** (Ctrl+Alt+F11) patches function bodies while the editor runs. Changes to headers, `UPROPERTY`/
  `UCLASS` layout or constructors need an editor restart and full build; old **Hot Reload** corrupts Blueprints — keep it
  off. If Blueprints break after a reflected change, close the editor and build from the IDE.
- Version control: commit `Source/`, `Config/`, `Content/`, `.uproject`, `Plugins/`; ignore `Binaries/`,
  `Intermediate/`, `Saved/`, `DerivedDataCache/`, `.vs/`. Binary assets cannot be merged — use locking (Perforce,
  Git LFS locks) and **One File Per Actor** with World Partition so level edits don't collide.
- Toolchain: Visual Studio 2022 or Rider on Windows; the engine's release notes list the supported compiler/SDK per version.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-modules ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/module-properties-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-build-tool-target-reference ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/build-configurations-reference-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/one-file-per-actor-in-unreal-engine

---

## 5. C++ idioms and pitfalls

- Strings: `FString` (mutable text), `FName` (case-insensitive interned identifiers — asset/bone/socket names), `FText`
  (user-visible, localizable). `TEXT("...")` for literals; `*MyString` to pass `const TCHAR*` to `UE_LOG`/`Printf`.
- Containers: `TArray`, `TMap`, `TSet`; iterate with range-for; don't mutate while iterating; `Reserve` for hot paths.
- Casting: `Cast<AMyCharacter>(Actor)` returns null on mismatch; `CastChecked` asserts. Avoid casting every tick.
- Logging: `UE_LOG(LogTemp, Warning, TEXT("HP %d"), Hp);` define your own category with
  `DECLARE_LOG_CATEGORY_EXTERN`/`DEFINE_LOG_CATEGORY`. On-screen: `GEngine->AddOnScreenDebugMessage`.
- Assertions: `check()` (crash, stripped in Shipping), `ensure()` (logs once, continues), `verify()`.
- Delegates: single (`DECLARE_DELEGATE`), multicast (`DECLARE_MULTICAST_DELEGATE`), dynamic (`DECLARE_DYNAMIC_MULTICAST_DELEGATE_*`,
  usable in Blueprint with `UPROPERTY(BlueprintAssignable)`; bound functions must be `UFUNCTION()`). Unbind in `EndPlay`.
- Getting things: `GetWorld()`, `UGameplayStatics::GetPlayerController(this, 0)` (single-player/local only — wrong on a
  dedicated server), `GetOwner()`, `FindComponentByClass<T>()`. Avoid `GetAllActorsOfClass` in Tick.
- Timers: `FTimerHandle` + `GetWorldTimerManager().SetTimer(Handle, this, &AMyActor::Fire, 0.5f, true);` clear in `EndPlay`.
- Async: `AsyncTask(ENamedThreads::GameThread, ...)`; UObjects are game-thread only.
- Interfaces: `UINTERFACE` + `IMyInterface`; call with `IMyInterface::Execute_Fn(Obj)` for Blueprint-implementable ones.
- Data: `UDataAsset`/`UPrimaryDataAsset` (Unity ScriptableObject), `UDataTable` + `FTableRowBase` rows from CSV/JSON,
  Gameplay Tags for hierarchical identifiers (`Ability.Fire.Primary`).
- Include what you use; forward-declare in headers; `.generated.h` last.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/epic-cplusplus-coding-standard-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/string-handling-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/delegates-and-lambda-functions-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/logging-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/using-gameplay-tags-in-unreal-engine

---

## 6. Blueprints versus C++

- Typical split: C++ base classes own systems, data layout, replication, performance-critical code; Blueprint subclasses
  configure assets, tune values, script level events, UI and cosmetic logic.
- Expose with `UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)` and `UFUNCTION(BlueprintCallable)`; let designers
  override behaviour through `BlueprintImplementableEvent`/`BlueprintNativeEvent`.
- Blueprint nativization was removed in UE5. Blueprint VM overhead matters mainly for heavy per-tick loops.
- Hard references in Blueprints (casting to a Blueprint class, direct asset references) pull whole asset chains into
  memory; use interfaces, soft references and base C++ classes to cut chains (check with the Size Map / Reference Viewer).
- Blueprint debugging: breakpoints, watch values, "Print String", Blueprint debugger, `Visual Logger`.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprints-visual-scripting-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/exposing-gameplay-elements-to-blueprints-visual-scripting-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-best-practices-in-unreal-engine

---

## 7. Enhanced Input

- Default input system in UE5 (legacy Action/Axis mappings are deprecated). Module `EnhancedInput` (enabled by default
  in new projects; add to `.Build.cs` for C++ use).
- Assets: **`UInputAction`** (value type `Digital (bool)`, `Axis1D (float)`, `Axis2D (FVector2D)`, `Axis3D (FVector)`),
  **`UInputMappingContext`** (keys → actions, with **Modifiers** such as Dead Zone, Negate, Swizzle Input Axis Values,
  and **Triggers** such as Pressed, Released, Hold, Tap, Chorded Action).
- A mapping context does nothing until it is **added for the local player**:

```cpp
if (APlayerController* PC = Cast<APlayerController>(GetController()))
    if (auto* Sub = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
        Sub->AddMappingContext(DefaultMappingContext, /*Priority*/ 0);
```

  Do it when the pawn is possessed locally (`PawnClientRestart`, `NotifyControllerChanged`, or `BeginPlay` of a
  locally-controlled pawn / the PlayerController). On a listen server/clients, `GetLocalPlayer()` is null for remote pawns.
- Bind in `SetupPlayerInputComponent`:

```cpp
auto* EIC = CastChecked<UEnhancedInputComponent>(PlayerInputComponent);
EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AMyCharacter::Move);
void AMyCharacter::Move(const FInputActionValue& Value) { const FVector2D Axis = Value.Get<FVector2D>(); ... }
```

  `ETriggerEvent`: `Started`, `Ongoing`, `Triggered`, `Completed`, `Canceled`.
- Project Settings → Input: Default Player Input Class `EnhancedPlayerInput`, Default Input Component Class
  `EnhancedInputComponent` (defaults in new projects).
- Priority: higher-priority contexts win when they map the same key. Remove/add contexts for modes (vehicle, menu).
- Player-mappable keys / rebinding: `UEnhancedInputUserSettings` and Player Mappable Key Settings on actions.
- Input in UI: `SetInputMode(FInputModeUIOnly/GameAndUI/GameOnly)` and `bShowMouseCursor` on the PlayerController.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/EnhancedInput/UEnhancedInputComponent

---

## 8. Rendering

- **Nanite**: virtualized micro-polygon geometry; draws film-quality meshes with automatic LOD. Enable per static mesh.
  Supports opaque and masked materials, World Position Offset (with cost), skeletal meshes and foliage in newer
  versions (Nanite Foliage/skinning experimental in 5.7). Translucent materials are not Nanite. Use for high-poly static
  geometry; profile with the Nanite visualization modes.
- **Lumen**: dynamic global illumination and reflections (software ray tracing through distance fields / surface cache;
  hardware ray tracing optional). Light leaks usually come from thin walls (< ~10 cm) or meshes without distance fields —
  thicken walls, check mesh distance fields, use Lumen scene view. 5.8 adds **Lumen Lite** (medium quality, beta).
- **Virtual Shadow Maps (VSM)**: high-resolution shadows designed for Nanite; costly with heavy WPO/invalidations.
- **MegaLights** (production-ready in 5.8): many shadowed dynamic lights at a fixed cost.
- **Substrate** materials: production-ready and on by default from 5.7 (layered/blended material framework replacing the
  legacy shading models).
- **TSR** (Temporal Super Resolution) is the default upscaler/anti-aliasing.
- **Shader compilation / PSO stutter**: first-use pipeline state compilation hitches on PC/D3D12/Vulkan. Mitigate with
  PSO precaching (default in UE5.x), bundled PSO caches gathered from play sessions, warm-up screens; 5.8 reduced
  permutations.
- Scalability: `sg.*` scalability groups (`sg.GlobalIlluminationQuality`, `sg.ShadowQuality`), device profiles for
  platforms.
- Mobile: Mobile renderer (forward/deferred), many UE5 features (Lumen, Nanite) limited or absent.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/megalights-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/substrate-materials-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/pso-precaching-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/temporal-super-resolution-in-unreal-engine

---

## 9. World building at scale

- **World Partition**: one persistent level divided into a grid of cells streamed by distance to streaming sources
  (players). Replaces World Composition / manual level streaming for open worlds. **Data Layers** toggle content sets;
  **Level Instances** and **Packed Level Actors** reuse groups; **HLODs** stand in for unloaded cells.
- **One File Per Actor** stores each actor in its own external file: fewer merge conflicts.
- Networked World Partition: server streams by all players; clients by their own position.
- PCG framework (production-ready 5.7) generates foliage and props by rules.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---data-layers-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview

---

## 10. Physics and movement

- **Chaos** is the physics engine (PhysX removed in UE5).
- Collision: each primitive has an **Object Type** (channel) and **responses** (Ignore / Overlap / Block) per channel,
  usually set through **collision presets/profiles**. Overlap events need `Generate Overlap Events` on **both** sides and
  at least one side responding Overlap; hit events need `Simulation Generates Hit Events` for simulated bodies.
  Custom channels in Project Settings → Collision.
- Queries: `GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params)`, `SweepSingleByChannel`,
  `OverlapMultiByObjectType`; ignore self with `FCollisionQueryParams::AddIgnoredActor(this)`. Visualize with
  `DrawDebugLine`.
- Simulated bodies: `SetSimulatePhysics(true)`, `AddImpulse`, `AddForce`; move kinematic things with `SetActorLocation(..., bSweep=true)`.
- **`UCharacterMovementComponent`** provides walking/falling/swimming/flying/custom modes with client-side prediction
  and server reconciliation via saved moves. Extend with custom movement modes and `FSavedMove_Character` flags for new
  networked abilities (sprint) — do not just change `MaxWalkSpeed` from a client.
- **Mover** plugin (Chaos-based successor to CMC, network-prediction friendly) is experimental *(status may have changed
  in 5.8 — unverified)*.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/traces-with-raycasts-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/understanding-networked-movement-in-the-character-movement-component-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-in-unreal-engine

---

## 11. Animation

- **Animation Blueprint** (`UAnimInstance`): Event Graph computes variables (speed, isFalling) — prefer the thread-safe
  `BlueprintThreadSafeUpdateAnimation` / property access; Anim Graph blends poses (state machines, blend spaces,
  layered blend per bone, Linked Anim Layers).
- **Montages** for one-shot actions (attacks, reloads) with sections, slots and notifies (`PlayAnimMontage`,
  `Montage_Play`, `OnMontageEnded`). **Anim Notifies** fire gameplay events at frames.
- **Root motion** from montages replicates in multiplayer; root motion from everything is not recommended for networked
  characters.
- **Control Rig** for procedural rigging/animation in-engine; **IK Rig** + **IK Retargeter** for retargeting between
  skeletons; **Motion Matching** (Pose Search) for data-driven locomotion.
- **Sequencer** for cinematics; **Timeline** nodes in Blueprints for simple curves (the TweenService equivalent).

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprints-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-montage-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/control-rig-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-matching-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine

---

## 12. UI

- **UMG** (Unreal Motion Graphics): Widget Blueprints (`UUserWidget`) built from panels (Canvas, Horizontal/Vertical Box,
  Overlay, Grid, Size Box, Scale Box) and widgets (Text, Image, Button, Progress Bar). Anchors and offsets per Canvas slot
  (like Roblox Scale/Offset); DPI scaling curve in Project Settings → User Interface.
- C++: `CreateWidget<UMyWidget>(PlayerController, WidgetClass)` then `AddToViewport()`; bind with
  `UPROPERTY(meta=(BindWidget))` members. Create UI only on the owning client (never on a dedicated server; check
  `IsLocalController()`).
- Avoid UMG property **bindings** (evaluated every frame); push updates from events/delegates or use the **UMG
  ViewModel (MVVM)** plugin.
- **Common UI** plugin for gamepad/console-friendly menus, input routing and activatable widget stacks.
- **Slate** is the underlying C++ UI framework (editor tools, custom widgets).
- Input mode and focus: `SetInputMode`, `SetUserFocus`; invisible widgets with `Visibility = Visible` still block clicks
  — use `HitTestInvisible`/`SelfHitTestInvisible`/`Collapsed`.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/creating-user-interfaces-with-umg-and-slate-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/common-ui-plugin-for-advanced-user-interfaces-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/umg-viewmodel-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/slate-user-interface-programming-framework-for-unreal-engine

---

## 13. Networking and replication

### 13.1 Model
- Client-server, **server-authoritative**. Modes: Standalone, Listen Server (a player hosts), Dedicated Server (separate
  headless process; needs the Server target, built from a source engine), Client. Check with `GetNetMode()`.
- `HasAuthority()` is true on the server for server-spawned actors. `GetLocalRole()` / `GetRemoteRole()`:
  `ROLE_Authority`, `ROLE_AutonomousProxy` (the owning client's own pawn), `ROLE_SimulatedProxy` (other clients' copies).
  `IsLocallyControlled()` on pawns; `IsLocalController()` on controllers.
- **Ownership**: an actor's owner chain ends at a `PlayerController` → that client's connection "owns" it. Pawns are
  owned by their controller after possession; `SetOwner(PC)` on the server for weapons/items.
- **Relevancy** decides which clients get an actor (`NetCullDistanceSquared`, `bAlwaysRelevant`, `bOnlyRelevantToOwner`);
  `NetUpdateFrequency`, `MinNetUpdateFrequency`, `NetPriority`, dormancy (`SetNetDormancy`, `FlushNetDormancy`) control
  bandwidth.

### 13.2 Property replication
1. `bReplicates = true` (constructor) or `SetReplicates(true)`; components: `SetIsReplicatedByDefault(true)`.
2. `UPROPERTY(Replicated)` or `UPROPERTY(ReplicatedUsing = OnRep_Health)` + `UFUNCTION() void OnRep_Health();`
3. Override `GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const`, call `Super`, include
   `Net/UnrealNetwork.h`, register `DOREPLIFETIME(AMyActor, Health);` or `DOREPLIFETIME_CONDITION(..., COND_OwnerOnly)`.
   Conditions: `COND_None`, `COND_InitialOnly`, `COND_OwnerOnly`, `COND_SkipOwner`, `COND_SimulatedOnly`,
   `COND_AutonomousOnly`, `COND_InitialOrOwner`, `COND_Custom`, `COND_Never`. `DOREPLIFETIME_CONDITION_NOTIFY` with
   `REPNOTIFY_Always` fires OnRep even when the value didn't change.
4. Only **server** changes replicate to clients; client-side changes are local and get overwritten.
- **C++ OnRep functions run only on clients** when the value arrives; the server does not call them automatically —
  call `OnRep_Health()` yourself after changing it on the server (listen-server host needs it). In Blueprint, setting a
  RepNotify variable calls the function on the server too.
- Replicated arrays of structs: `FFastArraySerializer` for efficient delta replication.
- **Push model** (`MARK_PROPERTY_DIRTY_FROM_NAME`, `FDoRepLifetimeParams{bIsPushBased=true}`) lets the server skip
  comparing unchanged properties.
- Subobjects (UObjects inside actors) replicate via the registered subobject list (`AddReplicatedSubObject`).

### 13.3 RPCs
- `UFUNCTION(Server, Reliable)` (client → server), `UFUNCTION(Client, Reliable)` (server → owning client),
  `UFUNCTION(NetMulticast, Unreliable)` (server → server + all relevant clients). Body goes in `Name_Implementation`.
  RPCs are **Unreliable by default**; mark gameplay-critical ones `Reliable` but never call Reliable RPCs every tick
  (overflow disconnects).
- `WithValidation` adds `bool Name_Validate(...)`; returning false **kicks the client**. Use it only for impossible
  inputs; do normal gameplay checks inside `_Implementation`.
- **A Server RPC must be called on an actor the calling client owns** (its PlayerController, its possessed pawn, or an
  actor whose owner chain leads to its controller). Called on an unowned actor (a door, a pickup, a level actor) the RPC
  is **dropped** silently (with a log warning). Route interactions through the PlayerController or pawn:
  `ServerInteract(Door)` on the character, then the server acts on the door.
- Multicast called from a client runs only locally. Client RPC on an unowned actor runs on the server.
- Never trust RPC parameters: the server recomputes damage, cost, cooldown and range.

### 13.4 Iris and other systems
- **Iris**: new replication system (filtering, prioritization, quantized state). The 5.8 docs label it Experimental and
  opt-in: enable the plugin, `SetupIrisSupport(Target)` in `Build.cs`, `bUseIris = true` in `Target.cs`,
  `net.Iris.UseIrisReplication=1` and `net.SubObjects.DefaultUseSubObjectReplicationList=1` in `DefaultEngine.ini`.
  Existing `UPROPERTY` replication code largely keeps working. Epic's 5.8 keynote coverage calls it production-ready;
  verify per project.
- **Network Prediction** plugin / **Mover** for new predicted movement; **CharacterMovementComponent** remains the
  stable default.
- Online: **Online Subsystem** / **Online Services** with **Epic Online Services (EOS)** for sessions, lobbies,
  matchmaking, voice; Steam via OnlineSubsystemSteam. Unreal has no hosted game servers — you host dedicated servers
  yourself or via a provider.
- Debug: PIE with "Number of Players" and "Net Mode: Play as Client", `net.PktLag`, `net.PktLoss` emulation, Network
  Profiler / Networking Insights (`-NetTrace=1 -trace=net`), `p.NetShowCorrections 1` for movement corrections.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-role-and-remote-role-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-owner-and-owning-connection-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/replicate-actor-properties-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/remote-procedure-calls-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-relevancy-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-iris-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-insights-in-unreal-engine

---

## 14. Gameplay Ability System (GAS)

- Plugin **GameplayAbilities**; modules `GameplayAbilities`, `GameplayTags`, `GameplayTasks` in `.Build.cs`.
- Pieces:
  - **`UAbilitySystemComponent` (ASC)** — owns abilities, attribute sets, active effects, tags; the actor implements
    `IAbilitySystemInterface::GetAbilitySystemComponent()`.
  - **`UGameplayAbility`** — an action (`ActivateAbility`, `CommitAbility` for cost/cooldown, `EndAbility`), with
    instancing and net execution policies (`LocalPredicted`, `ServerOnly`, `ServerInitiated`, `LocalOnly`).
  - **`UAttributeSet`** — `FGameplayAttributeData` members (Health, MaxHealth, Mana) with `ATTRIBUTE_ACCESSORS`;
    clamp in `PreAttributeChange`, react to damage meta-attributes in `PostGameplayEffectExecute`.
  - **`UGameplayEffect`** — data-only changes to attributes/tags: Instant, Duration, Infinite; modifiers, executions
    (`UGameplayEffectExecutionCalculation`), stacking; cost and cooldown effects. In 5.3+ effects are composed from
    `UGameplayEffectComponent`s.
  - **Gameplay Tags** — state and identity (`State.Stunned`, `Ability.Dash`); activation/blocked/cancel tags on
    abilities.
  - **Gameplay Cues** — cosmetic effects (sounds, particles) triggered by tags `GameplayCue.*`, replicated cheaply.
  - **Ability Tasks** — async latent actions inside abilities (`PlayMontageAndWait`, `WaitTargetData`, `WaitGameplayEvent`).
- **Where to put the ASC**: on the **PlayerState** for player characters (attributes and cooldowns survive death and
  respawn; ASC then replicates at PlayerState frequency, raise `NetUpdateFrequency`), or on the **Pawn** for AI and simple
  games.
- **Owner vs Avatar**: OwnerActor = the actor that owns the ASC (PlayerState); AvatarActor = the physical pawn.
  Call `ASC->InitAbilityActorInfo(OwnerActor, AvatarActor)` on **both** server and client after possession: server in
  `PossessedBy`, client in `OnRep_PlayerState` (when the ASC lives on PlayerState); for ASC on the pawn, server in
  `PossessedBy` and client in `AcknowledgePossession`/`OnRep_Controller`. Missing client init ⇒ abilities don't activate
  locally / attributes look stale.
- **Replication mode** (`SetReplicationMode`): `Full` (single-player), `Mixed` (player-controlled: effects replicate
  fully only to the owner, minimal to others — requires the owner's controller chain), `Minimal` (AI). Attributes
  replicate with `UPROPERTY(ReplicatedUsing = OnRep_Health)` + `GAMEPLAYATTRIBUTE_REPNOTIFY(UMyAttributeSet, Health, OldHealth)`
  and `DOREPLIFETIME_CONDITION_NOTIFY(UMyAttributeSet, Health, COND_None, REPNOTIFY_Always)`.
- Grant abilities on the **server only** (`GiveAbility(FGameplayAbilitySpec(...))`); activate with
  `TryActivateAbilityByClass` / by tag or input binding. Prediction keys let local-predicted abilities and effects run
  immediately and roll back if the server rejects.
- `UAbilitySystemGlobals::Get().InitGlobalData()` is called automatically in recent versions *(older tutorials call it
  manually)*.
- Lyra sample project is the reference implementation.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/understanding-the-unreal-engine-gameplay-ability-system ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-effects-for-the-gameplay-ability-system-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/using-gameplay-abilities-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine
*(Owner/avatar initialisation timing and replication-mode guidance are long-standing GAS practice, documented in Epic's
API reference for `UAbilitySystemComponent::InitAbilityActorInfo` and `SetReplicationMode`; the overview pages do not
spell them out.)*

---

## 15. Save data

- **`USaveGame`** subclass with `UPROPERTY()` fields → `UGameplayStatics::CreateSaveGameObject(UMySave::StaticClass())`,
  `SaveGameToSlot(Save, SlotName, UserIndex)`, `LoadGameFromSlot`, `DoesSaveGameExist`, `DeleteGameInSlot`.
  Async: `AsyncSaveGameToSlot` / `AsyncLoadGameFromSlot` to avoid hitches.
- Files land in `Saved/SaveGames/` (desktop); platforms route through `ISaveGameSystem`.
- Saving actors/objects: store IDs, soft paths (`FSoftObjectPath`) and plain data, not raw pointers. For world state,
  serialize properties marked `UPROPERTY(SaveGame)` with `FObjectAndNameAsStringProxyArchive` with `ArIsSaveGame = true`.
- Version the format (an int `SaveVersion` field) and migrate on load.
- Server-authoritative multiplayer: save on the server only; clients' saves are trivially editable. Online persistence
  needs a backend (EOS Player Data Storage, your own service).

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UGameplayStatics/SaveGameToSlot

---

## 16. Performance and profiling

- Start with **`stat unit`**: Frame, Game (game thread), Draw (render thread), GPU, RHIT. The largest bounds the frame.
  Then `stat fps`, `stat game`, `stat gpu`, `stat scenerendering`, `stat memory`, `stat streaming`, `stat net`.
- **Unreal Insights** (`-trace=cpu,gpu,frame,bookmark,loadtime,memory`, or `Trace.Start` / Session Frontend): CPU/GPU
  timing, memory (`-trace=memory`), networking, asset loading. 5.8 adds UObject counts, hitch snapshots
  (`snapshothitches`) and World Partition Insights.
- `ProfileGPU` (Ctrl+Shift+, ) for a single-frame GPU breakdown; RenderDoc/PIX for deep GPU debugging.
- `memreport -full` for memory; `obj list` for UObject counts; `obj gc` / `obj.collectgarbage` to test GC.
- Game thread: too many ticking actors (disable tick, tick intervals, aggregate managers), Blueprint loops,
  `GetAllActorsOfClass`, spawning/destroying (pool actors), heavy `Cast` chains, GC spikes (incremental GC, clustering).
  **Significance Manager** to scale work by importance; **Animation Budget Allocator** for many skeletal meshes;
  URO (update rate optimization).
- Render thread/GPU: draw calls (instancing with ISM/HISM, Nanite), shadow cost (VSM invalidation by WPO), Lumen
  settings, translucency overdraw, Niagara particle counts, post-process.
- Hitches: PSO compilation, asset loading (async load, soft references), GC, level streaming.
- Profile **packaged Development/Test builds** on target hardware; editor numbers mislead.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/stat-commands-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-insights-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-performance-profiling-and-configuration-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/significance-manager-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/memory-insights-in-unreal-engine

---

## 17. Build, cook, package, test

- **Cooking** converts assets to platform formats; **packaging** builds the executable + `.pak`/IoStore (`.utoc/.ucas`)
  containers. Editor: Platforms menu → Package Project, or **Project Launcher**.
- Command line (**Unreal Automation Tool**):
  `RunUAT.bat BuildCookRun -project="C:\P\MyGame.uproject" -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory="C:\Out"`
  (add `-server -serverconfig=Development` for a dedicated server, `-iostore`, `-compressed`, `-prereqs`).
  Build only: `Build.bat MyGameEditor Win64 Development -Project="..."`.
- Assets referenced only by string paths are not cooked: add them to Primary Asset Labels / Asset Manager rules or
  "Additional Asset Directories to Cook".
- Shipping builds strip `UE_LOG` (unless enabled), console and stats; test with **Test** configuration for profiling
  hooks.
- **Automation**: Automation Test framework (`IMPLEMENT_SIMPLE_AUTOMATION_TEST`, Spec tests), Functional Tests
  (`AFunctionalTest` in maps), Gauntlet for session tests; run headless:
  `UnrealEditor-Cmd.exe MyGame.uproject -ExecCmds="Automation RunTests MyGame; Quit" -unattended -nullrhi -log`.
- Editor scripting: Python (Editor Scripting plugins) and Editor Utility Widgets/Blueprints.
- Opening an untrusted project runs its code and plugins — treat as executing untrusted software.

Sources: https://dev.epicgames.com/documentation/en-us/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-automation-tool-overview-for-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/automation-test-framework-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/cooking-content-in-unreal-engine ·
https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-and-automating-the-unreal-editor

---

## 18. Common bugs and fixes

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | Crash or garbage data some seconds after creating a UObject with `NewObject` | Pointer member without `UPROPERTY()` → collected by GC | Mark the member `UPROPERTY()` (use `TObjectPtr<>`), or hold it via `FGCObject`/`AddToRoot`. |
| 2 | `LNK2019 unresolved external symbol` for an engine class | Module not in `.Build.cs` (e.g. `EnhancedInput`, `UMG`, `GameplayAbilities`) | Add to Public/PrivateDependencyModuleNames, regenerate, rebuild. |
| 3 | `Cannot open include file "X.generated.h"` | Header lacks `UCLASS`/`GENERATED_BODY`, or include order | `.generated.h` last; reflected class in header; rebuild. |
| 4 | Server RPC never runs on the server | Called on an actor the client does not own | Call on PlayerController/pawn and pass the target actor; or `SetOwner` on the server. |
| 5 | Server RPC runs but nothing replicates | Actor not replicated (`bReplicates` false) | Set `bReplicates = true`. |
| 6 | Replicated variable never updates on clients | Missing `GetLifetimeReplicatedProps`/`DOREPLIFETIME`, or the value is changed on a client | Register it; change only on the server. |
| 7 | OnRep fires on clients but not on the listen-server host | C++ OnRep isn't called on the server | Call `OnRep_X()` manually after setting on the server. |
| 8 | OnRep doesn't fire when setting the same value | Default notify only on change | `DOREPLIFETIME_CONDITION_NOTIFY(..., REPNOTIFY_Always)`. |
| 9 | Enhanced Input actions never fire | Mapping context never added, added for wrong player, or before the local player exists | `AddMappingContext` via `UEnhancedInputLocalPlayerSubsystem` once possessed; check Default Input Component Class. |
| 10 | Input works in PIE single player but not as client | Context added in `BeginPlay` on server only / `GetLocalPlayer()` null | Add in `PawnClientRestart`/`NotifyControllerChanged` for the locally controlled pawn. |
| 11 | Blueprint values reset / Blueprint corrupt after compile | Hot Reload / Live Coding after header change | Close editor, full build, reopen; keep Hot Reload off. |
| 12 | Crash at editor start in constructor | Constructor uses `GetWorld()`, other actors, or loads assets wrongly | Move logic to `BeginPlay`; use `ConstructorHelpers::FObjectFinder` only in constructors (or soft refs). |
| 13 | `BeginPlay` logic runs twice / on clients | Not guarded by authority | `if (HasAuthority())`. |
| 14 | `UGameplayStatics::GetPlayerController(this, 0)` wrong in multiplayer | Index 0 is the local/first controller only | Use `GetController()`, `GetOwner()`, or PlayerState relationships. |
| 15 | GAS ability won't activate on client | `InitAbilityActorInfo` not called client-side, ability granted on client, or wrong net execution policy | Init on both sides (PossessedBy + OnRep_PlayerState); grant on server. |
| 16 | GAS attributes don't update on clients | Missing `GAMEPLAYATTRIBUTE_REPNOTIFY` / DOREPLIFETIME in AttributeSet or ASC not replicated | Add both; `SetIsReplicated(true)`; mode Mixed for players. |
| 17 | Overlap events don't fire | `Generate Overlap Events` off on one side, responses Block/Ignore | Enable on both, set Overlap response on the right channel. |
| 18 | Character rubber-bands when sprinting | Speed changed on client only | Server-side speed + CMC saved-move flag, or GAS with predicted effect. |
| 19 | Lumen light leaking indoors | Thin walls, missing distance fields | Thicker walls (≥ 10 cm), check Mesh Distance Fields, Lumen scene debug view. |
| 20 | Stutter the first time an effect or area appears | PSO/shader compile | PSO precaching, bundled PSO cache, warm-up. |
| 21 | Packaged build missing assets (null soft refs) | Assets referenced only by string, not cooked | Primary Asset Labels / Asset Manager / directories to cook. |
| 22 | Packaged build crash that never happens in editor | GC timing, uninitialized pointer, editor-only code (`WITH_EDITOR`) | Check `UPROPERTY` coverage, test Development package with logs, `-stompmalloc`. |
| 23 | Widget blocks clicks while invisible | Visibility `Visible` with zero opacity | Use `Collapsed` / `HitTestInvisible`. |
| 24 | Reliable RPC overflow disconnects client | Reliable RPC every tick | Unreliable for frequent updates; replicate state instead. |
| 25 | Dedicated server crashes on UI code | Widgets created on server | Guard with `IsLocalController()` / `GetNetMode() != NM_DedicatedServer`. |
| 26 | `Accessed None` in Blueprint | Null reference (failed cast, not-yet-spawned) | `IsValid` node, initialise on correct event. |
| 27 | World Partition actors missing on client | Not loaded in the client's streaming range / not relevant | Streaming sources, `bAlwaysRelevant`/spatial loading off for managers. |
| 28 | Nanite mesh renders wrong / falls back | Unsupported material (translucent) or feature | Use opaque/masked material; check Nanite support for the feature in your version. |

---

## 19. Roblox → Unreal map

| Roblox | Unreal | Notes |
|---|---|---|
| DataModel / `game` | `UGameInstance` + `UWorld` | |
| Workspace | `UWorld` / persistent level (World Partition) | |
| Part / MeshPart | `AStaticMeshActor` / `UStaticMeshComponent` | Collision via presets. |
| Model | Blueprint Actor class or Level Instance / Packed Level Actor | |
| ServerScriptService Script | Server-side code in GameMode or actors guarded by `HasAuthority()` | GameMode exists only on the server. |
| LocalScript | Code on the owning client: PlayerController, `IsLocallyControlled()` pawn logic, widgets | |
| ModuleScript | C++ class / module, Blueprint Function Library, Subsystem | |
| RemoteEvent (client → server) | `UFUNCTION(Server, Reliable)` on an actor the client owns | Ownership required. |
| RemoteEvent (server → client) | `UFUNCTION(Client, Reliable)` / `NetMulticast` | |
| RemoteFunction | No direct equivalent | Request RPC + response Client RPC or replicated property. |
| Attributes / ValueObjects | Replicated `UPROPERTY` with RepNotify; GAS attributes | |
| leaderstats | `APlayerState` replicated properties | |
| BindableEvent | Delegates (multicast/dynamic) | |
| CollectionService tags | Gameplay Tags / Actor Tags | |
| RunService.Heartbeat | `Tick(DeltaSeconds)` / timers | |
| `task.wait` / `task.delay` | Timers (`SetTimer`), latent Blueprint `Delay`, Ability Tasks | |
| TweenService | Timelines, curves, UMG animations, Sequencer | |
| Humanoid | `ACharacter` + `UCharacterMovementComponent` + Anim Blueprint | Health is yours (or GAS). |
| Animator / AnimationTrack | Anim Blueprint + Montages | |
| UserInputService / ContextActionService | Enhanced Input (actions + mapping contexts) | |
| ScreenGui | UMG Widget added to viewport | Anchors ≈ Scale. |
| DataStoreService | `USaveGame` locally; online needs EOS or your backend | |
| StreamingEnabled | World Partition streaming + network relevancy | |
| Players service | `AGameStateBase::PlayerArray`, `PostLogin`/`Logout` in GameMode | |
| Roblox hosting / matchmaking | You host dedicated servers; EOS sessions/lobbies | |
| Studio | Unreal Editor | |

Mindset differences: Unreal replication is explicit (nothing replicates unless the actor and property are marked),
ownership decides who may call Server RPCs, C++ memory is GC-managed only through reflected references, and you own the
whole pipeline (servers, persistence, platform certification, builds).

---

## 20. Sources

Official (checked 2026-10-13):
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-7-release-notes
- https://www.unrealengine.com/news/unreal-engine-5-7-is-now-available
- https://www.unrealengine.com/news/state-of-unreal-2026-top-news-from-the-show
- https://dev.epicgames.com/documentation/en-us/unreal-engine/objects-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-object-handling-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties
- https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-framework-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-modules
- https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime
- https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/replicate-actor-properties-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/remote-procedure-calls-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-owner-and-owning-connection-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-iris-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/stat-commands-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-insights-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-automation-tool-overview-for-unreal-engine

Community (marked where used):
- https://tomlooman.com/unreal-engine-5-8-performance-highlights/ — 5.8 cvar-level performance notes.

Note: several official URLs above are the stable slugs of Epic's documentation; Epic occasionally renames pages. A page
that 404s should be looked up by title in the documentation search rather than replaced with a guess.
