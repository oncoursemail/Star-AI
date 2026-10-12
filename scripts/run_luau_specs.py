#!/usr/bin/env python3
"""Run repository Luau specs against the official standalone Luau CLI.

Sources are copied into a temporary sandbox and rewritten there; files in the
repository are never changed. Three rewrites are applied, each keeping line
numbers unchanged so failure messages point at the real source line:

* Roblox-style ModuleScript requires (``game:GetService(...):WaitForChild(...)``,
  ``script.Parent...``) become relative CLI requires.
* ``local X = game:GetService(...)`` lines become comments (the CLI has no ``game``).
* ``ArenaFactory.luau`` and its spec get a tiny in-memory Instance/workspace
  stand-in. That stand-in approximates the engine; it is not Roblox itself.

Specs execute, not merely parse, and a spec file that defines no cases fails.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

SPEC_TIMEOUT_SECONDS = 60
ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SERVICE = re.compile(r'game:GetService\("([^"]+)"\)')
CHILD = re.compile(r':WaitForChild\("([^"]+)"\)')
REQUIRE = re.compile(r'require\(([^\n]+)\)')
ALIAS = re.compile(r'local\s+(\w+)\s*=\s*(.+)')
ENGINE = """local Engine = {}
local objects = {}
local Node = {}
Node.__index = Node
function Node:FindFirstChild(name)
    for _, child in ipairs(objects) do
        if child.Parent == self and child.Name == name then return child end
    end
end
function Node:IsA(name) return self.ClassName == name end
function Node:IsDescendantOf(ancestor)
    local parent = self.Parent
    while parent do
        if parent == ancestor then return true end
        parent = parent.Parent
    end
    return false
end
function Node:Destroy()
    for _, child in ipairs(objects) do
        if child.Parent == self then child:Destroy() end
    end
    self.Parent = nil
end
Engine.workspace = setmetatable({Name="Workspace", ClassName="Workspace"}, Node)
Engine.Instance = {}
function Engine.Instance.new(name)
    local item = setmetatable({ClassName=name, Parent=nil}, Node)
    table.insert(objects, item)
    return item
