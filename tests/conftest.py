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


@pytest.fixture(autouse=True)
def _default_slot_pinning(monkeypatch):
    """The slot rules are tested as the app ships them, whatever the machine's environment says."""
    monkeypatch.delenv("STAR_SERVER_SLOT_PINNING", raising=False)


@pytest.fixture(autouse=True)
def _no_resource_planner(monkeypatch):
    """No test may talk to a real resource planner (star/planner_client.py reads $STAR_PLANNER_URL or
    ~/.star/planner_url). Tests of the planner hand in their own URL or client."""
    monkeypatch.setenv("STAR_PLANNER_URL", "off")
    monkeypatch.setenv("STAR_NS_PLANNER_URL", "off")


@pytest.fixture(autouse=True)
def _offline_slot_probe(monkeypatch):
    """Before a chat turn on STAR Server the app asks the server which slots are busy (issue 118).
    No test may reach a real address for that: by default the page answers "not here", which is the
    probe's no-change path. Tests of the probe install their own transport."""
    import httpx
    import star.providers as providers

    def clear():
        providers._BUSY_SLOTS.clear()
        providers._NO_SLOTS_PAGE.clear()
    clear()
    monkeypatch.delenv("STAR_SERVER_SLOT_PROBE", raising=False)
    monkeypatch.setattr(providers, "_SLOT_PROBE_TRANSPORT", httpx.MockTransport(lambda request: httpx.Response(404)))
    yield
    clear()
