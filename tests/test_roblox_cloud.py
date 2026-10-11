"""Roblox Open Cloud access: key sources, the Test button, the test-experience guard and approvals.

Everything here runs against tests/roblox_fakes.py. The one test that talks to Roblox is at the end
and is skipped unless the owner's key file exists; it only reads.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType
import xml.etree.ElementTree as ET

import httpx
import pytest

from star import roblox_cloud as rc
from star.roblox_cloud import CloudError, OpenCloud, RobloxCloud
from star.roblox_pipeline import OWNER_STEPS, TEST_HARNESS, run_pipeline, summarize_test
from star.roblox_place import BuildError, build_place
from tests.roblox_fakes import ACCOUNT, FULL_SCOPES, KEY, PLACE, UNIVERSE, FakeRoblox

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "roblox-test-place"
_KEYRING_GET = rc._keyring_get


@pytest.fixture(autouse=True)
def no_real_key(monkeypatch, tmp_path):
    """No test here may see the owner's key file, keyring entry or environment."""
    for name in rc.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(rc.KEY_FILE_ENV, str(tmp_path / "absent.env"))
    vault: dict = {}
    monkeypatch.setattr(rc, "_keyring_get", lambda: vault.get("key"))
    return vault


@pytest.fixture
def fake():
    return FakeRoblox()


@pytest.fixture
def isolated_keyring(monkeypatch, no_real_key):
    """Exercise the real lazy keyring reader against an in-memory module only."""
    module = ModuleType("keyring")
    stored = {}
    module.get_password = lambda service, name: stored.get((service, name))
    module.set_password = lambda service, name, value: stored.update({(service, name): value})
    module.delete_password = lambda service, name: stored.pop((service, name), None)
    monkeypatch.setitem(sys.modules, "keyring", module)
    monkeypatch.setattr(rc, "_keyring_get", _KEYRING_GET)
    return module, stored


def cloud_for(fake, tmp_path, **more) -> RobloxCloud:
    return RobloxCloud(home=tmp_path, key=KEY, source="keyring", client=fake.client(),
                       sleep=lambda _seconds: None, **more)


def ready(fake, tmp_path) -> RobloxCloud:
    cloud = cloud_for(fake, tmp_path)
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    fake.calls.clear()
    return cloud


# ------------------------------------------------------------------ the key file and its sources

def test_key_file_accepts_a_named_line_and_keeps_the_padding():
    assert rc.parse_key_file(f"ROBLOX_OPEN_CLOUD_API_KEY={KEY}\n") == KEY
    assert KEY.endswith("==")                                  # split on the FIRST "=" only
    assert rc.parse_key_file(f'export ROBLOX_OPEN_CLOUD_API_KEY = "{KEY}"\r\n') == KEY
    assert rc.parse_key_file(f"\ufeff# my key\nOTHER=1\nROBLOX_API_KEY={KEY}\n") == KEY


def test_key_file_accepts_a_bare_key_even_when_it_looks_like_an_assignment():
    assert rc.parse_key_file(KEY + "\n") == KEY
    plain = "A" * 40 + "=="            # letters then padding: NAME= with nothing after it is not NAME=value
    assert rc.parse_key_file(plain) == plain
    single = "b" * 43 + "="
    assert rc.parse_key_file("\n  " + single + "  \n") == single


def test_key_file_ignores_other_variables_and_junk():
    assert rc.parse_key_file("") is None
    assert rc.parse_key_file("# nothing\n\n") is None
    assert rc.parse_key_file("GITHUB_TOKEN=" + "x" * 40) is None        # another service's secret is not our key
    assert rc.parse_key_file("too short") is None
    assert rc.parse_key_file("has a space " + "x" * 40) is None


def test_key_sources_in_order(monkeypatch, tmp_path, no_real_key):
    assert rc.load_key() == (None, "") and rc.key_present() is False
    path = tmp_path / "star.env"
    path.write_text(f"ROBLOX_OPEN_CLOUD_API_KEY={KEY}\n", encoding="utf-8")
    monkeypatch.setenv(rc.KEY_FILE_ENV, str(path))
    assert rc.load_key() == (KEY, "file")
    no_real_key["key"] = "K" * 50
    assert rc.load_key() == ("K" * 50, "keyring")
    monkeypatch.setenv("ROBLOX_OPEN_CLOUD_API_KEY", "E" * 50)
    assert rc.load_key() == ("E" * 50, "environment")


