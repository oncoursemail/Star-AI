# C++ (C++23 published, C++26 technically complete) - STAR language research

> Status: checked on 2026-10-13. **C++23** is ISO/IEC 14882:2024. **C++26** was completed technically at the
> March 2026 WG21 meeting (London Croydon) and sent for its final international approval ballot (Herb Sutter's trip
> report); treat ISO publication as pending unless the user says otherwise. **GCC 16** switched its default dialect to
> `-std=gnu++20` and implements C++26 reflection (`-std=c++26 -freflection`) and contracts (GCC 16 changes page).
> Use C++ for engines (Unreal, most AAA in-house engines), high-performance libraries, embedded and anything that must
> interoperate with existing C/C++ code. It gives total control and zero-cost abstractions at the price of undefined
> behaviour (UB) when you break the rules.

## 0. Current version and what changed 2024-2026

- **C++23** (ISO/IEC 14882:2024): `std::expected<T,E>`, `std::print`/`std::println` (`<print>`), `std::mdspan`,
  `std::flat_map`/`flat_set`, `std::generator` (coroutine generator), deducing `this` (explicit object parameter),
  `if consteval`, `auto(x)` decay-copy, multidimensional `operator[]`, `std::to_underlying`, `std::unreachable`,
  ranges additions (`views::zip`, `enumerate`, `chunk`, `slide`, `stride`, `cartesian_product`, `ranges::to`),
  `import std;` / `import std.compat;` standard library modules, `#elifdef`, `size_t` literal suffix `uz`,
  `std::stacktrace`, `std::move_only_function`, `std::byteswap`, `[[assume(expr)]]`.
- **C++26** (the "Fab Four" per the committee convener):
  1. **Static reflection** (P2996): the `^^` reflection operator yields a `std::meta::info`; splicers `[: r :]` turn it
     back into code; `std::meta::members_of`, `identifier_of`, `enumerators_of`, etc.; `template for` (expansion
     statements) to iterate at compile time. Enables enum-to-string, serialization, ORM bindings without macros.
  2. **Less UB**: reading an uninitialized automatic variable is now **erroneous behaviour** (a defined, diagnosable
     wrong value, opt out with `[[indeterminate]]`) instead of UB; **hardened standard library** (bounds checks on
     `operator[]`, `front()`, `back()` for `vector`, `span`, `string`, `string_view`, `optional`, etc. in hardened
     implementations).
  3. **Contracts** (P2900): `pre(cond)` and `post(r: cond)` on function declarations, `contract_assert(cond)`
     statement; evaluation semantics (ignore, observe, enforce, quick-enforce) chosen by the implementation/build.
     Controversial in committee (final poll 114/12/3) but kept.
  4. **`std::execution`** (senders/receivers, P2300): structured async and parallelism; powerful but under-documented.
  Others: `#embed` (from C23), pack indexing `Ts...[0]`, `= delete("reason")`, placeholder `_` variables,
  structured bindings as conditions, `std::inplace_vector`, `std::hive`, `std::simd`, `std::linalg` (BLAS-like),
  `std::text_encoding`, saturation arithmetic (`std::add_sat`), `std::copyable_function`, `std::function_ref`,
  hazard pointers and RCU, `std::submdspan`, debugging (`std::breakpoint`).
- Compilers in 2026: GCC 16 (C++20 default, reflection and contracts behind `-std=c++26 -freflection`), Clang/libc++
  and MSVC implement most of C++23 and a growing part of C++26; check cppreference's compiler support table.
  **Modules**: `import std;` works with recent MSVC, Clang+libc++ and GCC (GCC still calls modules support
  experimental, `-fmodules`); CMake 3.28+ supports named modules with Ninja/VS generators. Headers remain the safe
  default for portable code.
- Next: C++29 cycle started (more memory safety, profiles, less UB).

## 1. Mental model

- Value semantics by default: objects are copied unless you move or reference them. The compiler generates special
  members (copy/move constructor and assignment, destructor) when it can.
- **RAII**: resources (memory, files, locks, sockets) are owned by objects whose destructor releases them;
  destruction is deterministic at scope exit, in reverse order of construction. No GC.
- **Zero-overhead principle**: you do not pay for what you do not use; templates are instantiated per type at compile
  time.
