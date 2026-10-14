---
name: lang-c
description: C (C23, ISO/IEC 9899:2024) memory safety, undefined behaviour, common compiler/linker errors, build and test tooling. Use for C code, gcc/clang errors, malloc/free bugs, buffer overflows, C23 features or embedding the Lua/Luau C API.
---
# C (C23)
- C23 is ISO/IEC 9899:2024. GCC 15+ compiles as `-std=gnu23` by default: `bool`, `true`, `false`, `nullptr`, `static_assert`, `typeof`, `constexpr` are keywords, and `int f();` now means no parameters. Old code may need fixes (or `-std=gnu17` while migrating). MSVC supports only parts of C23.
- Undefined behaviour lets the optimiser delete your checks: signed overflow, out-of-bounds, use after free, uninitialized reads, misaligned or wrongly typed access (strict aliasing), shifting by the type width or more, `INT_MIN / -1`.
- Check overflow before it happens: C23 `ckd_add(&r, a, b)` / `ckd_mul` from `<stdckdint.h>` return true on overflow; never write `if (a + b < a)` for signed ints.
- Strings: allocate `strlen(s) + 1`; use `snprintf` and check its return for truncation; never `gets`, `strcpy`, `sprintf` into fixed buffers, or `printf(user_text)`.
- `realloc`: assign to a temporary, check NULL, then replace the pointer. After `free(p)` set `p = NULL`. Document who owns and frees each allocation.
- Arrays decay to pointers in parameters: pass a length (`size_t n`). Use `size_t` for sizes; beware signed/unsigned comparisons and integer promotion.
- "implicit declaration of function" is an error in GCC 14+: include the right header. "undefined reference" is a link error: add the object or library (`-lm`), libraries after objects. "multiple definition": `extern` declaration in the header, one definition in a `.c` file.
- Errors: return status codes (0 = success, errno values); check every `malloc`, `fopen`, `fread`, `fclose`; parse numbers with `strtol`/`strtoull` + `endptr` + `errno`, never `atoi`. Clean up with `goto cleanup` in reverse order.
- Threads: data races are UB; use `<stdatomic.h>` or mutexes, not `volatile`.
- Build with warnings: `-Wall -Wextra -Wpedantic -Wconversion -Wshadow -Wformat=2`; test under `-fsanitize=address,undefined` (plus a separate `-fsanitize=thread` build); fuzz parsers with libFuzzer.
- Release hardening: `-O2 -D_FORTIFY_SOURCE=3 -fstack-protector-strong -fPIE -pie -Wl,-z,relro,-z,now` (`-fhardened` on GCC 14+).
- Injection: SQLite `sqlite3_prepare_v2` + `sqlite3_bind_*`; `execve`/`posix_spawn` with an argv array, never `system()` with user input.
- Lua/Luau embedding is a C API: Luau compiles source with `luau_compile`, loads bytecode with `luau_load`, calls with `lua_pcall`, sandboxes with `luaL_sandbox`.
