#!/usr/bin/env python3
"""Run repository Luau specs against the official standalone Luau CLI.

Sources are copied into a temporary sandbox and rewritten there; files in the
repository are never changed. Three rewrites are applied, each keeping line
numbers unchanged so failure messages point at the real source line:

* Roblox-style ModuleScript requires (``game:GetService(...):WaitForChild(...)``,
  ``script.Parent...``) become relative CLI requires.
* ``local X = game:GetService(...)`` lines become comments (the CLI has no ``game``).
* ``ArenaFactory.luau`` and its spec get a tiny in-memory Instance/workspace
  stand-in. It creates only Model, Part, SpawnLocation and a Workspace singleton.
  Inheritance is simulated; property validation, physics, replication and
  Studio semantics are not covered. Unsupported classes fail closed.

Specs execute, not merely parse. A pass requires bounded, nonempty case
evidence, consistent totals and a zero interpreter exit, not Studio verification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

SPEC_TIMEOUT_SECONDS = 60
MAX_CASES_PER_SPEC = 128
MAX_CASE_NAME_BYTES = 160
MAX_SPEC_OUTPUT_BYTES = 128_000
_CASE_ROW = re.compile(r"@@STAR_LUAU_CASE_V1\t([1-9][0-9]{0,2})\t(PASS|FAIL)\t([0-9a-f]+)")
_SUMMARY_ROW = re.compile(r"@@STAR_LUAU_SUMMARY_V1\t(0|[1-9][0-9]{0,2})\t(0|[1-9][0-9]{0,2})")
ARENA_SPEC = pathlib.Path(
    "roblox-templates/rounds/ServerScriptService/Tests/ArenaFactory.spec.luau"
)
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
-- Offline test-only class graph. These are the ancestors of the classes
-- modeled by ArenaFactory, not a general Roblox class catalogue.
local PARENT_CLASS = {
    Object = false,
    Instance = "Object",
    PVInstance = "Instance",
    Model = "PVInstance",
    WorldRoot = "Model",
    Workspace = "WorldRoot",
    BasePart = "PVInstance",
    FormFactorPart = "BasePart",
    Part = "FormFactorPart",
    SpawnLocation = "Part",
}
local CREATABLE = {Model = true, Part = true, SpawnLocation = true}
function Node:FindFirstChild(name)
    for _, child in ipairs(objects) do
        if child.Parent == self and child.Name == name then return child end
    end
end
function Node:IsA(name)
    -- Reject unmodeled names rather than validating arbitrary engine classes.
    if type(name) ~= "string" or PARENT_CLASS[name] == nil then
        error("unsupported headless IsA class: " .. tostring(name), 2)
    end
    local current = self.ClassName
    while current do
        if current == name then return true end
        current = PARENT_CLASS[current]
    end
    return false
end
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
    if type(name) ~= "string" or not CREATABLE[name] then
        error("unsupported headless Instance.new class: " .. tostring(name), 2)
    end
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
    """Luau driver: bounded case-by-case evidence, even if a case fails.

    Human-facing PASS/FAIL lines remain unchanged. Reserved protocol rows
    are parsed by Python and hidden from ordinary command output.
    """
    return (
        f'local suite = require("./{module_name}")\n'
        'if type(suite) ~= "table" then error("spec must return a table") end\n'
        'local names = {}\n'
        'for name in pairs(suite) do\n'
        '  if type(name) ~= "string" or #name == 0 or #name > 160 then\n'
        '    error("invalid spec case name")\n'
        '  end\n'
        '  table.insert(names, name)\n'
        'end\n'
        'table.sort(names)\n'
        'if #names == 0 then error("spec defines no cases") end\n'
        'if #names > 128 then error("too many spec cases") end\n'
        'local function hex_name(name)\n'
        '  return (string.gsub(name, ".", function(c)\n'
        '    return string.format("%02x", string.byte(c))\n'
        '  end))\n'
        'end\n'
        'local failed = 0\n'
        'for index, name in ipairs(names) do\n'
        '  local ok, err = pcall(suite[name])\n'
        '  if ok then print("  PASS " .. name)\n'
        '  else failed += 1; print("  FAIL " .. name .. ": " .. tostring(err)) end\n'
        '  print("@@STAR_LUAU_CASE_V1\\t" .. index .. "\\t" .. (ok and "PASS" or "FAIL") .. "\\t" .. hex_name(name))\n'
        'end\n'
        'print("@@STAR_LUAU_SUMMARY_V1\\t" .. #names .. "\\t" .. failed)\n'
        'if failed > 0 then error(tostring(failed) .. " case(s) failed") end\n'
    )


@dataclass(frozen=True)
class SpecEvidence:
    attempted: int
    verified: int
    failed: int
    reason: str | None


def parse_case_evidence(output: str, returncode: int) -> SpecEvidence:
    """Accept only complete, bounded, internally consistent driver evidence.

    Ordinary spec stdout (including plain PASS text) is never evidence.
    This is a protocol check, not an attestation against adversarial Luau code.
    """
    def invalid(reason: str) -> SpecEvidence:
        return SpecEvidence(0, 0, 0, reason)

    if not isinstance(output, str) or len(output.encode("utf-8")) > MAX_SPEC_OUTPUT_BYTES:
        return invalid("missing or oversized interpreter output")
    if type(returncode) is not int:
        return invalid("invalid interpreter exit status")
    cases: dict[int, tuple[str, bool]] = {}
    seen_names: set[str] = set()
    summary: tuple[int, int] | None = None
    for line in output.splitlines():
        if not line.startswith("@@STAR_LUAU_"):
            continue
        if match := _CASE_ROW.fullmatch(line):
            index = int(match[1])
            if index > MAX_CASES_PER_SPEC or index in cases:
                return invalid("duplicate or out-of-range case index")
            try:
                name_bytes = bytes.fromhex(match[3])
                name = name_bytes.decode("utf-8")
            except (ValueError, UnicodeError):
                return invalid("invalid case name encoding")
            if (not name or len(name_bytes) > MAX_CASE_NAME_BYTES
                    or not name.isprintable() or name in seen_names):
                return invalid("empty, duplicate or unsupported case name")
            seen_names.add(name)
            cases[index] = (name, match[2] == "PASS")
        elif match := _SUMMARY_ROW.fullmatch(line):
            if summary is not None:
                return invalid("duplicate case summary")
            summary = (int(match[1]), int(match[2]))
        else:
            return invalid("malformed case evidence")
    if summary is None:
        return invalid("missing case summary")
    attempted, declared_failed = summary
    if not 1 <= attempted <= MAX_CASES_PER_SPEC:
        return invalid("empty or oversized case summary")
    if set(cases) != set(range(1, attempted + 1)):
        return invalid("missing, repeated or non-contiguous case evidence")
    failed = sum(not passed for _, passed in cases.values())
    if declared_failed != failed:
        return invalid("conflicting case totals")
    if returncode == 0 and failed:
        return invalid("interpreter exited zero after failed case(s)")
    if returncode != 0 and not failed:
        return invalid("interpreter failed after apparent PASS case(s)")
    return SpecEvidence(attempted, attempted - failed, failed,
                        f"{failed} case(s) failed" if failed else None)


def _visible_output(output: str) -> str:
    """Omit reserved machine rows while retaining legacy PASS/FAIL text."""
    return "".join(line for line in output.splitlines(keepends=True)
                   if not line.startswith("@@STAR_LUAU_"))


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


def run(cli: str, root: pathlib.Path, *, json_output: bool = False) -> int:
    specs = sorted(root.rglob("*.spec.luau"))
    if not specs:
        if json_output:
            print(json.dumps({"status": "fail", "specs": [], "attempted": 0,
                              "verified": 0, "error": "no Luau specs found"}, sort_keys=True))
        else:
            print("FAIL: no Luau specs found", file=sys.stderr)
        return 1
    failures, attempted, verified = 0, 0, 0
    records: list[dict[str, str | int | bool | None]] = []
    with tempfile.TemporaryDirectory(prefix="star-luau-specs-") as tmp:
        stage = pathlib.Path(tmp)
        stage_sources(root, stage)
        for spec in specs:
            staged = stage / spec.relative_to(root)
            driver = staged.with_name(staged.name + ".runner.luau")
            driver.write_text(driver_source(staged.stem), encoding="utf-8")
            relative = spec.relative_to(root)
            simulated = relative == ARENA_SPEC
            if not json_output:
                print(f"RUN {relative}", flush=True)
                if simulated:
                    print("  SIMULATED ROBLOX INSTANCE: native Luau CLI with limited doubles; "
                          "not Roblox Studio", flush=True)
            try:
                result = subprocess.run([cli, str(driver)], cwd=staged.parent, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        timeout=SPEC_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                evidence = SpecEvidence(0, 0, 0,
                                        f"no result after {SPEC_TIMEOUT_SECONDS} seconds")
                output = ""
            except OSError:
                evidence = SpecEvidence(0, 0, 0, "Luau interpreter could not start")
                output = ""
            else:
                output = result.stdout if isinstance(result.stdout, str) else ""
                evidence = parse_case_evidence(output, result.returncode)
            attempted += evidence.attempted
            verified += evidence.verified
            if evidence.reason is not None:
                failures += 1
            if not json_output:
                if len(output.encode("utf-8")) <= MAX_SPEC_OUTPUT_BYTES:
                    print(_visible_output(output), end="", flush=True)
                if evidence.reason is not None:
                    print(f"FAIL spec: {evidence.reason}", flush=True)
                else:
                    print("PASS spec", flush=True)
            records.append({"file": relative.as_posix(),
                            "status": "fail" if evidence.reason else "pass",
                            "attempted": evidence.attempted,
                            "verified": evidence.verified,
                            "reason": evidence.reason,
                            "simulated_roblox": simulated})
    if json_output:
        print(json.dumps({"status": "fail" if failures else "pass",
                          "spec_files": len(specs),
                          "spec_files_passed": len(specs) - failures,
                          "attempted": attempted, "verified": verified,
                          "scope": "native Luau CLI; not Roblox Studio",
                          "specs": records}, sort_keys=True))
    else:
        print(f"{len(specs) - failures}/{len(specs)} spec files passed"
              f"; {attempted} attempted, {verified} verified cases")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--luau", default="luau", help="path to Luau interpreter")
    parser.add_argument("--examples", type=pathlib.Path, default=EXAMPLES)
    parser.add_argument("--json", action="store_true", help="machine-readable evidence report")
    args = parser.parse_args()
    cli = shutil.which(args.luau)
    if not cli:
        parser.error(f"Luau CLI not found: {args.luau}")
    return run(cli, args.examples.resolve(), json_output=args.json)


if __name__ == "__main__":
    sys.exit(main())
