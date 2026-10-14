# C (C23 = ISO/IEC 9899:2024) - STAR language research

> Status: checked on 2026-10-13. **C23** was published as ISO/IEC 9899:2024 (October 2024). **GCC 15** changed its
> default C dialect from `-std=gnu17` to **`-std=gnu23`** (GCC 15 changes page), so code that used `bool`, `true`,
> `false`, `nullptr`, `static_assert` or `typeof` as identifiers, or old K&R/unprototyped declarations, can break when
> simply recompiled. GCC 15/16 also implement parts of the next revision, **C2y** (`-std=c2y`). Use C for kernels,
> embedded firmware, small portable libraries with a stable ABI, language runtimes (Lua, Luau's C API surface, CPython),
> and as the lingua franca for FFI.

## 0. Current version and what changed 2024-2026

C23 headline features (cppreference C23 page, N3220 working draft):
- `bool`, `true`, `false`, `alignas`, `alignof`, `static_assert`, `thread_local` are **keywords** (no header needed).
- **`nullptr`** and `nullptr_t`; prefer it over `NULL` (which may be `0` or `(void*)0`).
- **`constexpr`** objects (not functions): `constexpr int N = 16;`.
- **`typeof`** and `typeof_unqual`; **`auto`** type inference for object definitions (`auto x = 1.5;`).
- **Attributes** `[[nodiscard]]`, `[[maybe_unused]]`, `[[deprecated]]`, `[[fallthrough]]`, `[[noreturn]]`,
  `[[unsequenced]]`, `[[reproducible]]`.
- **`#embed`** to include binary files as initializers; `#elifdef`, `#elifndef`, `#warning`, `__has_include`,
  `__has_c_attribute`, `__VA_OPT__`.
- **`<stdckdint.h>`**: `ckd_add(&r, a, b)`, `ckd_sub`, `ckd_mul` return `true` on overflow (checked arithmetic).
- **`_BitInt(N)`** bit-precise integers; binary literals `0b1010`; digit separators `1'000'000`; `u8` character
  constants; `%b` printf conversion; `char8_t`-like `unsigned char` UTF-8 literals.
- **Empty initializer** `= {}` zero-initializes anything (including VLAs).
- Enums with fixed underlying type `enum E : unsigned char { ... };`.
- **K&R function definitions removed**; `int f();` now means `int f(void);` (no parameters), as in C++.
- Two's complement is mandatory for signed integers (overflow is **still UB**).
- `<stdbit.h>` (`stdc_count_ones`, `stdc_leading_zeros`, ...), `memset_explicit`, `strdup`/`strndup` standardized,
  `memccpy`, `timegm`, `unreachable()` macro in `<stddef.h>`.
- Labels before declarations and at end of blocks; storage-class specifiers in compound literals; `= {}` for VLAs.
- Removed: trigraphs, `ATOMIC_VAR_INIT` deprecated, `gets` was already gone in C11.

C2y (in progress, implemented partly with `-std=c2y` in GCC 15/16 and Clang): e.g. the `_Countof` operator (array
element count), `if` declarations, case range expressions, `0o` octal prefix; a `defer` technical specification is
being worked on separately. Treat any C2y feature as non-portable today.

Compiler support: GCC 15+ (`gnu23` default), Clang 18+ (`-std=c23`; most features), MSVC supports C11/C17 (`/std:c17`)
and only some C23 features; check the MSVC docs before using C23 on Windows.

## 1. Mental model

- C is a thin layer over the machine: you manage memory, lifetimes and layout yourself. The standard defines an
  **abstract machine**; anything outside its rules is **undefined behaviour** (UB) and the optimiser assumes it never
  happens.
- Values are copied; arrays decay to pointers to their first element when passed to functions (the size is lost: pass
  a length).
- Strings are NUL-terminated `char` arrays; every string API depends on the terminator being there.
- Compilation units: `.c` files compiled separately, `.h` headers declare; the linker resolves symbols. `static` at file
  scope means "internal linkage".
- The preprocessor is a textual macro system that runs before compilation.
- There is no namespacing, no generics (except `_Generic` and macros), no exceptions, no RAII, no GC.

## 2. Type system

- Integer types: `char` (signedness implementation-defined), `short`, `int`, `long`, `long long`, plus unsigned
  variants; exact sizes from `<stdint.h>`: `int32_t`, `uint8_t`, `size_t` (sizes), `ptrdiff_t`, `intptr_t`.
- **Integer promotions**: operands smaller than `int` are promoted to `int` before arithmetic; **usual arithmetic
  conversions** convert `int` to `unsigned` when mixed: `-1 < 1u` is false.
- Floating: `float`, `double`, `long double`; `_Decimal32/64/128` optional in C23.
- Pointers: `T*`, `void*` (implicit conversion to/from any object pointer in C, not in C++), function pointers.
  `restrict` promises no aliasing.
- Qualifiers: `const`, `volatile` (for memory-mapped I/O, not for threads), `_Atomic`.
- Aggregates: arrays, `struct`, `union`; designated initializers `(struct P){ .x = 1, .y = 2 }`; compound literals;
  flexible array members `struct buf { size_t n; char data[]; };`.
- Variably modified types / VLAs (optional since C11; avoid on stacks with untrusted sizes).
- `_Generic(x, int: f_int, double: f_double)(x)` for type-generic macros.
- Enumerations are integers; C23 allows a fixed underlying type.

## 3. Memory model and ownership

- Storage: automatic (stack), static, thread (`thread_local`), allocated (`malloc`, `calloc`, `realloc`,
  `aligned_alloc`, `free`).
- Ownership is a **convention** you must document: who allocates, who frees, and when. Common conventions: "caller
  frees" with a paired `x_create`/`x_destroy`, out-parameters, arenas (free everything at once).
- `malloc` returns `NULL` on failure; check it. `realloc` may move the block: never write `p = realloc(p, n)` (leaks on
  failure); use a temporary.
- `free(NULL)` is a no-op; after `free(p)`, set `p = NULL` to avoid double free and use-after-free.
- Allocation size overflow: `malloc(n * sizeof *p)` can overflow; use `calloc(n, sizeof *p)` or `ckd_mul`.
- Strict aliasing: accessing an object through an lvalue of an incompatible type is UB (except `char`/`unsigned char`
  access). Type-pun via `memcpy` (or unions, which C permits).
- Alignment: `alignas`, `alignof`, `aligned_alloc(alignment, size)` (size must be a multiple of alignment).
- The C11 memory model (`<stdatomic.h>`) defines data races as UB.
- Cleanup idiom: single exit with `goto cleanup;` labels (common and accepted in C), or GCC/Clang
  `__attribute__((cleanup(fn)))` (non-standard).

## 4. Concurrency

- C11 `<threads.h>`: `thrd_create`, `thrd_join`, `mtx_t`, `cnd_t`, `tss_t`, `call_once` (optional; glibc supports it,
  MSVC added it recently). POSIX `pthread_*` is more widely used; Windows has its own APIs.
- `<stdatomic.h>`: `_Atomic int counter;`, `atomic_fetch_add_explicit(&c, 1, memory_order_relaxed)`,
  `atomic_thread_fence`. Memory orders match C++.
- `volatile` is **not** a synchronization primitive.
- Signal handlers may only touch `volatile sig_atomic_t` or lock-free atomics and call async-signal-safe functions.
- Thread-local storage: `thread_local` keyword (C23) / `_Thread_local` (C11).
- `errno` is thread-local.

## 5. Error handling

- No exceptions. Conventions: return an `int` status (0 success, negative errno), return `NULL` and set `errno`,
  out-parameters for results, or a result struct.
- Check every return value of I/O and allocation (`fopen`, `fread`, `fwrite`, `fclose`, `malloc`, `snprintf`).
  C23 `[[nodiscard]]` helps.
- `errno` must be set to 0 before a call if you check it afterwards for functions like `strtol`.
- Parsing numbers: `strtol`/`strtoull` with `endptr` and `errno == ERANGE` checks; never `atoi` (no error reporting).
- `assert` (from `<assert.h>`) disappears under `NDEBUG`: never put side effects or input validation in it.
- `setjmp`/`longjmp` exist (Lua's error handling uses them) but skip cleanup; avoid in new code.

```c
#include <errno.h>
#include <stdckdint.h>
#include <stdlib.h>
#include <stdio.h>

// Returns 0 on success, an errno value on failure. *out is written only on success.
int parse_count(const char *text, size_t *out) {
    if (text == nullptr || *text == '\0') return EINVAL;
    errno = 0;
    char *end = nullptr;
    unsigned long long v = strtoull(text, &end, 10);
    if (errno == ERANGE) return ERANGE;
    if (*end != '\0') return EINVAL;
    size_t bytes;
    if (ckd_mul(&bytes, (size_t)v, sizeof(double))) return EOVERFLOW; // would overflow an allocation size
    *out = (size_t)v;
    return 0;
}
```

## 6. Toolchain, build and package management

- Compilers: GCC (`gcc -std=c23`), Clang (`clang -std=c23`), MSVC (`cl /std:c17`), TinyCC, `zig cc` (Clang-based,
  easy cross-compiling).
- Warnings: `-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Wformat=2 -Wnull-dereference
  -Werror=implicit-function-declaration -Wvla` (GCC 14 made implicit function declarations and implicit int errors by
  default).
- Build: Make, **CMake** (`project(x LANGUAGES C)`, `set(CMAKE_C_STANDARD 23)`), **Meson**, Ninja, Autotools (legacy).
- Packages: system package managers (apt, brew, MSYS2), **vcpkg**, **Conan**, Meson WrapDB, single-header libraries
  (stb, miniaudio), git submodules.
- Static analysis: `clang --analyze`, `scan-build`, `gcc -fanalyzer`, clang-tidy, cppcheck, Coverity, CodeQL.
- Debugging: gdb, lldb, Visual Studio; valgrind (memcheck, helgrind), rr (record/replay).

## 7. Testing

- Frameworks: **Unity** (ThrowTheSwitch, embedded friendly), **CMocka**, **Criterion**, **Check**, greatest, munit;
  CTest runs any executable that returns non-zero on failure.
- Always run tests under sanitizers: `-fsanitize=address,undefined -fno-omit-frame-pointer -g`; a separate TSan build
  for threaded code; MSan (Clang) for uninitialized reads; valgrind where sanitizers are unavailable.
- Fuzz parsers with libFuzzer (`LLVMFuzzerTestOneInput`) or AFL++; OSS-Fuzz for open source.
- Compile with `-O0 -g` and `-O2` in CI: some UB only shows at higher optimisation.

## 8. Idiomatic patterns

- Opaque types: `typedef struct Parser Parser;` in the header; definition in the `.c` file; `Parser *parser_new(void);
  void parser_free(Parser *);`.
- Pass buffers with lengths: `int f(const uint8_t *data, size_t len);`; use `size_t` for sizes and indices.
- Error-code returns + `goto cleanup` for resource release in reverse order.
- `snprintf` for formatting with bounds; check its return value for truncation (`ret >= size`).
- `static` for internal functions; one header per module with include guards or `#pragma once`.
- `const` correctness on pointer parameters.
- Arena allocators for per-frame / per-request memory in games and servers.
- Tagged unions: `struct Value { enum Kind kind; union { double n; char *s; } as; };` with a `switch` on `kind`
  (how Lua represents values).
- `sizeof *ptr` instead of `sizeof(Type)` to keep allocation sizes in sync.

## 9. Top 30 pitfalls and compiler-error fixes

1. **Buffer overflow with `strcpy`/`strcat`/`sprintf`/`gets`** - no bounds. Fix: `snprintf`, `memcpy` with explicit
   lengths, `strlcpy` where available; `gets` was removed in C11.
2. **Off-by-one for the NUL terminator** - `malloc(strlen(s))` should be `strlen(s) + 1`.
3. **Use after free / double free** - Fix: set pointers to `NULL` after `free`, single ownership, ASan.
4. **Returning a pointer to a local array** - "warning: function returns address of local variable". Fix: caller
   provides the buffer, or allocate.
5. **Uninitialized variables** - UB to read. Fix: initialize (`= {}` in C23), `-Wuninitialized`, MSan.
6. **Signed overflow is UB** - `if (x + 1 < x)` is optimised away. Fix: `ckd_add` (C23) or check before:
   `if (x > INT_MAX - 1)`.
7. **Integer promotion surprises** - `uint8_t a = 200, b = 100; if (a + b > 255)` is true (promoted to `int`);
   `unsigned` vs `int` comparisons. Fix: explicit casts, `-Wsign-compare`.
8. **`realloc` misuse** - `p = realloc(p, n);` leaks `p` on failure. Fix: `void *tmp = realloc(p, n); if (!tmp) {...}
   p = tmp;`.
9. **Array decay and `sizeof`** - `sizeof(arr)` inside a function taking `int arr[]` gives the pointer size. Fix: pass
   the length; C2y `_Countof` only works on real arrays.
10. **Format string bugs** - `printf(user_input)`; mismatched specifiers (`%d` for `size_t`: use `%zu`; `int64_t`: use
    `PRId64`). Fix: `-Wformat=2 -Wformat-security`.
11. **`implicit declaration of function 'X'`** - an error in GCC 14+ and C99+: missing `#include`. Fix: include the
    header (`<string.h>` for `memcpy`, `<stdlib.h>` for `malloc`).
12. **`undefined reference to 'X'`** - missing object file or library (`-lm` for `<math.h>` on Linux, link order matters:
    libraries after objects).
13. **`multiple definition of 'X'`** - a variable defined (not just declared) in a header. Fix: `extern int x;` in the
    header, `int x;` in one `.c`.
14. **C23 keyword clashes** after GCC 15 default change - "expected identifier before 'bool'" in old code that
    `typedef int bool;` or names a variable `nullptr`/`typeof`. Fix: remove the typedef, rename, or build with
    `-std=gnu17` while migrating.
15. **Unprototyped `int f();`** now means no parameters in C23: calls with arguments fail ("too many arguments to
    function"). Fix: write real prototypes.
16. **Strict aliasing violations** - `*(float*)&int_var`. Fix: `memcpy`, unions, or `-fno-strict-aliasing` for
    legacy code.
17. **Misaligned access** - casting a `char*` buffer to `uint32_t*`. Fix: `memcpy` into a local.
18. **Macro pitfalls** - `#define SQ(x) x*x` gives `SQ(a+1) == a+1*a+1`; double evaluation `MAX(i++, j)`. Fix:
    parenthesize everything, use `static inline` functions or `_Generic`.
19. **Missing `break` in `switch`** - fallthrough. Fix: `-Wimplicit-fallthrough`, `[[fallthrough]]` when intended.
20. **`=` vs `==` in conditions** - Fix: `-Wparentheses` (in `-Wall`).
21. **Shift UB** - shifting by >= width or shifting negative values, `1 << 31` with 32-bit `int`. Fix: `1u << 31`,
    range-check shift counts.
22. **Division by zero and `INT_MIN / -1`** - UB. Check first.
23. **`char` signedness** - `char c = 200;` negative on x86; `isalpha(c)` with negative `c` is UB. Fix: cast to
    `unsigned char` before `<ctype.h>` calls.
24. **`strncpy` does not NUL-terminate** when the source is too long. Fix: set the last byte, or use `snprintf`.
25. **`fgets` keeps the newline**; `scanf("%s")` overflows. Fix: `fgets` + `strcspn(buf, "\n")`, width limits
    `%63s`.
26. **Ignoring `fclose`/`fflush` errors** loses write failures (full disk).
27. **Data races on globals** across threads - UB. Fix: mutexes, `_Atomic`.
28. **`volatile` used for thread sync** - wrong; use atomics.
29. **Dangling pointers into a `realloc`'d array** (like iterator invalidation). Fix: store indices, not pointers.
30. **Time-of-check/time-of-use with files** (`access` then `open`). Fix: open with flags (`O_CREAT|O_EXCL`,
    `O_NOFOLLOW`) and check the result.
31. **Integer overflow in size calculations** - `malloc(w * h * 4)` for image buffers from untrusted files. Fix:
    `ckd_mul` and limits.
32. **`#include` guards missing** - "redefinition of struct". Fix: `#pragma once` or guards.

## 10. Performance

- Optimise with `-O2` (default for releases), `-O3`, `-march=native` (local only), LTO (`-flto`), PGO
  (`-fprofile-generate/-use`).
- Profile: `perf`, VTune, Instruments, Tracy, gprof (old), cachegrind.
- Cache-friendly layouts (arrays of structs vs struct of arrays), avoid pointer chasing, arenas and pools instead of
  many `malloc`s, `restrict` to enable vectorisation, `static inline` small functions, branch hints
  (`__builtin_expect`), `memcpy` is usually optimal.
- Avoid repeated `strlen` in loops; prefer length-carrying string structs.
- Benchmark with realistic data; check generated code on Compiler Explorer.

## 11. Security

- C is not memory-safe; memory-safety bugs dominate CVEs. Treat every external input (files, network, save data,
  mods) as hostile; validate lengths before copying.
- Hardening: `-D_FORTIFY_SOURCE=3` (with `-O2`), `-fstack-protector-strong`, `-fstack-clash-protection`,
  `-fcf-protection=full`, `-fPIE -pie`, `-Wl,-z,relro,-z,now,-z,noexecstack`; GCC 14+ `-fhardened` enables a
  recommended set; `-ftrivial-auto-var-init=zero`; `-fsanitize=bounds` in testing.
- Use bounded APIs (`snprintf`, `memcpy` with checked sizes), checked arithmetic (`<stdckdint.h>`), and
  `memset_explicit` (C23) to wipe secrets (plain `memset` may be optimised away).
- Command injection: never `system()`/`popen()` with user text; use `execve`/`posix_spawn` with an argument vector.
- SQL injection: SQLite `sqlite3_prepare_v2` + `sqlite3_bind_text` instead of building SQL with `sprintf`.
- Format string attacks: constant format strings only.
- Follow SEI CERT C and MISRA C (safety-critical); run static analyzers and fuzzers.

## 12. Game-development usage

- Libraries in C: **raylib** (6.0, 2026-04) for simple games, **SDL3** (3.4.x in 2026) for windowing/input/audio/GPU,
  sokol headers, stb_image/stb_truetype, miniaudio, cglm, Chipmunk2D, flecs (ECS in C), GLFW + OpenGL/Vulkan.
- Engines with C cores or C APIs: Lua and Luau embedding APIs are C (`lua_State`, stack-based `lua_push*`,
  `lua_call`/`lua_pcall`, `luaL_ref`); Luau keeps the C API but loads compiled bytecode (`luau_compile` then
  `luau_load`) and provides `luaL_sandbox`/`luaL_sandboxthread` for sandboxing; userdata with destructors via
  `lua_newuserdatadtor` in Luau.
- Handmade-style engines, retro/console homebrew, embedded handhelds, and game-server modules.
- Typical patterns: fixed timestep loop, arenas per frame, entity arrays with free lists, hot-reloadable game DLL.

```c
// Minimal raylib loop (raylib 5/6 API)
#include "raylib.h"
int main(void) {
    InitWindow(800, 450, "demo");
    SetTargetFPS(60);
    Vector2 pos = { 400, 225 };
    while (!WindowShouldClose()) {
        float dt = GetFrameTime();
        if (IsKeyDown(KEY_RIGHT)) pos.x += 200 * dt;
        if (IsKeyDown(KEY_LEFT))  pos.x -= 200 * dt;
        BeginDrawing();
        ClearBackground(RAYWHITE);
        DrawCircleV(pos, 20, MAROON);
        EndDrawing();
    }
    CloseWindow();
    return 0;
}
```

## 13. Cheat sheet: C vs Luau

| Concept | Luau | C |
|---|---|---|
| Variable | `local x = 1` | `int x = 1;` / C23 `auto x = 1;` |
| Constant | `local MAX = 10` | `constexpr int MAX = 10;` (C23), `#define`, `enum` |
| Nil | `nil` | `nullptr` (C23) / `NULL` for pointers; no nil for values |
| Number | `number` (f64) | `int`, `long`, `size_t`, `double`, ... explicit sizes |
| Integer division | `7 // 2 == 3` floored | `7 / 2 == 3` truncated (`-7 / 2 == -3`) |
| Indexing | 1-based tables | 0-based arrays, no bounds check |
| Array | `{1, 2, 3}` | `int a[3] = {1, 2, 3};` or `malloc`'d buffer + length |
| Map | table | none in the standard library: write a hash table or use a library |
| Length | `#t` | track it yourself; `strlen` for strings, `sizeof a / sizeof a[0]` for arrays |
| String | immutable value | `char *` NUL-terminated buffer you manage |
| Concat | `a .. b` | `snprintf(buf, n, "%s%s", a, b)` |
| Format | `string.format` | `printf`/`snprintf` family |
| Function | `local function f(a)` | `int f(int a) { ... }` |
| Closure | captures upvalues | none: function pointer + `void *ctx` |
| Multiple returns | `return a, b` | out-parameters or a returned struct |
| Module | `require` | header + `.c` file, linked |
| Class / OOP | metatables | structs + function pointers (vtables by hand) |
| Error | `error`, `pcall` | return codes, `errno`; `setjmp`/`longjmp` (rare) |
| Coroutine | `coroutine.*` | none in the standard; threads (`thrd_create`) |
| Types | gradual | static, weak (implicit conversions) |
| Generics | `<T>` | `void *`, macros, `_Generic` |
| Iteration | `for i, v in ipairs(t)` | `for (size_t i = 0; i < n; i++)` |
| Equality | `==` | `==` for scalars/pointers; `memcmp`/`strcmp` for contents |
| Memory | GC | manual `malloc`/`free` |
| Truthiness | only `nil`/`false` falsy | `0` and null pointers are false |

## 14. Sources

Standard and compilers:
- https://www.iso.org/standard/82075.html - ISO/IEC 9899:2024 (C23)
- https://en.cppreference.com/w/c/23 - C23 feature list
- https://open-std.org/JTC1/SC22/WG14/www/docs/n3220.pdf - C23 working draft
- https://www.open-std.org/jtc1/sc22/wg14/ - WG14 papers, C2y work
- https://gcc.gnu.org/gcc-15/changes.html - GCC 15 default gnu23, C2y features
- https://gcc.gnu.org/gcc-16/changes.html - GCC 16 C2y additions
- https://gcc.gnu.org/gcc-14/porting_to.html - implicit declarations now errors
- https://clang.llvm.org/c_status.html - Clang C status
- https://learn.microsoft.com/en-us/cpp/build/reference/std-specify-language-standard-version - MSVC C standard flags

Language and UB:
- https://en.cppreference.com/w/c/language/behavior - undefined behaviour
- https://en.cppreference.com/w/c/header/stdckdint - checked arithmetic
- https://en.cppreference.com/w/c/language/conversion - integer promotions and conversions
- https://wiki.sei.cmu.edu/confluence/display/c - SEI CERT C coding standard

Tooling, testing, security:
- https://cmake.org/cmake/help/latest/prop_tgt/C_STANDARD.html - CMake C standard
- https://mesonbuild.com/ - Meson build
- https://www.throwtheswitch.org/unity - Unity test framework
- https://cmocka.org/ - CMocka
- https://clang.llvm.org/docs/AddressSanitizer.html - ASan
- https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html - sanitizer and hardening options
- https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html - hardening guide
- https://www.sqlite.org/c3ref/bind_blob.html - parameter binding
- https://llvm.org/docs/LibFuzzer.html - fuzzing

Game development and embedding:
- https://www.raylib.com/ - raylib
- https://github.com/raysan5/raylib/releases - raylib 6.0 release
- https://wiki.libsdl.org/SDL3/FrontPage - SDL3
- https://www.lua.org/manual/5.4/manual.html#4 - Lua C API
- https://github.com/luau-lang/luau - Luau C API (lua.h, luacode.h)
