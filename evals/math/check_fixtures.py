"""Offline checks for reviewed math fixtures, NOT a sandbox for model answers.

Only the two checked-in answers for an enumerated task ID are executed. Prefer a
standalone Luau CLI. Lua 5.4 may check the deliberately shared language subset,
but that is numerical compatibility evidence, not native Luau validation.
No downloading, services, application credentials or Roblox engine are needed.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "golden-tasks-v1.json"
TOPICS = (
    "vectors", "dot-product", "cross-product", "cframe-composition", "look-at",
    "lerp", "easing-polynomial", "easing-transcendental", "critical-spring",
    "bezier-quadratic", "bezier-cubic", "projectile-motion", "projectile-launch",
    "angle-wrap", "angular-lerp", "ray-plane", "ray-sphere", "weighted-random",
    "seeded-random", "fixed-timestep",
)
LABELS = re.compile(r'^check\("([^"\n]+)"\s*,', re.M)
FIELDS = {
    "id", "category", "topic", "goal", "prompt", "run_mode", "fixture_status",
    "tolerance", "unit_test", "reference_answer", "bad_answer", "bad_answer_reason",
    "bad_answer_fails",
}
# A format/purity lint, not a security boundary or a substitute for execution.
FORBIDDEN = re.compile(
    r"\b(?:game|workspace|Instance|Vector3|CFrame|Random|require|loadstring|"
    r"getfenv|setfenv|io|os|debug)\b|\bmath\s*\.\s*random(?:seed)?\b"
)


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_catalog() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    validate_catalog(data)
    return data


def validate_catalog(data: dict) -> None:
    """Validate the standalone format without changing any existing eval schema."""
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    require(isinstance(data, dict), "catalog must be an object")
    require(set(data) == {"schema_version", "name", "harness_owned", "scope", "tasks"}, "catalog fields")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "schema version")
    require(data["name"] == "roblox-game-math" and data["harness_owned"] is True, "catalog ownership")
    require(isinstance(data["scope"], str) and bool(data["scope"].strip()), "scope")
    tasks = data["tasks"]
    require(isinstance(tasks, list) and len(tasks) == 20, "exactly twenty tasks required")
    for number, task in enumerate(tasks, 1):
        require(isinstance(task, dict) and set(task) == FIELDS, f"task {number}: fields")
        tag = f"MATH-{number:02d}"
        require(task["id"] == tag and task["topic"] == TOPICS[number - 1], f"{tag}: identity/topic")
        require(task["category"] == "game-math" and task["run_mode"] == "automated"
                and task["fixture_status"] == "implemented", f"{tag}: status")
        for field in ("goal", "prompt", "reference_answer", "bad_answer", "bad_answer_reason"):
            value = task[field]
            require(isinstance(value, str) and 1 <= len(value.strip()) <= 12_000, f"{tag}: {field}")
        require("pure Luau" in task["prompt"] and "absolute tolerance 1e-9" in task["prompt"], f"{tag}: contract")
        tolerance = task["tolerance"]
        require(isinstance(tolerance, dict) and set(tolerance) == {"absolute", "relative"}, f"{tag}: tolerance")
        require(all(type(v) in (int, float) and math.isfinite(v) for v in tolerance.values()), f"{tag}: finite tolerance")
        require(tolerance == {"absolute": 1e-9, "relative": 0}, f"{tag}: tolerance values")
        unit = task["unit_test"]
        require(isinstance(unit, dict) and set(unit) == {"checks", "body"}, f"{tag}: unit test")
        require(isinstance(unit["body"], str) and 1 <= len(unit["body"]) <= 12_000, f"{tag}: body")
        body = unit["body"]
        labels = LABELS.findall(body)
        require(type(unit["checks"]) is int and unit["checks"] == len(labels) >= 6, f"{tag}: check count")
        require(len(labels) == len(set(labels)), f"{tag}: duplicate check label")
        require(body.startswith("local f = load_answer()\n") and "<= 1e-9" in body, f"{tag}: harness convention")
        require(not re.search(r"\bfunction\s+(?:check|load_answer)\b", body), f"{tag}: harness override")
        failures = task["bad_answer_fails"]
        require(isinstance(failures, list) and bool(failures) and all(isinstance(x, str) for x in failures), f"{tag}: failures")
        require(len(set(failures)) == len(failures) and set(failures) <= set(labels), f"{tag}: named failures")
        require(task["reference_answer"] != task["bad_answer"], f"{tag}: distinct answers")
        for role in ("reference_answer", "bad_answer"):
            code = task[role]
            require(not FORBIDDEN.search(code), f"{tag}: {role} must be pure")
            require(bool(re.search(r"\nreturn [A-Za-z_]\w*\s*\Z", code)), f"{tag}: module return")
        require(not FORBIDDEN.search(body), f"{tag}: tests must be offline")


def runtime() -> tuple[str, str] | None:
    """Discover an installed runtime; never install one as a test side effect."""
    executable = shutil.which("luau")
    if executable:
        return "luau", executable
    library = ctypes.util.find_library("lua5.4")
    return ("lua54-compat", library) if library else None


def fixture(task_id: str, role: str) -> dict:
    if role not in {"reference_answer", "bad_answer"}:
        raise ValueError("only checked-in reference_answer and bad_answer are supported")
    for task in load_catalog()["tasks"]:
        if task["id"] == task_id:
            return task
    raise ValueError("unknown fixture ID")


def script(task: dict, role: str) -> str:
    """Wrap trusted fixture functions, keeping check/load_answer harness-owned."""
    return (
        "local function check(name, ok)\n"
        '    print("@@T\\t" .. (ok and "pass" or "fail") .. "\\t" .. name)\n'
        "end\nlocal function load_answer()\n    return (function()\n"
        + task[role] + "\n    end)(), {}\nend\n"
        + "local ok, err = pcall(function()\n" + task["unit_test"]["body"] + "\nend)\n"
        + 'if not ok then print("@@ERR\\t" .. tostring(err)) end\nprint("@@DONE")\n'
    )


def _lua54_worker(task_id: str, role: str) -> None:
    """Execute in a disposable child process; used only for reviewed fixtures."""
    name = ctypes.util.find_library("lua5.4")
    if not name:
        raise RuntimeError("Lua 5.4 library unavailable")
    lua = ctypes.CDLL(name)
    pointer = ctypes.c_void_p
    lua.luaL_newstate.argtypes, lua.luaL_newstate.restype = [], pointer
    lua.luaL_openlibs.argtypes = [pointer]
    lua.luaL_openlibs.restype = None
    lua.luaL_loadbufferx.argtypes = [pointer, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
    lua.luaL_loadbufferx.restype = ctypes.c_int
    lua.lua_pcallk.argtypes = [pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, pointer]
    lua.lua_pcallk.restype = ctypes.c_int
    lua.lua_tolstring.argtypes = [pointer, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    lua.lua_tolstring.restype = ctypes.c_char_p
    lua.lua_close.argtypes, lua.lua_close.restype = [pointer], None
    state = lua.luaL_newstate()
    if not state:
        raise RuntimeError("could not allocate Lua state")
    try:
        lua.luaL_openlibs(state)
        source = script(fixture(task_id, role), role).encode("utf-8")
        status = lua.luaL_loadbufferx(state, source, len(source), b"math-fixture", b"t")
        if status == 0:
            status = lua.lua_pcallk(state, 0, 0, 0, 0, None)
        if status:
            error = lua.lua_tolstring(state, -1, None)
            raise RuntimeError(error.decode("utf-8", "replace") if error else "Lua failed")
    finally:
        lua.lua_close(state)


def run_fixture(task_id: str, role: str, selected: tuple[str, str]) -> dict:
    task = fixture(task_id, role)
    kind, executable = selected
    with tempfile.TemporaryDirectory(prefix="star-math-") as directory:
        if kind == "luau":
            path = Path(directory) / "fixture.luau"
            path.write_text(script(task, role), encoding="utf-8")
            argv = [executable, str(path)]
        elif kind == "lua54-compat":
            argv = [sys.executable, str(Path(__file__).resolve()), "--lua54-worker", task_id, role]
        else:
            raise ValueError("unsupported runtime")
        done = subprocess.run(argv, cwd=directory, capture_output=True, text=True, timeout=10, check=False)
    results, errors, completed = [], [], 0
    for line in done.stdout.splitlines():
        if line.startswith("@@T\t"):
            parts = line.split("\t", 2)
            if len(parts) != 3 or parts[1] not in {"pass", "fail"}:
                errors.append("malformed result")
            else:
                results.append((parts[2], parts[1] == "pass"))
        elif line.startswith("@@ERR\t"):
            errors.append(line[6:])
        elif line == "@@DONE":
            completed += 1
    if done.returncode:
        errors.append(f"runtime exit {done.returncode}: {done.stderr[:500]}")
    if completed != 1:
        errors.append("harness did not finish exactly once")
    if [name for name, _ in results] != LABELS.findall(task["unit_test"]["body"]):
        errors.append("assertion names/order/count differ from the catalog")
    return {"runtime": kind, "results": results, "errors": errors}


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--lua54-worker":
        _lua54_worker(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit("Use pytest -q tests/test_game_math_catalog.py; this is not an answer-execution CLI.")
