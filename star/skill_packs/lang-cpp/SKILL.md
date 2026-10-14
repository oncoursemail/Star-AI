---
name: lang-cpp
description: Modern C++ (C++23; C++26 completed in 2026) RAII, ownership, undefined behaviour, template and linker errors, CMake and testing. Use for C++ code, g++/clang++/MSVC errors, smart pointers, iterator invalidation, Unreal C++ or embedding Luau.
---
# Modern C++ (C++23; C++26 technically complete March 2026)
- Set the standard explicitly (`-std=c++23`, `/std:c++latest`). GCC 16 defaults to `gnu++20`; C++26 reflection needs `-std=c++26 -freflection` on GCC 16. Check compiler support before using C++26 (reflection, contracts `pre`/`post`/`contract_assert`, `std::execution`).
- RAII everywhere: no raw `new`/`delete`. `std::make_unique` for sole ownership; `std::make_shared` plus `std::weak_ptr` for shared ownership and back-references. Raw pointers, references, `std::span` and `std::string_view` never own.
- Rule of zero: let members manage resources. If you write a destructor, consider all five special members and mark moves `noexcept`.
- Dangling is the top bug: never return references or views to locals or temporaries (`std::string_view sv = make_string();` dangles). Lambdas capturing by reference must not outlive the scope.
- Iterator invalidation: `push_back` can invalidate all iterators and references; erasing inside a range-for is UB. Use `std::erase_if(v, pred)` (C++20).
- UB the optimiser exploits: signed overflow, out-of-bounds `[]`, reading moved-from or uninitialized values (erroneous behaviour in C++26), data races, strict aliasing (use `std::bit_cast` or `memcpy`).
- Errors: exceptions (catch by `const&`), or `std::expected<T, E>` (C++23) where exceptions are off (Unreal, many games). Mark must-check results `[[nodiscard]]`.
- Threads: `std::jthread` (joins itself), `std::scoped_lock(m1, m2)`, `std::atomic`; condition variables with a predicate.
- Errors decoded: "undefined reference" / LNK2019 = missing definition or library, or a template defined in a `.cpp`; "multiple definition" / LNK2005 = non-`inline` definition in a header; "use of deleted function" = copying a move-only type (use `std::move` or references); template walls: read the first error and the candidate notes, constrain with concepts.
- Integer differences from Luau: `/` truncates toward zero and `%` keeps the sign (`-7 / 2 == -3`).
- Build: CMake targets (`target_link_libraries`, `CMAKE_CXX_STANDARD 23`), vcpkg or Conan; warnings `-Wall -Wextra -Wpedantic -Wconversion`; GoogleTest or Catch2 via CTest; CI with `-fsanitize=address,undefined` and a TSan build; hardened library modes (`_GLIBCXX_ASSERTIONS`, libc++ hardening).
- Security: `std::format` instead of `printf(user)`, prepared statements for SQL, argv-based process spawning, validate lengths in untrusted save and network data.
- Unreal: `UPROPERTY()` on `UObject*` members (or `TObjectPtr`) so the GC tracks them; no exceptions; `TWeakObjectPtr` for non-owning actor references.
