# Verse (UEFN / Unreal Engine) for STAR (research, checked 2026-10-13)

Status: the language semantics come from Epic's official **Book of Verse** (github.com/verselang/book, read 2026-10-13). It documents the head of Verse's main development branch, so a few described features are unreleased: the book itself marks **live variables** (`set live`, `when`, `upon`) as "Unreleased Feature" [1][2].

- Verse ships today in **UEFN (Unreal Editor for Fortnite)**. A third-party tracker lists UEFN v41.20 (16 Jul 2026) as the latest release it covers [9].
- Secondary press coverage (GamesBeat, Automaton, 17–18 June 2026) reports that Epic announced **Unreal Engine 6** at State of Unreal on 17 June 2026, built around Verse and the Scene Graph and merging UE5 with UEFN, with Early Access targeted for late 2027 [10][11].

Unverified as of 2026-10-13 (no Epic primary page fetched):
- the exact UE6 dates
- Blueprint deprecation plans
- the current UEFN version number
- per-player persistence size limits

Epic's documentation site (dev.epicgames.com) renders client-side and could not be fetched as text, so facts come from the Book of Verse repo plus secondary sources.

---

## 1. Mental model

Verse is a **functional-logic language with imperative conveniences**, designed by Epic (Simon Peyton Jones, Lennart Augustsson, Tim Sweeney et al.) for a "metaverse-first" single global simulation [2]. Five ideas matter more than syntax:

1. **Failure, not booleans, drives control flow.** An expression either *succeeds* with a value or *fails* with no value. `if (X := Arr[I])` branches on whether indexing succeeded. There are no exceptions, and failure is not an error [3].
2. **Failable calls use square brackets.** A function marked `<decides>` is called `F[x]`, and only inside a **failure context** (`if` condition, `for` domain, `<decides>` body, `or` left side, `option{...}`, `not`). Ordinary calls use `()` and must succeed [3][4].
3. **Transactions.** In a failure context, state changes are **speculative**: if the context fails, every `set` performed inside it (even across nested method calls) is rolled back [3].
4. **Effects are declared in the signature** (`<computes>`, `<reads>`, `<writes>`, `<allocates>`, `<transacts>`, `<decides>`, `<suspends>`, `<converges>`, `<predicts>`). The compiler rejects calls that exceed the caller's effects [4].
5. **Structured concurrency** (`sync`, `race`, `rush`, `branch`) inside `<suspends>` functions, plus `spawn` as the one unstructured escape hatch [5].

Everything is an expression (`if`, `for`, `case`, blocks yield values). Identifiers are conventionally `PascalCase` for functions/variables and `snake_case` for types (`player_profile`, `creative_device`).

## 2. Type system

- Static, strong, with inference for constants (`X := 5`) and subtyping. Primitives: `logic` (`true`/`false`), `int`, `float`, `rational`, `char`, `char32`, `string`, plus `any`, `void`, `comparable`, `type` [6].
- **int**: integer literals must fit 64-bit. On **VerseVM** arithmetic is arbitrary precision, while the older **BPVM** raises `MathIntrinsicCallFailure` on 64-bit overflow. Stay within 64 bits for portable code [6].
- **Integer `/` is failable and yields a `rational`** (exact fraction, `7/3`). Division by zero fails. Convert with `Floor(R)`/`Ceil(R)`. `int` is a subtype of `rational`. Float operations: `Floor[F]`, `Ceil[F]`, `Round[F]`, `Int[F]` are failable (`[]`) because NaN/Inf cannot convert [6].
- Containers [7]:
  - Option `?t` (`false` is empty, `option{V}` is filled, `O?` unwraps and is failable).
  - Tuple `(1, 2.0, "x")`, indexed `T(0)` (compile-time checked).
  - Array `[]t` written `array{1,2,3}`. It is immutable, 0-based, `A[I]` is failable, `.Length`, `+` concatenates, and `set A += array{4}` works on a `var`.
  - Map `[k]v` written `map{"a" => 1}`. Lookup `M[K]` is failable, and `set M[K] = V` is a failable write.
  - `weak_map(k, v)`, used for persistence.
