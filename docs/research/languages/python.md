# Python for STAR (research, checked 2026-10-13)

Status: **Python 3.15.0 was released on 2026-10-09**, the 3.14 line is at 3.14.8 (bugfix), and 3.13 is at 3.13.16 (security-only per python.org) [1][2][3]. For "Python 3.13-3.14" questions assume 3.14 as the default target. 3.15 features are listed separately (section 12) because many users and libraries will not be on it yet. Unverified as of 2026-10-13: the exact state of uv/Ruff version numbers (they release weekly), and whether `ty` has left beta (last seen release: 0.0.78, 2026-09-02) [16].

## 1. Mental model

- Everything is an object. A name is a reference bound in a namespace (module, function, class), and assignment never copies. `a = b` gives two names for one object. Mutation through one name is visible through the other. This is the root cause of most "my list changed by itself" bugs.
- Scopes follow LEGB: Local, Enclosing function, Global (module), Builtins. Assigning to a name anywhere in a function makes it local for the whole function (hence `UnboundLocalError`). Use `nonlocal` and `global` to rebind outer names.
- Code runs top to bottom when a module is imported. Imports are cached in `sys.modules`, so a module body runs once per process. `if __name__ == "__main__":` guards script-only code. This guard is mandatory with `multiprocessing` on spawn/forkserver platforms (Windows, macOS, and since 3.14 the Linux default is forkserver) [1].
- Indentation is syntax. Blocks have no `end`. There is no block scope: a variable bound inside `if` or `for` is visible after it in the same function.
- Dunder protocols drive the language. `len(x)` calls `x.__len__`, `for` calls `__iter__`/`__next__`, `with` calls `__enter__`/`__exit__`, `a + b` calls `__add__` then `__radd__`. Luau metatables (`__index`, `__add`, `__call`) map onto these.
- Duck typing at runtime, gradual static typing through annotations checked by external tools (mypy, pyright, ty). The interpreter **never enforces annotations**.
- CPython, the reference implementation, is a bytecode VM with reference counting plus a cyclic GC. The classic build has a Global Interpreter Lock (GIL). The free-threaded build (`python3.14t`) removes it (section 3).

## 2. Type system

Dynamic and strong: `"1" + 1` raises `TypeError`, with no implicit coercion apart from numeric widening (`int` to `float` to `complex`) and truthiness.

Core types: `int` (arbitrary precision, never overflows), `float` (IEEE-754 double), `complex`, `bool` (a subclass of `int`: `True + True == 2`), `str` (immutable Unicode code points), `bytes`/`bytearray`, `list`, `tuple`, `dict` (insertion-ordered since 3.7), `set`/`frozenset`, `None`. Python 3.15 adds the built-in `frozendict` (PEP 814) [3].

Static typing (annotations):

```python
from collections.abc import Callable, Iterable, Sequence
from typing import Protocol, TypedDict, Literal, Self, override, TypeIs, ReadOnly

# PEP 695 (3.12+) generic syntax: no TypeVar boilerplate
def first[T](items: Sequence[T]) -> T | None:
    return items[0] if items else None

class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []
    def push(self, item: T) -> Self:
        self._items.append(item)
        return self

type Vec2 = tuple[float, float]          # PEP 695 type alias statement (lazily evaluated)
class HasHp(Protocol):                   # structural typing, like a Luau table type
    hp: int

class Save(TypedDict):
    version: int
    coins: ReadOnly[int]                 # PEP 705 (3.13)

def is_str(x: object) -> TypeIs[str]:    # PEP 742 (3.13) narrowing in both branches
    return isinstance(x, str)

class Base:
    def tick(self, dt: float) -> None: ...
class Enemy(Base):
    @override                            # PEP 698: the checker errors if Base has no tick
    def tick(self, dt: float) -> None: ...
```

