"""Offline layout contract for the self-contained, server-authoritative tycoon example."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "examples" / "roblox-templates" / "tycoon"


def test_tycoon_source_and_rojo_layout():
    project = json.loads((ROOT / "default.project.json").read_text(encoding="utf-8"))
    tree = project["tree"]
    assert tree["$className"] == "DataModel"
    assert tree["ReplicatedStorage"]["$path"] == "ReplicatedStorage"
    assert tree["ServerScriptService"]["$path"] == "ServerScriptService"
    assert tree["StarterPlayer"]["StarterPlayerScripts"]["$path"] == "StarterPlayer/StarterPlayerScripts"

    sources = {
        "ReplicatedStorage/Shared/Economy.luau",
        "ServerScriptService/PlayerData.luau",
        "ServerScriptService/Plots.luau",
        "ServerScriptService/Tycoon.server.luau",
        "ServerScriptService/Tests/Economy.spec.luau",
        "StarterPlayer/StarterPlayerScripts/Hud.client.luau",
    }
    for name in sources:
        script = ROOT / name
        assert script.is_file(), name
        assert script.read_text(encoding="utf-8").startswith("--!strict\n"), name

    economy = (ROOT / "ReplicatedStorage/Shared/Economy.luau").read_text(encoding="utf-8")
    data = (ROOT / "ServerScriptService/PlayerData.luau").read_text(encoding="utf-8")
    plots = (ROOT / "ServerScriptService/Plots.luau").read_text(encoding="utf-8")
    server = (ROOT / "ServerScriptService/Tycoon.server.luau").read_text(encoding="utf-8")
    specs = (ROOT / "ServerScriptService/Tests/Economy.spec.luau").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert all(word in economy for word in ("prerequisite", "MAX_ACTIVE_DROPS", "function Economy.buy",
                                          "function Economy.collect", "function Economy.rebirth",
                                          "function Economy.fromSaved", "function Economy.multiplier"))
    assert all(word in data for word in ("UpdateAsync", "pcall", "MAX_ATTEMPTS", "lease", "function PlayerData.save"))
    assert "PlayerRemoving" not in plots  # plot ownership is cleaned up by the server entrypoint
    assert all(word in plots for word in ("collector.Touched", "plot.activeDrops[part] = nil",
                                        "prompt.Triggered", "Plots.release", "MAX_ACTIVE_DROPS"))
    assert all(word in server for word in ("PlayerAdded", "PlayerRemoving", "BindToClose", "PlayerData.save",
                                         "Economy.buy", "Economy.collect", "Economy.rebirth"))
    assert all(name in specs for name in ("starter is owned", "prerequisites are enforced",
                                          "insufficient cash", "successful purchase", "collection accepts",
                                          "rebirth requires", "loading repairs", "catalog returns"))
    assert "return {" in specs and specs.count('"] = function()') >= 7
    assert "trust rules" in readme.lower() and "playtest checklist" in readme.lower()