- **Undefined behaviour** is a contract with the optimiser: the compiler assumes UB never happens, so a UB bug can
  delete checks, reorder code, or "time travel". "It works on my machine" proves nothing.
- Translation model: headers are textually included (`#include`); each `.cpp` is a translation unit; the One
  Definition Rule (ODR) must hold across all of them. Modules (C++20) replace this with compiled interfaces.
- Multi-paradigm: procedural, OOP (virtual dispatch), generic (templates, concepts), functional (lambdas, ranges),
  compile-time (`constexpr`, `consteval`, reflection in C++26).

## 2. Type system

- Fundamental types with implementation-defined sizes (`int` is at least 16 bits; use `<cstdint>` `std::int32_t`,
  `std::size_t`). `char` signedness is implementation-defined. Signed overflow is UB; unsigned wraps.
- Implicit conversions and integral promotions (`unsigned` vs `int` comparisons: `-1 < 0u` is false). Brace
  initialization `{}` forbids narrowing: `int x{3.5};` is an error.
- References `T&` (non-null, non-reseatable alias), rvalue references `T&&` (bind to temporaries; enable moves),
  forwarding references `template<class T> void f(T&& x)` with `std::forward<T>(x)`.
- `const` (read-only view), `constexpr` (may be evaluated at compile time), `consteval` (must be), `constinit`
  (static init at compile time).
- Classes: access control, constructors (use member init lists), `explicit` single-arg constructors, `virtual` and
  `override`/`final`, abstract classes (pure virtual), multiple inheritance, `= default` / `= delete`.
- Templates: function/class/variable/alias templates; specialization; SFINAE (old) vs **concepts** (C++20):
  `template<std::integral T> T gcd(T a, T b);`, `requires` clauses, `auto` parameters (abbreviated templates).
- Sum types: `std::variant` + `std::visit` (or `std::get_if`), `std::optional<T>`, `std::expected<T,E>` (C++23),
  `std::any`.
- `auto` and `decltype(auto)` deduction; CTAD (`std::vector v{1,2,3};`); structured bindings `auto [k, v] = pair;`.
- Strongly typed `enum class` (prefer over plain `enum`).
- Value categories: lvalue, xvalue, prvalue; guaranteed copy elision for prvalues (C++17).

## 3. Memory model and ownership

- Storage durations: automatic (stack), static, thread, dynamic (`new`/`delete`, allocators).
- **Do not write `new`/`delete` in application code.** Use:
  - `std::unique_ptr<T>` (sole owner, zero overhead, movable not copyable) via `std::make_unique<T>(args)`.
  - `std::shared_ptr<T>` (ref-counted, atomic counts) via `std::make_shared`; `std::weak_ptr` to break cycles.
  - Containers (`std::vector`, `std::string`, `std::array`) own their elements.
  - Raw pointers and references are **non-owning** observers; `std::span<T>` / `std::string_view` are non-owning views.
- **Rule of zero**: if members manage themselves (smart pointers, containers), declare no special members. **Rule of
  five**: if you write any of destructor, copy ctor, copy assign, move ctor, move assign, consider all five (and
  mark moves `noexcept` so `vector` uses them on reallocation).
- Moves leave the source in a valid but unspecified state (for std types usually empty). `std::move` is only a cast.
- Object lifetime: using an object after its lifetime ended is UB (dangling pointer/reference/iterator/view).
- Iterator invalidation: `vector::push_back` may reallocate and invalidate all iterators, pointers and references;
  `erase` invalidates from the erased point; `unordered_map` rehash invalidates iterators (not references).
- Strict aliasing: accessing an object through an unrelated pointer type is UB; use `std::memcpy` or
  `std::bit_cast` (C++20) for type punning.
- Alignment, `alignas`, placement new, `std::launder` for advanced cases.
- Memory model for threads: C++11 defines happens-before; a data race on a non-atomic is UB.

## 4. Concurrency

- `std::thread` (must be joined or detached; destructor of a joinable thread calls `std::terminate`);
  prefer **`std::jthread`** (C++20, joins automatically, supports `std::stop_token`).