- Type parameter defaults (PEP 696, 3.13): `class Box[T = int]: ...`.
- `@warnings.deprecated` (PEP 702, 3.13) is seen by type checkers and also warns at runtime.
- **Deferred annotations (PEPs 649 and 749, 3.14):** annotations are no longer evaluated at definition time. They are stored as an `__annotate__` function and evaluated on demand. Forward references work without quotes or `from __future__ import annotations`. Read annotations with `annotationlib.get_annotations(obj, format=Format.VALUE | FORWARDREF | STRING)` rather than poking `__annotations__` directly [1]. Libraries that introspect annotations at runtime (pydantic, dataclasses, FastAPI) handle this on current versions. Older pinned versions may not.
- 3.15 typing additions: PEP 728 (`TypedDict` extra items via `closed=True`/`extra_items=`), PEP 747 `TypeForm`, PEP 800 disjoint bases [3].
- Use `X | None`, not `Optional[X]`, and built-in generics (`list[int]`, `dict[str, int]`), not `typing.List`. Import ABCs from `collections.abc`.

## 3. Runtime, concurrency and async model

**GIL build:** only one thread executes Python bytecode at a time. Threads still help for I/O (the GIL is released during blocking I/O and in many C extensions such as NumPy). CPU-bound parallel work needs `multiprocessing`, `concurrent.futures.ProcessPoolExecutor`, subinterpreters, or the free-threaded build.

**Free-threaded build (PEP 703, PEP 779):** experimental in 3.13, **officially supported (phase II) in 3.14** but still not the default [1]. The executable is `python3.14t`. On Windows, choose the free-threaded option in the installer or install manager. Check it with `sys._is_gil_enabled()` and `sysconfig.get_config_var("Py_GIL_DISABLED")`. Importing a C extension that is not marked free-threading-safe re-enables the GIL with a warning (force it off with `PYTHON_GIL=0`/`-X gil=0`). Single-threaded code is a few percent slower (the 3.14 docs quote about 5 to 10 percent) [1]. Built-in `dict`/`list` operations are internally locked, but compound operations (check-then-set) still race, so use `threading.Lock`. 3.15 adds a stable ABI for free-threaded builds (`abi3t`, PEP 803) [3].

**Subinterpreters (PEP 734, 3.14):** `concurrent.interpreters` and `concurrent.futures.InterpreterPoolExecutor` give isolated interpreters, each with its own GIL, in one process. They share data via `Queue` or by pickling.

**asyncio:** single-threaded cooperative concurrency on an event loop. `async def` creates a coroutine function, and calling it returns a coroutine object that does nothing until awaited or scheduled.

```python
import asyncio

async def fetch(i: int) -> int:
    await asyncio.sleep(0.1)          # never time.sleep() inside async code
    return i * 2

async def main() -> None:
    async with asyncio.timeout(2):    # 3.11+
        async with asyncio.TaskGroup() as tg:     # 3.11+ structured concurrency
            tasks = [tg.create_task(fetch(i)) for i in range(5)]
    print([t.result() for t in tasks])            # one failure cancels siblings, raises ExceptionGroup

asyncio.run(main())
```

- Prefer `TaskGroup` over bare `asyncio.gather`/`create_task`. A task created with `create_task` and not referenced can be garbage-collected mid-flight. Keep a reference, or use a TaskGroup.
- Blocking calls freeze the whole loop. Wrap them with `await asyncio.to_thread(fn, *args)`.
- `except*` handles `ExceptionGroup` (3.11+).
- 3.14 adds introspection: `python -m asyncio ps <pid>` and `python -m asyncio pstree <pid>` show running tasks [1].
- 3.14 deprecates `asyncio.get_event_loop()` implicitly creating a loop (it now raises if none). Use `asyncio.run` or `asyncio.Runner`.

Generators (`yield`) are the closest analogue to Luau coroutines: a generator suspends at `yield` and resumes on `next()`/`send()`. They are stackful only one frame deep. `yield from` delegates.

**Memory:** reference counting frees most objects immediately. Cycles are collected by the generational GC (incremental GC work landed in 3.14 [1]). `__del__` timing is not guaranteed, so use context managers for resources.

**JIT:** an experimental copy-and-patch JIT exists since 3.13. The official 3.14 Windows and macOS binaries include it, off by default, enabled with `PYTHON_JIT=1` [1]. Do not promise speedups from it. Measure.

## 4. Tooling and package management

