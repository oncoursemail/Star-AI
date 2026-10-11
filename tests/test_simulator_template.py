"""Offline shape and trust-boundary checks for the source-built simulator example."""
from pathlib import Path
import xml.etree.ElementTree as ET

from star.roblox_place import build_place

ROOT = Path(__file__).resolve().parents[1] / "examples" / "roblox-templates" / "simulator"
SHARED = ROOT / "ReplicatedStorage" / "Shared"
SERVER = ROOT / "ServerScriptService"
SPECS = SERVER / "Tests"


def test_simulator_builds_into_an_actual_roblox_place():
    built = build_place(ROOT)
    expected = {
        "ServerScriptService/Simulator.server.luau",
        "ServerScriptService/SimulatorService.luau",
        "ServerScriptService/ProfileStore.luau",
        "StarterPlayer/StarterPlayerScripts/Simulator.client.luau",
        "ReplicatedStorage/Shared/RateLimiter.luau",
        "ReplicatedStorage/Shared/CostCurve.luau",
        "ReplicatedStorage/Shared/MultiplierMath.luau",
        "ReplicatedStorage/Shared/SimulatorConfig.luau",
    }
    assert expected <= set(built.files)
    tree = ET.fromstring(built.data)
    instances = {(node.attrib["class"], node.findtext("./Properties/string[@name='Name']"))
                 for node in tree.iter("Item")}
    assert ("Script", "Simulator") in instances
    assert ("LocalScript", "Simulator") in instances
    assert ("ModuleScript", "SimulatorService") in instances
    assert ("Folder", "SimulatorRemotes") not in instances  # created by the server


def test_pure_modules_have_no_engine_side_effects():
    for filename in ("RateLimiter.luau", "CostCurve.luau", "MultiplierMath.luau"):
        source = (SHARED / filename).read_text(encoding="utf-8")
        for service_api in ("game:", "game.", "workspace", "DataStoreService", "RemoteEvent",
                            "RemoteFunction", "Instance.new", "task.wait", "os.clock"):
            assert service_api not in source, (filename, service_api)
        assert source.startswith("--!strict\n")
        assert "return " in source


def test_server_is_the_authority_and_persistence_has_a_session_lease():
    server = (SERVER / "Simulator.server.luau").read_text(encoding="utf-8")
    service = (SERVER / "SimulatorService.luau").read_text(encoding="utf-8")
    store = (SERVER / "ProfileStore.luau").read_text(encoding="utf-8")
    client = (ROOT / "StarterPlayer" / "StarterPlayerScripts" / "Simulator.client.luau").read_text(encoding="utf-8")
    assert "OnServerEvent" in server and "Service.apply(" in server
    assert "RateLimiter.allow(requestLimit" in server
    assert "leaderstats" in server and "Coins" in server and "Rebirths" in server
    assert "PlayerRemoving" in server and "BindToClose" in server
    assert "UpdateAsync" in store and "pcall" in store
    assert "sessionId" in store and "profile_in_use" in store and "session_lost" in store
    assert "CostCurve.price(profile.upgradeLevel)" in service
    assert "profile.pets[arg] = true" in service
    assert "profile.runEarned < Config.ZONES[arg].threshold" in service
    assert "RateLimiter.allow(clickLimit" in service
    assert "FireServer" in client and "InvokeServer" in client
    assert "DataStoreService" not in client and "OnServerEvent" not in client


def test_luau_specs_cover_spam_economy_and_save_failure_without_network():
    names = {p.name for p in SPECS.glob("*.spec.luau")}
    assert names == {"RateLimiter.spec.luau", "CostCurve.spec.luau",
                     "MultiplierMath.spec.luau", "SimulatorService.spec.luau",
                     "ProfileStore.spec.luau"}
    for source_file in SPECS.glob("*.spec.luau"):
        text = source_file.read_text(encoding="utf-8")
        assert text.startswith("--!strict\n") and "return {" in text
        assert "function()" in text
    spam = (SPECS / "SimulatorService.spec.luau").read_text(encoding="utf-8")
    assert "999 do" in spam and "i / 1000" in spam and "profile.coins == 4" in spam
    failures = (SPECS / "ProfileStore.spec.luau").read_text(encoding="utf-8")
    assert "session_lost" in failures and "data_store_unavailable" in failures