end
Engine.Vector3 = {new=function(...) return {...} end}
Engine.CFrame = {new=function(...) return {...} end}
Engine.Color3 = {fromRGB=function(...) return {...} end}
Engine.Enum = {Material={SmoothPlastic="SmoothPlastic"}}
return Engine
"""


def mapped_require(expression: str, source: pathlib.Path, template: pathlib.Path,
                   aliases: dict[str, list[str]]) -> str | None:
    expr = expression.strip()
    if expr.startswith(('"', "'")):
        return None
    service = SERVICE.search(expr)
    if service:
        components = [service.group(1)] + CHILD.findall(expr)
    elif expr.startswith("script.Parent"):
        components = ["ServerScriptService"] + CHILD.findall(expr)
    else:
        head = re.match(r'(\w+)', expr)
        if not head or head.group(1) not in aliases:
            return None
        components = aliases[head.group(1)] + CHILD.findall(expr)
    if not components:
        return None
    candidate = template.joinpath(*components).with_suffix(".luau")
    if not candidate.is_file():
        return None  # Non-spec engine script; an executed unresolved require still fails.
    relative = pathlib.Path(os.path.relpath(candidate.with_suffix(""), source.parent))
    path = relative.as_posix()
    if not path.startswith("."):
        path = "./" + path
    return f'require("{path}")'


def translate(source: pathlib.Path, template: pathlib.Path, text: str) -> str:
    aliases: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = ALIAS.search(line)
        if match:
            name, value = match.groups()
            service = SERVICE.search(value)
            if service:
                aliases[name] = [service.group(1)] + CHILD.findall(value)
            else:
                alias_name = re.match(r'(\w+)', value)
                if alias_name and alias_name.group(1) in aliases:
                    aliases[name] = aliases[alias_name.group(1)] + CHILD.findall(value)

    def replace(match: re.Match[str]) -> str:
        rewritten = mapped_require(match.group(1), source, template, aliases)
        return rewritten if rewritten is not None else match.group(0)

    return re.sub(r"(?m)^local \w+ = game:GetService\([^\n]+$", "-- CLI service alias", REQUIRE.sub(replace, text))


def engine_prefix(prefix: str) -> str:
    """One line, no newline, so the injected locals do not shift any line number."""
    return (
        f'local __engine = require("{prefix}__headless_engine"); '
        "local workspace = __engine.workspace; "
        "local Instance = __engine.Instance; "
        "local Vector3 = __engine.Vector3; "
        "local CFrame = __engine.CFrame; "
        "local Color3 = __engine.Color3; "
        "local Enum = __engine.Enum; "
    )


def driver_source(module_name: str) -> str:
    """Luau driver: run every case of a spec table even if another case fails."""
    return (
        f'local suite = require("./{module_name}")\n'
        'local names = {}\n'
        'for name in pairs(suite) do table.insert(names, name) end\n'
        'table.sort(names)\n'
        'if #names == 0 then error("spec defines no cases") end\n'
        'local failed = 0\n'
        'for _, name in ipairs(names) do\n'
        '  local ok, err = pcall(suite[name])\n'
        '  if ok then print("  PASS " .. name)\n'
        '  else failed += 1; print("  FAIL " .. name .. ": " .. tostring(err)) end\n'
        'end\n'
        'if failed > 0 then error(tostring(failed) .. " case(s) failed") end\n'
    )


def stage_sources(root: pathlib.Path, stage: pathlib.Path) -> None:
    """Copy every .luau file under root into stage, translated for the CLI."""
    for source in root.rglob("*.luau"):
        destination = stage / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        template = next(
            (parent for parent in [source.parent, *source.parents]
             if parent.parent == root / "roblox-templates"
             or parent == root / "roblox-test-place"),
            None,
        )
        if template is None:
            raise ValueError(f"no template root for {source}")
        transformed = translate(source, template, source.read_text(encoding="utf-8"))
        destination.write_text(transformed, encoding="utf-8")

    # A minimal in-memory Roblox instance tree for the ArenaFactory cases.
    engine_dir = stage / "roblox-templates/rounds/ServerScriptService"
    if not engine_dir.is_dir():
        return
    (engine_dir / "__headless_engine.luau").write_text(ENGINE, encoding="utf-8")
    for original in [
        engine_dir / "ArenaFactory.luau",
        engine_dir / "Tests/ArenaFactory.spec.luau",
    ]:
        prefix = "./" if original.parent == engine_dir else "../"
        original.write_text(engine_prefix(prefix) + original.read_text(encoding="utf-8"),
                            encoding="utf-8")


def run(cli: str, root: pathlib.Path) -> int:
    specs = sorted(root.rglob("*.spec.luau"))
    if not specs:
        print("FAIL: no Luau specs found", file=sys.stderr)
        return 1
    failures = 0
    with tempfile.TemporaryDirectory(prefix="star-luau-specs-") as tmp:
        stage = pathlib.Path(tmp)
        stage_sources(root, stage)
        for spec in specs:
            staged = stage / spec.relative_to(root)
            driver = staged.with_name(staged.name + ".runner.luau")
            driver.write_text(driver_source(staged.stem), encoding="utf-8")
            print(f"RUN {spec.relative_to(root)}", flush=True)
            try:
                result = subprocess.run([cli, str(driver)], cwd=staged.parent, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        timeout=SPEC_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                failures += 1
                print(f"FAIL spec: no result after {SPEC_TIMEOUT_SECONDS} seconds", flush=True)
                continue
            print(result.stdout, end="", flush=True)
            if result.returncode:
                failures += 1
                print("FAIL spec", flush=True)
            else:
                print("PASS spec", flush=True)
    print(f"{len(specs) - failures}/{len(specs)} spec files passed")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--luau", default="luau", help="path to Luau interpreter")
    parser.add_argument("--examples", type=pathlib.Path, default=EXAMPLES)
    args = parser.parse_args()
    cli = shutil.which(args.luau)
    if not cli:
        parser.error(f"Luau CLI not found: {args.luau}")
    return run(cli, args.examples.resolve())


if __name__ == "__main__":
    sys.exit(main())
