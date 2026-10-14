---
name: lang-dart-elixir-functional
description: Dart 3.x (Flutter, Flame), Elixir 1.20 on Erlang/OTP, and brief Haskell and OCaml rules: null safety, async and isolates, processes and supervisors, laziness, common error messages and fixes. Use when writing, reviewing or debugging code in these languages.
---
# Dart, Elixir, Haskell, OCaml
## Dart 3 (Flutter, Flame)
- Sound null safety: `String?` must be checked before use. Promotion after `!= null` works only on locals and private final fields; copy a field to a local first. Avoid `!` unless proven (runtime error "Null check operator used on a null value").
- Conditions must be `bool` (no truthiness). Lists are 0-based. `7 / 2` is 3.5, use `~/` for integer division.
- `jsonDecode` gives `Map<String, dynamic>` and `List<dynamic>`; destructure with patterns (`if (json case {'x': int x})`) or `List<String>.from(...)` instead of unchecked casts.
- Use records and patterns, sealed classes with exhaustive `switch` expressions, enhanced enums, extension types. Dot shorthands (3.10) need `sdk: ^3.10.0` in pubspec; primary constructors `class Point(final int x, final int y);` are stable in 3.13. Macros were cancelled: use build_runner code generation.
- One event loop per isolate. `await` every Future you start (lint `unawaited_futures`); `forEach` with an async callback does not wait, use `for` with `await` or `Future.wait`. CPU-heavy work goes to `Isolate.run`; isolates share no memory and send only plain data.
- Flutter: after an `await` in a State, check `mounted` before `setState`. Use `const` widgets and `ListView.builder`. Profile in profile mode, never debug.
- Flame: a `FlameGame` holds components; movement goes in `update(double dt)` with dt in seconds; reuse `Vector2` objects in hot loops; `HasCollisionDetection` plus hitboxes for collisions.
- Use `dart:js_interop` and `package:web`; `dart:html` is deprecated and unsupported on Wasm. Keep secrets out of app binaries.
## Elixir (1.20, OTP 29)
- Data is immutable; rebinding a name does not change the old value. `if`/`case` return values, so assignments inside them do not leak out.
- `=` is a pattern match: `{:ok, x} = f()` raises MatchError on `{:error, _}`. Handle expected failures with `case` or `with`; bang functions (`File.read!`) raise.
- Processes are cheap and isolated; let a supervisor restart crashed processes. A GenServer handles one message at a time: shard per room or player and put read-heavy shared data in ETS. Never `GenServer.call(self(), ...)`; `call` times out after 5 seconds by default.
- Periodic ticks: `Process.send_after(self(), :tick, ms)` in `handle_info`.
- JSON and params give string keys; `map.key` raises on missing atom keys. Never `String.to_atom` on user input (atoms are never collected); use `String.to_existing_atom` or keep strings.
- Lists are linked: prepend then reverse, never `list ++ [x]` in a loop; `length` is O(n). `div`/`rem` truncate, `Integer.mod` floors.
- 1.20 infers and checks types for all code without annotations and warns about verified bugs and dead clauses; read the expected versus given types it prints. Typespecs are still for Dialyzer.
- Tooling: mix, Hex, ExUnit (`async: true`, `assert_receive`, doctests), Credo, Sobelow. Ecto queries interpolate with `^value`, never string-built fragments. Escape output in HEEx; authorize every LiveView `handle_event`. Never expose Erlang distribution ports.
## Haskell (GHC 9.14 LTS)
- Lazy by default: use `foldl'`, `Data.Map.Strict`, and bang patterns for accumulators to avoid space leaks. Avoid partial functions (`head`, `fromJust`, `!!`, `read`); use pattern matching, `NonEmpty`, `readMaybe`.
- Compile with `-Wall`. Install with GHCup, build with cabal or Stack. `do` blocks end in an expression (`pure x`). Indentation is significant.
## OCaml (5.4)
- Strict evaluation; `+` is int-only and `+.` is float; convert with `float_of_int`. `=` is structural equality, `==` is physical.
- Use the `_opt` functions (`Hashtbl.find_opt`) instead of catching Not_found; treat warning 8 (non-exhaustive match) as an error; wrap a nested `match` in parentheses.
- OCaml 5 has domains for parallelism (about one per core) and effect handlers (Eio). Build with dune, install with opam.
## Versus Luau
- 0-based indexing everywhere here (Luau is 1-based). No truthiness in Dart, Haskell or OCaml; Elixir matches Luau (only nil and false are falsy).
- Errors: Dart `try`/`on`/`catch`; Elixir `{:error, reason}` tuples plus supervisors; Haskell `Maybe`/`Either`; OCaml `option`/`result`.
