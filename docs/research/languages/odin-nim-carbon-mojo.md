# Odin, Nim, Carbon and Mojo - STAR language research (brief)

> Status: checked on 2026-10-13. Odin: monthly `dev-YYYY-MM` releases, latest **dev-2026-10 (2026-10-06)** on GitHub.
> Nim: stable line **2.2**, latest patch **2.2.12** (nim-lang.org blog). Carbon: **experimental**; the official roadmap
> lists "ship a working 0.1 language for evaluation" as a *potential 2026 goal*, 0.2 in 2027-2028 and 1.0 *beyond
> 2028*; do not recommend it for production. Mojo: **Mojo 1.0 released 2026-08-11** with Modular 26.5 (stability
> promise for APIs marked stable); the compiler was reported open-sourced under Apache-2.0 with LLVM exceptions on
> 2026-08-18 (secondary sources; confirm on modular.com before quoting). These are niche: answer carefully and say
> when something is version-specific.

## Odin

- **What it is**: a C alternative for "the joy of programming": simple, data-oriented, manual memory with implicit
  context allocators. Used by JangaFX (EmberGen) and hobby game developers. Ships vendor bindings for raylib, SDL2/3,
  OpenGL, Vulkan, DirectX, Metal, miniaudio, stb in `vendor:`.
- **Mental model**: procedures (`main :: proc() {}`), structs, tagged unions, distinct types, no methods/classes, no
  exceptions, no GC. Every procedure gets an implicit `context` carrying `context.allocator`,
  `context.temp_allocator` and `context.logger`.
- **Memory**: `new`, `make`, `delete`, `free`; `defer delete(x)`; `free_all(context.temp_allocator)` per frame;
  tracking allocator (`mem.Tracking_Allocator`) to find leaks.
- **Errors**: multiple return values with an error/ok last (`value, ok := m[key]`), `or_return`, `or_else`,
  `or_break`, `or_continue`; enums/unions as error types.
- **Toolchain**: `odin run .`, `odin build . -o:speed`, `odin test .`; a package is a directory; no package manager
  (vendor or git submodules). Debug builds bounds-check; `#no_bounds_check` disables locally.
- **Newer (2026)**: monthly releases add features; e.g. dev-2026-07 notes mention a restricted `-bedrock` subset mode and
  stack canaries (from a release mirror; verify on GitHub).
- **Pitfalls**: (1) forgetting `delete` for `make`d slices/maps/dynamic arrays; (2) returning slices of
  `temp_allocator` memory that is freed at frame end; (3) `context` changes are scoped; (4) `:=` declares, `=` assigns;
  (5) unused imports/variables are errors only with `-vet`; (6) strings are UTF-8 byte slices, `for r in str` yields
  runes; (7) maps are not ordered; (8) dynamic arrays need `append(&arr, x)` with a pointer; (9) foreign imports need
  the right library paths per OS; (10) `distinct` types do not implicitly convert.
- **Game dev**: strongest fit of the four: `vendor:raylib` lets you write a game in minutes; hot reload templates
  exist; Karl Zylinski's "Understanding the Odin Programming Language" book and templates are the common learning path.
- **vs Luau**: `local x = 1` -> `x := 1`; tables -> `[dynamic]T` + `map[K]V`; `nil` -> `nil` for pointers/maps or
  `Maybe(T)`; `pcall` -> multiple return values + `or_return`; metatables -> structs + procedure groups;
  `require` -> `import "core:fmt"`; GC -> allocators; 1-based -> 0-based.

## Nim

- **What it is**: Python-like syntax, statically typed, compiles to C/C++/Objective-C/JavaScript; powerful macros;
  memory managed by **ORC** (reference counting + cycle collector, default since Nim 2.0) or ARC.
- **Mental model**: indentation-based syntax, procedures, `object`/`ref object`, generics, templates and AST macros,
  uniform function call syntax (`x.len` == `len(x)`), compile-time evaluation (`static`, `const`).
- **Memory**: value types (`object`, `seq`, `string` with move semantics/destructors), `ref` for heap references;
  `=destroy`, `=copy`, `=sink` hooks; ORC handles cycles; `--mm:arc` for no cycle collector (deterministic, used in
  embedded/games).
- **Errors**: exceptions (`raise newException(ValueError, "msg")`, `try/except/finally`), effect system tracks raised
  exceptions (`{.raises: [].}`); `Option[T]` and result libraries (`results`) also common.
- **Concurrency**: threads (`std/typedthreads`), channels, `malebolgia`/`taskpools` for structured parallelism;
  `asyncdispatch`/`chronos` for async I/O.
- **Toolchain**: `nim c -d:release app.nim`, `-d:danger` (no runtime checks), `nim js`; **Nimble** package manager
  (`nimble init`, `nimble install`), Atlas (newer workspace tool); `std/unittest` and `testament` for tests.
- **Status**: stable 2.2 line (2.2.12 latest patch); Nimony/Nim 3 is the next-generation compiler in development
  (verify status).
- **Pitfalls**: (1) style insensitivity (`fooBar` == `foo_bar`, first letter case-sensitive) confuses grep;
  (2) `ref` vs value semantics; (3) `seq` is a value type, copying on assignment unless moved; (4) `-d:danger` removes
  bounds/overflow checks; (5) exceptions vs `{.raises.}` annotations mismatch errors; (6) integer division is `div`
  and `mod`, `/` returns float; (7) `var` parameters for mutation; (8) GC-safety (`gcsafe`) errors with threads;
  (9) macros produce hard error messages: use `expandMacros`; (10) mixing `asyncdispatch` and `chronos`.
