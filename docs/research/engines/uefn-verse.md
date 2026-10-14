# Fortnite UEFN + Verse: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Fortnite / UEFN 42.30 (2026-10-01); Verse language version 1 (stabilized in 32.00, 2024-11-01).** Free editor (Windows only); islands earn via Epic's engagement payouts and in-island transactions.

## At a glance
| | |
|---|---|
| Best for | Multiplayer Fortnite "islands": shooters, tycoons, obbies/parkour, party games, racing, using Fortnite characters, weapons and devices |
| Weak at | Anything outside Fortnite's look and rules; custom netcode; client-side scripting; non-Epic platforms; offline/single-player games |
| Language(s) | Verse (statically typed, functional-logic, effect system, failure contexts); Blueprints are not available in UEFN |
| Editor / tooling | Unreal Editor for Fortnite (UEFN, Windows), Fortnite Creative (in-game), VS Code + Verse extension, Creator Portal, Unreal MCP plugin (42.00+) |
| Platforms (export) | Runs inside Fortnite on every Fortnite platform (PC, consoles, mobile, cloud); no standalone export |
| License / cost | Free; Epic's Fortnite EULA and Island Creator Rules apply; you do not own a shippable executable |
| Roblox-likeness | high: hosted platform, server-authoritative scripts, discovery + creator payouts, devices ~ Roblox prefab models; but language and data model are very different |

## Architecture and lifecycle
- A UEFN **project** is an Unreal-style content project; the playable unit is an **island**. Levels are built from Fortnite assets, imported meshes, and **devices** (prebuilt gameplay actors: trigger_device, button_device, score_manager_device, item_granter_device, mutator_zone_device, elimination_manager_device, player_spawner_device, hud_message_device, etc.).
- Verse code lives in `.verse` files in the project's Verse module. A Verse class that derives from `creative_device` becomes a placeable device; its `OnBegin<override>()<suspends>:void` runs when the game starts, `OnEnd<override>():void` when it ends.
- All Verse runs on the **server** (authoritative). There is no LocalScript equivalent for gameplay; UI built in Verse is created per player on the server and replicated.
- Devices expose **events** (`listenable(t)`) you `.Subscribe(Handler)` to, and **functions** you call (`Enable()`, `Activate(Agent)` ...). `@editable` fields link Verse to devices placed in the level (set in the Details panel).
- **Scene Graph** (Beta since 36.00, June 2025; still beta-labeled as of the 42.x notes, with publishing allowed): entities + components + prefabs, a newer object model reachable from Verse. Coexists with devices; it does not replace them. Component lifecycle: Initialized, AddedToScene, BeginSimulation, EndSimulation, RemovingFromScene, Uninitializing (`OnAddedToScene`, `OnBeginSimulation`, `OnSimulate<suspends>`, ...). Only one component of a given class/subclass per entity.
- Concurrency is structured: `<suspends>` functions can `Sleep`, `Await` events and use `sync`, `race`, `rush`, `branch`, `spawn`. Suspended tasks are canceled when their owner (race loser, disposed component, game end) ends.
- Iteration loop: edit Verse -> Build Verse Code -> Launch Session (connects a Fortnite client to the editor session) -> Push Changes / Push Verse Changes for live updates.

## Project layout
```
MyIsland/
  MyIsland.uefnproject
  Content/                 # assets, levels, prefabs, materials, UMG widgets
  Plugins/MyIsland/Content/...
  Verse/ (shown in Verse Explorer)  # *.verse files, one module per folder
    my_game_device.verse
  MyIsland.code-workspace  # opened by "Verse > Open Verse Explorer / VS Code"
```
- Module paths: `/Fortnite.com/...` (devices, characters, UI, playspaces), `/Verse.org/...` (language, Simulation, Random, Colors, SceneGraph, SpatialMath), `/UnrealEngine.com/Temporary/...` (Diagnostics, SpatialMath legacy, UI). Bring names in with `using { /Fortnite.com/Devices }`.
- Generated API digest files (`Fortnite.digest.verse`, `Verse.digest.verse`, `UnrealEngine.digest.verse`) in the project are the ground truth for names and signatures for the installed version. Read them before guessing an API.