| Need | Current default (2026) | Notes |
|---|---|---|
| Install Python on Windows | **Python install manager** (`py install 3.14`, `py list`) | New in 3.14, from the Microsoft Store or python.org. It replaces the old `py.exe` launcher plus installer [1] |
| Projects, venvs, lockfiles | **uv** (`uv init`, `uv add`, `uv run`, `uv sync`, `uv lock`) | Rust, very fast, manages Python versions too (`uv python install 3.14`). Writes `uv.lock` |
| Alternatives | pip + venv (stdlib), Poetry, PDM, Hatch | `python -m venv .venv` then `.venv\Scripts\activate` on Windows |
| One-off tools | `uvx ruff`, `pipx run` | |
| Inline script deps | PEP 723 `# /// script` block, run with `uv run script.py` | |
| Lint + format | **Ruff** (`ruff check --fix`, `ruff format`) | Replaces flake8, isort, black, pyupgrade |
| Type check | **mypy** (reference), **pyright**/basedpyright (fast, VS Code Pylance), **ty** (Astral, beta) | Pick one per project and run it in CI |
| Build backend | hatchling, setuptools (>=61 with `pyproject.toml`), uv_build, flit-core, maturin (Rust), scikit-build-core (C++) | |
| Project metadata | `pyproject.toml` (`[project]`, PEP 621) | `setup.py` is legacy |
| Lockfile standard | `pylock.toml` (PEP 751, accepted 2025) | pip and uv can export it |

```toml
[project]
name = "game-tools"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["httpx>=0.27"]

[dependency-groups]          # PEP 735
dev = ["pytest>=8", "ruff", "mypy"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.mypy]
strict = true
```

## 5. Testing

- **pytest** is the de facto standard: plain `assert` with introspected failure messages, fixtures, `@pytest.mark.parametrize`, `tmp_path`, `monkeypatch`, `capsys`. Use `pytest -q`, `-x` (stop on first failure), `-k name`, `--lf` (last failed).
- `unittest` is in the stdlib (xUnit style). `unittest.mock` provides `patch`, `MagicMock`, `AsyncMock`.
- Async tests: `pytest-asyncio` or `anyio`'s pytest plugin.
- Property-based testing: Hypothesis. Coverage: `coverage run -m pytest` or `pytest-cov`. Doctests: `python -m doctest`.

```python
import pytest
from game.combat import damage

@pytest.mark.parametrize(("atk", "arm", "want"), [(10, 0, 10), (10, 5, 5), (3, 9, 1)])
def test_damage_floors_at_one(atk: int, arm: int, want: int) -> None:
    assert damage(atk, arm) == want

def test_negative_attack_rejected() -> None:
    with pytest.raises(ValueError, match="attack"):
        damage(-1, 0)
```

## 6. Idiomatic patterns

```python
from dataclasses import dataclass, field
from pathlib import Path
from enum import StrEnum
import json, logging

log = logging.getLogger(__name__)

class Team(StrEnum):
    RED = "red"
    BLUE = "blue"

@dataclass(slots=True)                    # frozen=True for value objects
class Player:
    name: str
    team: Team
    hp: int = 100
    items: list[str] = field(default_factory=list)   # never `items: list = []`

def load_players(path: Path) -> list[Player]:
    with path.open(encoding="utf-8") as f:            # always pass encoding (pre-3.15)
        raw = json.load(f)
    return [Player(p["name"], Team(p["team"])) for p in raw]

# EAFP: try it, handle the specific failure
def get_hp(stats: dict[str, int], key: str) -> int:
    try:
        return stats[key]
    except KeyError:
        return 0            # or stats.get(key, 0)

# Structural pattern matching (3.10+)
def handle(msg: dict) -> str:
    match msg:
        case {"type": "move", "x": int(x), "y": int(y)}:
            return f"move {x},{y}"
        case {"type": "chat", "text": str(text)} if text:
            return text
        case _:
            raise ValueError(f"bad message: {msg!r}")

# enumerate/zip instead of index arithmetic
for i, (name, score) in enumerate(zip(names, scores, strict=True), start=1):
    print(f"{i}. {name}: {score:,}")

# Comprehensions and generator expressions
alive = [p for p in players if p.hp > 0]
total = sum(p.hp for p in players)            # no intermediate list
by_team = {t: [p for p in players if p.team is t] for t in Team}
```

