# Sources for unreal-cpp-gameplay

Checked against the official Unreal Engine documentation (labelled 5.8) on 2026-10-13. Epic's documentation is not openly
licensed: the guidance is written in STAR's own words and only links to the pages. Deeper reference: docs/research/engines/unreal.md.

| Claim in the skill | Documentation page |
|---|---|
| Reflection macros, GENERATED_BODY, naming prefixes | https://dev.epicgames.com/documentation/en-us/unreal-engine/objects-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/epic-cplusplus-coding-standard-for-unreal-engine |
| GC sees only reflected references; UPROPERTY keeps UObjects alive; weak and soft pointers | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-object-handling-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties |
| Actor lifecycle: constructor, BeginPlay, EndPlay, deferred spawning | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle and https://dev.epicgames.com/documentation/en-us/unreal-engine/spawning-actors-in-unreal-engine |
| Tick control and timers | https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-ticking-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine |
| GameMode, GameState, PlayerController, PlayerState, Pawn roles | https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-framework-in-unreal-engine |
| Modules and Build.cs dependencies | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-modules and https://dev.epicgames.com/documentation/en-us/unreal-engine/module-properties-in-unreal-engine |
| Live Coding limits | https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime |
| Enhanced Input actions, mapping contexts, AddMappingContext, BindAction, ETriggerEvent | https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/EnhancedInput/UEnhancedInputComponent |
| Blueprint exposure specifiers and best practice | https://dev.epicgames.com/documentation/en-us/unreal-engine/exposing-gameplay-elements-to-blueprints-visual-scripting-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-best-practices-in-unreal-engine |
| Subsystems | https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine |

API names verified against the official reference on 2026-10-13: UCLASS, USTRUCT, UENUM, UPROPERTY, UFUNCTION, GENERATED_BODY,
TObjectPtr, TWeakObjectPtr, TSoftObjectPtr, IsValid, CreateDefaultSubobject, AActor::BeginPlay, AActor::EndPlay,
UWorld::SpawnActorDeferred, AActor::FinishSpawning, PublicDependencyModuleNames, PrivateDependencyModuleNames,
UEnhancedInputLocalPlayerSubsystem::AddMappingContext, UEnhancedInputComponent::BindAction, ETriggerEvent, HasAuthority,
IsLocallyControlled, UCharacterMovementComponent.
No compile or editor run is claimed.
