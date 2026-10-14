The crash is caused by `std::find` being slow. It is safe to erase inside a range-based for loop as long as you break
afterwards, so add a `break;` after the erase and the crash goes away.
