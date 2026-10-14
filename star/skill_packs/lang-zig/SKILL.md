---
name: lang-zig
description: Zig (0.17.0, October 2026; pre-1.0 with breaking changes every release) allocators, error unions, std.Io, build.zig and version migration. Use for Zig code, zig build errors, porting older Zig code, or C interop from Zig.
---
# Zig 0.17 (pre-1.0: say which version an answer targets)
- Releases: 0.15 (Aug 2025), 0.16 (Apr 2026), 0.17 (Oct 2026). Each one breaks code. Check `zig version` and `minimum_zig_version` in build.zig.zon; never mix APIs from different versions.
- 0.15 "Writergate": `std.Io.Writer`/`std.Io.Reader` with buffers; flush buffered writers; `std.ArrayList` is unmanaged (`var list: std.ArrayList(u8) = .empty;`, then `try list.append(gpa, x)` and `list.deinit(gpa)`); `usingnamespace` and the `async` keywords removed; format methods use `{f}`.
- 0.16: all I/O takes an `std.Io`. Write `pub fn main(init: std.process.Init) !void` and use `init.gpa`, `init.io`, `init.arena`, `init.environ_map` (env vars and args are no longer global). Concurrency: `io.async(f, .{args})` returns a future with `.await(io)` / `.cancel(io)`; `Io.Group`, `Io.Queue`; `std.Thread.Pool` removed; `@Type` replaced by `@Int`, `@Struct` and friends; tests use `std.testing.io`.
- 0.17: `@cImport` removed (use the translate-c package from build.zig); `errdefer |err|` capture removed (wrap the call with `catch |err|`); `[x] ** n` removed (use `@splat(x)`); `DebugAllocator` deprecated for `std.heap.SafeAllocator`; `StackFallbackAllocator` renamed `BufferFirstAllocator`; `std.fmt.allocPrint(a, ...)` became `a.print(...)`; `ArrayList.getLast` became `last()`; `@bitCast` on arrays and vectors changed meaning.
- Memory: pass `std.mem.Allocator` explicitly; `defer x.deinit(gpa)` right after creating; `errdefer` to undo partial work on error; arenas for per-frame or per-request memory; `std.testing.allocator` fails tests that leak.
- Errors: `!T` error unions, `try`, `catch |err| switch (err) {...}`; an ignored error union is a compile error; `catch unreachable` only when failure is impossible.
- Compile errors: unused locals or params (`_ = x;`), `var` never mutated (use `const`), no implicit narrowing (`@intCast` with a result type), exhaustive `switch`, compare strings with `std.mem.eql(u8, a, b)`.
- Safety: Debug and ReleaseSafe panic on overflow, out-of-bounds and null unwrap; ReleaseFast makes them undefined behaviour. Ship security-sensitive code as ReleaseSafe.
- Commands: `zig init`, `zig build`, `zig build run`, `zig build test`, `zig fmt .`, `zig fetch --save <url>`, cross-compile with `-Dtarget=x86_64-windows`; `zig cc` is a cross C compiler.
- Pointers into an ArrayList are invalidated when it grows: store indices.
