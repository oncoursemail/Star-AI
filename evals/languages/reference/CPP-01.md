`erase` shifts the later elements and **invalidates** iterators and references at and after the erased position, and
the range-based `for` keeps using its hidden iterator (and your `e` reference) after the erase. Using an invalidated
iterator is **undefined behaviour**, which is why the crash is random.

Since C++20 the idiomatic fix is `std::erase_if`, which does the erase-remove idiom in one call:

```cpp
#include <vector>

std::erase_if(enemies, [](const Enemy& e) { return e.hp <= 0; });
```

On older standards: `enemies.erase(std::remove_if(enemies.begin(), enemies.end(), pred), enemies.end());`.