- Mutexes: `std::mutex`, `std::shared_mutex`; lock with `std::scoped_lock lk(m1, m2);` (deadlock-free multi-lock)
  or `std::unique_lock` (for condition variables). Never lock/unlock manually.
- `std::condition_variable` with a predicate: `cv.wait(lk, []{ return ready; });` (handles spurious wakeups).
- `std::atomic<T>` with memory orders (`relaxed`, `acquire`, `release`, `acq_rel`, `seq_cst` default);
  `std::atomic<std::shared_ptr<T>>` (C++20); `std::atomic_ref`.
- Higher level: `std::async` + `std::future` (beware: the future from `std::async` blocks in its destructor),
  `std::latch`, `std::barrier`, `std::counting_semaphore` (C++20), parallel algorithms
  (`std::sort(std::execution::par, ...)`), C++26 `std::execution` senders/receivers.
- Coroutines (C++20): `co_await`, `co_yield`, `co_return`; the standard gives the machinery, libraries give tasks
  (`std::generator` in C++23; cppcoro, folly, Asio, `std::execution` in C++26). Dangling-reference risk: coroutine
  parameters taken by reference may die before the coroutine resumes; take by value.
- Game engines usually use a job system (task graph over a worker pool) rather than raw threads.

## 5. Error handling

- Exceptions: `throw std::runtime_error("...")`, `try { } catch (const std::exception& e) { }`. Catch by const
  reference. Destructors must not throw (they are `noexcept` by default). Mark move ops and swap `noexcept`.
- Exception safety guarantees: basic (no leaks, valid state), strong (commit or rollback), nothrow.
- Many game engines and embedded builds compile with exceptions **off** (`-fno-exceptions`, Unreal does not use
  them): use `std::expected<T, E>` (C++23), `std::optional`, error codes, `std::error_code`.
- `std::expected` monadic ops: `.and_then`, `.transform`, `.or_else`, `.transform_error`.
- Contracts (C++26) for preconditions instead of `assert` macros where supported.
- `[[nodiscard]]` on functions whose result must be checked.
- `std::terminate` on: unhandled exception, exception escaping `noexcept`, joinable `std::thread` destroyed.

```cpp
#include <expected>
#include <string>
#include <charconv>

enum class ParseError { Empty, NotANumber, OutOfRange };

std::expected<int, ParseError> parse_int(std::string_view s) {
    if (s.empty()) return std::unexpected(ParseError::Empty);
    int value{};
    auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), value);
    if (ec == std::errc::result_out_of_range) return std::unexpected(ParseError::OutOfRange);
    if (ec != std::errc{} || ptr != s.data() + s.size()) return std::unexpected(ParseError::NotANumber);
    return value;
}
```

## 6. Toolchain, build and package management

- Compilers: GCC (`g++`), Clang (`clang++`, libc++ or libstdc++), MSVC (`cl`, Visual Studio 2022/2026). Set the
  standard explicitly: `-std=c++23` / `/std:c++latest`.
- Warnings: `-Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror` (GCC/Clang), `/W4 /permissive- /WX` (MSVC).
- **CMake** is the de facto build system (Meson, Bazel, Premake, xmake also used; Unreal uses UnrealBuildTool):
  ```cmake
  cmake_minimum_required(VERSION 3.28)
  project(game LANGUAGES CXX)
  set(CMAKE_CXX_STANDARD 23)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
  set(CMAKE_CXX_EXTENSIONS OFF)
  add_executable(game src/main.cpp)
  target_compile_options(game PRIVATE $<$<CXX_COMPILER_ID:MSVC>:/W4> $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra>)
  find_package(fmt CONFIG REQUIRED)
  target_link_libraries(game PRIVATE fmt::fmt)
  ```
  Modern CMake: targets and `target_*` commands, not global `include_directories`. Presets in `CMakePresets.json`.
  `cmake -S . -B build -G Ninja && cmake --build build && ctest --test-dir build`.
- Package managers: **vcpkg** (manifest `vcpkg.json`, integrates via toolchain file), **Conan 2**, CMake
  `FetchContent`, CPM.cmake. There is no official registry.