## Scripting idioms
Device skeleton:
```verse
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }

coin_room_device := class(creative_device):
    @editable
    CoinTrigger : trigger_device = trigger_device{}
    @editable
    ScoreManager : score_manager_device = score_manager_device{}

    var CoinsTaken : int = 0

    OnBegin<override>()<suspends>:void =
        CoinTrigger.TriggeredEvent.Subscribe(OnCoin)

    OnCoin(MaybeAgent : ?agent):void =
        if (Agent := MaybeAgent?):
            set CoinsTaken += 1
            ScoreManager.Activate(Agent)
            Print("Coins taken: {CoinsTaken}")
```
Failure contexts and `<decides>`:
```verse
# Indexing, casts, option unwrap, map lookup and comparisons can FAIL; they must sit in a failure context.
if (First := Players[0], FC := First.GetFortCharacter[]):
    FC.Damage(10.0)

GetBonus(Score:int)<decides><transacts>:int =
    Score > 100          # fails (and rolls back) if not true
    5                    # only reached when the line above succeeds

if (B := GetBonus[Score]) then Print("Bonus {B}") else Print("No bonus")
```
- Call `<decides>` functions with square brackets `F[]`, never `F()`.
- `<transacts>` = effects can be rolled back (required for code that runs inside a failure context and writes `var`s). Default (no specifier) is `no_rollback`, which cannot be called in a failure context and cannot be written explicitly.
- `set` is required to mutate a `var`: `set Count += 1`. Map writes are failable: `if (set Scores[Player] = 0) {}`.
- Option: `var Target : ?agent = false`; set `option{Agent}`; unwrap with `Target?` in a failure context.

Concurrency:
```verse
RoundLoop()<suspends>:void =
    race:
        block:
            Sleep(120.0)
            Print("Time up")
        WinTrigger.TriggeredEvent.Await()   # first to finish wins, the other is canceled
    spawn{ CleanupAsync() }                 # fire-and-forget; spawn takes a single call expression
    sync:
        FadeOut()
        PlayOutro()                          # both run, wait for both
```
- Event handlers registered with `Subscribe` must NOT be `<suspends>`; spawn async work from them: `OnCoin(A:?agent):void = spawn{ Celebrate(A) }`.
- `Subscribe` returns a `cancelable`; keep it and call `.Cancel()` to unsubscribe.

Players:
```verse
OnBegin<override>()<suspends>:void =
    GetPlayspace().PlayerAddedEvent().Subscribe(OnPlayerAdded)
    for (P : GetPlayspace().GetPlayers()) { OnPlayerAdded(P) }

OnPlayerAdded(P : player):void =
    if (FC := P.GetFortCharacter[]):
        FC.EliminatedEvent().Subscribe(OnEliminated)
```
`agent` is the general "someone who triggered something"; `player` is a subtype. Cast with `player[Agent]` (failable).

Persistence (`weak_map(player, t)`; see Save data). Scene Graph component:
```verse
using { /Verse.org/Simulation }
using { /Verse.org/SceneGraph }     # older samples: /UnrealEngine.com/Temporary/SceneGraph
blink_component := class<final_super>(component):
    @editable
    Period : float = 1.0
    OnBeginSimulation<override>():void =
        (super:)OnBeginSimulation()
    OnSimulate<override>()<suspends>:void =
        loop:
            Sleep(Period)
            Print("tick")   # canceled automatically when the component is disposed
```

