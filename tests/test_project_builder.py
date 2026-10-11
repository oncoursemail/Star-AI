"""Offline end-to-end tests for the real builder path."""
import json
from pathlib import Path

import pytest

from star.project_builder import build_project, ordered_modules, validate_code


def module(name, kind="shared", requires=()):
    return {"name": name, "kind": kind, "purpose": "An isolated example",
            "interface": ["run"], "requires": list(requires)}


def good(name="run"):
    return f"```luau\nlocal M = {{}}\nfunction M.{name}() return true end\nreturn M\n```"


def test_five_modules_and_dependency_context(tmp_path):
    plan = {"modules": [
        module("Final", "server", ["Client", "Items"]),
        module("Client", "client", ["Math"]),
        module("Items", "shared", ["Math"]),
        module("Math"), module("Utilities"),
    ]}
    calls = []
    def fake(prompt):
        calls.append(json.loads(prompt[prompt.index('{"module":'):]))
        return good()
    manifest = build_project(plan, tmp_path / "game", fake)
    assert len(manifest["generated"]) == 5
    assert not manifest["failed"]
    assert [c["module"]["name"] for c in calls].index("Math") < [c["module"]["name"] for c in calls].index("Client")
    final = next(c for c in calls if c["module"]["name"] == "Final")
    assert {i["name"] for i in final["dependency_interfaces"]} == {"Client", "Items"}
    assert all("source" not in i and "code" not in i for i in final["dependency_interfaces"])
    root = tmp_path / "game"
    assert (root / "src/ServerScriptService/Server/Final.lua").exists()
    assert (root / "src/StarterPlayer/StarterPlayerScripts/Client/Client.lua").exists()
    assert (root / "src/ReplicatedStorage/Shared/Math.lua").exists()
    assert json.loads((root / "default.project.json").read_text())["tree"]["ServerScriptService"]["$path"] == "src/ServerScriptService"
    assert json.loads((root / "manifest.json").read_text()) == manifest


def test_repair_includes_static_failure(tmp_path):
    prompts = []
    def fake(prompt):
        prompts.append(prompt)
        return "```luau\nreturn {}\n```" if len(prompts) == 1 else good()
    manifest = build_project([module("Repair")], tmp_path / "out", fake)
    assert manifest["generated"][0]["attempts"] == 2
    assert "Missing public interface: run" in prompts[1]


def test_double_failure_recorded_without_writing_script(tmp_path):
    manifest = build_project([module("Bad")], tmp_path / "out", lambda _: "```luau\n\n```")
    assert manifest["failed"][0]["attempts"] == 2
    assert not (tmp_path / "out/src/ReplicatedStorage/Shared/Bad.lua").exists()
    assert (tmp_path / "out/manifest.json").exists()


@pytest.mark.parametrize("name", ["../escape", "a/b", "..", "A\\B", ""])
def test_path_guard_rejects_unsafe_names(tmp_path, name):
    with pytest.raises(ValueError):
        build_project([module(name)], tmp_path / "out", lambda _: good())
    assert not (tmp_path / "out").exists()


def test_existing_files_not_overwritten(tmp_path):
    root = tmp_path / "out"
    root.mkdir()
    (root / "manifest.json").write_text("sentinel")
    with pytest.raises(FileExistsError):
        build_project([module("Safe")], root, lambda _: good())
    assert (root / "manifest.json").read_text() == "sentinel"


def test_symlink_path_cannot_escape(tmp_path):
    root = tmp_path / "out"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "src").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        build_project([module("Safe")], root, lambda _: good())
    assert list(outside.iterdir()) == []


def test_dependency_order_cycle_and_unknown():
    names = [m["name"] for m in ordered_modules([module("C", requires=["B"]), module("B", requires=["A"]), module("A")])]
    assert names == ["A", "B", "C"]
    with pytest.raises(ValueError, match="Cyclic"):
        ordered_modules([module("A", requires=["B"]), module("B", requires=["A"])])
    with pytest.raises(ValueError, match="Unknown"):
        ordered_modules([module("A", requires=["Missing"])])


@pytest.mark.parametrize("response", [
    "```luau\nlocal M={}\nfunction M.run() game:HttpGet('x') end\nreturn M\n```",
    "```luau\nlocal M={}\nfunction M.run() loadstring('x') end\nreturn M\n```",
    "```luau\nlocal M={}\nfunction M.run() require(123) end\nreturn M\n```",
])
def test_forbidden_apis(response):
    _, error = validate_code(response, ["run"])
    assert error == "Forbidden API detected"
