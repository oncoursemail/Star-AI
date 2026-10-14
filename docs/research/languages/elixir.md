# Elixir for STAR (research, checked 2026-10-13)

Status: **Elixir 1.20** released 2026-06-03 ("now a gradually typed language" [1]); 1.20.x patch releases exist (1.20.2 seen on third-party mirrors, unverified). **Elixir 1.19** (2025-10-16) [2]. **Erlang/OTP 29.0** released 2026-05-13 [3]; OTP 28 is the previous major. Per a changelog excerpt, Elixir 1.20 requires OTP 27+ and supports OTP 29 (secondary source, unverified). Phoenix 1.8 and LiveView 1.1 (2025-07-30) are current [8].

---

## 1. Mental model

- **Functional language on the BEAM** (Erlang VM). Data is **immutable**; "changing" a map returns a new map. Variables can be *rebound* (`x = x + 1`) but the old value never changes.
- **Processes** are the unit of everything: lightweight (a few KB), isolated heaps, preemptively scheduled by the VM across all cores, communicating only by **message passing** (`send`/`receive`). Millions per node are normal.
- **"Let it crash"**: don't defensively handle every error inside a process; let it crash and let a **supervisor** restart it in a known good state. Errors you *expect* are returned as `{:ok, value}` / `{:error, reason}` tuples.
- **Pattern matching** with `=` (the "match operator", not assignment), in function heads, `case`, `with`, and `receive`.
- **OTP** = the standard library of behaviours: `GenServer` (stateful server process), `Supervisor`, `Application`, `Registry`, `Task`, `Agent`, `:ets` (in-memory tables), `:gen_statem`.
- **Hot code upgrades**, distribution (`Node.connect`), and soft real-time latency are built in. Garbage collection is per process (no stop-the-world for the whole node).
- Macros (`defmacro`, `quote`/`unquote`) power DSLs (Phoenix router, Ecto queries, ExUnit).

## 2. Type system

- Dynamically typed, strongly typed (`1 + "a"` raises `ArithmeticError`).
- **Set-theoretic gradual type system** built into the compiler (no annotations needed):
  - 1.17 (2024): set-theoretic data types, warnings for some type violations in patterns.
  - 1.18 (2024-12): type checking of function calls, LSP listeners, built-in `JSON` module.
  - 1.19 (2025-10): type inference for anonymous functions, type checking of protocols (e.g. warns when interpolating a value that does not implement `String.Chars`) [2].
  - **1.20 (2026-06)**: type inference of all constructs; every program is gradually type checked for "verified bugs" (violations guaranteed to fail at runtime) and dead code; `dynamic()` treated as a range; guards infer unions/intersections/negations; `case` clauses narrow later clauses (detects redundant clauses) [1].
  - **Not yet**: user-written type signatures in the new system (planned after recursive/parametric type support) [1].
- `@spec` / `@type` typespecs (Erlang-style) remain, used by **Dialyzer** (via `dialyxir`) and documentation; they are not checked by the new compiler type system.
- Structs: `defstruct [:name, hp: 100]` + `@enforce_keys`. Protocols give polymorphism over data types (`Enumerable`, `String.Chars`, `Jason.Encoder`/`JSON.Encoder`).

## 3. Runtime, concurrency and async model

- BEAM schedulers (one per core) preempt processes by *reductions*, so one busy process cannot starve others (unless it calls long-running NIFs).
- Primitives: `spawn/1`, `spawn_link/1`, `send/2`, `receive do ... after ms -> ... end`, `Process.monitor/1`.
- **Task**: `Task.async(fn -> work() end) |> Task.await(5_000)`, `Task.async_stream(list, fun, max_concurrency: 8)`; under `Task.Supervisor` for fire-and-forget.
- **GenServer**: client API + server callbacks; `call` (synchronous, default 5 s timeout), `cast` (async), `handle_info` (raw messages, timers).