- **Immutability by default**: a plain `X:int = 1` or `X := 1` cannot change. Mutable variables need `var` **with an explicit type and initial value** (`var Health:float = 100.0`; `var H := 1.0` is an error) and are updated only with `set` [8].
- Classes `class`, structs `struct` (value-like, no methods with effects beyond construction), interfaces `interface`, enums `enum{A, B}`, modules `module`. Class specifiers include `<abstract>`, `<final>`, `<concrete>` (all fields have defaults, so it can be constructed with `T{}`), `<unique>` (identity equality), `<persistable>`, `<castable>` and `<final_super>`. Access specifiers: `<public>`, `<protected>`, `<private>`, `<internal>` (module default), `<scoped{...}>` [1].
- Casting is failable: `if (Char := fort_character[Agent])`-style casts use `T[value]` to downcast [3].
- Parametric types: `my_box(t:type) := class{ Value:t }`. Functions take `t:type` parameters with `where t:subtype(comparable)` constraints.

## 3. Runtime, concurrency and async model

**Effects** (from the Book's table) [4]:

| Specifier | Meaning | Notes |
|---|---|---|
| (none) | default = reads, writes, allocates, succeeds, dictates | like `<transacts>` but cannot fail |
| `<transacts>` | reads + writes + allocates; changes can be rolled back | exclusive |
| `<computes>` | pure: no heap effects | exclusive; `<computes><decides>` OK |
| `<reads>`, `<writes>`, `<allocates>` | finer heap effects | additive |
| `<decides>` | may fail; call with `[]` | additive; **cannot combine with `<suspends>`** |
| `<suspends>` | may suspend (async); can call `Sleep`, `Await`, use `sync`/`race`/... | additive |
| `<converges>` | guaranteed to terminate | only on `<native>` functions, abstract methods, type signatures |
| `<predicts>` | may run with client prediction | clears `dictates` |
| `no_rollback` (internal) | transactions disallowed | being deprecated |

At most one *exclusive* specifier (`<converges>`, `<computes>`, `<transacts>`). Duplicates are errors. Epic's UEFN docs historically required `<transacts>` alongside `<decides>` on user functions (`F()<transacts><decides>:void`). The Book now shows `<decides>` alone in places. **Write `<transacts><decides>` for UEFN** unless the user's compiler accepts the shorter form [3][4][12].

**Concurrency** [5]:

```verse
# Structured: all need a <suspends> context
FightRound()<suspends>:void =
    sync:                       # run all arms concurrently, wait for all; results in written order
        PlayIntro()
        CountdownTimer(3.0)
    Winner := race:             # first to finish wins; the others are CANCELLED
        block:
            Sleep(60.0)
            "timeout"
        block:
            AllEnemiesDefeated.Await()
            "victory"
    rush:                       # first to finish continues; losers keep running in background
        SlowSave()
        Sleep(0.5)
    branch:                     # fire-and-forget bound to the enclosing scope:
        AmbientMusic()          # cancelled when the enclosing function returns
    Print("Result: {Winner}")

# Unstructured: works anywhere (even non-suspends code); returns task(t)
OnPlayerAdded(Agent:agent):void =
    spawn{ WelcomeSequence(Agent) }   # body must be a <suspends> call; cannot spawn a <decides> function
```

- `Sleep(Seconds)` suspends. `Sleep(0.0)` waits until the next simulation update. Events: `event(t)`, `.Signal(V)`, `.Await()`. Device events are `listenable(t)` with `.Subscribe(Handler)` (the handler is an immediate function, so do async work via `spawn`) or `.Await()` inside `<suspends>` code.
- `task(t)` from `spawn` supports `.Await()` and `.Cancel()`. Cancelled structured arms run their `defer:` blocks.
- `Err("msg")` is a **runtime error**: unrecoverable, it propagates up and terminates the task. It is not catchable [3].
- Live variables (`set live X = Y + 1`, `when`, `upon`) are **documented but unreleased** [2].

## 4. Tooling and package management

- **UEFN** (Windows) is the only shipping toolchain: Verse files live in the project's `Content/` (or `Plugins/<Project>/Content`), and you edit in **VS Code with the Verse extension** (launched from UEFN: Verse > Open in VS Code). Build with "Verse > Build Verse Code" (Ctrl+Shift+B) and push changes to the live session.
- The API surface lives in generated digests (`Fortnite.digest.verse`, `Verse.digest.verse`, `UnrealEngine.digest.verse`). Consult them for exact device/class signatures, and do not invent APIs.
- Modules: `using { /Fortnite.com/Devices }`, `using { /Verse.org/Simulation }`, `using { /UnrealEngine.com/Temporary/Diagnostics }`, `using { /Fortnite.com/Characters }`, `using { /UnrealEngine.com/Temporary/SpatialMath }`. Your own modules use folder paths (`/YourName@fortnite.com/Project/Module`).
- No public package manager. Sharing happens via UEFN projects/assets. Epic has stated an intention to open the language (the Book is public on GitHub, and a community repo collects papers). Treat any claim of a standalone open-source Verse compiler as unverified.
- **Versioned language/persistence evolution**: the Book's chapter 18 "evolution" covers compatibility rules once an island is live. Persistable types cannot change shape incompatibly after release [1].

## 5. Testing

- No mainstream unit-test framework. Test in **UEFN live edit sessions** (Launch Session), using `Print()` and the **Verse log**, `Logger := log{Channel := my_log_channel}` with a `log_channel` class, and on-screen debug draw (`debug_draw` in `/UnrealEngine.com/Temporary/Diagnostics`).
- Design for testability: keep game rules in pure `<computes>` or `<transacts><decides>` functions with no device dependency, so they can be exercised from a test device's `OnBegin` with asserts expressed as failures (`if (not Validate[...]) { Print("FAIL ...") }`).
- The Book's own examples are compiled by a `versetest` harness, which suggests internal tooling but is not a public user framework [1].

## 6. Idiomatic patterns

**A creative device** (the entry point of most UEFN Verse):

```verse
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }

coin_game_device := class(creative_device):
    @editable
    CollectButton:button_device = button_device{}
    @editable
    Reward:int = 10

    var Scores:[agent]int = map{}

    OnBegin<override>()<suspends>:void =
        CollectButton.InteractedWithEvent.Subscribe(OnCollect)

    OnCollect(Agent:agent):void =
        Current := if (S := Scores[Agent]) then S else 0
        if (set Scores[Agent] = Current + Reward):   # map write is failable: put it in a failure context
            Print("Score now {Current + Reward}")
```

**Failure as validation with rollback** [3]:

```verse
wallet := class:
    var Gold:int = 100
    TryBuy(Cost:int)<transacts><decides>:void =
        set Gold = Gold - Cost      # provisional
        Gold >= 0                   # if this fails, the subtraction is rolled back

W := wallet{}
if (W.TryBuy[150]) then Print("bought") else Print("too expensive")   # Gold is still 100
```

**Defaulting and option**:

```verse
Name := if (N := MaybeName?) then N else "Guest"
Value := Arr[I] or 0                       # `or` handles failure of the left side
FirstHigh := option{ first(S : Scores, S > 100). S }   # wraps failure into ?int (see Book ch. 8)
```

**Loops**: `for (X : Items, X.Active?)` filters (failure skips the iteration). `for (I := 0..N-1)` gives a range. `loop:` with `break`. `for` yields an array of results (`Doubled := for (X : Nums) { X * 2 }`).

**Persistence** [13]:

```verse
player_profile := class<final><persistable>:
    Version:int = 1
    BestTime:float = 0.0
    Unlocked:[]string = array{}

var Profiles:weak_map(player, player_profile) = map{}   # must be module-scoped

SaveBest(P:player, T:float)<transacts>:void =
    Old := if (Prof := Profiles[P]) then Prof else player_profile{}
    if (set Profiles[P] = player_profile{ Version := Old.Version, BestTime := T, Unlocked := Old.Unlocked }) {}
```

Persistable class rules [13]:
- `<final>`
- not `<unique>`
- no superclass or interface
- not parametric
- only persistable field types
- **no `var` fields**
- field initializers cannot call functions

Persisted integers must fit 64 bits (`IntegerBoundsExceeded`). Records are immutable, so replace the whole value to update it.

## 7. Top pitfalls and error-message fixes

Verse errors are reported with numeric codes (for example `3512`, `3510`). The texts below are representative, so match on meaning.

| Error (representative text / code) | Cause | Fix |
|---|---|---|
| `This invocation calls a function that has the 'decides' effect, which is not allowed by its context.` | Called a failable function/expression outside a failure context | Wrap in `if (...)`, use `or` fallback, or mark the caller `<decides>` |
| Calling `F()` on a `<decides>` function (wrong bracket) | `<decides>` functions are called with `[]` | `F[x]` inside a failure context |
| `This expression can fail, but ...` on `set M[K] = V` / `A[I]` (3512-style) | Map writes and array indexing are failable | `if (set M[K] = V) {}`; `if (X := A[I])` |
| `This invocation calls a function that has the 'suspends' effect, which is not allowed by its context.` | `Sleep`/`Await`/`sync` in an immediate function (e.g. a `Subscribe` handler) | Mark `<suspends>` or `spawn{ AsyncWork() }` from the handler |
| `<suspends>` and `<decides>` together rejected | The combination is illegal | Split: a `<suspends>` wrapper that calls a `<decides>` check in `if` |
| `spawn` of a `<decides>`/non-suspends function rejected (3511/3538) | `spawn` needs a `<suspends>` call | Wrap in a `<suspends>` function |
| `var Health := 100.0` rejected | `var` needs an explicit type | `var Health:float = 100.0` |
| Assigning without `set` / to a non-var | Immutability by default | Declare `var`, update with `set X = ...` |
| Integer `/` where an `int` is expected | `/` on ints yields failable `rational` | `if (R := A / B) { Q := Floor(R) }`, or use float math |
| `Floor(MyFloat)` rejected | Float→int conversion is failable | `if (I := Floor[MyFloat])` / `Int[MyFloat]` |
| Persistable class rejected (3662/3663/3664/3665) | `var` field, missing `<final>`, `<unique>`, superclass/interface | Follow the persistable rules above |
| Function in a field initializer rejected (3582) | Initializers must be literals/constants | Compute in `OnBegin` or a constructor function |
| `Unknown identifier` for a device class | Missing `using { /Fortnite.com/Devices }` | Add the right `using` |
| `@editable` device is `{}` default at runtime | Not assigned in the UEFN Details panel | Select the Verse device in the level and assign references |
| Runtime: `MathIntrinsicCallFailure` | 64-bit overflow on BPVM | Clamp values; avoid huge products |
| Runtime error from `Err()` kills the task | `Err` is not catchable | Use failure (`<decides>`) for expected conditions |

## 8. Performance

- Verse runs server-side in Fortnite (server authority, `dictates`). Keep per-tick work small: avoid `loop: Sleep(0.0)` polling of many agents. Prefer `Await()` on events and `Subscribe`.
- Arrays are immutable values, so `set A += array{X}` in a loop copies. Build with `for` comprehensions or maps.
- Each spawned task costs memory. Cancel tasks (`task.Cancel()`) or use `race` with an end-of-round event so per-player loops end when the player leaves.
- UEFN has memory budgets for islands (the editor's memory calculator). Verse objects count toward them.
- Speculative execution means work inside a failing `if` condition is wasted and rolled back. Put cheap checks first in a failure context.

## 9. Security

- Server-authoritative by design: Verse game logic runs on the server, and clients only send input through devices. Still **validate state transitions** (cooldowns, currency) in Verse rather than trusting device event frequency, and rate-limit handlers that grant rewards.
- Persistence is per player via `weak_map(player, t)`. Validate and version (`Version:int` field) before migrating saved data. Range-check ints before persisting.
- No file, network or OS access exists in Verse for UEFN islands, so there is no injection surface there. The risks are economic exploits and griefing via device spam.
- Respect Epic's creator rules (e.g. no misleading rewards). Islands are certified by Epic before going live.

## 10. Game-dev usage

- `creative_device` subclasses placed in the level, `@editable` references to built-in devices (triggers, buttons, item granters, HUD message devices, `player_spawner_device`, `elimination_manager`), and `GetPlayspace().GetPlayers()` / `PlayerAddedEvent()` for player lifecycle.
- `agent` is the base for players and NPCs. Get the character with `if (FC := Agent.GetFortCharacter[])`, then `FC.Damage(10.0)`, `FC.GetTransform()`, `FC.TeleportTo[Pos, Rot]`.
- UI via `/UnrealEngine.com/Temporary/UI` and `/Fortnite.com/UI` (canvas, `text_block`, `button_loud`), added with `GetPlayerUI[Player].AddWidget(...)`.
- **Scene Graph** (entities + components, prefabs) is Epic's new Verse-first object model (entity/component classes in Verse). UE6 is reported to adopt it as the core gameplay framework [10][11]. Check the user's UEFN version for whether Scene Graph APIs are beta or released.
- NPC behaviours: `npc_behavior` subclasses with `OnBegin<override>()<suspends>`.

## 11. Cheat sheet vs Luau

| Concept | Luau | Verse |
|---|---|---|
| Indexing base | 1 | 0; `A[I]` is failable |
| Null | `nil` | no null; option `?t` (`false` = empty, `option{x}`) |
| Truthiness | `nil`/`false` falsy | no truthiness: conditions are *success/failure*; `logic` must be queried `B?` |
| Equality | `==`, `~=` | `=`, `<>` (both failable comparisons) |
| Assignment | `x = 1` | `X := 1` (constant) / `var X:int = 1` + `set X = 2` |
| String concat | `..` | `+` on strings; interpolation `"{X}"` |
| Interpolation | `` `{x}` `` | `"Score: {X}"` |
| Tables/maps | `{}` | `array{}` (`[]t`), `map{K => V}` (`[k]v`), tuples, structs |
| Length | `#t` | `A.Length` |
| Methods/self | `function T:m()` + `self` | `m():void =` inside `class`; `Self` |
| Closures | anonymous functions | nested functions; lambdas limited (no general anonymous function literal in UEFN) |
| Coroutines vs async | `task.spawn`, `task.wait` | `<suspends>`, `Sleep`, `sync`/`race`/`rush`/`branch`, `spawn{}` |
| Integer division | `//` | `/` gives failable `rational`; `Floor(R)` |
| Error handling | `pcall`/`error` | failure (`<decides>`, `if`, `or`) for expected cases; `Err()` is uncatchable |
| Modules | `require(ModuleScript)` | `using { /Path/Module }`, `module:` |
| Events | `:Connect(fn)` | `.Subscribe(fn)`, `.Await()` |
| Types | gradual, `--!strict` | static, mandatory where not inferable; effects in signatures |
| Mutation | anything mutable | immutable by default; `var` + `set`; transactions roll back on failure |
| Persistence | DataStoreService (async, yields, can error) | module-scoped `weak_map(player, t)` of `<persistable>` types (auto loaded/saved) |
| Comments | `--` | `#` and `<# block #>` |

## 12. Recent changes and version notes

- Verse launched with UEFN (March 2023). UEFN updates track Fortnite seasons. A third-party tracker lists v39.00 (29 Nov 2025) through v41.20 (16 Jul 2026), mostly adding device classes and keeping existing code compiling [9].
- The Book of Verse (public GitHub, maintained by Epic) is the language reference at the head of development. It includes unreleased features (live variables) [1][2].
- VerseVM (arbitrary-precision ints) vs BPVM (64-bit, overflow runtime error) both appear in the Book [6].
- Unreal Engine 6 (announced 17 June 2026 per press): it merges UE5 and UEFN around Verse and Scene Graph, keeps Blueprints supported at Early Access per some reports, and targets Early Access in late 2027. Treat the dates and Blueprint plans as **unverified** [10][11].

## Sources

1. Book of Verse repository (Epic Games), https://github.com/verselang/book (accessed 2026-10-13)
2. Book of Verse, Overview and Live Variables chapters, https://github.com/verselang/book/blob/main/docs/00_overview.md and https://github.com/verselang/book/blob/main/docs/15_live_variables.md
3. Book of Verse, Failure, https://github.com/verselang/book/blob/main/docs/08_failure.md
4. Book of Verse, Effects, https://github.com/verselang/book/blob/main/docs/13_effects.md
5. Book of Verse, Concurrency, https://github.com/verselang/book/blob/main/docs/14_concurrency.md
6. Book of Verse, Primitives, https://github.com/verselang/book/blob/main/docs/02_primitives.md
7. Book of Verse, Containers, https://github.com/verselang/book/blob/main/docs/03_containers.md
8. Book of Verse, Mutability, https://github.com/verselang/book/blob/main/docs/05_mutability.md
9. UEFN version history (third party, unofficial), https://uefncentral.com/uefn-releases
10. GamesBeat, "Unreal Engine 6 will combine UE5 and UEFN into a unified engine", https://gamesbeat.com/unreal-engine-6-will-combine-ue5-and-uefn-into-a-unified-engine-state-of-unreal/
11. Automaton (JP), UE6 early access late 2027, https://automaton-media.com/articles/newsjp/20260618-450312/
12. Epic: Failure in Verse (UEFN docs), https://dev.epicgames.com/documentation/en-us/uefn/failure-in-verse
13. Book of Verse, Persistable types, https://github.com/verselang/book/blob/main/docs/17_persistable.md
14. Epic: Verse language reference, https://dev.epicgames.com/documentation/en-us/uefn/verse-language-reference
15. Epic: Book of Verse landing page, https://dev.epicgames.com/documentation/en-us/fortnite/verse-language-book-of-verse-reference
