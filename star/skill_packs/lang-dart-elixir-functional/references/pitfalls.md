# Dart, Elixir, Haskell, OCaml: error messages, fixes, and a Luau cheat sheet

Condensed from docs/research/languages/dart.md, elixir.md and haskell-ocaml.md (checked 2026-10-13).

## Dart

| Error text | Cause | Fix |
|---|---|---|
| `The property 'x' can't be unconditionally accessed because the receiver can be 'null'.` | Nullable receiver | Check, `?.`, `??` |
| `A value of type 'String?' can't be assigned to a variable of type 'String'.` | Nullable into non-nullable | `?? default` or early return |
| Field not promoted after a null check | Promotion works only on locals and private final fields | Copy to a local |
| `Null check operator used on a null value` | `!` on null | Remove `!`, handle null |
| `LateInitializationError: Field 'x' has not been initialized.` | `late` read early | Initialise first or make nullable |
| `type 'List<dynamic>' is not a subtype of type 'List<String>'` | jsonDecode types | `List<String>.from(x)` or `.cast<String>()` |
| `setState() called after dispose()` | Async finished after unmount | `if (!mounted) return;` |
| `Bad state: Stream has already been listened to.` | Single-subscription stream | Broadcast stream |
| `Illegal argument in isolate message` | Sending closures or handles | Send plain data; top-level functions |
| `RenderFlex overflowed by N pixels` | Row too wide | `Expanded`, `Flexible`, `Wrap` |

## Elixir

| Error text | Cause | Fix |
|---|---|---|
| `(MatchError) no match of right hand side value: {:error, ...}` | Asserting `{:ok, x} =` | `case`/`with` |
| `(FunctionClauseError) no function clause matching` | No clause accepts args | Add clause; check key types |
| `(KeyError) key :hp not found in: %{"hp" => 10}` | Atom vs string keys | Convert at boundary |
| `(UndefinedFunctionError) function Foo.bar/1 is undefined` | Arity, alias, deps | Check arity and `alias` |
| `(Protocol.UndefinedError) protocol String.Chars not implemented` | Interpolating a struct | `inspect/1` |
| `exited in: GenServer.call(..., 5000) ** (EXIT) time out` | Blocked server, self-call | Move slow work to Task; no self-calls |
| `no process: the process is not alive` | Name not started | Supervise; check Registry |
| `warning: variable "x" is unused` after `if` | Bindings do not leak from `if`/`case` | Bind the result of the expression |
| `(BadMapError) expected a map, got: nil` | Update on nil | Ensure map exists |
| `(ArgumentError) ... :ets.lookup` | ETS owner died | Long-lived owner, `:heir` |

## Haskell and OCaml

| Error text | Cause | Fix |
|---|---|---|
| `Couldn't match expected type 'Int' with actual type 'Integer'` | Numeric types | Signatures, `fromIntegral` |
| `Ambiguous type variable ... arising from a use of 'read'` | No target type | Annotate; `readMaybe` |
| `Non-exhaustive patterns in function f` | Missing case | `-Wall`, handle all cases |
| `Prelude.head: empty list` | Partial function | Pattern match, `NonEmpty` |
| Stack overflow or memory growth in a fold | Lazy accumulator | `foldl'`, bang patterns |
| `This expression has type float but an expression was expected of type int` (OCaml) | Mixed int/float operators | `+.`, `float_of_int` |
| `Warning 8 [partial-match]` (OCaml) | Non-exhaustive match | Add cases |
| `Exception: Not_found.` (OCaml) | `Hashtbl.find` miss | `find_opt` |
| `'_weak1` type (OCaml) | Value restriction | Eta-expand |

## Luau cheat sheet

| Concept | Luau | Dart | Elixir | Haskell | OCaml |
|---|---|---|---|---|---|
| Index base | 1 | 0 | 0 | 0 (`!!`) | 0 |
| Null | `nil` | `null` | `nil` | `Nothing` | `None` |
| Truthiness | nil/false falsy | bool only | nil/false falsy | Bool only | bool only |
| Not equal | `~=` | `!=` | `!=` | `/=` | `<>` |
| Concat | `..` | `'$a$b'` | `<>` | `++` | `^` |
| Int division | `//` | `~/` | `div` | `div` | `/` |
| Mutation | yes | yes | no (rebind) | no (IORef) | `ref`, `mutable` |
| Coroutines | `coroutine.*` | `async*`/`sync*` generators | processes | green threads | effects |
| Errors | `error`/`pcall` | `throw`/`try on catch` | `{:error, r}`, `raise`/`rescue` | `Either`, exceptions in IO | `result`, `raise`/`try with` |
| Frame loop | Heartbeat(dt) | Flame `update(dt)` | `Process.send_after` tick | n/a | n/a |