```elixir
defmodule Game.Room do
  use GenServer

  # Client API
  def start_link(id), do: GenServer.start_link(__MODULE__, id, name: via(id))
  def join(id, player), do: GenServer.call(via(id), {:join, player})
  def tick(id), do: GenServer.cast(via(id), :tick)

  defp via(id), do: {:via, Registry, {Game.RoomRegistry, id}}

  # Server callbacks
  @impl true
  def init(id) do
    Process.send_after(self(), :tick, 50)
    {:ok, %{id: id, players: %{}, frame: 0}}
  end

  @impl true
  def handle_call({:join, p}, _from, state) when map_size(state.players) < 8 do
    {:reply, :ok, put_in(state.players[p.id], p)}
  end
  def handle_call({:join, _p}, _from, state), do: {:reply, {:error, :full}, state}

  @impl true
  def handle_info(:tick, state) do
    Process.send_after(self(), :tick, 50)          # 20 Hz simulation loop
    {:noreply, %{state | frame: state.frame + 1}}
  end
end
```

- Supervision tree in `application.ex`:

```elixir
children = [
  {Registry, keys: :unique, name: Game.RoomRegistry},
  {DynamicSupervisor, name: Game.RoomSup, strategy: :one_for_one},
  GameWeb.Endpoint
]
Supervisor.start_link(children, strategy: :one_for_one, name: Game.Supervisor)
```

- Distribution and clustering: `libcluster`, `Phoenix.PubSub` (pg2/pg based), `Horde` for distributed supervisors.

## 4. Tooling and package management

- **Mix**: `mix new app --sup`, `mix deps.get`, `mix compile`, `mix test`, `mix format`, `mix release`. **Hex** package manager (hex.pm), docs on HexDocs (ExDoc).
- `mix.exs` deps: `{:phoenix, "~> 1.8"}`, `mix.lock` committed.
- Version managers: `asdf`/`mise` (pin both `erlang` and `elixir` in `.tool-versions`), Windows installer from elixir-lang.org.
- **IEx**: `iex -S mix`, `h Enum.map`, `i value`, `recompile`, `dbg/2` (1.14+) in pipelines.
- Linters: **Credo**; Dialyzer via `dialyxir`; **Sobelow** (Phoenix security). Official **Expert** language server (the official LSP team formed 2024; status of naming/releases unverified as of 2026-10-13); ElixirLS, Lexical, Next LS are the predecessors.
- `Mix.install([:req, :jason])` for single-file scripts / Livebook notebooks.
- 1.20 adds `:module_definition` compiler option (`:interpreted` mode for faster compile of module bodies) [1].

## 5. Testing

- **ExUnit**: `use ExUnit.Case, async: true` runs test modules concurrently; `describe`, `test`, `setup`, `assert`, `refute`, `assert_raise`, `assert_receive` (for messages), doctests (`doctest MyModule`).
- Property-based: **StreamData** (`check all x <- integer()`).
- Phoenix: `ConnCase`, `LiveViewTest` (`live(conn, "/")`, `render_click`). Ecto sandbox for concurrent DB tests.
- Mocks: **Mox** (behaviour-based mocks, explicit contracts).

```elixir
defmodule Game.ScoreTest do
  use ExUnit.Case, async: true
  doctest Game.Score

  test "adds points" do
    assert Game.Score.add(%{total: 0}, 10) == %{total: 10}
  end

  test "room replies when full" do
    {:ok, pid} = start_supervised({Game.Room, "r1"})
    assert is_pid(pid)
  end
end
```

## 6. Idiomatic patterns