def test_saving_goes_to_the_keyring_and_a_failure_never_repeats_the_key(monkeypatch, tmp_path, isolated_keyring):
    keyring, stored = isolated_keyring
    # Core installs may omit the desktop keyring dependency. That still supports
    # the owner-selected key file and a sanitized refusal to save in the vault.
    with monkeypatch.context() as missing:
        missing.setitem(sys.modules, "keyring", None)
        assert rc.load_key() == (None, "")
        path = tmp_path / "star.env"
        path.write_text(f"ROBLOX_OPEN_CLOUD_API_KEY={KEY}\n", encoding="utf-8")
        missing.setenv(rc.KEY_FILE_ENV, str(path))
        assert rc.load_key() == (KEY, "file")
        with pytest.raises(CloudError) as unavailable:
            rc.save_key(KEY)
        assert KEY not in str(unavailable.value) and "star.env" in str(unavailable.value)
        rc.clear_key()
        assert stored == {}
    rc.save_key("  " + KEY + "\n")
    assert stored == {("STAR Intelligence", "roblox_open_cloud"): KEY}
    assert rc.load_key() == (KEY, "keyring")
    for bad in ("", "short", "with space " + "x" * 30, None, 7):
        with pytest.raises(CloudError):
            rc.save_key(bad)

    def explode(*_):
        raise RuntimeError("vault says: " + KEY)
    monkeypatch.setattr(keyring, "set_password", explode)
    with pytest.raises(CloudError) as caught:
        rc.save_key(KEY)
    assert KEY not in str(caught.value) and "star.env" in str(caught.value)


# ------------------------------------------------------------------ the Test button

def test_no_key_is_a_state_not_an_error(tmp_path):
    cloud = RobloxCloud(home=tmp_path)
    assert cloud.status()["state"] == "no_key"
    assert cloud.check_key()["state"] == "no_key"
    with pytest.raises(CloudError):
        cloud.universe(UNIVERSE)