## Pitfalls (what AI answers get wrong)
1. **Using Roblox/Lua/Unreal C++ habits.** There is no `wait()`, no `while true do`, no Blueprints, no `Tick()` in UEFN. Use `loop:` + `Sleep(Seconds)` inside a `<suspends>` function (or `OnSimulate` for Scene Graph).
2. **`()` vs `[]` calls.** `GetFortCharacter[]`, `player[Agent]`, `Arr[I]`, `Map[K]`, `TeleportTo[...]` are failable and need `[]` inside `if (...)`, `for` filters or another `<decides>` function. Writing `P.GetFortCharacter()` is a compile error.
3. **Suspending event handlers.** `OnTriggered(A:?agent)<suspends>:void` cannot be passed to `Subscribe`; keep handlers non-suspending and `spawn{}` the async part.
4. **`spawn` takes one async call expression**, not a block: `spawn{ Run() }` OK; multi-statement block inside `spawn` is not.
5. **Integer division is failable and returns `rational`**: `Total / 2` must be in a failure context and converted, e.g. `if (Half := Floor(Total / 2))` (verify exact conversion against the digest for your version). Float -> int: `Int[F]`, `Floor[F]`, `Round[F]` are failable.
6. **Two SpatialMath modules.** Classic device APIs use `/UnrealEngine.com/Temporary/SpatialMath` (`vector3`, `rotation`); Scene Graph uses `/Verse.org/SpatialMath`. Convert with `FromVector3` / `FromRotation`; importing both unqualified causes ambiguous names.
7. **Persistence limits.** At most 4 `weak_map(player, ...)` module variables per island; 256 KB per player record; persistable classes must be `<final><persistable>`, have no superclass, no `var` members; after release you may only add fields with defaults. Rolling back an island resets player data.
8. **42.20/42.30 API moves.** `Fortnite.com/Marketplace` moved to `/UnrealEngine.com/Marketplace` (aliases kept, but `using { /UnrealEngine.com }` + a local `Marketplace` symbol now conflicts). `fort_vehicle.GetPassengers()` is deprecated -> `GetOccupants()`. `fort_template_ability` is no longer parametric; `fort_target_affiliation.Any` removed.
9. **Scoped `internal`.** Since 42.00, `internal` members of a `scoped` interface are no longer visible to the targeting module; use `public`/`protected`.
10. **Client `OnReceive` (Scene Graph scene events) is ignored since 42.30** and logs a message; dispatch from the server path.
11. **Strings vs `message`.** UI text wants `message`, not `string`: declare `Label<localizes>(S:string):message = "{S}"`. Passing a `string` to `text_block{DefaultText := ...}` fails to compile.
12. **Assuming Scene Graph is final.** It is beta; APIs and module paths moved (`/UnrealEngine.com/Temporary/SceneGraph` in older samples vs `/Verse.org/SceneGraph` in current API reference). Check the digest.
13. **Physics (Beta) toggle moved** to the Island Settings device in 42.00 (not Project Settings).
14. **No shadowing.** Verse rejects a local or field whose name shadows another visible identifier (e.g. a field named `Round` next to the `Round[]` function). Pick distinct names.
15. **`@editable` default must be constructible**: `MyButton : button_device = button_device{}`; forgetting to assign the placed device in the Details panel leaves a dummy device that never fires.

## Rendering
Unreal Engine 5 renderer under Fortnite's scalability (Nanite and Lumen on supported platforms; mobile uses lower tiers). Materials/meshes via UEFN content browser; imported assets must pass memory budget (island memory limit shown as 300 MB, still 100,000 "units" internally as of 42.30) and validation (missing LODs flagged; new imports default Min LOD for Low/Medium = 2 since 42.00). Post-process, sky, fog via devices/volumes. No custom shaders beyond material graphs.

## Physics
Fortnite character movement is built in. Scene Graph + Physics (Beta) adds rigid body simulation (enabled per island via Island Settings device since 42.00). Collisions/overlaps for gameplay are usually done via devices (trigger_device, mutator_zone_device, damage_volume_device) and their events (`AgentEntersEvent`, `TriggeredEvent`). `fort_character.TeleportTo[Position, Rotation]` (failable), `.Damage(Amount)`, `.Heal(Amount)`.