```elixir
# Pipelines: data first
"  Hello World  "
|> String.trim()
|> String.downcase()
|> String.split()
|> Enum.map(&String.capitalize/1)
|> Enum.join(" ")

# Multi-clause functions with guards instead of if/else chains
def damage(%{shield: s} = target, amount) when s > 0, do: %{target | shield: max(s - amount, 0)}
def damage(%{hp: hp} = target, amount), do: %{target | hp: max(hp - amount, 0)}

# with for happy-path chaining of {:ok, _} results
with {:ok, user} <- Accounts.fetch(id),
     {:ok, item} <- Shop.fetch(item_id),
     :ok <- Wallet.charge(user, item.price) do
  {:ok, Inventory.grant(user, item)}
else
  {:error, :insufficient_funds} -> {:error, "not enough coins"}
  {:error, reason} -> {:error, reason}
end

# Comprehensions
for {name, score} <- scores, score > 100, into: %{}, do: {name, score * 2}

# Enum (eager) vs Stream (lazy)
File.stream!("log.txt") |> Stream.filter(&String.contains?(&1, "ERROR")) |> Enum.take(10)

# Update nested data
state = update_in(state, [:players, id, :hp], &(&1 - 10))

# ETS for fast shared reads
:ets.new(:leaderboard, [:named_table, :set, :public, read_concurrency: true])
:ets.insert(:leaderboard, {"alice", 120})
```

Naming: functions returning booleans end in `?`; functions that raise end in `!` (`File.read!`) while the non-bang version returns `{:ok, _} | {:error, _}`.

## 7. Top pitfalls and error-message fixes

| Exact error text | Cause | Fix |
|---|---|---|
| `** (MatchError) no match of right hand side value: {:error, :enoent}` | `{:ok, x} = File.read(path)` when it failed | Use `case`/`with` to handle `{:error, _}`, or `File.read!` if crashing is intended |
| `** (FunctionClauseError) no function clause matching in Game.damage/2` | No clause/guard accepts the args | Add a clause or fix the caller; check map keys/atoms vs strings |
| `** (KeyError) key :hp not found in: %{"hp" => 10}` | Atom vs string keys (params and JSON give string keys) | Convert at the boundary; `map["hp"]`; Ecto changesets cast params |
| `** (UndefinedFunctionError) function Foo.bar/1 is undefined (module Foo is not available)` | Typo, missing dependency, wrong arity, not compiled | Check `alias`, arity, `mix deps.get` |
| `** (ArgumentError) errors were found at the given arguments: * 1st argument: not an atom` | Erlang BIF got wrong type | Convert types (`String.to_existing_atom`) |
| `** (Protocol.UndefinedError) protocol String.Chars not implemented for %User{...}` (1.19+ also a compile-time warning [2]) | Interpolating a struct/map/tuple | `inspect(value)` or implement `String.Chars` |
| `** (exit) exited in: GenServer.call(#PID<...>, :get, 5000) ** (EXIT) time out` | Server busy/blocked or deadlocked (calling itself) | Never `GenServer.call(self(), ...)` inside callbacks; move slow work to Task; raise timeout deliberately |
| `** (exit) no process: the process is not alive or there's no process currently associated with the given name` | Calling a name that is not started or crashed | Start under supervisor; check `Registry` names; handle `:noproc` |
| `warning: variable "x" is unused (if the variable is not meant to be used, prefix it with an underscore)` | Rebinding inside `if`/`case` does not leak out | Return the new value from the expression: `x = if c, do: x + 1, else: x` |
| `** (CompileError) undefined variable "socket"` / `undefined function x/0` | Variable from an outer clause or typo | Pass it in |
| `** (ArithmeticError) bad argument in arithmetic expression` | Arithmetic with nil/string | Validate inputs; `String.to_integer` |
| `** (BadMapError) expected a map, got: nil` | `%{m | k: v}` or `Map.get` on nil | Ensure the map exists; `Map.put` on `%{}` |
| `** (ArgumentError) argument error :ets.lookup(:t, 1)` | ETS table missing (owner process died) | Create table in a supervised long-lived process; `:heir` option |
| Type warning from 1.20 checker, e.g. `incompatible types given to ...` (exact text varies) | A verified type violation | Read the expected vs given types it prints; fix the call |

