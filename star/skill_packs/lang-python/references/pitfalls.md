# Python: errors, fixes and Luau cheat sheet

Condensed from docs/research/languages/python.md (checked 2026-10-13). Bracketed numbers refer to that file's source list.

## 7. Top pitfalls and error-message fixes

| Exact error text (or symptom) | Cause | Fix |
|---|---|---|
| Default list "remembers" earlier calls | Mutable default argument evaluated once at `def` time | Use `def f(x=None): x = [] if x is None else x`, or `field(default_factory=list)` |
| `UnboundLocalError: cannot access local variable 'count' where it is not associated with a value` | Assigning to `count` inside the function made it local | Use `nonlocal count`/`global count`, or pass and return the value |
| `TypeError: 'NoneType' object is not subscriptable` | A function returned `None` (forgot `return`, or used `list.sort()`'s result) | `sorted(x)` returns a new list; `x.sort()` returns `None`. Check `is None` before indexing |
| `AttributeError: 'NoneType' object has no attribute 'group'` | `re.match`/`re.search` found nothing | `m = re.search(...); if m: ...` |
| `TypeError: can only concatenate str (not "int") to str` | `"hp: " + 5` | `f"hp: {5}"` or `str(5)` |
| `IndentationError: unexpected indent` / `TabError: inconsistent use of tabs and spaces in indentation` | Mixed tabs and spaces | Use 4 spaces; `ruff format` |
| `ModuleNotFoundError: No module named 'requests'` | Installed into a different interpreter or venv | `python -m pip install ...` with the same `python`, or `uv add`; check `sys.executable` |
| `ImportError: cannot import name 'X' from partially initialized module 'a' (most likely due to a circular import)` | Two modules import each other at top level | Move the import inside the function, extract the shared code into a third module, or use `if TYPE_CHECKING:` for type-only imports |
| `RuntimeError: dictionary changed size during iteration` | Adding or removing keys while looping over the dict | Iterate over `list(d)` or build a new dict |
| `RecursionError: maximum recursion depth exceeded` | Deep recursion (default limit 1000) | Convert to iteration or an explicit stack; raising `sys.setrecursionlimit` can crash the C stack |
| `RuntimeWarning: coroutine 'f' was never awaited` | Called an `async def` without `await` | `await f()` or `asyncio.create_task(f())`, keeping a reference |
| `RuntimeError: asyncio.run() cannot be called from a running event loop` | Calling `asyncio.run` inside Jupyter or an existing loop | `await main()` directly, or schedule on the running loop |
| `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d` (Windows) | `open()` without `encoding=` used the locale code page (cp1252) before 3.15 | Pass `encoding="utf-8"`; 3.15 makes UTF-8 the default (PEP 686) [3] |
| `TypeError: unhashable type: 'list'` | A list or dict used as a dict key or set member | Use a `tuple`/`frozenset`, or a frozen dataclass |
| `0.1 + 0.2 == 0.30000000000000004` | Binary floating point | `math.isclose`, or `decimal.Decimal` for money, `fractions.Fraction` |
| `is` vs `==` surprises (`SyntaxWarning: "is" with 'int' literal`) | `is` compares identity | Use `==` for values and `is` only for `None`/sentinels |
| Late-binding lambdas: `[lambda: i for i in range(3)]` all return 2 | Closures capture variables, not values | `lambda i=i: i`, or `functools.partial` |
| `SyntaxWarning: 'return' in a 'finally' block` (3.14) | PEP 765: `return`/`break`/`continue` in `finally` swallows exceptions | Move the control flow out of `finally` [1] |
| `ExceptionGroup` escapes a TaskGroup | Child tasks failed | `except* ValueError as eg:` and inspect `eg.exceptions` |

## 11. Cheat sheet vs Luau

| Concept | Luau | Python |
|---|---|---|
| Indexing | 1-based: `t[1]` | 0-based: `xs[0]`; `xs[-1]` is the last element |
| Length | `#t` | `len(xs)` |
| Absent value | `nil` | `None` (compare with `is None`) |
| Falsy values | only `nil` and `false` | `None`, `False`, `0`, `0.0`, `""`, `[]`, `{}`, `set()`, empty containers |
| Not-equal | `~=` | `!=` |
| Logical ops | `and`, `or`, `not` | `and`, `or`, `not` (same short-circuit, value-returning) |
| String concat | `a .. b` | `a + b`, f-string `f"{a}{b}"`, `"".join(parts)` |
| Interpolation | `` `hp {hp}` `` | `f"hp {hp}"` (t-strings `t"..."` return a Template, not a str) |
| Array | `{1, 2, 3}` (table) | `[1, 2, 3]` (list), `(1, 2, 3)` (tuple, immutable) |
| Map | `{a = 1}` / `t["a"]` | `{"a": 1}`, `d["a"]` raises `KeyError`; `d.get("a")` gives `None` |
| Missing key | returns `nil` | `KeyError` (use `.get`, `in`, `defaultdict`) |
| Iterate array | `for i, v in ipairs(t)` | `for i, v in enumerate(xs)` (i starts at 0) |
| Iterate map | `for k, v in pairs(t)` | `for k, v in d.items()` (insertion order) |
| Numeric for | `for i = 1, 10 do` (inclusive) | `for i in range(1, 11):` (end exclusive) |
| Integer division | `a // b` (floor) | `a // b` (floor; `-7 // 2 == -4`) |
| Division | `/` gives a float | `/` always gives a float |
| Numbers | one `number` (double) | `int` (unbounded) and `float` are separate |
| Methods | `function Obj:move(dx)`, call `obj:move(1)` | `def move(self, dx):`, call `obj.move(1)` (`self` is explicit in the def, implicit at the call) |
| Classes | metatable + `__index` | `class Obj:` with `__init__`; `@dataclass` |
| Closures | upvalues | closures; rebind outer names with `nonlocal` |
| Coroutines | `coroutine.wrap`, `task.spawn`, `task.wait` | generators (`yield`) or `async def` + `await` on asyncio; `await asyncio.sleep(s)` is the analogue of `task.wait` |
| Errors | `error(msg)`, `pcall(f)` returns `ok, err` | `raise ValueError(msg)`, `try/except/else/finally` |
| Modules | `local M = {} ... return M`, `require(path)` | each file is a module; `import pkg.mod`, `from x import y` |
| Local by default? | must write `local` | assignment in a function is local by default; module level is global to the module |
| Type annotations | checked by Luau in `--!strict` | ignored at runtime; checked by mypy, pyright or ty |
| Varargs | `...`, `select("#", ...)` | `*args`, `**kwargs` |
| Ternary | `if c then a else b` | `a if c else b` |
| Comments | `--`, `--[[ ]]` | `#`, docstrings `"""..."""` |
