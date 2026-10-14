#!/usr/bin/env python3
"""Native Luau syntax check on representative generated UI, using the pinned CLI."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from star.roblox_ui_compiler import compile_ui  # noqa: E402


def main() -> int:
    cli = shutil.which("luau-compile")
    if cli is None:
        print("FAIL: luau-compile missing; native syntax check must not skip")
        return 1
    cases = {}
    kinds = ("frame", "scroll", "grid", "text", "button", "image",
             "input", "toggle", "progress")
    for kind in kinds:
        child = {"type": kind, "id": "child"}
        if kind == "image":
            child["image"] = "rbxassetid://12345"
        if kind == "input":
            child["placeholder"] = "Enter" + chr(1) + "☃"
            child["states"] = {"pressed": {"transparency": 0.2}}
        if kind == "button":
            child["states"] = {"hover": {"background": "dark"}}
        if kind == "grid":
            child["layout"] = {"kind": "grid", "columns": 2}
        cases[kind] = {"palette": {"dark": "#111111"}, "root": {
            "type": "screen", "id": "root", "children": [child]}}
    cases["escape-string"] = {"root": {"type": "screen", "id": "root", "children": [
        {"type": "text", "id": "escape", "name": '"' + chr(92) + chr(1),
         "text": 'Quote " slash ' + chr(92) + ' snow ☃ ' + chr(1)}
    ]}}
    cases["minimal"] = {"root": {"type": "screen", "id": "root"}}
    cases["local-limit"] = {"root": {"type": "screen", "id": "root", "children": [
        {"type": "text", "id": f"n{i}", "text": "Snow ☃"} for i in range(149)
    ]}}
    failed = []
    with tempfile.TemporaryDirectory(prefix="star-ui-luau-") as temp:
        directory = pathlib.Path(temp)
        for name, spec in cases.items():
            path = directory / f"{name}.luau"
            path.write_text(compile_ui(spec).source, encoding="utf-8")
            result = subprocess.run([cli, str(path)], cwd=ROOT, text=True,
                                    capture_output=True, timeout=30, check=False)
            if result.returncode:
                failed.append(name)
                print(f"FAIL {name}: {result.stderr or result.stdout}")
            else:
                print(f"PASS {name}")
    print(f"{len(cases) - len(failed)}/{len(cases)} generated modules parsed by native Luau")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