## Input
No raw key polling in classic Verse. Use input_trigger_device (bind to Fortnite input actions, events `PressedEvent`/`ReleasedEvent`), button_device interactions, signal_remote_manager_device. 42.00 added a Platform Controls Query (touch detection) and developer-customizable touchscreen controls (41.00, UMG Touch Control Layout Override widgets assigned via HUD Controller device). Verse Camera Modifiers are experimental.

## UI
- Verse UI: `GetPlayerUI[Player]` then `.AddWidget(canvas{...})` / `.RemoveWidget(W)`; widgets in `/UnrealEngine.com/Temporary/UI` and `/Fortnite.com/UI` (`canvas`, `canvas_slot`, `text_block`, `button_loud`, `button_quiet`, `stack_box`, `overlay`, `color_block`, `texture_block`).
- UMG widgets authored in UEFN can be driven from Verse (Verse support for UMG UI fields since 38.00; 42.30 lets Verse event fields bind to UMG widgets).
- Device UI: hud_message_device, billboard_device, popup_dialog_device, map_indicator_device; often enough without Verse.
```verse
using { /UnrealEngine.com/Temporary/UI }
using { /Fortnite.com/UI }
ScoreText<localizes>(S:int):message = "Score: {S}"
ShowScore(P:player, S:int):void =
    if (UI := GetPlayerUI[P]):
        UI.AddWidget(canvas{Slots := array{canvas_slot{Widget := text_block{DefaultText := ScoreText(S)}}}})
```

## Networking and multiplayer
Fully managed by Fortnite: dedicated servers, matchmaking, player counts set in Island Settings. Verse is server-authoritative; there are no RemoteEvents because there is no player-side code. Per-player state = maps keyed by `player`/`agent`. Teams via team_settings/class_designer devices and `GetPlayspace().GetTeamCollection()`. Chat/voice channel APIs exist in `/Verse.org/Chat` (verify per version).

## Save data
```verse
player_stats := class<final><persistable>:
    Version : int = 1
    Coins : int = 0
    BestTime : float = 0.0

var Saved : weak_map(player, player_stats) = map{}   # module scope, outside any class

GetStats(P:player):player_stats =
    if (S := Saved[P]) then S else player_stats{}

AddCoins(P:player, N:int):void =
    Old := GetStats(P)
    if (set Saved[P] = player_stats{Version := Old.Version, Coins := Old.Coins + N, BestTime := Old.BestTime}) {}
```
Rules (official): only readable/writable while that player is in the session; `weak_map(session, t)` is per round only; persistable types are primitives, arrays/maps/options/tuples of persistables, `<persistable>` structs/enums, `<final><persistable>` classes (no `var` fields, no superclass); 256 KB per player record (~24k numbers); check with `FitsInPlayerMap` before saving large data; max four player-keyed weak_maps; compatibility check runs on Launch Session/Push Changes/first release; rollback resets data. Since classes have no `var` fields, "updating" means constructing a new instance (copy pattern above).

## Performance
- Island memory budget (100,000 units, displayed as 300 MB) is enforced at upload; check via profiling tools (moved there in 42.30). Use LODs, HLODs and World Partition streaming.
- Verse: avoid tight `loop:` without `Sleep`; prefer event subscriptions; avoid per-frame UI rebuilds (keep widget references and `SetText`).
- `<localizes>` heavy modules were optimized in 42.30 (2,000+ previously hung loads).
- Device count and replicated props cost server time; use Scene Graph prefabs carefully (beta perf).

