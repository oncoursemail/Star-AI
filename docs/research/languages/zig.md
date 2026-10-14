# Zig (0.17.0, pre-1.0) - STAR language research

> Status: checked on 2026-10-13 against ziglang.org/download (releases: **0.17.0 on 2026-10-01**, 0.16.0 on
> 2026-04-13, 0.15.2 on 2025-10-11, 0.15.1 on 2025-08-19, 0.14.1 on 2025-05-21) and the 0.16.0 / 0.17.0 release
> notes. **Zig is pre-1.0 and every minor release breaks the standard library and sometimes the language.** The single
> most common reason an AI answer about Zig is wrong is that it was written for an older version. Always ask for or
> check `zig version` and the `minimum_zig_version` in `build.zig.zon`, and say which version an answer targets.
> Zig is a small, explicit systems language and a C/C++ cross-compiling toolchain (`zig cc`), used for systems
> tools (Bun, TigerBeetle, Ghostty), embedded, games and as a drop-in C build system.

## 0. Current version and what changed 2024-2026

**0.14 (2025-03)**: decl literals (`.init` style `const list: std.ArrayList(u8) = .empty;`), labeled `switch`
continue, `@FieldType`, `GeneralPurposeAllocator` renamed `DebugAllocator`, `std.heap.smp_allocator`.

**0.15 (2025-08, "Writergate")**:
- New non-generic **`std.Io.Writer` / `std.Io.Reader`** interfaces with the buffer inside the interface; the old
  generic `std.io` readers/writers were deprecated (removed in 0.16). You must **flush** buffered writers.
- `std.ArrayList` became the **unmanaged** variant (no allocator field; pass the allocator to each mutating call:
  `try list.append(gpa, x)`, `list.deinit(gpa)`); the managed one is `std.array_list.Managed`.
- `usingnamespace` removed; `async`/`await` keywords removed (async returns later as a library feature on `Io`).
- Format methods must be invoked with `{f}`; `format` signature simplified to `fn format(self, w: *std.Io.Writer) !void`.

**0.16 (2026-04-13, "I/O as an Interface")**:
- **All I/O takes an `std.Io` instance** (files, networking, sleeping, time, process spawning, mutex waiting).
  Implementations: `Io.Threaded` (feature-complete, used by default), `Io.Evented` (experimental green threads),
  `Io.Uring`, `Io.Kqueue`, `Io.Dispatch` (proofs of concept), `Io.failing`.
- **"Juicy Main"**: `pub fn main(init: std.process.Init) !void` gives `init.gpa` (leak-checked in Debug), `init.io`,
  `init.arena`, `init.environ_map`, `init.minimal.args`. Environment variables and process args are **no longer
  global**: pass them in.
- Concurrency primitives on `Io`: `io.async(f, .{args})` returns a `Future(T)` with `await(io)` and `cancel(io)`;
  `io.concurrent` (must run concurrently, can fail with `error.ConcurrencyUnavailable`); `Io.Group`, `Io.Queue(T)`,
  `Io.Select`, `Io.Batch`; cancellation through `error.Canceled`. `std.Thread.Pool` removed.
- `std.testing.io` for tests (like `std.testing.allocator`).
- `@Type` removed; replaced by `@Int`, `@Struct`, `@Union`, `@Enum`, `@Pointer`, `@Fn`, `@Tuple`, `@EnumLiteral`.
- `@cImport` deprecated (C translation moves to the build system).
- `std.mem.indexOf*` renamed toward `find*` (`find`, `findScalar`, `findLast`...) plus `cut`, `cutPrefix`,
  `cutSuffix`, `cutScalar`.
- More containers unmanaged; `PriorityQueue`/`PriorityDequeue` use `.empty`, `push`/`pop`; `ArrayHashMap`
  managed variants removed (`std.array_hash_map.Auto`, `.String`, `.Custom`).
- `heap.ArenaAllocator` thread-safe and lock-free; `heap.ThreadSafeAllocator` removed.
- File system API moved under `std.Io` (`std.Io.Dir`, `std.Io.File`), e.g.
  `try std.Io.File.stdout().writeStreamingAll(io, "Hello\n");`.
- Language: forbids returning the address of a trivial local; runtime vector indexes forbidden; pointers forbidden
  in packed structs/unions; small ints coerce to floats.
