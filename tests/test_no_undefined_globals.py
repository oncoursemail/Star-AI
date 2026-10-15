"""Every global name used inside the star package must exist.

A function that reads a module-level name nobody defines only fails when that
line runs (a NameError deep inside a worker thread, for example). This check
walks Python's own symbol tables, so it needs no third-party linter.
"""
from __future__ import annotations

import builtins
from pathlib import Path
import symtable

ROOT = Path(__file__).resolve().parents[1] / "star"
# Names Python provides to every module without importing them.
MODULE_NAMES = {"__file__", "__name__", "__doc__", "__spec__", "__loader__", "__package__",
                "__path__", "__builtins__", "__annotations__", "__dict__", "__module__", "__qualname__",
                "__class__"}
# Ghidra scripts (PR #344) run inside Ghidra, which injects its API as globals (pyproject.toml excludes them from ruff too).
NOT_STAR_RUNTIME = ("re_scripts",)


def _undefined(source: str, label: str) -> list[str]:
    top = symtable.symtable(source, label, "exec")
    defined = {sym.get_name() for sym in top.get_symbols() if sym.is_assigned() or sym.is_imported()
               or sym.is_namespace()}
    if any(sym.get_name() == "*" for sym in top.get_symbols()):
        return []
    known = defined | set(dir(builtins)) | MODULE_NAMES
    missing: list[str] = []

    def walk(table: symtable.SymbolTable) -> None:
        for sym in table.get_symbols():
            name = sym.get_name()
            if (table is not top and sym.is_referenced() and sym.is_global()
                    and not sym.is_declared_global() and name not in known):
                missing.append(f"{label}: {table.get_name()} uses {name}")
        for child in table.get_children():
            walk(child)

    walk(top)
    return missing


def test_star_functions_only_use_defined_global_names():
    problems = [problem for path in sorted(ROOT.rglob("*.py"))
                if path.relative_to(ROOT).parts[0] not in NOT_STAR_RUNTIME
                for problem in _undefined(path.read_text(encoding="utf-8"), path.relative_to(ROOT.parent).as_posix())]
    assert problems == []


def test_checker_reports_a_missing_import():
    # The shape of the testBlender bridge bug: a lambda inside a method used asyncio unimported.
    source = "class Bridge:\n    def call(self):\n        return lambda: asyncio.run(None)\n"
    assert _undefined(source, "probe.py") == ["probe.py: lambda uses asyncio"]
    assert _undefined("import asyncio\n" + source, "probe.py") == []