- Context managers for every resource (`with open(...)`, `with lock:`). Write your own with `contextlib.contextmanager`.
- `pathlib.Path` over `os.path` string juggling.
- f-strings: `f"{value=}"` for debugging, `f"{x:.2f}"`. Since 3.12 f-strings can nest the same quotes.
- **t-strings (PEP 750, 3.14):** `t"Hello {name}"` evaluates to a `string.templatelib.Template` (strings and `Interpolation` objects), **not a `str`**. They exist so libraries can escape values safely (SQL, HTML, shell). Never pass a Template where a `str` is expected. Process it with a function that walks `template.strings` and `template.interpolations` [1][7].
- Logging with `logging.getLogger(__name__)` and lazy `%s` arguments, not `print`, in libraries.
- `functools.cache`/`lru_cache` for memoising pure functions. `itertools` (`batched` 3.12+, `pairwise`, `chain`, `groupby` needs pre-sorted input).
- `except A, B:` without parentheses is allowed again in 3.14 (PEP 758), but only without `as`. Keep the parentheses for code that must run on 3.13 [1].

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

## 8. Performance

- Measure first: `python -m cProfile -o out.prof script.py` plus snakeviz, `py-spy` (sampling, no code change), `timeit`, `tracemalloc` for memory. 3.15 adds the `profiling.sampling` (Tachyon) and `profiling.tracing` modules (PEP 799) [3].
- Use the right container: `set`/`dict` for membership (O(1)) over list scans; `collections.deque` for queues (`list.pop(0)` is O(n)); `heapq` for priority queues; `bisect` for sorted inserts.
- Build strings with `"".join(parts)`, not `+=` in a loop.
- Local variable lookups are faster than global or attribute lookups in hot loops. Comprehensions beat explicit `append` loops. Built-ins (`sum`, `min`, `sorted` with `key=`) run in C.
- Use `__slots__` (`@dataclass(slots=True)`) for many small objects: less memory, faster attribute access.
- Numeric work belongs in NumPy (vectorise, avoid Python-level loops), or in Numba, Cython, mypyc, or a Rust extension through PyO3/maturin.
- CPU parallelism: processes, subinterpreters, or the free-threaded build. More threads on the GIL build make CPU-bound code slower, not faster.
- The 3.11+ specialising adaptive interpreter makes plain Python much faster than 3.10. Upgrading is often the cheapest optimisation.

## 9. Security

- **Never** `eval`/`exec` untrusted input. `ast.literal_eval` parses literals only.
- **Never** `pickle.load`/`shelve`/`marshal` untrusted data, because unpickling runs arbitrary code. Use JSON or msgpack. `yaml.load` without `SafeLoader` is also unsafe, so use `yaml.safe_load`.
- `subprocess.run([...], check=True)` with an argument list. Avoid `shell=True` with interpolated strings (command injection). `shlex.quote` covers POSIX shells only.
- SQL: use parameterised queries (`cur.execute("... WHERE id = ?", (uid,))`), never f-strings. t-strings let libraries build safe queries, but only when the library supports Templates.
- Paths: resolve and check containment (`p.resolve().is_relative_to(base)`) before serving user-supplied paths. `tarfile.extractall` should use `filter="data"` (the default since 3.14) to block path traversal [1].
- Secrets: the `secrets` module (`token_urlsafe`) for tokens, never `random`. Use `hmac.compare_digest` for constant-time comparison.
- Supply chain: pin with lockfiles (`uv.lock`), check with `pip-audit`, beware typosquatting. Do not `pip install` as admin into the system Python.
- `xml.etree` is vulnerable to some entity attacks, so use `defusedxml` for untrusted XML.
- `requests`/`httpx`: always set `timeout=`, and keep `verify=True`.

## 10. Game-dev usage

- **Pygame-ce** (community fork of pygame, recommended for new projects), **Arcade** (OpenGL-based, typed API), **Pyglet**, **Ursina** (3D, on Panda3D), **Panda3D** (full 3D engine with C++ core), **Ren'Py** (visual novels), **Godot** via the GDScript-like syntax (not Python) or godot-python bindings.
- **Blender** scripting uses the embedded Python `bpy` API (Blender 4.x/5.x bundles Python 3.11 or newer). It is the main Python use next to Roblox workflows: batch export FBX/glTF, procedural meshes, rigging tools.
- Tooling around games: asset pipelines, build scripts, level-data converters, server backends (FastAPI/aiohttp), analytics with pandas or Polars, ML for NPCs and procedural content.
- A fixed-timestep loop in pygame-ce:

