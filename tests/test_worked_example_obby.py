"""Read-only inspection and real staged native-Luau test wiring for the obby."""
from pathlib import Path
import shutil

import pytest

from scripts import run_luau_specs as runner

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "roblox" / "obby"


def test_project_has_actual_wired_server_code_and_pure_core():
    server = (PROJECT / "ServerScriptService" / "ObbyServer.server.luau").read_text()
    core = (PROJECT / "ServerScriptService" / "StageCore.luau").read_text()
    spec = (PROJECT / "ServerScriptService" / "Tests" / "StageCore.spec.luau").read_text()
    assert "StageCore = require(script.Parent:WaitForChild" in server
    assert "Players.PlayerAdded:Connect" in server and "Players.PlayerRemoving:Connect" in server
    assert "CharacterAdded:Connect" in server and "StageCore.advance" in server
    assert "StageCore.claimFinish" in server and "StageCore.shouldKill" in server
    assert "leaderstats" in server and 'Name = "Stage"' in server
    assert "game:GetService" not in core and "workspace." not in core
    assert spec.count('"] = function()') >= 12
    readme = (PROJECT / "README.md").read_text()
    assert "server" in readme and "not simulate" in readme


def test_obby_native_spec_is_discovered_and_staged_without_writes(tmp_path):
    root = ROOT / "examples"
    stage = tmp_path / "staged"
    stage.mkdir()
    runner.stage_sources(root, stage)
    spec = stage / "roblox/obby/ServerScriptService/Tests/StageCore.spec.luau"
    source = stage / "roblox/obby/ServerScriptService/StageCore.luau"
    assert spec.is_file() and source.is_file()
    assert 'require("../StageCore")' in spec.read_text()
    assert "function Obby.claimFinish" in source.read_text()
    assert (PROJECT / "ServerScriptService/StageCore.luau").read_bytes() == source.read_bytes()


@pytest.mark.skipif(shutil.which("luau") is None, reason="native Luau exercised in pinned Luau specs CI")
def test_full_examples_run_with_actual_native_interpreter():
    assert runner.run(shutil.which("luau"), ROOT / "examples") == 0