- Toolchain: LLVM 21, new ELF linker, incremental compilation progress, fuzzer improvements.

**0.17 (2026-10-01)**:
- **`@cImport` removed**; C translation is the official `translate-c` package
  (`zig fetch --save git+https://codeberg.org/ziglang/translate-c`) used from `build.zig`; `std.Build.Step.TranslateC`
  deprecated.
- **`errdefer |err|` capture removed**: move the error handling to a wrapper that uses `catch |err|`.
- **Array multiplication `**` removed**: `var a: [N]u8 = @splat(0);` instead of `[1]u8{0} ** N`.
- `void{}` syntax removed (use `{}`); `i0` removed; `@divCeil`, `@backingInt`/`@fromBackingInt` added;
  `@hasDecl` true only for public declarations; `@bitCast` semantics changed for arrays/vectors (can silently
  change behaviour; re-test bit casts).
- `std.heap.DebugAllocator` **deprecated**, replaced by the thread-safe **`std.heap.SafeAllocator`** (leak report on
  `deinit`, detects double free and mismatched frees).
- `std.heap.StackFallbackAllocator` renamed **`BufferFirstAllocator`** (buffer passed in); `std.heap.stackFallback`
  removed.
- `std.fmt.allocPrint(a, ...)` moved to the allocator: `try allocator.print("{s}={d}", .{x, y})`.
- `ArrayList.getLast`/`getLastOrNull` deprecated for `last()` (returns optional) and `lastPtr()`.
- `std.lang.OptimizeMode` renamed `Optimize` with tags `.debug`, `.safe`, `.fast`, `.small`; std types are referred to
  as `std.lang.*` in 0.17 notes (for example `std.lang.Endian.native`); `@import("builtin").cpu/os/abi` deprecated
  for `@import("builtin").target.*` (removed in 0.18).
- Build system: separate configure and make processes, reworked cache, Build Server Protocol, local package overrides,
  project-local package fetching (0.16).
- Toolchain: LLVM 22; incremental compilation expected to work on x86_64-linux.

Migration rule for STAR: if the user's code uses `std.io.getStdOut()`, `GeneralPurposeAllocator`, `@cImport`,
`usingnamespace`, `async`, managed `ArrayList.init(allocator)` or `[_]T{0} ** n`, it is pre-0.15/0.16/0.17 code. Do not
mix eras in one answer.

## 1. Mental model

- "No hidden control flow, no hidden allocations": no operator overloading, no exceptions, no implicit allocation;
  functions that allocate take an `std.mem.Allocator` parameter; functions that do I/O take an `std.Io` (0.16+).
- **comptime**: the same language runs at compile time. Generics are functions that take `comptime T: type` and
  return types; reflection is `@typeInfo`; there is no separate macro or template language.
- Errors are values: error unions `!T` with `try`/`catch`, and `errdefer` for cleanup on the error path.
- Optionals `?T` instead of null pointers; `orelse` and `if (opt) |v|` unwrap.
- Safety: **Debug** and **ReleaseSafe** builds check for illegal behaviour (overflow, out-of-bounds, null unwrap,
  invalid enum, wrong union field) and panic with a stack trace; **ReleaseFast/ReleaseSmall** turn those into
  undefined behaviour. Choose per build.
- C interop is first class; Zig can compile C/C++ and link libc for many targets out of the box.

## 2. Type system

- Integers of any width: `u8`, `i32`, `u7`, `usize`, `isize`, `comptime_int`; floats `f16`, `f32`, `f64`, `f80`,
  `f128`; `bool`; `void`; `noreturn`; `type`; `anyerror`.
- Overflow is illegal behaviour (checked in safe modes). Wrapping `+%`, saturating `+|`, `@addWithOverflow`.
- Casts are explicit builtins: `@intCast`, `@floatFromInt`, `@intFromFloat`, `@truncate`, `@ptrCast`, `@alignCast`,
  `@as(T, x)` for safe coercion; result-type inference (`const x: u8 = @intCast(y);`).
- Pointers: single-item `*T`, many-item `[*]T`, slices `[]T` (pointer + length), sentinel-terminated `[:0]u8`,
  C pointers `[*c]T` (only for C interop), optional pointers `?*T` (same size as a pointer).
