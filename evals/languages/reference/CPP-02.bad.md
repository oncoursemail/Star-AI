`std::string_view` copies the characters when you construct it, so this is fine. The garbage comes from `std::cout`
buffering; add `std::flush` after the print.