- Tooling: clang-tidy (incl. `cppcoreguidelines-*`, `bugprone-*`, `modernize-*`), clang-format, clangd, include-what-
  you-use, ccache/sccache, compile_commands.json (`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).

## 7. Testing

- Frameworks: **GoogleTest** (`TEST(Suite, Name) { EXPECT_EQ(a, b); }`, GoogleMock), **Catch2 v3**
  (`TEST_CASE("...") { REQUIRE(x == 1); SECTION(...) }`), doctest, Boost.Test. Run through CTest
  (`gtest_discover_tests(target)`).
- Sanitizers in CI: `-fsanitize=address,undefined` (ASan + UBSan), `-fsanitize=thread` (TSan, separate build),
  MSan (Clang only), `_GLIBCXX_ASSERTIONS` / `_LIBCPP_HARDENING_MODE` for checked standard library.
- Fuzzing: libFuzzer (`-fsanitize=fuzzer`), AFL++.
- Compile-time tests: `static_assert`, `constexpr` evaluation catches UB at compile time (UB in a constant expression
  is a compile error).
- Benchmarks: Google Benchmark, nanobench.

## 8. Idiomatic patterns

- RAII wrappers for every C resource (`std::unique_ptr<FILE, decltype(&fclose)>`).
- Pass small types by value, large read-only by `const T&`, sinks by value then `std::move`, views as
  `std::string_view` / `std::span<const T>` parameters.
- Return values, not out-params (copy elision, `std::expected`, structured bindings).
- Prefer algorithms and ranges over raw loops: `std::ranges::sort(v)`, `v | std::views::filter(...) |
  std::views::transform(...)`, `std::ranges::to<std::vector>()` (C++23).
- `enum class` + `switch` without `default` to get "unhandled enumerator" warnings.
- PIMPL for ABI stability and compile times; CRTP for static polymorphism; type erasure (`std::function`,
  `std::move_only_function`, `std::function_ref`).
- `std::format`/`std::print` instead of `printf` and iostream chains.
- Strong types (wrappers) for units and ids.
- Follow the C++ Core Guidelines (GSL `not_null`, `narrow`).

## 9. Top 30 pitfalls and compiler-error fixes

1. **Dangling reference/pointer to a local** - returning `const std::string&` to a local or temporary. Fix: return by
   value. (GCC: "warning: reference to local variable returned"; Clang `-Wreturn-stack-address`.)
2. **`std::string_view` / `std::span` to a temporary** - `std::string_view sv = get_string();` dangles at the `;`.
   Fix: keep a `std::string` alive or return `std::string`.
3. **Iterator invalidation** - `for (auto& x : v) if (...) v.push_back(...)` or `erase` in a loop. Fix: erase-remove
   (`std::erase_if(v, pred)` C++20), index loop, or collect then apply.
   ```cpp
   for (auto it = v.begin(); it != v.end(); ++it) if (dead(*it)) v.erase(it); // UB
   std::erase_if(v, dead);                                                   // ok
   ```
4. **Use after move** - reading a moved-from object (valid but unspecified). Fix: do not use, or reassign first.
5. **Signed integer overflow is UB** - loops `for (int i = 0; i < n; i += 2)` overflow; `INT_MAX + 1`. Fix: wider
   types, `std::add_sat` (C++26), checked helpers, `-fsanitize=undefined`.
6. **Uninitialized variables** - UB before C++26, erroneous behaviour in C++26. Fix: always initialize
   (`int x{};`), enable `-Wuninitialized`, `-ftrivial-auto-var-init=zero`.
7. **Out-of-bounds `operator[]`** - unchecked. Fix: `.at()`, `std::span`, hardened library modes, ASan.
8. **Signed/unsigned comparison** - `if (i < v.size())` with negative `i`. Fix: `std::ssize(v)` or
   `std::cmp_less(i, v.size())` (C++20).
9. **Most vexing parse** - `Widget w();` declares a function. Fix: `Widget w;` or `Widget w{};`.
10. **Slicing** - passing a derived object by value as base loses derived parts and virtual behaviour. Fix: pass by
    reference or pointer.
11. **Missing virtual destructor** - deleting a derived object via base pointer is UB. Fix: `virtual ~Base() = default;`.
12. **Calling virtual functions in constructors/destructors** - dispatches to the base version.
13. **`undefined reference to 'X'` (linker)** - function declared but not defined/linked, template defined in a
    `.cpp`, missing `target_link_libraries`, C function without `extern "C"`. Fix: define it, move templates to
    headers, link the library.
14. **`multiple definition of 'X'` / LNK2005** - non-inline function or variable defined in a header included twice.
    Fix: `inline` (C++17 inline variables), or move the definition to one `.cpp`.
15. **Template error walls** - "no matching function for call to"; "required from here". Fix: read the first error
    and the "note: candidate" lines; constrain templates with concepts to get short errors.
16. **`error: use of deleted function`** - copying a `std::unique_ptr` or a class with a non-copyable member. Fix:
    `std::move`, pass by reference, or `shared_ptr` if ownership truly is shared.
17. **`error: 'X' was not declared in this scope` / C2065** - missing `#include` or namespace (`std::`). Do not rely
    on transitive includes.
18. **`incomplete type` errors** - using a forward-declared class's members, or `unique_ptr<Impl>` destructor in a
    header. Fix: include the definition; define the destructor in the `.cpp` for PIMPL.
19. **`cannot bind non-const lvalue reference to an rvalue`** - passing a temporary to `T&`. Fix: `const T&` or
    `T&&` or by value.
20. **Static initialization order fiasco** - a global in one TU uses a global from another before it is built. Fix:
    function-local static (Meyers singleton), `constinit`, or no globals.
21. **ODR violations** - two different definitions of the same inline function/class (different macros or flags per
    TU). Silent UB. Fix: consistent flags, unique names in anonymous namespaces.
22. **Data race** - two threads touching a non-atomic, one writing. UB. Fix: mutex/atomic; TSan.
23. **Deadlock from lock order** - fix with `std::scoped_lock(m1, m2)`.
24. **`std::thread` destructor terminates** - forgot `join()`. Fix: `std::jthread`.
25. **Lambda capturing `this` or locals by reference** that outlive the scope (callbacks, threads, coroutines). Fix:
    capture by value, `[self = shared_from_this()]`, or `[*this]`.
26. **`std::vector<bool>`** is a bitset proxy, not a container of `bool`; `auto& b = v[0]` fails. Use
    `std::vector<char>` or `std::bitset`.
27. **`std::shared_ptr` cycles** leak. Fix: `std::weak_ptr` for back-references.
28. **`auto` deduces a copy** - `for (auto x : big_vector)` copies each element. Fix: `const auto&`.
29. **Exceptions across C boundaries or engine callbacks** - terminate or UB. Fix: catch at the boundary,
    `noexcept` callbacks.
30. **Integer division and `%` with negatives** truncate toward zero (`-7 / 2 == -3`, `-7 % 2 == -1`) unlike Luau's
    floored `//` and `%`.
31. **`#include <bits/stdc++.h>` / `using namespace std;` in headers** - non-portable, name clashes.
32. **`std::endl` in hot loops** flushes every line; use `'\n'`.

## 10. Performance

- Build Release with optimisation (`-O2`/`-O3`, `/O2`), LTO (`-flto`), PGO for large apps; measure with perf, VTune,
  Tracy, Superluminal, Visual Studio profiler, `-ftime-trace` for compile time.
- Data-oriented design: contiguous arrays, struct-of-arrays, avoid pointer chasing and `std::list`;
  `std::vector::reserve`; `std::flat_map` (C++23) for small maps.
- Avoid unnecessary copies (`const&`, moves, `std::string_view`), allocations in hot loops (arenas,
  `std::pmr::monotonic_buffer_resource`), virtual calls in tight loops (devirtualize, `final`), exceptions on hot paths.
- `constexpr` to move work to compile time; `[[likely]]`/`[[unlikely]]`; SIMD (`std::simd` C++26, intrinsics).
- False sharing: pad per-thread data to `std::hardware_destructive_interference_size`.
- `std::unordered_map` is node-based and slow-ish; use open-addressing maps (`absl::flat_hash_map`,
  `ankerl::unordered_dense`) for hot paths.
- Compile times: forward declarations, PIMPL, precompiled headers, modules, unity builds, ccache.

## 11. Security

- Memory-safety bugs (buffer overflow, use-after-free, double free, type confusion) are the majority of C++ CVEs.
  Mitigate: smart pointers and containers, `std::span`, bounds-checked hardened library (C++26 standardizes it;
  enable libc++ `_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST`, libstdc++ `_GLIBCXX_ASSERTIONS`, MSVC
  `_ITERATOR_DEBUG_LEVEL` in debug / `/sdl`), sanitizers and fuzzing in CI.
- Hardening flags: `-D_FORTIFY_SOURCE=3 -fstack-protector-strong -fstack-clash-protection -fcf-protection=full -fPIE
  -pie -Wl,-z,relro,-z,now` (GCC 14+ also offers `-fhardened`), MSVC `/GS /guard:cf /DYNAMICBASE /CETCOMPAT`.
- UB-sensitive checks: never test overflow after the fact (`if (a + b < a)` for signed ints is optimised away);
  use `__builtin_add_overflow` or `ckd_add` (C23 `<stdckdint.h>`, available in C++ via compilers).
- Format strings: `std::format` checks at compile time; never pass user input as a `printf` format.
- Injection: SQL via prepared statements (`sqlite3_prepare_v2` + `sqlite3_bind_*`), never string concatenation;
  avoid `system()` and `popen()` with user data (use `posix_spawn`/`CreateProcess` with argument arrays).
- Deserialization: validate lengths before `memcpy`; treat network/save-file data as hostile (save files are a
  classic game exploit vector).
- Supply chain: pin vcpkg baselines / Conan lockfiles, verify hashes, review CMake `FetchContent` URLs.
- Governments (CISA/NSA) recommend memory-safe languages for new code; C++26 profiles/hardening are the committee's
  response. Be honest: C++ is not memory-safe by default.

## 12. Game-development usage

- **Unreal Engine 5** gameplay code is C++ with the reflection macros `UCLASS()`, `UPROPERTY()`, `UFUNCTION()`,
  `GENERATED_BODY()`; garbage-collected `UObject`s (raw `UObject*` members must be `UPROPERTY()` or `TObjectPtr`
  to be tracked), `TArray`/`TMap`/`FString`, no exceptions, Unreal Build Tool (`*.Build.cs`), Live Coding. Blueprints
  call `BlueprintCallable` functions. Use `TWeakObjectPtr` for non-owning references to actors.
- In-house engines (id Tech, Frostbite, Decima, Source 2), Godot's core (Godot 4 GDExtension in C++ via godot-cpp),
  O3DE, Cocos2d-x/Axmol, raylib (C API), SDL3, Dear ImGui (debug UI), EnTT/flecs (ECS), Box2D/Jolt/PhysX (physics),
  bgfx/Diligent/Vulkan/D3D12/Metal.
- **Luau** itself is written in C++ (Roblox's open source VM, compiler and analyzer: `luau-lang/luau`). Embedding:
  `lua_State* L = luaL_newstate(); luaL_openlibs(L);` then compile with `luau_compile` and load bytecode with
  `luau_load`, call with `lua_pcall`; sandbox with `luaL_sandbox`. sol2 binds standard Lua; Luau's API differs (no
  `luaL_loadstring` of source; you compile first).
- Typical engine patterns: fixed-timestep loop, job systems, frame allocators, handles instead of pointers,
  hot-reload of game DLLs, ECS.

## 13. Cheat sheet: C++ vs Luau

| Concept | Luau | C++ |
|---|---|---|
| Variable | `local x = 1` | `int x = 1;` / `auto x = 1;` / `const auto x = 1;` |
| Nil | `nil` | `nullptr` (pointers), `std::optional<T>` (`std::nullopt`) |
| Number | `number` (f64) | `int`, `std::int64_t`, `float`, `double`, sizes vary |
| Integer division | `7 // 2 == 3`, floors | `7 / 2 == 3`, truncates toward zero (`-7 / 2 == -3`) |
| Modulo | `-7 % 2 == 1` | `-7 % 2 == -1` |
| Indexing | 1-based | 0-based; `v[i]` unchecked, `v.at(i)` throws |
| Array | `{1, 2, 3}` | `std::vector<int>{1, 2, 3}`, `std::array<int, 3>` |
| Map | `{a = 1}` | `std::unordered_map<std::string, int>`, `std::map` (ordered) |
| Length | `#t` | `v.size()` (unsigned), `std::ssize(v)` |
| String | immutable, `..` | `std::string` mutable, `+`, `std::format("{}{}", a, b)` |
| Function | `local function f(a)` | `int f(int a) { return a; }` |
| Closure | `function() return x end` | `[x]() { return x; }` / `[&x]` by reference |
| Multiple returns | `return a, b` | `return std::pair{a, b};` + `auto [a, b] = f();` |
| Module | `require(...)` | `#include "x.h"` / `import mod;` (C++20 modules) |
| Class | metatable | `class` / `struct` with members, ctors, dtor |
| Method | `obj:M()` | `obj.m()`, `ptr->m()` |
| Inheritance | `setmetatable(Derived, {__index = Base})` | `class D : public B` + `virtual`/`override` |
| Error | `error("x")`, `pcall` | `throw`, `try/catch`; or `std::expected` |
| Coroutine | `coroutine.wrap` | C++20 coroutines (`co_yield`), `std::generator` |
| Threads | single-threaded VM + `task` scheduler | `std::jthread`, mutexes, atomics |
| Types | gradual, optional | static, mandatory, templates + concepts |
| Generic | `<T>` | `template<typename T>` / `auto` params |
| Iteration | `for _, v in t` | `for (const auto& v : container)` |
| Equality | `==` reference for tables | `==` value (operator==), pointers compare addresses |
| Memory | GC | RAII + smart pointers, manual control |
| String format | `string.format("%.2f", x)` | `std::format("{:.2f}", x)`, `std::println` |
| Truthiness | `nil`/`false` falsy | `0`, `nullptr`, `false` convert to false |

## 14. Sources

Standards and status:
- https://herbsutter.com/2026/03/ - C++26 complete, Fab Four, contracts vote
- https://www.iso.org/standard/83626.html - ISO/IEC 14882:2024 (C++23)
- https://en.cppreference.com/w/cpp/23 - C++23 feature list
- https://en.cppreference.com/w/cpp/26 - C++26 feature list
- https://en.cppreference.com/w/cpp/compiler_support - compiler support tables
- https://isocpp.org/std/the-standard - standard status
- https://wg21.link/P2996 - reflection paper
- https://wg21.link/P2900 - contracts paper
- https://wg21.link/P2300 - std::execution paper
- https://wg21.link/P2795 - erroneous behaviour for uninitialized reads
- https://wg21.link/P3471 - standard library hardening
- https://gcc.gnu.org/gcc-16/changes.html - GCC 16: C++20 default, reflection, contracts
- https://gcc.gnu.org/gcc-15/changes.html - GCC 15 changes
- https://clang.llvm.org/cxx_status.html - Clang C++ status
- https://learn.microsoft.com/en-us/cpp/overview/visual-cpp-language-conformance - MSVC conformance

Language, library, guidelines:
- https://en.cppreference.com/w/cpp/language/ub - undefined behaviour
- https://en.cppreference.com/w/cpp/container#Iterator_invalidation - invalidation rules
- https://en.cppreference.com/w/cpp/utility/expected - std::expected
- https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines - Core Guidelines
- https://en.cppreference.com/w/cpp/language/rule_of_three - rule of 3/5/0

Tooling, testing, security:
- https://cmake.org/cmake/help/latest/manual/cmake-cxxmodules.7.html - CMake C++ modules
- https://learn.microsoft.com/en-us/vcpkg/ - vcpkg manifests
- https://docs.conan.io/2/ - Conan 2
- https://google.github.io/googletest/ - GoogleTest
- https://github.com/catchorg/Catch2 - Catch2
- https://clang.llvm.org/docs/AddressSanitizer.html - ASan
- https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html - UBSan
- https://libcxx.llvm.org/Hardening.html - libc++ hardening modes
- https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html - hardening flags
- https://wiki.sei.cmu.edu/confluence/display/cplusplus - SEI CERT C++

Game development:
- https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-with-cplusplus-in-unreal-engine - Unreal C++
- https://github.com/luau-lang/luau - Luau VM in C++, embedding API
- https://github.com/skypjack/entt - EnTT ECS