- Arrays `[N]T` are values (copied); slices are views.
- Strings are `[]const u8` (bytes, UTF-8 by convention); literals are `*const [N:0]u8`.
- `struct` (with methods and decls), `enum`, `union(enum)` tagged unions, `packed struct`, `extern struct` (C ABI),
  `opaque {}`.
- Error sets: `error{NotFound, Invalid}`, merged with `||`, inferred with `!T`.
- Generics: `fn List(comptime T: type) type { return struct { items: []T, ... }; }`; duck-typed `anytype`
  parameters.
- No inheritance, no interfaces keyword: vtables by hand (`std.mem.Allocator` and `std.Io` are fat pointers with a
  vtable), or `anytype` static dispatch.

## 3. Memory model and ownership

- Manual memory management with **explicit allocators**. Convention: whoever receives an allocator and returns
  memory documents who frees it; `defer allocator.free(buf);` right after allocation.
- Allocators: `init.gpa` from Juicy Main (0.16+), `std.heap.SafeAllocator` (0.17, debug checks; was
  `DebugAllocator`/`GeneralPurposeAllocator`), `std.heap.ArenaAllocator` (free all at once; thread-safe since 0.16),
  `std.heap.FixedBufferAllocator` (from a stack buffer), `std.heap.BufferFirstAllocator` (0.17), `std.heap.page_allocator`,
  `std.heap.c_allocator` (needs libc), `std.heap.smp_allocator` (fast multi-threaded), `std.testing.allocator`
  (fails tests on leaks).
- `defer` runs at scope exit; `errdefer` only when the scope exits with an error (rollback of partial
  construction).
- Containers are **unmanaged**: they do not store the allocator: `var list: std.ArrayList(u8) = .empty;
  defer list.deinit(gpa); try list.append(gpa, 'x');`.
- Dangling pointers are possible: a slice into an `ArrayList` is invalidated when it grows (0.17 adds pointer-stability
  checks in safe builds).
- `undefined` means "uninitialized": reading it is illegal; Debug builds fill it with `0xaa` bytes to expose bugs.

## 4. Concurrency

- 0.16+: concurrency is expressed through `std.Io`: `io.async`/`io.concurrent` return futures, `Io.Group` manages many
  tasks, `Io.Queue(T)` is an MPMC channel, `Io.Select` waits for the first of several; cancellation returns
  `error.Canceled` from most I/O. `defer _ = future.cancel(io) catch {};` releases a task on error paths.
- Threads still exist: `std.Thread.spawn(.{}, func, .{args})` + `join()`; `std.Thread.Mutex`, `std.Thread.Condition`,
  `std.atomic.Value(T)` with explicit orderings.
- Thread-local: `threadlocal var x: u32 = 0;`.
- Single-threaded builds (`-fsingle-threaded`) make sync primitives no-ops; `Io.Threaded` then runs async tasks
  sequentially.

## 5. Error handling

```zig
const std = @import("std");

const ParseError = error{ Empty, NotANumber };

fn parsePort(text: []const u8) (ParseError || std.fmt.ParseIntError)!u16 {
    if (text.len == 0) return error.Empty;
    return std.fmt.parseInt(u16, text, 10);
}

fn loadConfig(gpa: std.mem.Allocator) !*Config {
    const cfg = try gpa.create(Config);
    errdefer gpa.destroy(cfg); // only runs if a later `try` fails
    cfg.port = try parsePort("8080");
    return cfg;
}
```

- `try x` = `x catch |err| return err`. `catch |err| switch (err) { ... }` handles specific errors; `catch unreachable`
  asserts success (illegal behaviour if wrong).
- Error return traces in Debug show where an error was created and propagated.
- `@panic("msg")` / `std.debug.panic` for unrecoverable bugs; `unreachable` for impossible states.
- Error sets are exhaustively checked by `switch`; `anyerror` is the global set.
- 0.17: `errdefer |err|` capture is gone; to log the error, wrap: `inner() catch |err| { log; return err; }`.

## 6. Toolchain, build and package management

- Install: download from ziglang.org (tarball), `zvm`/`zigup` version managers, or package managers (often behind).
- `zig init` creates `build.zig` + `build.zig.zon` + `src/main.zig` + `src/root.zig`.
- `zig build` (runs `build.zig`), `zig build run`, `zig build test`, `zig build -Doptimize=ReleaseFast`
  (verify the option spelling for your version; 0.17 renamed `std.lang.Optimize` tags), `zig build --watch`,
  `zig run file.zig`, `zig test file.zig`, `zig fmt .`, `zig fetch --save <url>` (adds a dependency hash to
  `build.zig.zon`).