## Build and export
No export. Build Verse -> Launch Session -> Upload to private version -> release through the Creator Portal after moderation (Content Pre-Checks in editor are informational). Islands get an island code; ratings via IARC questionnaire. Creator Economy: engagement payouts from a revenue pool; in-island transactions (sell durable/consumable items, bundles, paid areas; not standard Fortnite cosmetics) launched January 2026 with 100% of V-Bucks value to creators through 2027-01-31, then 50%. 42.30: Rocket Racing template islands were removed; UEFN Source Assets can be sold on Fab from 2026-10-15 (88% to creators). Unreal MCP (42.00) lets local coding agents compile Verse, place devices, create Scene Graph entities and run play sessions.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| "This invocation calls a function that has the 'decides' effect..." | Called failable function with `()` or outside a failure context | Use `F[]` inside `if (...)` |
| Handler never fires | `@editable` field not assigned in Details panel, or device disabled | Select the Verse device in the level and set the reference; check `Enable()` |
| "Subscribe ... expected function without suspends" | Handler marked `<suspends>` | Remove `<suspends>`; `spawn{ Async(...) }` inside |
| Ambiguous `vector3` | Both SpatialMath modules imported | Qualify or use `FromVector3` |
| Persistence compile error after update | Changed a persisted field type / removed field | Only add fields with defaults; keep old shape |
| Text widget compile error | Passed `string` where `message` required | `<localizes>` helper function |
| Player data lost when testing | Session-only map (`weak_map(session, ...)`) or rollback | Use `weak_map(player, ...)` at module scope |
| Verse change not visible in session | Did not Build Verse / Push Verse Changes | Build, then Push Changes |
| Upload blocked | Memory over budget or experimental feature (e.g. Telekineticon) | Reduce memory; remove experimental devices |

## Mapping from Roblox
| Roblox | UEFN / Verse | Notes |
|---|---|---|
| Workspace / Instance tree | Level actors + Outliner; Scene Graph entity hierarchy (beta) | No dynamic Instance.new for arbitrary actors; prop_manipulator/spawners or Scene Graph `entity` |
| Part | Static mesh prop / building piece; `creative_prop` | `creative_prop.TeleportTo[...]`, `.Hide()`, `.Show()` |
| Model | Prefab (Scene Graph) / grouped props | |
| Script (server) | `creative_device` subclass in `.verse` | All Verse is server-side |
| LocalScript | No equivalent | UI is created per player from the server |
| ModuleScript | Verse module (folder) + `using { /MyProject/Module }` | |
| RemoteEvent | Not needed | No client code; device events instead |
| DataStore | `weak_map(player, t)` persistable module var | 256 KB/player, 4 maps max |
| Players / PlayerAdded | `GetPlayspace().GetPlayers()`, `PlayerAddedEvent()` | |
| Humanoid | `fort_character` via `Player.GetFortCharacter[]` | Damage/Heal/TeleportTo/EliminatedEvent |
| RunService.Heartbeat | `loop:` + `Sleep(0.0)` in a `<suspends>` fn, or `OnSimulate` | No per-frame callback in devices |
| RenderStepped | No equivalent | |
| TweenService | Cinematic Sequence device; `creative_prop.MoveTo(...)<suspends>` | MoveTo animates over seconds |
| CollectionService tags | Gameplay tags: `tag` subclasses + `FindCreativeObjectsWithTag` | Fixed in 42.00 after a regression |
| Attributes | `@editable` fields | Set in Details panel |
| ScreenGui | `GetPlayerUI[P].AddWidget(canvas{...})` or UMG widget | `message` type for text |
| UserInputService | input_trigger_device events | No raw key polling |
| task.wait(n) | `Sleep(n)` | Only in `<suspends>` |
| Studio playtest | Launch Session + Push Changes | Runs in a real Fortnite client |
| Publishing | Creator Portal release after moderation | Engagement payouts + in-island transactions |