- **Game dev**: naylib/nimraylib_now (raylib), sdl2/sdl3 bindings, `nico` (fantasy console), Godot via `gdext-nim`
  (verify maintenance); embedding Lua via `nimLUA`/C API.
- **vs Luau**: `local x = 1` -> `var x = 1`/`let x = 1`; tables -> `seq[T]`, `Table[K, V]`; `nil` -> `nil` for refs,
  `Option[T]`; `pcall` -> `try/except`; `..` -> `&`; `#t` -> `len(t)`; `require` -> `import std/tables`; 1-based ->
  0-based (but arrays can declare ranges, e.g. `array[1..10, int]`).

## Carbon

- **What it is**: Google-led experimental successor to C++ with bidirectional C++ interop, aiming for a memory-safe
  subset later. Not usable in production; the toolchain (`carbon` explorer/compiler, built with Bazel) is for
  experimentation.
- **Roadmap (official)**: 2025 objectives were C++ interop demos (access most non-template C++ APIs from Carbon, and
  non-generic Carbon APIs from C++) and a concrete memory-safety design; **potential 2026 goal: 0.1 language for
  evaluation**; 0.2 by 2027-2028; 1.0 beyond 2028.
- **Syntax sketch**: `fn Main() -> i32 { var x: i32 = 1; return x; }`, `package Geometry;`, `class Circle { var r: f64; }`,
  generics with `[T:! type]`, interfaces and `impl`, `let` for immutable bindings.
- **Memory/errors**: manual like C++ today (unsafe), memory-safe design work in progress; errors not finalized.
- **Pitfalls**: syntax and semantics change frequently; examples online are often outdated; there is no stable
  standard library; do not suggest Carbon for shipping games.
- **vs Luau**: `local x = 1` -> `var x: i32 = 1;`; module `require` -> `package`/`import`; classes are nominal;
  everything typed.

## Mojo

- **What it is**: Modular's Python-superset-style systems language for AI/accelerator programming (CPU, GPU via
  MLIR), with Python interop. **1.0 released 2026-08-11** (Modular 26.5); 1.x promises backward compatibility for APIs
  marked stable (not the entire standard library). Modular was acquired by Qualcomm (closed 2026-07-29 per secondary
  sources; verify).
- **Mental model**: `def` (Python-like, flexible) and `fn` (strict, typed) functions were the historical split; recent
  versions moved toward unified `def` with typed signatures (check the version's docs); `struct` (static, value
  semantics), `trait`s, `comptime`/parameters in `[]` for compile-time metaprogramming, SIMD types first class.
- **Memory**: ownership and borrowing with argument conventions (`read`/`mut`/`owned` in current releases; older
  releases used `borrowed`/`inout`/`owned`), ASAP destruction (values are destroyed after last use), lifetimes/origins
  for references; Python objects via `PythonObject` are reference counted.
- **Errors**: `raises` functions and `try/except` like Python; typed error work evolved over releases.
- **Toolchain**: `pixi` (recommended) or `magic` (older) to install; `mojo run file.mojo`, `mojo build`, `mojo test`,
  `mojo format`; packages as `.mojopkg`; VS Code extension.
- **Pitfalls**: (1) huge API churn before 1.0: older blog posts use `let`, `inout`, `borrowed`, `fn`/`def` rules that
  changed; (2) not all Python works natively: Python libraries run through interop (CPython); (3) GPU code targets
  specific vendors; (4) platform support (Linux/macOS first; Windows via WSL historically: verify); (5) standard library
  APIs outside the marked-stable set may still change in 1.x.
- **Game dev**: not a game-dev language in practice; possible for compute kernels (physics, ML inference) called from
  Python.
- **vs Luau**: `local x = 1` -> `var x = 1`; tables -> `List[T]`, `Dict[K, V]`; `pcall` -> `try/except`; classes ->
  `struct`; GC -> ownership/ASAP destruction.

## Sources

- https://github.com/odin-lang/Odin/releases - Odin monthly releases (dev-2026-10)
- https://odin-lang.org/docs/overview/ - Odin language overview
- https://pkg.odin-lang.org/ - Odin core and vendor packages
- https://nim-lang.org/blog.html - Nim 2.2.x release announcements
- https://nim-lang.org/docs/manual.html - Nim manual
- https://nim-lang.org/docs/mm.html - Nim memory management (ORC/ARC)
- https://github.com/nim-lang/nimble - Nimble package manager
- https://github.com/carbon-language/carbon-lang/blob/trunk/docs/project/roadmap.md - Carbon roadmap
- https://docs.carbon-lang.dev/ - Carbon documentation
- https://docs.carbon-lang.dev/proposals/p002759-defining-the-0-1-language.html - Carbon 0.1 definition
- https://www.modular.com/blog/modular-26-5-mojo-1-0-is-here - Mojo 1.0 announcement
- https://docs.modular.com/mojo/manual/ - Mojo manual
- https://docs.modular.com/mojo/changelog/ - Mojo changelog (API changes by version)
- https://en.wikipedia.org/wiki/Mojo_(programming_language) - open-source compiler date (secondary)