```python
import pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()
STEP = 1 / 60
acc = 0.0
running = True
while running:
    acc += clock.tick(144) / 1000            # ms to seconds, cap 144 fps
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
    while acc >= STEP:                       # deterministic physics
        world.update(STEP)
        acc -= STEP
    world.draw(screen)
    pygame.display.flip()
pygame.quit()
```

- Python is too slow for per-object inner loops at thousands of entities per frame unless the work is vectorised (NumPy) or in C. Keep hot paths in the engine.

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

## 12. Recent changes and version notes

- **3.13 (Oct 2024):** new interactive REPL (colour, multiline editing), experimental free-threaded build and JIT, PEP 667 defined `locals()` semantics, removal of the "dead batteries" (PEP 594: `cgi`, `crypt`, `telnetlib`, `imghdr`, `audioop` and others), `copy.replace`, typing additions (PEP 696, 702, 705, 742), iOS and Android tier-3 support [4].
- **3.14 (Oct 2025):** deferred annotations plus `annotationlib` (PEP 649/749), template strings (PEP 750), `concurrent.interpreters` (PEP 734), free-threading officially supported (PEP 779), `compression.zstd` (PEP 784), `except` without parentheses (PEP 758), warnings for control flow in `finally` (PEP 765), safe external debugger interface `sys.remote_exec` (PEP 768), asyncio introspection CLI, Python install manager for Windows, colour in the REPL and in `unittest`/`argparse`/`json` output, the `forkserver` default start method on Linux, and the JIT in the official Windows and macOS binaries (off by default) [1].
- **3.15 (2026-10-09):** explicit lazy imports `lazy import json` (PEP 810; module scope only, errors surface at first use), the `frozendict` built-in (PEP 814), the `sentinel` built-in (PEP 661), unpacking in comprehensions `[*xs for xs in lists]` (PEP 798), UTF-8 as the default encoding (PEP 686; set `PYTHONUTF8=0` for the old behaviour), the `profiling` package with the Tachyon sampling profiler (PEP 799), frame pointers on by default (PEP 831), the `abi3t` stable ABI for free-threaded builds, the `math.integer` module, and `re.prefixmatch` with `re.match` soft-deprecated [3].
- Support windows: each minor version gets about 2 years of bugfixes and then security fixes up to 5 years after release (PEP 602). 3.9 reached end of life in October 2025 [2].

## Sources

1. What's New In Python 3.14: https://docs.python.org/3/whatsnew/3.14.html
2. Python downloads and release status: https://www.python.org/downloads/
3. What's New In Python 3.15: https://docs.python.org/3.15/whatsnew/3.15.html
4. What's New In Python 3.13: https://docs.python.org/3/whatsnew/3.13.html
5. PEP 790, Python 3.15 release schedule: https://peps.python.org/pep-0790/
6. PEP 695, type parameter syntax: https://peps.python.org/pep-0695/
7. PEP 750, template strings: https://peps.python.org/pep-0750/
8. PEP 649, deferred evaluation of annotations: https://peps.python.org/pep-0649/
9. PEP 703, making the GIL optional: https://peps.python.org/pep-0703/
10. Python free-threading HOWTO: https://docs.python.org/3/howto/free-threading-python.html
11. asyncio task groups and timeouts: https://docs.python.org/3/library/asyncio-task.html
12. typing module: https://docs.python.org/3/library/typing.html
13. Python Packaging User Guide, pyproject.toml: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
14. uv documentation: https://docs.astral.sh/uv/
15. Ruff documentation: https://docs.astral.sh/ruff/
16. ty documentation: https://docs.astral.sh/ty/
17. mypy documentation: https://mypy.readthedocs.io/en/stable/
18. pytest documentation: https://docs.pytest.org/en/stable/
19. pickle security warning: https://docs.python.org/3/library/pickle.html
20. subprocess security considerations: https://docs.python.org/3/library/subprocess.html#security-considerations
21. tarfile extraction filters: https://docs.python.org/3/library/tarfile.html#tarfile-extraction-filter
22. pygame-ce documentation: https://pyga.me/docs/
23. Blender Python API: https://docs.blender.org/api/current/
24. PEP 602, annual release cycle: https://peps.python.org/pep-0602/
