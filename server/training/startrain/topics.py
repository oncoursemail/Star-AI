"""Seed topics for the task writer, weighted towards where the evaluation gate shows failures.

The weights come from the per-category pass/fail table of the day-1 baselines (`docs/agents/skills-eval.md`,
`evals/results/baseline-*.json`): categories that failed get weight 3, partly failing 2, passing 1. Only
CATEGORY-level information was used. No evaluation prompt, reference answer or test is read or quoted here, and
the task writer never sees any: closeness to an evaluation task is removed afterwards by gate G8.

mode "pure": plain Luau, `--!strict`, checked by the strict type analyser and run in the standalone VM.
mode "mock": Roblox-flavoured; checked non-strict and run against the harness stand-ins (Instance, services,
Vector3, UDim2 ...). A kept mock example is "mock-verified", not "run in Roblox".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    id: str
    category: str
    mode: str
    weight: int
    text: str
    difficulty: int = 2


def _t(id, category, mode, weight, text, difficulty=2):
    return Topic(id, category, mode, weight, text, difficulty)


TOPICS: list[Topic] = [
    # --- strict typed Luau: data structures, parsing, algorithms (pure) -------------------------------------
    _t("typed-containers", "luau-typing", "pure", 2, "A small strictly typed container module (stack, queue, deque, ring buffer, priority queue, set) with exported types and generic-free but precise signatures."),
    _t("typed-records", "luau-typing", "pure", 2, "Strictly typed record handling: exported type aliases, optional fields, union types, type refinement with typeof/type checks, and functions that validate untyped input into a typed record."),
    _t("string-parsing", "luau-syntax", "pure", 3, "String parsing utilities: splitting, trimming, key=value or CSV-like parsing, escapes, string.find/match/gmatch/gsub patterns with captures, and robust handling of empty or malformed input."),
    _t("string-format", "luau-syntax", "pure", 2, "Formatting helpers: number formatting with separators, durations like 1h 05m, padding, string.format specifiers, pluralisation, simple templating with ${name} placeholders."),
    _t("metatable-oop", "luau-syntax", "pure", 2, "Metatable-based classes: constructors, methods with self, __index inheritance, __tostring, __eq, __lt, __add operators, and read-only tables via __newindex."),
    _t("iterators-coroutines", "luau-syntax", "pure", 2, "Custom iterators, generalized iteration with __iter, coroutine.wrap generators, producers/consumers with coroutine.yield, and coroutine.status checks."),
    _t("table-utils", "luau-syntax", "pure", 2, "Table utilities: deep copy with cycles, deep equal, merge, groupBy, chunk, zip, flatten, binary search, stable sort with a comparator, table.freeze behaviour."),
    _t("math-utils", "luau-syntax", "pure", 2, "Numeric helpers: clamp, lerp, inverse lerp, remap, rounding to n decimals, wrap-around angles, smoothstep, easing functions, safe division, integer-only checks."),
    _t("algorithms-grid", "luau-typing", "pure", 2, "Grid algorithms on a 2D array: BFS shortest path with obstacles, flood fill, neighbour enumeration, connected components, with strict types for cells and paths."),
    _t("lru-cache-memo", "luau-typing", "pure", 2, "Caching: LRU cache with capacity, memoize with a key function, time-based expiry using an injected clock function, cache statistics."),
    _t("state-machine", "luau-typing", "pure", 2, "A finite state machine module with typed states and transitions, guards, enter/exit callbacks, and errors on illegal transitions."),
    _t("event-emitter", "luau-typing", "pure", 2, "A typed event emitter or signal class implemented in pure Luau: connect, once, disconnect, fire with arguments, safe removal during dispatch."),
    _t("buffer-binary", "luau-syntax", "pure", 2, "Binary work with the buffer library and bit32: pack/unpack integers and floats into a buffer, little-endian helpers, bit flags, simple checksums."),
    _t("test-first-modules", "engineering-test-first", "pure", 3, "A small well-specified module such as a money formatter, a rate limiter with an injected clock, a semantic-version comparer or a text wrapper, written so every edge case in the task statement is testable."),
    _t("error-handling", "luau-syntax", "pure", 2, "Error handling: pcall/xpcall patterns, error with tables, retry with a bounded number of attempts, result objects (ok, value, err) and assertions with messages."),
    # --- remotes and server-side validation (mock) ----------------------------------------------------------
    _t("remote-validation", "remote-security", "mock", 3, "Server-side validation of RemoteEvent arguments: type and range checks, rejecting NaN and infinity, clamping, whitelisting ids against server data, never trusting client-sent state."),
    _t("remote-rate-limit", "remote-security", "mock", 3, "Per-player rate limiting and cooldowns for RemoteEvent handlers: token bucket or sliding window, cleanup when the player leaves via Players.PlayerRemoving, no memory growth."),
    _t("remote-authority", "remote-security", "mock", 3, "Server-authoritative actions started by a client request: the server checks ownership, distance, cooldown and resources itself, then applies the result and replies with FireClient."),
    _t("remote-stream", "remote-security", "mock", 3, "High-frequency client-to-server input (aim direction, movement intent) sent over an UnreliableRemoteEvent, with server-side sanity limits and throttling."),
    _t("remote-function-safety", "remote-security", "mock", 2, "RemoteFunction OnServerInvoke handlers that validate input, never yield on client-controlled values, and always return a table with ok and error fields."),
    _t("player-lifecycle", "remote-security", "mock", 3, "Per-player state tables created on Players.PlayerAdded (including players already in the game) and always cleaned on PlayerRemoving; counting tracked players; avoiding leaks."),
    _t("sanity-checks", "remote-security", "mock", 2, "Anti-exploit sanity checks on the server: maximum speed or teleport distance between updates, magnitude limits using Vector3, health and walk-speed changes only by server code."),
    # --- data stores (mock) ---------------------------------------------------------------------------------
    _t("datastore-retry", "datastore-safety", "mock", 3, "Reliable saving and loading through a DataStore stand-in the test injects into game:GetService(\"DataStoreService\"): pcall every call, bounded retries with backoff using task.wait, never losing data on failure."),
    _t("datastore-update", "datastore-safety", "mock", 3, "UpdateAsync-based changes (increment, merge, claim a reward once) on an injected DataStore stand-in: the transform function must be pure and return the new value, or nil to cancel."),
    _t("datastore-session", "datastore-safety", "mock", 3, "Session data for each player: load on join with defaults and schema migration, autosave interval, save on PlayerRemoving, and saving every remaining player inside game:BindToClose."),
    _t("datastore-schema", "datastore-safety", "pure", 2, "Pure data-shape helpers for saved data: version numbers, migrating old shapes to the new one step by step, filling defaults without overwriting existing values, validating and rejecting corrupt data."),
    # --- inventory / economy systems (mock + pure) ----------------------------------------------------------
    _t("inventory-server", "server-authoritative-systems", "mock", 3, "A server-side inventory/shop module: purchase checks currency and stock before changing anything, returns a result object, is atomic (all or nothing), and keeps client calls from setting state."),
    _t("economy-sim", "server-authoritative-systems", "pure", 3, "A small economy or crafting simulation in pure Luau driven by an injected clock: income per second, upgrade costs that grow geometrically, offline progress, and exact reporting of times and totals."),
    _t("loot-weighted", "server-authoritative-systems", "pure", 2, "Weighted random selection (loot tables, rarity tiers) driven by an injected random function so it is testable; pity counters; guaranteed drops."),
    _t("quests-progress", "server-authoritative-systems", "mock", 2, "Quest or achievement progress tracking per player on the server: progress events, completion exactly once, reward callbacks, cleanup on leave."),
    # --- UI structure (mock) ---------------------------------------------------------------------------------
    _t("ui-responsive", "ui-layout", "mock", 3, "Building a responsive ScreenGui in code: Frames sized with UDim2 scale, UIAspectRatioConstraint to keep slots square, UIScale driven by a viewport size argument, UISizeConstraint bounds."),
    _t("ui-lists-grids", "ui-layout", "mock", 3, "Inventory or leaderboard lists built with UIListLayout / UIGridLayout, UIPadding, sorting order via LayoutOrder, and rebuilding the list from a data array without leaking old children."),
    _t("ui-buttons", "ui-interaction", "mock", 3, "Interactive buttons: MouseButton1Click handlers, disabled and cooldown states, hover feedback by changing properties, selection state, and cleaning up connections when the UI is destroyed."),
    _t("ui-text", "ui-text", "mock", 3, "Text UI: TextLabel properties, bounded text sizes (TextScaled with UITextSizeConstraint), truncating long names, number formatting for currency or timers, rich text escaping."),
    _t("ui-bars-tween", "ui-interaction", "mock", 2, "Progress and health bars: computing fill size from value/max with clamping, animating through TweenService with TweenInfo, colour changes by threshold with Color3 lerp."),
    # --- animation, tools, effects (mock + pure) -------------------------------------------------------------
    _t("anim-tween-math", "animation", "pure", 3, "Animation math in pure Luau: easing curves (quad, cubic, sine, back, elastic), frame-rate independent smoothing (exponential decay), springs with damping, keyframe interpolation between numbers."),
    _t("anim-combat-timing", "animation", "pure", 3, "Combat timing helpers: combo windows, input buffering, cooldown and recovery frames, animation priority resolution (action over movement over idle), cancel rules, driven by an injected clock."),
    _t("anim-procedural", "animation", "mock", 3, "Procedural motion with Vector3 and Heartbeat: bobbing, orbiting, following a target with exponential smoothing, rotating around an axis, driven by RunService.Heartbeat delta time."),
    _t("anim-events", "animation", "mock", 2, "Animation event plumbing: playing a track, reacting to named markers, stopping tracks on unequip, priorities, and cleaning up connections with a Janitor-style helper."),
    _t("tool-equip", "tool-attachment", "mock", 3, "A Tool server script: reacting to Activated and Equipped/Unequipped, a cooldown, a Handle part, holding state per tool instance, and cleaning up connections when the tool is destroyed."),
    _t("vfx-emitters", "vfx-particles", "mock", 2, "Visual effects set up in code: ParticleEmitter properties (Rate, Lifetime as NumberRange, Speed), Beam and Trail attachments, PointLight flashes, enabling and disabling on events."),
    _t("vfx-pooling", "vfx-performance", "mock", 3, "Effect or projectile pooling: pre-created Parts, acquire/release with a cap, reuse without creating new instances, counting active and total created, bounded lifetimes through Debris or task.delay."),
    _t("vfx-lifetimes", "vfx-timing", "pure", 2, "Timing of effects: scheduling by priority queue, fading by lifetime fraction, burst patterns, maximum lifetime enforcement, deterministic with an injected clock."),
    # --- performance and streaming (mock + pure) ---------------------------------------------------------------
    _t("perf-pooling", "performance", "mock", 3, "Object pooling for frequently spawned parts or models: preallocate, get/release, reuse released objects without creating new ones, reset state on release, never exceed a maximum."),
    _t("perf-batching", "performance", "pure", 2, "Reducing per-frame work: debouncing, throttling by interval, batching updates in a queue processed with a time budget per frame, dirty flags, spatial hashing for neighbour lookups."),
    _t("perf-streaming", "performance-streaming", "mock", 3, "Working with StreamingEnabled worlds: reacting to instances streaming in and out (ChildAdded, AncestryChanged, CollectionService tags), setting a model's ModelStreamingMode, never assuming a part exists."),
    _t("perf-connections", "performance", "mock", 2, "Connection hygiene: storing RBXScriptConnections and disconnecting them, a Janitor/Maid class, cleaning on Destroying and PlayerRemoving, avoiding closures that keep large tables alive."),
    # --- building / layout (pure + mock) -----------------------------------------------------------------------
    _t("build-grid-snap", "building-grid", "pure", 3, "Grid building math: snapping positions to a grid size, converting between cell coordinates and world positions, footprint overlap tests for placing objects, rotation in 90 degree steps."),
    _t("build-wall-layout", "building-grid", "pure", 3, "Layout of repeated modular pieces: filling a length with pieces of fixed sizes (largest first, remainder handling), centring the row, reporting the pieces and checking the total."),
    _t("build-placement", "building-layout", "mock", 2, "Placing and arranging parts in code: creating Parts with Size, Position and Anchored, parenting them to a Model, naming, rows/rings/stairs of parts using Vector3 maths."),
    _t("build-lighting", "building-lighting", "mock", 2, "Lighting setup in code: adding PointLight/SpotLight children with Brightness, Range and Color, toggling groups of lights by CollectionService tag, day-night values interpolated by time."),
    # --- engineering practice (pure) ----------------------------------------------------------------------------
    _t("eng-debug-fix", "engineering-debugging", "pure", 1, "A function with a subtle bug (off-by-one, wrong comparison, shared mutable default, nil handling) rewritten correctly; the task states the symptom and the exact required behaviour."),
    _t("eng-spec-first", "engineering-test-first", "pure", 3, "A function specified precisely by examples (inputs and exact outputs including edge cases such as empty input, duplicates, negatives and ties) that must be implemented to satisfy every example."),
]


def by_id() -> dict[str, Topic]:
    return {t.id: t for t in TOPICS}


def validate() -> list[str]:
    problems = []
    seen = set()
    for t in TOPICS:
        if t.id in seen:
            problems.append("duplicate topic id " + t.id)
        seen.add(t.id)
        if t.mode not in ("pure", "mock"):
            problems.append(f"{t.id}: bad mode")
        if not 1 <= t.weight <= 5:
            problems.append(f"{t.id}: bad weight")
    return problems
