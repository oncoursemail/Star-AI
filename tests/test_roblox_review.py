"""Findings of the independent review of the Roblox access work, each one as a test.

Every test here failed on the reviewed head (ee4b0dd) and passes after its fix. Open Cloud runs
against tests/roblox_fakes.py and Studio against tests/studio_fake.py; nothing talks to Roblox.
"""
import asyncio
import hashlib

import httpx
import pytest

from star import roblox_cloud as rc, studio_loop as sl
from star.roblox_cloud import CloudError, RobloxCloud
from star.roblox_pipeline import run_pipeline
from star.roblox_place import build_place
from star.studio import list_tools
from tests.roblox_fakes import ACCOUNT, KEY, PLACE, UNIVERSE, FakeRoblox
from tests.studio_fake import TOOLS, FakeStudio
from tests.test_roblox_cloud import EXAMPLE

DENIED_PLACE, DENIED_UNIVERSE = 129870808752914, 10767753099
SID = "studio-1"


@pytest.fixture(autouse=True)
def no_real_key(monkeypatch, tmp_path):
    for name in rc.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(rc.KEY_FILE_ENV, str(tmp_path / "absent.env"))
    monkeypatch.setattr(rc, "_keyring_get", lambda: None)


@pytest.fixture
def fake():
    return FakeRoblox()


def cloud_on(handler, tmp_path) -> RobloxCloud:
    return RobloxCloud(home=tmp_path, key=KEY, source="keyring", sleep=lambda _seconds: None,
                       client=httpx.Client(transport=httpx.MockTransport(handler)))


def ready(fake, tmp_path, handler=None) -> RobloxCloud:
    cloud = cloud_on(fake.handle, tmp_path)
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    fake.calls.clear()
    return cloud if handler is None else cloud_on(handler, tmp_path)


def own_private(fake, universe: int, root_place: int, *places: int) -> None:
    fake.universes[universe] = {"user": f"users/{ACCOUNT}", "visibility": "PRIVATE", "displayName": "Other",
                                "rootPlace": f"universes/{universe}/places/{root_place}"}
    for place in (root_place, *places):
        fake.places[(universe, place)] = {"path": f"universes/{universe}/places/{place}"}


def run(coroutine):
    return asyncio.run(coroutine)


async def opened(fake, **settings):
    settings.setdefault("opted_in", True)
    return await sl.open_guarded(fake, await list_tools(fake), studio_id=fake.studio_id, **settings)


# ------------------------------------------------------------------ 1. the deny-list names the experience too

def test_no_place_of_the_denied_experience_can_be_the_target(fake, tmp_path):
    """The denied place is one place of an experience. A second place of that experience, which is
    not its start place, got past a list that only held the one place id."""
    assert DENIED_PLACE in rc.DENIED_PLACE_IDS and DENIED_UNIVERSE in rc.DENIED_UNIVERSE_IDS
    own_private(fake, DENIED_UNIVERSE, 501, 502)
    cloud = cloud_on(fake.handle, tmp_path)
    for place in (501, 502):
        with pytest.raises(CloudError, match="deny-list"):
            cloud.set_test_experience(DENIED_UNIVERSE, place, human_approved=True)
    assert fake.calls == []                                   # refused before anything is asked of Roblox
    assert cloud.status()["test_experience"] is None
    assert cloud.status()["denied_universe_ids"] == [DENIED_UNIVERSE]


def test_a_saved_choice_of_the_denied_experience_never_gets_a_write(fake, tmp_path):
    own_private(fake, DENIED_UNIVERSE, 501, 502)
    cloud = cloud_on(fake.handle, tmp_path)
    rc._write_json(tmp_path / "roblox" / "access.json", {"test_experience": {
        "universe_id": DENIED_UNIVERSE, "place_id": 502, "owner_user_id": ACCOUNT, "name": "x"}})
    for attempt in (lambda: cloud.publish_place(b"<roblox/>"), lambda: cloud.run_luau("return 1")):
        with pytest.raises(CloudError, match="deny-list"):
            attempt()
    assert fake.writes() == []


def test_studio_never_edits_another_place_of_the_denied_experience():
    facts = dict(place_id=502, game_id=DENIED_UNIVERSE, creator_id=4242, creator_type="User", name="Lobby",
                 scripts=4, marker=True)
    verdict = sl.judge(sl.PlaceIdentity(**facts), opted_in=True, own_places=True, own_account_id=4242)
    assert (verdict.kind, verdict.editable) == ("denied", False)
    fake_studio = FakeStudio(name="Lobby", place_id=502, game_id=DENIED_UNIVERSE, creator_id=4242)
    studio = run(opened(fake_studio, own_places=True, own_account_id=4242))
    assert studio.verdict.kind == "denied" and not studio.verdict.editable
    # A universe id in the instance name is enough to ask that place nothing at all.
    named = FakeStudio(name=f"Lobby [{DENIED_UNIVERSE}]", place_id=502, game_id=DENIED_UNIVERSE, creator_id=4242)
    run(opened(named, own_places=True, own_account_id=4242))
    assert named.names() == ["list_roblox_studios"]


# ------------------------------------------------------------------ 2. an approval is for the place it named

def test_an_approval_is_not_carried_over_to_another_test_experience(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    digest = cloud.store_build(build_place(EXAMPLE).data)
    publish = cloud.request_action("publish", "Publish the shop", {"sha256": digest})
    test = cloud.request_action("run_test", "Run the shop tests", {"script": "return 1"})
    assert publish["target"]["place_id"] == PLACE
    own_private(fake, 7002, 9002)
    cloud.set_test_experience(7002, 9002, human_approved=True)      # the owner chose another one meanwhile
    for action in (publish, test):
        done = cloud.decide(action["id"], approved=True, human_approved=True)
        assert done["status"] == "failed" and "another test experience" in done["result"]["error"]
    assert fake.writes() == [] and fake.published == [] and fake.tasks == {}