- `build.zig` is Zig code: `b.addExecutable(.{ .name = "app", .root_module = b.createModule(.{ .root_source_file =
  b.path("src/main.zig"), .target = target, .optimize = optimize }) })` (root_module style since 0.14/0.15),
  `b.installArtifact(exe)`, `b.dependency("raylib_zig", .{...})`.
- Package manager: `build.zig.zon` lists dependencies by URL + hash (content-addressed, no central registry).
  0.16/0.17 add local package overrides and project-local fetch directories.
- Cross-compiling: `-Dtarget=x86_64-windows`, `aarch64-linux-musl`, `wasm32-wasi`; bundles libc headers for many
  targets. `zig cc` / `zig c++` act as a cross C/C++ compiler (`cargo zigbuild` uses it).
- ZLS is the language server (match its version to the compiler).

## 7. Testing

- `test "name" { try std.testing.expectEqual(@as(u32, 4), add(2, 2)); }` blocks live next to code; `zig build test`
  or `zig test file.zig`.
- `std.testing.allocator` fails the test on leaks; `std.testing.io` (0.16+) for I/O; `expectError`,
  `expectEqualStrings`, `expectEqualSlices`.
- Tests run in Debug by default with all safety checks; `zig build test -Doptimize=ReleaseSafe` to also check safe
  release builds.
- Built-in fuzzing: `zig build test --fuzz` with `std.testing.fuzz` (improved in 0.16/0.17).
- Unit-test timeouts in the build system (0.16).

## 8. Idiomatic patterns

- Pass `gpa: std.mem.Allocator` (and `io: std.Io` in 0.16+) explicitly; store them in a context struct when many
  functions need them.
- `init`/`deinit` pairs; `defer x.deinit(gpa);` right after creation; decl literals `.empty`, `.init`.
- Arena per request/frame: `var arena: std.heap.ArenaAllocator = .init(gpa); defer arena.deinit();`.
- Tagged unions + exhaustive `switch` for state machines.
- `comptime` for generic containers and compile-time tables; `inline for` over comptime-known lists.
- Return slices of caller-provided buffers to avoid allocation; `std.fmt.bufPrint`.
- Prefer `[]const u8` parameters; use sentinel slices only for C interop.
- Use `std.log` with scopes instead of `std.debug.print` in libraries.

## 9. Top 30 pitfalls and compiler-error fixes

1. **Version drift** - code from blog posts for 0.11-0.14 does not compile on 0.16/0.17. Fix: target one version; use
   the release-notes upgrade guides.
2. **`error: unused local variable` / `unused function parameter`** - Zig rejects unused locals. Fix: use it or
   `_ = x;`.
3. **`error: local variable is never mutated`** - declared `var` but never changed. Fix: `const`.
4. **`expected type 'u8', found 'usize'`** - no implicit narrowing. Fix: `@intCast(x)` with a result type, or
   change the type.
5. **`error: expected error union type, found ...`** - `try` on a non-error value. Remove `try`.
6. **`error: error is ignored`** - calling a function returning `!T` without `try`/`catch`. Fix: `try f()` or handle
   it.
7. **`std.io.getStdOut()` does not exist** (0.15+). 0.15: `std.fs.File.stdout().writer(&buf)` + `.interface` +
   `flush()`; 0.16+: `std.Io.File.stdout()` with an `io` (e.g. `writeStreamingAll(io, bytes)`), or `std.debug.print`
   for debugging output to stderr.
8. **Forgot to flush** a buffered `std.Io.Writer` - output missing. Fix: `try w.flush();`.
9. **`ArrayList.init(allocator)` not found** (0.15+): use `var list: std.ArrayList(T) = .empty;` and pass `gpa` to
   `append`, `deinit`, `toOwnedSlice`.
10. **`GeneralPurposeAllocator`** renamed `DebugAllocator` (0.14) then deprecated for `SafeAllocator` (0.17); in 0.16+
    just use `init.gpa` from Juicy Main.
