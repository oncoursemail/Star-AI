---
name: engine-uefn-verse
description: Fortnite UEFN 42.x and the Verse language (devices, failure contexts, effects, concurrency, persistence, Scene Graph beta). Use when a request names UEFN, Fortnite Creative or Verse.
---
# engine-uefn-verse
## Scope
Fortnite / UEFN 42.30 (Oct 2026), Verse language version 1. Check the project's Fortnite version and its `*.digest.verse` files first: they are the ground truth for API names.

## Core model
- An island = level + devices (prebuilt actors) + Verse code. A `creative_device` subclass is placeable; `OnBegin<override>()<suspends>:void` runs at game start.
- All Verse runs on the server. No client scripts, no RemoteEvents; UI is created per player from the server.
- Devices expose events (`.Subscribe(F)`, `.Await()`); `@editable` fields link placed devices.
- Scene Graph (entities, components, prefabs) is still beta; it coexists with devices.

## Idioms
- Failable calls use brackets inside a failure context: `if (FC := P.GetFortCharacter[], Pl := player[Agent]):`.
- `<decides>` = can fail; `<transacts>` = can roll back; `<suspends>` = async. Default effect is no_rollback.
- Mutation needs `set`: `set Count += 1`; map writes are failable: `if (set Scores[P] = 0) {}`.
- Async: `loop:` + `Sleep(1.0)`; `race:` (first wins, others canceled), `sync:` (wait all), `spawn{ F() }` (one call).
- Handlers given to `Subscribe` are not `<suspends>`; spawn the async part.
- Players: `GetPlayspace().GetPlayers()`, `GetPlayspace().PlayerAddedEvent().Subscribe(...)`.
- UI text is `message`: `Txt<localizes>(S:int):message = "Score {S}"`; `GetPlayerUI[P]` then `.AddWidget(canvas{...})`.

## Pitfalls
1. No `wait()`, `while true`, Blueprints or Tick: use `loop:` + `Sleep` in a `<suspends>` function.
2. `P.GetFortCharacter()` is wrong: failable functions are called with `[]` in `if (...)`.
3. `Subscribe` rejects `<suspends>` handlers.
4. Integer `/` is failable and yields a rational: convert in a failure context (`Floor`, `Round`, `Int`).
5. Two math modules: devices use `/UnrealEngine.com/Temporary/SpatialMath`, Scene Graph uses `/Verse.org/SpatialMath`; convert with `FromVector3`/`FromRotation`.
6. Persistence: module-scope `var M : weak_map(player, T) = map{}`; T must be persistable (`class<final><persistable>`, no `var` fields, no superclass); max 4 player maps; 256 KB per player; only add fields with defaults after release.
7. 42.20: `Fortnite.com/Marketplace` moved to `/UnrealEngine.com/Marketplace` (aliases kept; a local `Marketplace` name can now conflict).
8. 42.00: `fort_vehicle.GetPassengers()` deprecated, use `GetOccupants()`; `internal` members of `scoped` interfaces are no longer visible to the target module.
9. 42.30: client-side Scene Graph `OnReceive` is ignored; `fort_target_affiliation.Any` removed.
10. Verse forbids shadowing (a field named `Round` collides with `Round[]`).
11. An unassigned `@editable` device never fires: set it in the Details panel.

## Roblox to UEFN
Script -> `creative_device` class; LocalScript -> none; ModuleScript -> Verse module + `using`
RemoteEvent -> not needed (server only); DataStore -> `weak_map(player, T)`
PlayerAdded -> `PlayerAddedEvent()`; Humanoid -> `fort_character` (`GetFortCharacter[]`)
Heartbeat -> `loop:` + `Sleep(0.0)` or Scene Graph `OnSimulate`; task.wait(n) -> `Sleep(n)`
TweenService -> `creative_prop.MoveTo(...)` or Cinematic Sequence device
Tags -> gameplay `tag` + `FindCreativeObjectsWithTag`; Attributes -> `@editable` fields
ScreenGui -> `GetPlayerUI[P].AddWidget(...)` or UMG; UserInputService -> input_trigger_device
Playtest -> Launch Session + Push Changes; Part -> prop; Model -> prefab

## Skeleton
```verse
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }

stats := class<final><persistable>:
    Best : int = 0

var Saved : weak_map(player, stats) = map{}

zone_game_device := class(creative_device):
    @editable
    Zone : trigger_device = trigger_device{}
    @editable
    Scorer : score_manager_device = score_manager_device{}
    var Hits : [player]int = map{}

    OnBegin<override>()<suspends>:void =
        Zone.TriggeredEvent.Subscribe(OnZone)

    OnZone(MaybeAgent : ?agent):void =
        if (Agent := MaybeAgent?, P := player[Agent]):
            N := (if (V := Hits[P]) then V else 0) + 1
            if (set Hits[P] = N) {}
            Scorer.Activate(Agent)
            Old := if (S := Saved[P]) then S.Best else 0
            if (N > Old, set Saved[P] = stats{Best := N}) {}
```

## Verification
Build Verse Code in UEFN and read the compiler output; Launch Session to test in the Fortnite client. Compare names with the digest files. Say "not compiled" unless a build actually ran.
