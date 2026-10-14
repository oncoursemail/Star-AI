"""Offline contracts for the standalone Roblox rounds example.

The Luau behavioral specs are run only by the owner-approved Roblox harness.
These checks validate the distributable place and its trust boundaries offline.
"""
from pathlib import Path

from star.roblox_place import build_place

SOURCE = Path(__file__).resolve().parents[1] / "examples" / "roblox-templates" / "rounds"


def source(path: str) -> str:
    return (SOURCE / path).read_text(encoding="utf-8")


def test_rounds_template_builds_into_a_reproducible_place_without_external_tools():
    first = build_place(SOURCE)
    second = build_place(SOURCE)
    assert first.builder == "star-builtin"
    assert first.sha256 == second.sha256 and first.data == second.data
    assert len(first.files) == 11
    assert "ServerScriptService/RoundServer.server.luau" in first.files
    assert "StarterPlayer/StarterPlayerScripts/RoundHud.client.luau" in first.files
    assert "ReplicatedStorage/Shared/RoundState.luau" in first.files
    assert "ReplicatedStorage/Shared/WinnerRules.luau" in first.files
    assert sum(name.endswith(".spec.luau") for name in first.files) == 4
    assert b'<Item class="Script"' in first.data
    assert b'<Item class="LocalScript"' in first.data
    assert b'<Item class="ModuleScript"' in first.data


def test_transition_specs_include_every_legal_edge_and_the_zero_player_round():
    specs = source("ServerScriptService/Tests/RoundState.spec.luau")
    for case in (
        "Intermission to Loading", "Intermission stays waiting with zero",
        "Intermission stays waiting with one", "Loading to Playing",
        "Loading to Intermission if the last players left",
        "Loading to Intermission below minimum",
        "Loading to Intermission on map failure",
        "Playing to Ended when a winner", "Playing to Ended on a timeout",
        "Playing to Ended when everyone has left", "Ended to Intermission",
        "forbids skipping any state", "rejects bad states",
    ):
        assert case in specs
    winner_specs = source("ServerScriptService/Tests/WinnerRules.spec.luau")
    for case in ("zero participants", "one survivor", "two survivors", "tied timeout",
                 "all-zero timeout", "zero survivors", "duplicate living identities"):
        assert case in winner_specs


def test_only_the_server_owns_rewards_and_state_mutation():
    server = source("ServerScriptService/RoundServer.server.luau")
    client = source("StarterPlayer/StarterPlayerScripts/RoundHud.client.luau")
    assert 'SetAttribute("RoundState", state)' in server
    assert 'SetAttribute("RoundDeadline", value)' in server
    assert "WinnerRules.resolve" in server
    assert "coins.Value += Config.WinnerCoins" in server
    assert "rewarded[userId] = true" in server
    assert "GetAttribute(\"RoundState\")" in client
    assert "GetAttribute(\"RoundDeadline\")" in client
    for untrusted in ("SetAttribute(", "FireServer(", "InvokeServer(", "Coins", "OnServerEvent"):
        assert untrusted not in client


def test_round_resources_are_scoped_and_cleanup_is_specified():
    server = source("ServerScriptService/RoundServer.server.luau")
    resources = source("ServerScriptService/RoundResources.luau")
    specs = source("ServerScriptService/Tests/RoundResources.spec.luau")
    assert "resources:cleanup()" in server
    assert "arena:Destroy()" in server
    assert "died:Disconnect()" in server and "removed:Disconnect()" in server
    assert "hook:Disconnect()" in server
    assert "table.clear(entrants)" in server
    assert "self.closed = true" in resources
    assert "disposes fake map and connections" in specs
    assert "cleanup is idempotent" in specs
    assert "registration after cleanup" in specs
