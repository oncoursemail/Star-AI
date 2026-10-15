# Haskell and OCaml for STAR (research, brief; checked 2026-10-13)

Status: **GHC 9.14.1** released 2025-12-19/27, the first GHC release designated **LTS** (support target 2-3 years; LTS status from GHC developer posts and secondary coverage) [1]. Newer GHC (9.16/10.x) release status unverified as of 2026-10-13. **OCaml 5.4.0** released 2025-10-09, 5.4.1 later [6]. OCaml 5.5 status unverified as of 2026-10-13.

These are brief notes: STAR users meet these languages mostly in compilers, tooling, Advent-of-Code style puzzles, finance, and type-system questions.

The two languages are covered side by side: each section has a Haskell part and an OCaml part.

## 1. Mental model

### Haskell
- **Purely functional, lazily evaluated, statically typed with global type inference.** Functions have no side effects; effects are *values* of type `IO a` that the runtime executes starting from `main :: IO ()`.
- **Laziness**: expressions are evaluated only when needed (call-by-need with sharing). Enables infinite lists (`take 5 [1..]`) but causes *space leaks* (unevaluated thunks pile up).
- **Type classes** (`Eq`, `Ord`, `Show`, `Functor`, `Monad`) provide ad-hoc polymorphism; `do` notation is sugar for monadic `>>=`.
- Everything is immutable; loops are recursion or folds; mutable state lives in `IORef`, `STRef`, `MVar`, `TVar` (STM).

### OCaml
- **Strict (eager), functional-first but pragmatic**: mutable `ref`, arrays, records with `mutable` fields, imperative loops and exceptions are all ordinary. Global type inference (HM), very fast native compiler, predictable performance.
- **Module system** is the big idea: modules, signatures (`.mli` interfaces), **functors** (modules parameterized by modules), first-class modules.
- **OCaml 5** (2022+) replaced the global runtime lock: **domains** for shared-memory parallelism and **effect handlers** for user-level concurrency (the basis of the **Eio** library) [7].

## 2. Type system

### Haskell
- Hindley-Milner plus many extensions: GADTs, type families, `DataKinds`, rank-N types, `LinearTypes`, `RequiredTypeArguments`. Language editions: `GHC2021` (default in modern GHC) and `GHC2024`.
- Algebraic data types and exhaustive pattern matching (`-Wincomplete-patterns`; turn on `-Wall`).
- `Maybe a` instead of null, `Either e a` for errors; `newtype` for zero-cost wrappers.

```haskell
data Shape = Circle Double | Rect Double Double deriving (Show, Eq)

area :: Shape -> Double
area (Circle r) = pi * r * r
area (Rect w h) = w * h

safeDiv :: Int -> Int -> Maybe Int
safeDiv _ 0 = Nothing
safeDiv a b = Just (a `div` b)
```

