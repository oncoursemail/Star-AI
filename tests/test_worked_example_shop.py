"""Standalone server-owned shop: complete wiring and native Luau specification coverage."""
from pathlib import Path
import shutil

import pytest

from scripts import run_luau_specs as runner

ROOT = Path(__file__).resolve().parents[1]
SHOP = ROOT / "examples" / "roblox" / "shop"


def test_server_validates_purchase_never_uses_client_price():
    server = (SHOP / "ServerScriptService/ShopServer.server.luau").read_text()
    core = (SHOP / "ServerScriptService/ShopCore.luau").read_text()
    inv = (SHOP / "ServerScriptService/Inventory.luau").read_text()
    client = (SHOP / "StarterPlayer/StarterPlayerScripts/ShopClient.client.luau").read_text()
    assert "remote.OnServerInvoke" in server and "Shop.purchase" in server
    assert "Shop.rollback" in server and "Shop.confirm" in server
    assert "Shop.ownedIds" in server and "PlayerRemoving" in server
    assert "clientPrice ~= nil" in core and "state.prices[itemId]" in core
    assert "Inventory.grantOnce" in core and "Inventory.revoke" in core
    assert "game:GetService" not in core and "game:GetService" not in inv
    assert "Remote:InvokeServer(itemId, 1)" in client
    assert "Remote:InvokeServer(itemId, 1," not in client


def test_project_has_catalog_server_inventory_client_readme_and_native_spec():
    paths = (
        "README.md", "ReplicatedStorage/ShopCatalog.luau",
        "ServerScriptService/Inventory.luau",
        "ServerScriptService/ShopCore.luau",
        "ServerScriptService/ShopServer.server.luau",
        "ServerScriptService/Tests/ShopCore.spec.luau",
        "StarterPlayer/StarterPlayerScripts/ShopClient.client.luau",
    )
    assert all((SHOP / path).is_file() for path in paths)
    core_spec = (SHOP / "ServerScriptService/Tests/ShopCore.spec.luau").read_text()
    assert core_spec.count('"] = function()') >= 13
    assert "client fabricated price" in core_spec
    assert "double click" in core_spec
    readme = (SHOP / "README.md").read_text()
    assert "session-only" in readme and "Studio" in readme


def test_actual_existing_spec_runner_stages_shop_core_unmodified(tmp_path):
    stage = tmp_path / "staged"
    stage.mkdir()
    runner.stage_sources(ROOT / "examples", stage)
    source = SHOP / "ServerScriptService/ShopCore.luau"
    staged = stage / "roblox/shop/ServerScriptService/ShopCore.luau"
    spec = stage / "roblox/shop/ServerScriptService/Tests/ShopCore.spec.luau"
    assert staged.read_bytes() == source.read_bytes()
    assert spec.is_file()
    assert 'require("../ShopCore")' in spec.read_text()
    assert 'require("../../ReplicatedStorage/ShopCatalog")' in spec.read_text()


@pytest.mark.skipif(shutil.which("luau") is None, reason="pinned native Luau specs CI executes the cases")
def test_native_runner_executes_shop_rules_and_negative_cases():
    assert runner.run(shutil.which("luau"), ROOT / "examples") == 0