def test_a_valid_key_reports_capabilities_by_status_and_never_the_key(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    assert cloud.status()["state"] == "unchecked"
    report = cloud.check_key()
    assert report["state"] == "valid" and report["missing"] == []
    assert report["account"] == {"user_id": ACCOUNT, "name": "StarOwnAccount"}
    assert [call["status"] for call in report["calls"]] == [200, 200, 200, 200, 200]
    granted = {item["id"]: item for item in report["capabilities"]}
    assert granted["publish_place"]["granted"] and granted["publish_place"]["evidence"] == "the key's scope list"
    assert granted["experience_info"]["status"] == 200 and granted["experience_info"]["evidence"] == "read call"
    assert granted["list_data_stores"]["status"] == 200
    assert granted["publish_message"]["granted"] is False
    assert fake.writes() == []                                    # the check only reads
    assert cloud.status()["state"] == "valid"
    everything = json.dumps([report, cloud.status()]) + (tmp_path / "roblox" / "access.json").read_text()
    assert KEY not in everything and KEY[:12] not in everything
    assert fake.seen_keys == {KEY}


def test_missing_permission_names_what_to_tick(tmp_path):
    fake = FakeRoblox(scopes=[FULL_SCOPES[0]])                    # can publish, cannot run Luau
    report = cloud_for(fake, tmp_path).check_key()
    assert report["state"] == "missing_permission"
    assert report["missing"] == ["universe.place.luau-execution-session:write"]
    assert any("No test experience" in text for text in report["warnings"])


def test_a_scope_limited_to_another_experience_does_not_count(tmp_path):
    scopes = [{**scope, "universeIds": ["555"]} for scope in FULL_SCOPES]
    fake = FakeRoblox(scopes=scopes)
    cloud = ready(fake, tmp_path)
    assert cloud.check_key()["state"] == "missing_permission"
    with pytest.raises(CloudError, match="universe-places:write"):
        cloud.publish_place(b"<roblox/>")
    assert fake.writes() == []


@pytest.mark.parametrize("change, reason", [({"revoked": True}, "rejected"), ({"enabled": False}, "disabled"),
                                             ({"expired": True}, "expired")])
def test_revoked_disabled_and_expired_keys(tmp_path, change, reason):
    fake = FakeRoblox()
    for name, value in change.items():
        setattr(fake, name, value)
    report = cloud_for(fake, tmp_path).check_key()
    assert (report["state"], report["reason"]) == ("revoked", reason)
    assert len(report["calls"]) == 1                              # nothing else is asked with a dead key


def test_text_that_is_not_a_key_and_an_unreachable_service(tmp_path):
    fake = FakeRoblox()
    cloud = RobloxCloud(home=tmp_path, key="x" * 30, source="file", client=fake.client())
    assert cloud.check_key()["state"] == "invalid"

    def offline(request):
        raise httpx.ConnectError("no route to host for " + request.headers.get("x-api-key", "introspect"))
    cloud = RobloxCloud(home=tmp_path, key=KEY, client=httpx.Client(transport=httpx.MockTransport(offline)))
    report = cloud.check_key()
    assert report["state"] == "unreachable" and KEY not in json.dumps(report)


def test_a_result_for_one_key_is_not_shown_for_another(fake, tmp_path):
    cloud_for(fake, tmp_path).check_key()
    other = RobloxCloud(home=tmp_path, key="Z" * 60, source="file", client=fake.client())
    assert other.status()["state"] == "unchecked" and other.status()["last_check"] is None


def test_the_spending_scopes_of_a_broad_key_are_pointed_out(tmp_path):
    fake = FakeRoblox(scopes=FULL_SCOPES + [
        {"name": "legacy-universe.badge", "operations": ["manage-and-spend-robux"]},
        {"name": "developer-product", "operations": ["read", "write"]}])
    report = cloud_for(fake, tmp_path).check_key()
    assert report["state"] == "valid" and "2 permission groups STAR never uses" in report["warnings"][0]


# ------------------------------------------------------------------ only documented endpoints

def test_only_catalogued_endpoints_can_be_called(fake):
    api = OpenCloud(KEY, client=fake.client())
    for name in ("publish_message", "restart_servers", "asset_create", "nonsense"):
        with pytest.raises(CloudError):
            api.call(name, universe=UNIVERSE)
    for bad in ("1/../2", -1, 0, 1.5, True, "12a", None):
        with pytest.raises(CloudError):
            api.call("universe", universe=bad)
    with pytest.raises(CloudError):
        api.call("luau_task", universe=1, place=2, version=3, session="a/b", task="t")
    assert fake.calls == []


def test_the_catalogue_cites_the_official_documentation():
    ids = [item.id for item in rc.ENDPOINTS]
    assert len(ids) == len(set(ids))
    for item in rc.ENDPOINTS:
        assert item.doc.startswith("https://create.roblox.com/docs/cloud/"), item.id
        assert item.method in ("GET", "POST") and item.path.startswith("/") and item.scope and item.limit
    written = (REPO / "docs" / "ROBLOX_ACCESS.md").read_text(encoding="utf-8")
    for item in rc.ENDPOINTS:
        assert item.path in written, f"docs/ROBLOX_ACCESS.md does not list {item.path}"


def test_universe_and_place_reads(fake, tmp_path):
    cloud = cloud_for(fake, tmp_path)
    assert cloud.universe(UNIVERSE)["metadata"]["visibility"] == "PRIVATE"
    assert cloud.place(UNIVERSE, PLACE)["metadata"]["serverSize"] == 10
    with pytest.raises(CloudError, match="HTTP 404"):
        cloud.universe(123)
    with pytest.raises(CloudError):
        cloud.data_stores()                                       # no test experience yet
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    assert cloud.data_stores()["data_stores"] == ["Coins"]


# ------------------------------------------------------------------ the test experience

def test_only_the_owner_chooses_the_test_experience(fake, tmp_path):
    cloud = cloud_for(fake, tmp_path)
    with pytest.raises(PermissionError):
        cloud.set_test_experience(UNIVERSE, PLACE)
    chosen = cloud.set_test_experience(str(UNIVERSE), PLACE, human_approved=True)
    assert chosen["owner_user_id"] == ACCOUNT and cloud.status()["test_experience"]["place_id"] == PLACE


def test_refuses_everything_that_is_not_its_own_private_place(fake, tmp_path):
    cloud = cloud_for(fake, tmp_path)
    fake.universes[1] = {"user": "users/999", "visibility": "PRIVATE", "rootPlace": "universes/1/places/11"}
    fake.universes[2] = {"group": "groups/5", "visibility": "PRIVATE", "rootPlace": "universes/2/places/22"}
    fake.universes[3] = {"user": f"users/{ACCOUNT}", "visibility": "PUBLIC", "rootPlace": "universes/3/places/33"}
    denied = next(iter(rc.DENIED_PLACE_IDS))
    fake.universes[4] = {"user": f"users/{ACCOUNT}", "visibility": "PRIVATE",
                         "rootPlace": f"universes/4/places/{denied}"}
    fake.places.update({(1, 11): {}, (2, 22): {}, (3, 33): {}, (4, 44): {}})
    for universe, place, why in ((1, 11, "not owned"), (2, 22, "not owned"), (3, 33, "public"),
                                 (4, 44, "deny-list"), (UNIVERSE, denied, "deny-list"),
                                 (UNIVERSE, 123456, "was not found")):
        with pytest.raises(CloudError, match=why):
            cloud.set_test_experience(universe, place, human_approved=True)
    assert cloud.status()["test_experience"] is None
    assert 129870808752914 in rc.DENIED_PLACE_IDS


def test_every_write_checks_the_experience_again(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    fake.universes[UNIVERSE]["visibility"] = "PUBLIC"             # it was made public afterwards
    with pytest.raises(CloudError, match="public"):
        cloud.publish_place(b"<roblox/>")
    with pytest.raises(CloudError, match="public"):
        cloud.run_luau("return 1")
    fake.universes[UNIVERSE]["visibility"] = "PRIVATE"
    fake.account = 31337                                          # the stored key is now another account's
    with pytest.raises(CloudError, match="another account"):
        cloud.publish_place(b"<roblox/>")
    assert fake.writes() == []


def test_no_write_without_a_test_experience(fake, tmp_path):
    cloud = cloud_for(fake, tmp_path)
    for attempt in (lambda: cloud.publish_place(b"<roblox/>"), lambda: cloud.run_luau("return 1"),
                    lambda: cloud.request_action("publish", "x", {})):
        with pytest.raises(CloudError, match="No test experience"):
            attempt()
    assert fake.calls == []


# ------------------------------------------------------------------ publish and Luau execution

def test_publish_sends_the_file_as_a_saved_version(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    data = build_place(EXAMPLE).data
    result = cloud.publish_place(data)
    assert result["version"] == 4 and result["version_type"] == "Saved" and result["sha256"] == hashlib.sha256(data).hexdigest()
    sent = fake.published[0]
    assert (sent["universe"], sent["place"], sent["version_type"]) == (UNIVERSE, PLACE, "Saved")
    assert sent["content_type"] == "application/xml" and sent["bytes"] == data
    with pytest.raises(CloudError):
        cloud.publish_place(data, version_type="Live")
    with pytest.raises(CloudError):
        cloud.publish_place(b"")
    fake.fail["publish"] = 409
    with pytest.raises(CloudError, match="Team Create"):
        cloud.publish_place(data)


def test_a_test_run_waits_for_the_task_and_collects_result_and_logs(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    record = cloud.run_luau(TEST_HARNESS, version=4)
    assert record["state"] == "COMPLETE" and record["version"] == 4 and "error" not in record
    assert record["http"] == {"create": 200, "task": 200} and record["logs_http"] == 200
    assert record["output"]["results"][0]["passed"] == 2 and record["logs"][0].startswith("STAR_TEST_RESULT")
    assert ("POST", f"/cloud/v2/universes/{UNIVERSE}/places/{PLACE}/versions/4/luau-execution-session-tasks") in fake.calls
    assert next(iter(fake.tasks.values()))["script"] == TEST_HARNESS
    assert summarize_test(record)["passed"] == 2


def test_a_failed_script_a_slow_task_and_a_refused_start(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    fake.task_result = {"state": "FAILED", "error": {"code": "SCRIPT_ERROR", "message": "attempt to index nil"}}
    record = cloud.run_luau("error('x')")
    assert record["state"] == "FAILED" and record["task_error"]["message"] == "attempt to index nil"

    fake.polls_before_done = 10 ** 6
    clock = iter(range(0, 10 ** 6, 100))
    slow = RobloxCloud(home=tmp_path, key=KEY, client=fake.client(), now=lambda: next(clock), sleep=lambda _s: None)
    record = slow.run_luau("while true do task.wait() end", wait_seconds=250)
    assert record["state"] == "TIMED_OUT" and "did not finish" in record["error"]

    fake.fail["create"] = 429
    record = cloud.run_luau("return 1")
    assert record["state"] == "NOT_CREATED" and "rate limiting" in record["error"]


def test_a_task_path_for_another_place_is_not_followed(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    fake.task_path_override = "universes/1/places/2/versions/3/luau-execution-sessions/s/tasks/t"
    record = cloud.run_luau("return 1")
    assert record["state"] == "NOT_CREATED"
    assert not any("/universes/1/" in path for _method, path in fake.calls)
    fake.task_path_override = f"universes/{UNIVERSE}/places/{PLACE}/versions/3/../../../../x/tasks/t"
    assert cloud.run_luau("return 1")["state"] == "NOT_CREATED"


# ------------------------------------------------------------------ approvals

def test_a_model_request_is_only_a_pending_action(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    action = cloud.request_action("run_test", "Run the shop tests", {"script": "return 1", "version": None})
    assert action["status"] == "pending" and action["target"]["place_id"] == PLACE
    assert action["detail"]["script_chars"] == 8 and "script" not in action["detail"]
    assert fake.calls == [] and cloud.status()["pending_actions"] == 1
    with pytest.raises(PermissionError):
        cloud.decide(action["id"], approved=True)                 # no owner click, no run
    assert fake.writes() == []


def test_an_approved_action_runs_exactly_once(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    action = cloud.request_action("run_test", "Run the shop tests", {"script": TEST_HARNESS, "version": None})
    done = cloud.decide(action["id"], approved=True, human_approved=True)
    assert done["status"] == "done" and done["result"]["state"] == "COMPLETE"
    assert len(fake.tasks) == 1
    with pytest.raises(CloudError, match="already done"):
        cloud.decide(action["id"], approved=True, human_approved=True)
    assert len(fake.tasks) == 1 and cloud.action(action["id"])["result"]["logs"]


def test_rejected_and_expired_actions_never_run(fake, tmp_path):
    moment = [1000.0]
    cloud = RobloxCloud(home=tmp_path, key=KEY, client=fake.client(), now=lambda: moment[0], sleep=lambda _s: None)
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    first = cloud.request_action("run_test", "one", {"script": "return 1"})
    assert cloud.decide(first["id"], approved=False, human_approved=True)["status"] == "rejected"
    second = cloud.request_action("run_test", "two", {"script": "return 2"})
    moment[0] += rc.ACTION_TTL + 1
    with pytest.raises(CloudError, match="already expired"):
        cloud.decide(second["id"], approved=True, human_approved=True)
    assert fake.writes() == []


def test_the_approved_place_file_is_the_one_that_is_published(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    build = build_place(EXAMPLE)
    digest = cloud.store_build(build.data)
    action = cloud.request_action("publish", "Publish the shop", {"sha256": digest, "bytes": len(build.data)})
    assert cloud.decide(action["id"], approved=True, human_approved=True)["result"]["version"] == 4
    assert fake.published[0]["bytes"] == build.data

    action = cloud.request_action("publish", "Publish again", {"sha256": digest, "bytes": len(build.data)})
    (tmp_path / "roblox" / "builds" / (digest + ".rbxlx")).write_bytes(b"<roblox>swapped</roblox>")
    failed = cloud.decide(action["id"], approved=True, human_approved=True)
    assert failed["status"] == "failed" and "changed after" in failed["result"]["error"]
    assert len(fake.published) == 1


def test_waiting_actions_are_limited(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    for number in range(rc.MAX_PENDING):
        cloud.request_action("run_test", f"run {number}", {"script": "return 1"})
    with pytest.raises(CloudError, match="Too many"):
        cloud.request_action("run_test", "one more", {"script": "return 1"})
    with pytest.raises(CloudError):
        cloud.request_action("delete_everything", "no", {})


def test_the_interface_actions(fake, tmp_path, isolated_keyring):
    _keyring, stored = isolated_keyring
    ask = lambda action, **body: rc.handle_action(tmp_path, action, body, client=fake.client())  # noqa: E731
    assert ask("robloxStatus")["state"] == "no_key"
    saved = ask("robloxSaveKey", key=KEY)
    assert saved["key_present"] and saved["source"] == "keyring" and KEY not in json.dumps(saved)
    assert stored == {("STAR Intelligence", "roblox_open_cloud"): KEY}
    tested = ask("robloxTestKey")
    assert tested["check"]["state"] == "valid" and KEY not in json.dumps(tested)
    with pytest.raises(PermissionError):
        ask("robloxSetTestExperience", universe_id=UNIVERSE, place_id=PLACE)
    assert ask("robloxSetTestExperience", universe_id=UNIVERSE, place_id=PLACE,
               approved=True)["test_experience"]["universe_id"] == UNIVERSE
    cloud = RobloxCloud(home=tmp_path, client=fake.client())
    action = cloud.request_action("run_test", "Run", {"script": "return 1"})
    assert ask("robloxListActions")["actions"][0]["id"] == action["id"]
    with pytest.raises(PermissionError):
        ask("robloxDecideAction", id=action["id"], decision="approve")
    assert ask("robloxDecideAction", id=action["id"], decision="approve", approved=True)["action"]["status"] == "done"
    assert ask("robloxClearTestExperience")["test_experience"] is None
    assert ask("robloxClearKey")["state"] == "no_key"
    assert stored == {} and rc.load_key() == (None, "")
    with pytest.raises(PermissionError):
        rc.handle_action(tmp_path, "publishRobloxGame", {})


# ------------------------------------------------------------------ the place builder

def test_the_example_place_builds_to_the_expected_tree():
    build = build_place(EXAMPLE)
    assert build.builder == "star-builtin" and build.sha256 == build_place(EXAMPLE).sha256    # same bytes again
    assert build.files == ("ReplicatedStorage/Shared/Catalog.luau", "ServerScriptService/Shop.luau",
                           "ServerScriptService/Tests/Shop.spec.luau")
    root = ET.fromstring(build.data)
    assert root.tag == "roblox" and root.get("version") == "4"

    def tree(item):
        name = item.find("Properties/string[@name='Name']").text
        return (item.get("class"), name, [tree(child) for child in item.findall("Item")])
    assert [tree(item) for item in root.findall("Item")] == [
        ("ReplicatedStorage", "ReplicatedStorage", [("Folder", "Shared", [("ModuleScript", "Catalog", [])])]),
        ("ServerScriptService", "ServerScriptService", [
            ("ModuleScript", "Shop", []), ("Folder", "Tests", [("ModuleScript", "Shop.spec", [])])])]
    source = root.find(".//Item[@class='ModuleScript']/Properties/ProtectedString[@name='Source']").text
    assert source == (EXAMPLE / "ReplicatedStorage/Shared/Catalog.luau").read_text(encoding="utf-8")
    referents = [item.get("referent") for item in root.iter("Item")]
    assert len(referents) == len(set(referents)) == build.instances == 7


def test_script_kinds_init_files_and_awkward_text(tmp_path):
    (tmp_path / "ServerScriptService" / "Shop").mkdir(parents=True)
    (tmp_path / "StarterPlayer" / "StarterPlayerScripts").mkdir(parents=True)
    (tmp_path / "ServerScriptService" / "Main.server.luau").write_text("print('a ]]> b <&> é')\r\n", encoding="utf-8")
    (tmp_path / "ServerScriptService" / "Shop" / "init.lua").write_text("return {}", encoding="utf-8")
    (tmp_path / "ServerScriptService" / "Shop" / "Prices.luau").write_text("return {}", encoding="utf-8")
    (tmp_path / "ServerScriptService" / "notes.md").write_text("ignored", encoding="utf-8")
    (tmp_path / "StarterPlayer" / "StarterPlayerScripts" / "Hud.client.luau").write_text("-- hud", encoding="utf-8")
    (tmp_path / "NotAService").mkdir()
    (tmp_path / "NotAService" / "X.luau").write_text("return 1", encoding="utf-8")
    root = ET.fromstring(build_place(tmp_path).data)
    classes = {item.find("Properties/string[@name='Name']").text: item.get("class") for item in root.iter("Item")}
    assert classes == {"ServerScriptService": "ServerScriptService", "Main": "Script", "Shop": "ModuleScript",
                       "Prices": "ModuleScript", "StarterPlayer": "StarterPlayer",
                       "StarterPlayerScripts": "StarterPlayerScripts", "Hud": "LocalScript"}
    main = root.find(".//Item[@class='Script']/Properties/ProtectedString").text
    assert main == "print('a ]]> b <&> é')\n"


def test_the_builder_refuses_what_it_cannot_represent(tmp_path):
    with pytest.raises(BuildError):
        build_place(tmp_path / "missing")
    with pytest.raises(BuildError, match="No Luau source"):
        build_place(tmp_path)
    service = tmp_path / "ServerScriptService"
    service.mkdir()
    (service / "init.luau").write_text("return 1", encoding="utf-8")
    with pytest.raises(BuildError, match="init script"):
        build_place(tmp_path)
    (service / "init.luau").unlink()
    (service / "A.luau").write_text("return 1", encoding="utf-8")
    (service / "A.server.luau").write_text("return 1", encoding="utf-8")
    with pytest.raises(BuildError, match="same name"):
        build_place(tmp_path)
    (service / "A.server.luau").unlink()
    (service / "B.luau").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(BuildError, match="UTF-8|Not text"):
        build_place(tmp_path)


# ------------------------------------------------------------------ the whole pipeline

def test_the_pipeline_end_to_end_against_the_fake(fake, tmp_path):
    cloud = ready(fake, tmp_path)
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] and [step["step"] for step in report["steps"]] == [
        "build", "key", "test experience", "publish", "run test", "result"]
    assert report["steps"][3]["version"] == 4 and report["steps"][4]["version"] == 4     # the version just published
    assert report["steps"][5]["summary"]["failed"] == 0
    assert KEY not in json.dumps(report)


def test_the_pipeline_stops_and_tells_the_owner_what_to_create(fake, tmp_path):
    report = run_pipeline(cloud_for(fake, tmp_path), EXAMPLE, publish_and_test=True)
    assert not report["ok"] and report["stopped_at"] == "test experience"
    assert report["owner_action"] == OWNER_STEPS and "Publish to Roblox" in OWNER_STEPS
    assert fake.writes() == []
    assert run_pipeline(RobloxCloud(home=tmp_path / "none"), EXAMPLE)["stopped_at"] == "key"


def test_without_the_owners_flag_nothing_is_published(fake, tmp_path):
    report = run_pipeline(ready(fake, tmp_path), EXAMPLE)
    assert report["ok"] and report["stopped_at"] == "publish" and fake.writes() == []


def test_failing_tests_fail_the_pipeline_and_the_log_line_is_enough(fake, tmp_path):
    fake.task_result = {"state": "COMPLETE", "output": {}}        # no returned value: read the marked log line
    fake.logs = ["hello", 'STAR_TEST_RESULT {"passed":0,"failed":1,"cases":[{"name":"a","ok":false,"message":"boom"}]}']
    report = run_pipeline(ready(fake, tmp_path), EXAMPLE, publish_and_test=True)
    assert not report["ok"]
    assert report["steps"][-1]["summary"] == {"passed": 0, "failed": 1,
                                              "cases": [{"name": "a", "ok": False, "message": "boom"}]}
    assert summarize_test({"logs": ["nothing useful"]}) is None


# ------------------------------------------------------------------ live, read only

OWNER_KEY_FILE = Path.home() / ".star" / "star.env"


@pytest.mark.skipif(not OWNER_KEY_FILE.is_file() or os.environ.get("STAR_SKIP_LIVE") == "1",
                    reason="needs the owner's Roblox key file; reads only")
def test_live_open_cloud_read_with_the_owners_key(monkeypatch, tmp_path, capsys):
    """One real, harmless round trip: the key describes itself and its own account is read."""
    monkeypatch.setenv(rc.KEY_FILE_ENV, str(OWNER_KEY_FILE))
    key, source = rc.load_key()
    if key is None:
        pytest.skip("the key file holds no usable key")
    cloud = RobloxCloud(home=tmp_path)
    try:
        report = cloud.check_key()
    finally:
        cloud.close()
    if report["state"] == "unreachable":
        pytest.skip("Roblox could not be reached from here")
    assert source == "file" and report["state"] in ("valid", "missing_permission", "revoked", "invalid")
    assert report["calls"][0] == {"call": "the key describes itself", "status": report["calls"][0]["status"]}
    if report["state"] in ("valid", "missing_permission"):
        assert report["calls"][0]["status"] == 200 and type(report["account"]["user_id"]) is int
        assert {item["id"] for item in report["capabilities"]} >= {"publish_place", "run_luau"}
    text = json.dumps(report) + (tmp_path / "roblox" / "access.json").read_text() + capsys.readouterr().out
    assert key not in text and key[:16] not in text and key[-16:] not in text
