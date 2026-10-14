A function template is not a function until it is **instantiated**. The compiler instantiates `clampAdd<int>` in
`main.cpp`, where it is called, but there it only sees the declaration from `math.h`, so it emits a reference to a
symbol that no translation unit defines. `math.cpp` has the definition but never uses `clampAdd<int>`, so nothing is
generated there. The linker then reports `undefined reference` / LNK2019.

Fix: move (define) the template in the header so every user can instantiate it:

```cpp
// math.h
#pragma once
template <typename T>
T clampAdd(T a, T b) { return a + b > T{100} ? T{100} : a + b; }
```

Alternative when you want to keep the body in `math.cpp`: add an explicit instantiation there for each type you need,
`template int clampAdd<int>(int, int);`.