## Minimal example
```verse
# Tag-zone score game: stepping into the trigger scores a point, persists best score.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }

score_save := class<final><persistable>:
    Best : int = 0

var BestScores : weak_map(player, score_save) = map{}

zone_score_device := class(creative_device):
    @editable
    Zone : trigger_device = trigger_device{}
    @editable
    ScoreManager : score_manager_device = score_manager_device{}

    var RoundScores : [player]int = map{}

    OnBegin<override>()<suspends>:void =
        Zone.TriggeredEvent.Subscribe(OnZone)
        race:
            Sleep(90.0)
            Zone.TriggeredEvent.Await()
        Print("First zone hit or time over")

    OnZone(MaybeAgent : ?agent):void =
        if (Agent := MaybeAgent?, P := player[Agent]):
            Current := (if (V := RoundScores[P]) then V else 0) + 1
            if (set RoundScores[P] = Current) {}
            ScoreManager.Activate(Agent)
            Old := if (S := BestScores[P]) then S.Best else 0
            if (Current > Old, set BestScores[P] = score_save{Best := Current}) {}
```

## Sources
- https://dev.epicgames.com/documentation/en-us/uefn/whats-new-in-unreal-editor-for-fortnite (release list; 42.30 on 2026-10-01, 42.00 on 2026-08-20)
- https://dev.epicgames.com/documentation/en-us/fortnite/42-00-fortnite-ecosystem-updates-and-release-notes (scoped internal change, GetPassengers deprecation, Physics toggle, Unreal MCP, camera/abilities experimental)
- https://dev.epicgames.com/documentation/en-us/fortnite/42-30-fortnite-ecosystem-updates-and-release-notes (Marketplace path move, ability API changes, client OnReceive ignored, memory limit display, Fab source assets)
- https://dev.epicgames.com/documentation/fortnite/38-00-fortnite-ecosystem-updates-and-release-notes (Verse support for UMG UI fields)
- https://dev.epicgames.com/documentation/fortnite/36-00-fortnite-ecosystem-updates-and-release-notes (Scene Graph beta)
- https://www.fortnite.com/news/publish-fortnite-islands-created-with-scene-graph-now-in-beta (Scene Graph publishable beta)
- https://dev.epicgames.com/documentation/fortnite/using-persistable-data-in-verse (weak_map rules, limits, persistable types)
- https://dev.epicgames.com/documentation/fortnite/verse-persistence-best-practices (versioned player_data, FitsInPlayerMap)
- https://dev.epicgames.com/documentation/en-us/fortnite/creating-your-own-component-using-verse-in-unreal-editor-for-fortnite (component lifecycle, class<final_super>(component))
- https://dev.epicgames.com/documentation/fortnite/scene-graph-known-issues-in-fortnite (SpatialMath conversion FromVector3/FromRotation)
- https://dev.epicgames.com/documentation/en-us/uefn/verse-language-version-updates-and-deprecations-in-verse (Verse V1 stabilization in 32.00)
- https://dev.epicgames.com/documentation/fortnite/specifiers-and-attributes-in-verse (effects; via search snippets: no_rollback default, transacts)
- https://www.fortnite.com/news/tools-for-in-island-transactions-now-available-to-fortnite-developers (in-island transactions, payout share)
- https://www.fortnite.com/news/unreal-mcp-is-now-available-in-uefn (Unreal MCP, 2026-08-20)
- https://uefncentral.com/verse-effects-explained (community: decides/suspends usage notes)

## Confidence and gaps
- High: release versions/dates, persistence rules, 42.x breaking changes, Scene Graph beta status, payout dates.
- Medium: exact module path for Scene Graph component (`/Verse.org/SceneGraph` per API reference; older samples use `/UnrealEngine.com/Temporary/SceneGraph`), integer-division conversion form, UI widget module split. Check the project's `*.digest.verse`.
- Not verified: "Persona" feature (nothing found); 39.x-41.x per-release Verse notes were not read individually; whether in-island transactions launched exactly on 2026-01-09.
- The official specifiers page did not render for the fetcher; effect descriptions come from search snippets of that page.
