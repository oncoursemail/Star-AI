"""Deferred imports for heavy third-party libraries on the desktop start-up path.

`import star.react_shell` (what the desktop runs before it can show a window) used to load
jsonschema, httpx and anyio although no window needs them until the first tool call, web
request or Studio session. A module-level name bound with `lazy_module` or `lazy_attr` behaves
like the real module or class for every use STAR makes of it (attribute access, calls,
`except httpx.HTTPError`, `isinstance(x, httpx.Response)`, monkeypatching in tests) and performs
the ordinary `importlib.import_module` on first use. The import system's own per-module lock
makes that first use thread-safe; nothing is put in `sys.modules` ahead of time.

Use only for names that module code reads inside functions. Anything evaluated while the module
itself is imported (a class base, a module constant, an unquoted annotation in a `def` without
`from __future__ import annotations`) would load the library at once and defeat the point.
"""
from __future__ import annotations

import importlib
from typing import Any


class _Lazy:
    __slots__ = ("_lazy_module_name", "_lazy_attr", "_lazy_target")

    def __init__(self, module: str, attr: str | None = None):
        object.__setattr__(self, "_lazy_module_name", module)
        object.__setattr__(self, "_lazy_attr", attr)
        object.__setattr__(self, "_lazy_target", None)

    def _lazy_load(self) -> Any:
        target = object.__getattribute__(self, "_lazy_target")
        if target is None:
            target = importlib.import_module(object.__getattribute__(self, "_lazy_module_name"))
            attr = object.__getattribute__(self, "_lazy_attr")
            if attr is not None:
                target = getattr(target, attr)
            object.__setattr__(self, "_lazy_target", target)
        return target

    def __getattr__(self, name: str) -> Any:   # only for names not found on the proxy itself
        return getattr(self._lazy_load(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._lazy_load(), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self._lazy_load(), name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._lazy_load()(*args, **kwargs)

    def __dir__(self) -> list[str]:
        return dir(self._lazy_load())

    def __repr__(self) -> str:
        name = object.__getattribute__(self, "_lazy_module_name")
        attr = object.__getattribute__(self, "_lazy_attr")
        state = "loaded" if object.__getattribute__(self, "_lazy_target") is not None else "not loaded"
        return f"<lazy {name}{'.' + attr if attr else ''} ({state})>"


def lazy_module(name: str) -> Any:
    """A stand-in for `import name` that imports the module on first attribute access."""
    return _Lazy(name)


def lazy_attr(module: str, attr: str) -> Any:
    """A stand-in for `from module import attr` (a class or function) imported on first use."""
    return _Lazy(module, attr)
