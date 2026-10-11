"""Suite-wide isolation.

STAR reads the owner's Roblox API key from a key file in the home folder (star/roblox_cloud.py). No
test may depend on, or use, the key of the machine it runs on: the file path points nowhere here.
The one live test names the real file itself.
"""
import pytest


@pytest.fixture(autouse=True)
def _no_owner_roblox_key(monkeypatch, tmp_path_factory):
    for name in ("ROBLOX_OPEN_CLOUD_API_KEY", "ROBLOX_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STAR_ROBLOX_KEY_FILE", str(tmp_path_factory.getbasetemp() / "no-roblox-key.env"))