11. **`@cImport` removed in 0.17** - use the `translate-c` package from `build.zig` (deprecated in 0.16).
12. **`errdefer |err|` no longer allowed** (0.17) - use a wrapper with `catch |err|`.
13. **`**` array repetition removed** (0.17) - `@splat(value)`.
14. **`usingnamespace` removed** (0.15) - re-export explicit declarations (`pub const foo = other.foo;`).
15. **`async`/`await`/`suspend` keywords gone** - 0.16 uses `io.async(...)`, `future.await(io)`.
16. **`@Type(...)` removed** (0.16) - use `@Int(.unsigned, 8)`, `@Struct(...)`, etc.
17. **Env vars via `std.os.environ` / `std.process.getEnvVarOwned`** - 0.16 makes them non-global; read from
    `init.environ_map` in `main` and pass along.
18. **Returning a slice of a stack array** - dangling; 0.16 forbids trivial cases ("returning address of local").
    Fix: allocate or have the caller pass a buffer.
19. **Holding a pointer/slice into an ArrayList across `append`** - invalidated on growth; store indices.
20. **Integer overflow panics in Debug** ("panic: integer overflow"). Fix: wider types, `+%`, `std.math.add`
    (returns error on overflow).
21. **`index out of bounds` panic** - slices are bounds-checked in safe modes; in ReleaseFast it is UB.
22. **`attempt to use null value`** - `opt.?` on null. Fix: `if (opt) |v|` or `orelse`.
23. **Comptime vs runtime confusion** - `unable to evaluate comptime expression` / "comptime call of non-comptime
    function". Fix: mark parameters `comptime` or compute at runtime.
24. **String comparisons with `==`** compares pointers/arrays, not contents of slices. Fix: `std.mem.eql(u8, a, b)`.
25. **`switch` must be exhaustive** - add `else =>` or handle all tags.
26. **Format specifier errors** - `{}` for slices prints bytes; use `{s}` for strings, `{d}` numbers, `{any}` debug,
    `{f}` for types with a `format` method (0.15+).
27. **Forgetting `defer deinit`** - leaks reported by `std.testing.allocator` / SafeAllocator at exit.
28. **`std.mem.indexOf` renamed** to `find` (0.16, with deprecation period); `std.mem.split` became
    `splitScalar`/`splitSequence`/`splitAny` (0.12+).
29. **Build API churn** - `b.addExecutable(.{ .root_source_file = ... })` (old) vs `.root_module = b.createModule(...)`
    (current). Copy from the version's `zig init` template.
30. **ZLS / compiler mismatch** gives bogus editor errors; install matching versions.
31. **`@bitCast` on arrays/vectors** changed meaning in 0.17 without compile errors; re-test.

## 10. Performance

- Build modes: Debug (safety, slow), ReleaseSafe (optimised + safety checks; good default for servers/tools),
  ReleaseFast (no checks), ReleaseSmall. Disable safety locally with `@setRuntimeSafety(false)` only in measured hot
  loops.
- Explicit allocators make allocation visible: arenas and fixed buffers for per-frame data.
- SIMD with `@Vector(4, f32)`; `comptime` precomputation; `inline` loops; `noalias`.
- Profile with perf, Tracy (zig bindings), Valgrind/callgrind; the self-hosted x86 backend compiles faster in Debug
  but LLVM optimises release builds.
- Data-oriented design is idiomatic (the Zig compiler itself uses struct-of-arrays via `std.MultiArrayList`).

## 11. Security

- Safe build modes catch overflow, bounds and null errors at runtime; ReleaseFast removes them, so deploy security-
  sensitive code as **ReleaseSafe**.
- Still possible: use-after-free, double free, data races, leaks, uninitialized reads in release modes. SafeAllocator
  (0.17) catches double frees and many use-after-free cases in testing.
- C interop inherits C's risks; validate lengths and pointers from C.
- Injection: build child process argv as arrays (`std.process.Child` with `argv`), never a shell string; parameterized
  SQL via SQLite bindings.
- Supply chain: dependencies are pinned by content hash in `build.zig.zon`; review `build.zig` of dependencies (it runs
  at build time).
- `std.crypto` is extensive (AES-GCM, ChaCha20-Poly1305, Ed25519, X25519, Argon2...); use it rather than hand-written
  crypto.

## 12. Game-development usage

- **raylib-zig** bindings (raylib 5/6), **SDL3** via `build.zig` packages (e.g. castholm/SDL), **sokol-zig**,
  **zig-gamedev** (zgui, zphysics, zmath...), **Mach** engine (Zig-native, tracks Zig nominated versions; check its
  required Zig version), Capy/others for UI.
