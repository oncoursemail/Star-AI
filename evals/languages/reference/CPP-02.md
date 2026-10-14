`makeName(7)` returns a **temporary** `std::string`. `std::string_view` is a non-owning view: it does not own the
characters, it only points at the string's buffer. The temporary is destroyed at the end of the full expression
(the `;`), so `name` is left **dangling**, and reading it is undefined behaviour (garbage or a crash).

Keep an owning `std::string` alive for as long as you use the view, or just store the string:

```cpp
int main() {
    std::string name = makeName(7);   // owns the characters
    std::cout << name << '
';
}
```

Use `std::string_view` for parameters, not for storing results of functions that return by value. Clang warns with
`-Wdangling` / `-Wreturn-stack-address`, and ASan reports `stack-use-after-scope` / `heap-use-after-free`.