Other mistakes:
- Lists are **linked lists**: `length/1` and `Enum.at/2` are O(n); append with `[new | list]` then `Enum.reverse`; never `list ++ [x]` in a loop.
- Atoms are never garbage-collected: never `String.to_atom(user_input)` (atom table exhaustion crashes the node) — use `String.to_existing_atom` or keep strings.
- Large binaries are reference-counted; holding a small sub-binary keeps the big one alive (`:binary.copy/1`).
- A GenServer is a serialization point: one process handles one message at a time. Don't funnel all players through one GenServer; shard (one process per room/player) or read via ETS.
- `if`/`case` are expressions — variables assigned inside don't escape.
- `==` vs `===`: `1 == 1.0` is true, `1 === 1.0` false. Integer division: `div(7, 2)`; `/` always returns float; `rem(-7, 3) == -1` (truncated), `Integer.mod(-7, 3) == 2` (floored, like Luau).
- Charlists vs strings: `'abc'` (charlist, now printed as `~c"abc"`) vs `"abc"` (binary).

## 8. Performance

- BEAM is optimized for latency and concurrency, not raw number crunching. JIT (BeamAsm) since OTP 24.
- For numeric work: **Nx** (tensors, `defn` numerical functions compiled by EXLA/XLA or Torchx; GPU support), **Axon** (neural nets), **Bumblebee** (pretrained models), **Explorer** (dataframes, Polars). **Rustler** for safe Rust NIFs; dirty schedulers for long native calls.
- Use ETS / `:persistent_term` for read-heavy shared data instead of a GenServer bottleneck.
- Binaries and iolists: build output as nested lists (iodata) instead of concatenating strings.
- Profile: `:observer.start()`, `:recon`, `mix profile.tprof` (OTP 27+) / `eprof` / `fprof`, Benchee for micro-benchmarks, `:telemetry` + Phoenix LiveDashboard.
- 1.19 compiles large projects up to 4x faster; 1.20 speeds compile/boot/test on many-core machines [1][2].

## 9. Security

- Atom exhaustion (above), `Code.eval_string`/`:erlang.binary_to_term` on untrusted input (use `binary_to_term(bin, [:safe])`, but prefer JSON).
- Ecto queries are parameterized by default (`from u in User, where: u.name == ^name`); `fragment("... #{x}")` with interpolation is injection — use `?` placeholders.
- Phoenix: CSRF protection, `~H` HEEx templates auto-escape; `raw/1` disables it. Check LiveView event params like any untrusted input (authorize every `handle_event`).
- Distribution cookie (`.erlang.cookie`) grants full code execution on a node: never expose EPMD/distribution ports publicly; use TLS distribution.
- OTP 29 disables SSH daemon shell/exec by default [3] (after the 2025 Erlang/OTP SSH pre-auth RCE, CVE-2025-32433): patch OTP promptly.
- `mix hex.audit`, `mix deps.audit` (mix_audit), Sobelow for Phoenix.

## 10. Game-dev usage