- Strengths: easy cross-compiling to Windows/macOS/Linux/WASM, C library reuse without bindings work (via translate-c),
  comptime ECS designs, deterministic memory.
- Embedding Lua/Luau: link the C library via `build.zig` (`ziglua` supports Lua 5.1-5.4, LuaJIT and Luau).
- Version churn is the main cost: game libraries pin specific Zig versions.

## 13. Cheat sheet: Zig vs Luau

| Concept | Luau | Zig |
|---|---|---|
| Variable | `local x = 1` | `var x: i32 = 1;` / `const x = 1;` |
| Nil | `nil` | optional `?T` with `null`; `orelse`, `if (x) \|v\|` |
| Number | `number` | `i32`, `u8`, `usize`, `f64`, arbitrary widths |
| Integer division | `7 // 2` | `@divFloor(7, 2)`, `@divTrunc`, `/` only for unsigned or comptime-known positive |
| Indexing | 1-based | 0-based, bounds-checked in safe modes |
| Array | `{1, 2, 3}` | `[_]i32{ 1, 2, 3 }`; dynamic `std.ArrayList(i32)` |
| Map | table | `std.AutoHashMapUnmanaged(K, V)` / `std.StringHashMapUnmanaged(V)` |
| Length | `#t` | `slice.len` |
| String | `"..."` | `[]const u8`; compare with `std.mem.eql` |
| Concat | `a .. b` | `std.mem.concat(gpa, u8, &.{a, b})`, `allocator.print` (0.17) |
| Format | `string.format` | `std.fmt.bufPrint(&buf, "{d}", .{n})` |
| Function | `local function f(a)` | `fn f(a: i32) i32 { return a; }` |
| Closure | upvalues | none: struct with a method, or context pointer |
| Multiple returns | `return a, b` | return a struct/tuple `.{ a, b }` |
| Module | `require` | `@import("file.zig")` |
| Class | metatable | `struct` with methods, `self` param |
| Error | `error`, `pcall` | error unions `!T`, `try`, `catch` |
| Cleanup | none (GC) | `defer`, `errdefer` |
| Coroutine | `coroutine` | `io.async` futures (0.16+), threads |
| Generics | `<T>` | `comptime T: type`, `anytype` |
| Iteration | `for i, v in ipairs(t)` | `for (items, 0..) \|v, i\|` |
| Equality | `==` | `==` for scalars; `std.mem.eql`, `std.meta.eql` |
| Memory | GC | explicit allocators |
| Compile-time | none | `comptime` blocks and params |
| Printing | `print(x)` | `std.debug.print("{any}\n", .{x})` |
| Truthiness | `nil`/`false` | only `bool` in conditions |

## 14. Sources

Releases and upgrade guides:
- https://ziglang.org/download/ - release list with dates (0.17.0, 0.16.0, 0.15.x)
- https://ziglang.org/download/0.17.0/release-notes.html - 0.17 language and std changes
- https://ziglang.org/download/0.16.0/release-notes.html - 0.16 I/O interface, Juicy Main
- https://ziglang.org/download/0.15.1/release-notes.html - Writergate, unmanaged ArrayList
- https://ziglang.org/download/0.14.0/release-notes.html - decl literals, DebugAllocator
- https://ziglang.org/download/index.json - machine-readable release index
- https://ziglang.org/news/ - Zig Software Foundation news
- https://ziglang.org/devlog/ - devlog (e.g. ArrayList pointer stability)

Language and std docs:
- https://ziglang.org/documentation/master/ - language reference (match your version)
- https://ziglang.org/documentation/master/std/ - standard library docs
- https://ziglang.org/learn/overview/ - design overview
- https://ziglang.org/learn/build-system/ - build system guide
- https://codeberg.org/ziglang/translate-c - translate-c package
- https://codeberg.org/ziglang/zig - source and issues (moved from GitHub)

Ecosystem:
- https://github.com/zigtools/zls - language server
- https://github.com/Not-Nik/raylib-zig - raylib bindings
- https://machengine.org/ - Mach engine
- https://github.com/zig-gamedev - zig-gamedev libraries
- https://github.com/natecraddock/ziglua - Lua/Luau bindings
- https://ziglang.org/learn/samples/ - official samples
- https://zig.guide/ - community guide (check the version banner)