### OCaml
- Variants, records, polymorphic variants (`` `Red ``), GADTs, objects (rarely used), exhaustive match warnings.
- 5.4 adds **labelled tuples** (`~x:1, ~y:2`), immutable arrays (`'a iarray`, `Iarray`), `[@atomic]` record fields with `Atomic.Loc`, new stdlib modules `Pair`, `Pqueue`, `Repr` [6].
- No overloading: `+` is int, `+.` is float; `print_int` vs `print_float`. `Int.to_float`, `float_of_int`.

```ocaml
type shape = Circle of float | Rect of float * float

let area = function
  | Circle r -> Float.pi *. r *. r
  | Rect (w, h) -> w *. h

let () =
  [Circle 1.0; Rect (2.0, 3.0)]
  |> List.map area
  |> List.iter (Printf.printf "%.2f\n")
```

## 3. Runtime, concurrency and async model

### Haskell
- GHC RTS: green threads (`forkIO`), very cheap; `-threaded` + `+RTS -N` for multicore. `MVar`, `Chan`, **STM** (`atomically`, `TVar`, `retry`) for composable transactions. `async` library (`concurrently`, `race`, `mapConcurrently`).
- Pure parallelism: `parallel` (`par`, `pseq`, strategies).
- Generational copying GC; nonmoving GC option for low latency.

### OCaml
- `Domain.spawn (fun () -> work ())` / `Domain.join` — one domain per core (do not spawn thousands).
- Effects: `effect E : int -> int` + `Effect.perform` with a handler (OCaml 5.3+ added dedicated `effect` syntax in `match ... with effect E k ->`).
- Libraries: **Eio** (effects-based direct-style I/O), **Lwt** and **Async** (monadic promise libraries, pre-OCaml 5), **Domainslib** (parallel task pools).

## 4. Tooling and package management

### Haskell
- **GHCup** installs GHC, cabal, Stack and HLS (Haskell Language Server); recommended on Windows/Linux/macOS [3].
- **cabal** (`cabal init`, `cabal build`, `cabal run`, `cabal repl`, Hackage registry) or **Stack** (curated Stackage snapshots `resolver: lts-xx`).
- **HLS** for editors; **hlint** for suggestions; **ormolu**/**fourmolu** formatting; `ghcid` for fast reload.

### OCaml
- **opam** (package manager, switches: `opam switch create 5.4.0` [6]), **dune** (build system; `dune init project`, `dune build`, `dune test`, `dune exec`), **ocaml-lsp-server** + **ocamlformat**, **utop** REPL, **odoc** docs.
- Dune package management (`dune pkg lock`) is maturing as an opam alternative (status unverified as of 2026-10-13).
- Windows: opam 2.2+ supports native Windows; Diskuv/MSYS2 alternatives.

## 5. Testing

### Haskell
- Testing: **hspec**, **tasty**, **QuickCheck** (property-based testing originated here), **hedgehog**, doctest.
- Typical layout: a `test-suite` stanza in the `.cabal` file with `type: exitcode-stdio-1.0`, run with `cabal test`; QuickCheck properties state laws (`prop_reverse xs = reverse (reverse xs) == xs`) and shrink failing inputs automatically.

### OCaml
- Testing: **Alcotest**, ppx_expect / ppx_inline_test (Jane Street), QCheck, cram tests in dune.
- Typical layout: a `test/dune` file with `(test (name test_main) (libraries alcotest mylib))`, run with `dune test`; expect tests (`let%expect_test`) print output and `dune promote` accepts a new snapshot.

## 6. Idiomatic patterns (code)

### Haskell
- Push effects to the edges: pure core functions, a thin `IO` shell. Use `Text` (not `String`) for text, `Data.Map.Strict` for maps, `foldl'` for strict folds, `traverse`/`mapM_` instead of manual recursion over effects.

```haskell
{-# LANGUAGE OverloadedStrings #-}
import qualified Data.Map.Strict as M
import Data.List (foldl')

wordCounts :: [String] -> M.Map String Int
wordCounts = foldl' (\m w -> M.insertWith (+) w 1 m) M.empty

main :: IO ()
main = mapM_ print (M.toList (wordCounts (words "a b a c b a")))
```

### OCaml
- Write the interface first (`.mli`), keep data immutable by default, use `option`/`result` plus `let*` binding operators, and pipe with `|>`.

```ocaml
let ( let* ) = Result.bind

let parse_age s =
  match int_of_string_opt s with
  | Some n when n >= 0 -> Ok n
  | _ -> Error ("bad age: " ^ s)

let () =
  match (let* a = parse_age "41" in Ok (a + 1)) with
  | Ok n -> Printf.printf "%d\n" n
  | Error e -> prerr_endline e
```

## 7. Top pitfalls and error-message fixes

### Haskell
| Error / symptom | Cause | Fix |
|---|---|---|
| `Couldn't match expected type 'Int' with actual type 'Integer'` / `'[Char]'` vs `Text` | Mismatched numeric/string types | Add type signatures; `fromIntegral`, `T.pack`/`T.unpack`; `OverloadedStrings` |
| `No instance for (Show (a -> b)) arising from a use of 'print'` | Printing a function (forgot an argument) | Apply all arguments |
| `Ambiguous type variable 'a0' arising from a use of 'read'` | `read` without a target type | Annotate: `read s :: Int`; prefer `readMaybe` |
| `Non-exhaustive patterns in function f` (runtime) | Missing case; also from `head []` | Enable `-Wall`; handle all constructors; avoid partial functions (`head`, `fromJust`, `!!`) — GHC 9.8+ warns on `head`/`tail` (`-Wx-partial`) |
| `Prelude.head: empty list` | Partial function on empty list | Pattern match or `Data.List.NonEmpty` |
| `<<loop>>` | A value defined in terms of itself (`let x = x + 1`) | Fix the recursion |
| `stack overflow` / huge memory with `foldl` | Thunk build-up from lazy accumulator | Use `foldl'` (strict), bang patterns `!acc`, `Data.Map.Strict`, `seq`/`deepseq` |
| `Could not find module 'Data.Text'` | Package not in `build-depends` | Add `text` to the `.cabal` file |
| `parse error (possibly incorrect indentation or mismatched brackets)` | Layout rule: `do`/`where`/`let` blocks must align | Align continuation lines deeper than the block start; spaces, no tabs |
| `The last statement in a 'do' block must be an expression` | Ended a `do` with `x <- ...` or `let` | Add `return x`/`pure x` |
| `Variable not in scope: foo` | Missing import or typo | `import Data.List (foo)` |
| lazy I/O: file handle closed before contents read | `readFile` + `hClose` in wrong order | Strict I/O (`Data.Text.IO.readFile`, `ByteString`), `withFile` and force contents |

### OCaml
| Error text | Cause | Fix |
|---|---|---|
| `Error: This expression has type float but an expression was expected of type int` | Mixed `+` and floats | Use `+.`, `*.`; convert with `float_of_int` |
| `Error: This expression has type int but an expression was expected of type unit` | Value discarded in a sequence `e1; e2` | `ignore (e1)` or `let _ = e1 in` |
| `Warning 8 [partial-match]: this pattern-matching is not exhaustive.` | Missing constructor | Add the case; treat warnings as errors in dune dev profile |
| `Error: Unbound value foo` | Defined later or not `rec` | Order definitions; `let rec` for recursion; open the module |
| `Error: Unbound module Yojson` | Library not in dune `(libraries ...)` | Add to `dune` file and `opam install` |
| `Exception: Not_found.` | `List.assoc`, `Hashtbl.find` miss | Use `_opt` variants (`Hashtbl.find_opt`) |
| `Exception: Invalid_argument "index out of bounds".` | Array/String index | Check `Array.length` |
| `Error: The value x has type '_weak1 list` | Value restriction on partial application | Eta-expand (`let f x = g x`) or add annotation |
| `Stack_overflow` | Non-tail-recursive function on long list | Tail-recursive with accumulator; OCaml 5 has larger growable stacks, `List.map` is tail-mod-cons since 5.1 |
| Syntax trap: nested `match` swallowing following cases | `match` inside a `match` arm without parens | Wrap inner match in `( ... )` or `begin ... end` |

## 8. Performance

- Haskell: laziness is the main performance hazard; profile with `+RTS -s` (allocation, GC time) and `-prof -fprof-auto` cost centres, and heap profiles (`+RTS -hT`). Use strict fields (`data P = P !Double !Double`), unboxed vectors (`vector`), `ByteString`/`Text`, and compile with `-O2`. Avoid `String` (a linked list of `Char`) in hot paths and `nub` (quadratic).
- OCaml: eager evaluation makes cost predictable; native code via `ocamlopt` is fast. Avoid polymorphic comparison (`compare`, `=`) in hot loops on boxed values; use `Int.equal`/specialised comparisons, `Float.Array`/`Bigarray` for unboxed floats, and tail recursion. In OCaml 5, spawn about one domain per core and use `Domainslib` task pools rather than thousands of domains; profile with `perf` and `memtrace`.

## 9. Security

- Both are memory-safe in ordinary code; the risky edges are FFI (`foreign import ccall`, OCaml `external`), `unsafePerformIO`/`Obj.magic`, and unsafe array access (`unsafeIndex`, `Array.unsafe_get`).
- Haskell: `read` on untrusted input throws; use `readMaybe` and proper parsers (`megaparsec`, `aeson` for JSON). Laziness can turn untrusted large inputs into memory exhaustion; parse strictly and bound sizes. Pin dependencies with `cabal freeze` or a Stackage snapshot.
- OCaml: `Marshal` on untrusted data is unsafe (it can crash or corrupt the runtime); use a typed format (yojson, sexp, protobuf). Pin with `opam lock` / `dune pkg lock`. Both: shell out with argument lists, never string-built commands.

## 10. Game-dev usage

### Haskell
- Niche: **Apecs** (ECS), **sdl2**/`h-raylib` bindings, functional reactive programming (Yampa, reflex), the commercial *Defect Process* game was written in Haskell. Common for tooling, compilers and proofs of game logic. Haskell is the language of Cardano/Plutus and many DSL compilers.

### OCaml
- Rare for shipping games; strong for tooling and compilers (Flow, Hack, Infer, Rust's original compiler, Coq/Rocq, Haxe compiler is written in OCaml), Jane Street trading systems. Bindings: `tsdl` (SDL2), `raylib-ocaml`. **js_of_ocaml**/**Melange** compile OCaml to JS for web games; **ReScript** descends from this line.

## 11. Cheat sheet vs Luau

| Concept | Luau | Haskell | OCaml |
|---|---|---|---|
| Indexing | 1-based tables | lists 0-based via `!!` (O(n), partial) | `arr.(0)`, `List.nth l 0` |
| Absent value | `nil` | `Nothing` (`Maybe`) | `None` (`option`) |
| Truthiness | nil/false falsy | `Bool` only | `bool` only |
| Not equal | `~=` | `/=` | `<>` (structural), `!=` (physical) |
| Equality | `==` | `==` (Eq class) | `=` structural, `==` physical |
| String concat | `..` | `++` (or `<>`) | `^` |
| List / array | table | `[1,2,3]` linked list | `[1;2;3]` list, `[|1;2|]` array |
| Map | table | `Data.Map` | `Map.Make(String)`, `Hashtbl` |
| Mutation | anywhere | `IORef`/`STRef` only | `ref`, `:=`, `!r`, `mutable` fields |
| Functions | `function(a, b)` | `f a b` curried | `fun a b -> ...` curried |
| Closures | yes | yes | yes |
| Coroutines | `coroutine.*` | green threads, `async` | effects, Eio fibers |
| Integer division | `//` | `div` (floor), `quot` (trunc) | `/` (trunc) on ints, `/.` floats |
| Modulo | floored | `mod` floored, `rem` trunc | `mod` truncated |
| Errors | `error`/`pcall` | `Either`, exceptions in IO (`throwIO`, `catch`) | `result`, exceptions `raise`, `try ... with` |
| Modules | `require` | `module X where` + `import` | file = module; `open`, functors |
| Pattern match | none | `case` / function equations | `match ... with` |

## 12. Recent changes and version notes

- GHC 9.14.1 (late 2025) is the first GHC release designated long-term support [1]; GHC2024 is the newest language edition; GHC 9.8+ warns on partial `head`/`tail` (`-Wx-partial`). Newer GHC versions after 9.14 are unverified as of 2026-10-13.
- OCaml 5.4.0 (2025-10-09) adds labelled tuples, immutable arrays, atomic record fields and new stdlib modules `Pair`, `Pqueue`, `Repr` [6]; OCaml 5.3 added dedicated effect-handler syntax; `List.map` is tail-recursive (tail-mod-cons) since 5.1. OCaml 5.5 status is unverified as of 2026-10-13.

## Sources

1. https://mailman.haskell.org/archives/list/ghc-devs@haskell.org/thread/SU3RZEHSTMMCJBOFOHBK6UTOZLQ56WND (GHC 9.14 release candidates / release announcements)
2. https://downloads.haskell.org/ghc/latest/docs/users_guide/
3. https://www.haskell.org/ghcup/
4. https://cabal.readthedocs.io/
5. https://wiki.haskell.org/Foldr_Foldl_Foldl%27
6. https://ocaml.org/changelog/2025-10-09-ocaml-540
7. https://ocaml.org/manual/5.4/effects.html
8. https://ocaml.org/docs/installing-ocaml
9. https://dune.readthedocs.io/
10. https://opam.ocaml.org/doc/Usage.html
11. https://github.com/ocaml-multicore/eio
12. https://hackage.haskell.org/package/async
13. https://ocaml.org/manual/5.4/parallelism.html
14. https://haskell-language-server.readthedocs.io/