- Elixir shines for **game servers**: per-room/per-match processes, presence (`Phoenix.Presence`), channels/WebSockets (`Phoenix.Channel`), matchmaking, chat, leaderboards (ETS), fault isolation (one crashed room doesn't take down others). Examples cited by the community: Discord's real-time infrastructure (Elixir), X-Plane multiplayer server [5].
- **LiveView** can render simple real-time browser games server-side (turn-based, board games) with no client JS logic.
- Not used for rendering clients. Pair with Unity/Godot/Roblox clients over WebSockets/HTTP (a Roblox server can call an Elixir HTTP API via `HttpService`).
- Simulation ticks: `Process.send_after/3` or `:timer.send_interval/2`; for deterministic lockstep use fixed-step integer math.

## 11. Cheat sheet vs Luau

| Concept | Luau | Elixir |
|---|---|---|
| Indexing base | 1 | 0 (`Enum.at(list, 0)`, `elem(tuple, 0)`) |
| Length | `#t` | `length(list)` (O(n)), `map_size(m)`, `String.length(s)` |
| Absent value | `nil` | `nil` (the atom `:nil`) |
| Truthiness | `nil`/`false` falsy | same: only `nil` and `false` falsy |
| Not equal | `~=` | `!=` / `!==` |
| String concat | `a .. b` | `a <> b`, `"#{a}#{b}"` |
| Array | table | list `[1, 2, 3]` (linked), tuple `{1, 2}` (fixed) |
| Map | table `{a = 1}` | `%{a: 1}` (atom keys), `%{"a" => 1}` |
| Missing key | nil | `m[:x]` -> nil; `m.x` raises KeyError; `Map.fetch` -> `:error` |
| Mutation | `t.x = 1` mutates | immutable: `m = %{m \| x: 1}` / `Map.put` |
| Iterate | `for i, v in ipairs(t)` | `Enum.each/map/reduce`, `for x <- list`, recursion |
| Methods / self | `obj:m()` | no objects; module functions take data first: `Player.move(p, dx)` |
| Closures | `function() end` | `fn x -> x * 2 end`, capture `&(&1 * 2)` |
| Coroutines | `coroutine.*` | processes + `send`/`receive` |
| Async | `task.spawn`, `task.wait(n)` | `Task.async/await`, `Process.send_after`, `:timer.sleep` |
| Integer division | `7 // 2` | `div(7, 2)`; `7 / 2` -> 3.5 |
| Modulo | floored | `rem` truncated, `Integer.mod` floored |
| Error raise | `error("x")` | `raise "x"`, `raise ArgumentError, "x"`; prefer `{:error, reason}` |
| Error catch | `pcall` | `try/rescue/after`; usually pattern match on tuples; supervisors restart |
| Modules | `require(m)` | `defmodule`, `alias`, `import`, `use`; compiled `.beam` |
| Heartbeat loop | `RunService.Heartbeat` | `Process.send_after(self(), :tick, ms)` in a GenServer |

## 12. Recent changes and version notes

- **Elixir 1.20 (2026-06-03)** [1]: whole-program gradual type inference/checking, guard narrowing, `case` narrowing/redundant-clause detection, typed tuple/map stdlib functions, faster compile/boot, `:module_definition` option. No user type signatures yet.
- **Elixir 1.19 (2025-10-16)** [2]: anonymous function inference, protocol checks, up to 4x faster compilation for large projects, OTP 28.1+ supported.
- **Elixir 1.18 (2024-12-19)**: call type checking, built-in `JSON`, LSP listeners, `mix format --migrate`.
- **OTP 29 (2026-05-13)** [3]: SSH daemon shell/exec off by default, `-unsafe` attribute and warnings, native records (EEP-79) experimental, `ct_doctest`, `io_ansi`, current dir last in code path, no 32-bit Windows build. Post-quantum hybrid SSH KEX default is from secondary coverage (unverified).
- **OTP 28 (2025)**: priority messages, `zstd` module, nominal types for Dialyzer.
- **LiveView 1.1 (2025-07-30)** [8]: colocated hooks (`<script :type={Phoenix.LiveView.ColocatedHook}>`, requires Phoenix 1.8), keyed comprehensions, `Phoenix.LiveView.Debug`. **Phoenix 1.8**: daisyUI/Tailwind v4 generators, magic-link `phx.gen.auth`, scopes.

## Sources

1. https://elixir-lang.org/blog/2026/06/03/elixir-v1-20-0-released/
2. https://elixir-lang.org/blog/2025/10/16/elixir-v1-19-0-released/
3. https://www.erlang.org/news/188 (Erlang/OTP 29.0)
4. https://hexdocs.pm/elixir/gradual-set-theoretic-types.html
5. https://elixir-lang.org/blog/ (case studies: Discord, X-Plane)
6. https://hexdocs.pm/elixir/GenServer.html
7. https://hexdocs.pm/elixir/Supervisor.html
8. https://phoenixframework.org/blog/phoenix-liveview-1-1-released
9. https://hexdocs.pm/ex_unit/ExUnit.html
10. https://hexdocs.pm/mix/Mix.html
11. https://hexdocs.pm/nx/Nx.html
12. https://www.erlang.org/doc/system/efficiency_guide.html
13. https://hexdocs.pm/elixir/anti-patterns.html
14. https://erlef.github.io/security-wg/secure_coding_and_deployment_hardening/
15. https://elixir.hexdocs.pm/1.19/changelog.html
16. https://www.erlang.org/patches/otp-29.0
