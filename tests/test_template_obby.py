"""Verify the standalone Rojo obby example keeps its API-free logic specs paired."""

import json
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / "examples" / "roblox-templates" / "obby"


def test_obby_template_layout_and_pure_module_specs():
    project = json.loads((TEMPLATE / "default.project.json").read_text(encoding="utf-8"))
    tree = project["tree"]
    assert tree["ReplicatedStorage"]["Shared"]["$path"] == "ReplicatedStorage/Shared"
    assert tree["ServerScriptService"]["$path"] == "ServerScriptService"
    assert tree["StarterPlayer"]["StarterPlayerScripts"]["$path"] == "StarterPlayer/StarterPlayerScripts"

    paths = (
        "README.md",
        "ServerScriptService/ObbyServer.server.luau",
        "ServerScriptService/CourseBuilder.luau",
        "ServerScriptService/PlayerData.luau",
        "ServerScriptService/CheckpointService.luau",
        "ServerScriptService/KillService.luau",
        "ServerScriptService/FinishService.luau",
        "ServerScriptService/TouchValidation.luau",
        "StarterPlayer/StarterPlayerScripts/StageHud.client.luau",
        "tests/run.luau",
    )
    for relative in paths:
        assert (TEMPLATE / relative).is_file(), relative

    shared = TEMPLATE / "ReplicatedStorage" / "Shared"
    modules = sorted(shared.glob("*.luau"))
    assert {module.stem for module in modules} == {"StageProgression", "SaveData"}
    for module in modules:
        assert (TEMPLATE / "tests" / f"{module.stem}.spec.luau").is_file()
        content = module.read_text(encoding="utf-8")
        assert content.startswith("--!strict\n")
        assert not any(api in content for api in ("game:", "script.", "Instance.new", "workspace"))
