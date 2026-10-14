"""Pipeline regressions use authored Open Cloud responses and disposable profiles only."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from star import roblox_cloud as rc
from star.roblox_pipeline import RESULT_MARK, run_pipeline, summarize_test
from tests.roblox_fakes import ACCOUNT, KEY, PLACE, UNIVERSE, FakeRoblox

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "roblox-test-place"
GOOD = {"passed": 1, "failed": 0, "cases": [{"name": "Example.spec: actual case", "ok": True}]}


@pytest.fixture
def setup_cloud(monkeypatch, tmp_path):
    for name in rc.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(rc.KEY_FILE_ENV, str(tmp_path / "absent.env"))
    monkeypatch.setattr(rc, "_keyring_get", lambda: None)
    fake = FakeRoblox()
    cloud = rc.RobloxCloud(home=tmp_path, key=KEY, source="authored-fake",
                           client=fake.client(), sleep=lambda _: None)
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    fake.universes[7002] = {"user": f"users/{ACCOUNT}", "visibility": "PRIVATE",
                            "rootPlace": "universes/7002/places/9002"}
    fake.places[(7002, 9002)] = {"path": "universes/7002/places/9002"}
    fake.calls.clear()
    yield cloud, fake
    cloud.close()


@pytest.mark.parametrize("switch_at", ["before_publish", "after_publish"])
def test_owner_choice_change_does_not_move_pipeline_approval(setup_cloud, monkeypatch, switch_at):
    cloud, fake = setup_cloud
    original = cloud.publish_place

    def switched(*args, **kwargs):
        if switch_at == "before_publish":
            cloud.set_test_experience(7002, 9002, human_approved=True)
        published = original(*args, **kwargs)
        if switch_at == "after_publish":
            cloud.set_test_experience(7002, 9002, human_approved=True)
        return published

    monkeypatch.setattr(cloud, "publish_place", switched)
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is False
    assert report["stopped_at"] == ("publish" if switch_at == "before_publish" else "run test")
    assert not fake.tasks
    assert all((entry["universe"], entry["place"]) == (UNIVERSE, PLACE)
               for entry in fake.published)
    if switch_at == "before_publish":
        assert not fake.published
    else:
        assert len(fake.published) == 1


def test_publish_and_test_share_pinned_target_and_exact_saved_version(setup_cloud, monkeypatch):
    cloud, fake = setup_cloud
    calls = []
    original_publish, original_run = cloud.publish_place, cloud.run_luau

    def publish(*args, **kwargs):
        calls.append(("publish", kwargs.get("only"), kwargs.get("version_type")))
        return original_publish(*args, **kwargs)

    def run(*args, **kwargs):
        calls.append(("test", kwargs.get("only"), kwargs.get("version")))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(cloud, "publish_place", publish)
    monkeypatch.setattr(cloud, "run_luau", run)
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is True
    assert calls == [("publish", (UNIVERSE, PLACE), "Saved"), ("test", (UNIVERSE, PLACE), 4)]
    assert fake.published[0]["version_type"] == "Saved"
    assert "/versions/4/" in next(iter(fake.tasks))


@pytest.mark.parametrize("change", [
    {"universe_id": 7002}, {"place_id": 9002}, {"place_id": str(PLACE)},
    {"version": None}, {"version": False}, {"version": 0}, {"version": -1},
    {"version": "4"}, {"version_type": "Published"},
])
def test_unconfirmed_publish_result_does_not_start_a_test(setup_cloud, monkeypatch, change):
    cloud, fake = setup_cloud
    original = cloud.publish_place

    def changed(*args, **kwargs):
        return {**original(*args, **kwargs), **change}

    monkeypatch.setattr(cloud, "publish_place", changed)
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is False and report["stopped_at"] == "publish"
    assert report["steps"][-1]["detail"]
    assert not fake.tasks


@pytest.mark.parametrize("change", [
    {"universe_id": 7002}, {"place_id": 9002}, {"version": 5}, {"version": "4"},
    {"version": None}, {"task_error": {"message": "execution failed"}},
])
def test_mismatched_or_errored_test_record_cannot_succeed(setup_cloud, monkeypatch, change):
    cloud, fake = setup_cloud
    original = cloud.run_luau

    def changed(*args, **kwargs):
        return {**original(*args, **kwargs), **change}

    monkeypatch.setattr(cloud, "run_luau", changed)
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is False and report["stopped_at"] == "run test"
    assert report["steps"][-1]["ok"] is False


INVALID = [
    {"passed": 0, "failed": 0, "cases": []},
    {"passed": -1, "failed": 0, "cases": []},
    {"passed": True, "failed": 0, "cases": [{"name": "a", "ok": True}]},
    {"passed": 2, "failed": 0, "cases": [{"name": "a", "ok": True}]},
    {"passed": 1, "failed": 0, "cases": [{"name": "a", "ok": False}]},
    {"passed": 1, "failed": 0, "cases": [{"name": "a", "ok": "true"}]},
    {"passed": 1, "failed": 0, "cases": [{"name": "a"}]},
    {"passed": 1, "failed": 0, "cases": [{"ok": True}]},
    {"passed": 1, "failed": 0, "cases": [{"name": " ", "ok": True}]},
    {"passed": 1, "failed": 0, "cases": [{"name": "a", "ok": True, "message": {}}]},
    {"passed": 1, "failed": 0, "cases": ["not a case"]},
    {"passed": 1, "failed": 0, "cases": {}},
    {"passed": 1, "failed": 0},
    {"passed": 1, "failed": 0, "executed": 0, "cases": [{"name": "a", "ok": True}]},
    {"passed": 1, "failed": 0, "executed": True, "cases": [{"name": "a", "ok": True}]},
    {"passed": 1, "failed": 0, "executed": 2, "cases": [{"name": "a", "ok": True}]},
    {"passed": 2, "failed": 0, "cases": [{"name": "a", "ok": True}, {"name": "a", "ok": True}]},
    {"passed": 1, "failed": 0, "cases": [{"name": "a" * 161, "ok": True}]},
    {"passed": 201, "failed": 0, "cases": [{"name": f"a{i}", "ok": True} for i in range(201)]},
]


@pytest.mark.parametrize("summary", INVALID)
def test_zero_or_malformed_reports_cannot_be_success(setup_cloud, summary):
    cloud, fake = setup_cloud
    fake.task_result = {"state": "COMPLETE", "output": {"results": [summary]}}
    fake.logs = []
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is False and report["stopped_at"] == "result"
    assert report["steps"][-1]["detail"]
    assert summarize_test({"output": {"results": [summary]}}) is None


def test_malformed_returned_report_cannot_be_replaced_with_a_passing_log(setup_cloud):
    cloud, fake = setup_cloud
    fake.task_result = {"state": "COMPLETE", "output": {"results": [deepcopy(INVALID[0])]}}
    fake.logs = [RESULT_MARK + json.dumps(GOOD)]
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is False and report["stopped_at"] == "result"


def test_malformed_latest_log_does_not_reuse_an_earlier_passing_report():
    assert summarize_test({"logs": [RESULT_MARK + json.dumps(GOOD), RESULT_MARK + "{truncated"]}) is None


def test_multiple_returned_reports_are_ambiguous():
    assert summarize_test({"output": {"results": [deepcopy(GOOD), deepcopy(GOOD)]}}) is None


def test_malformed_results_container_cannot_fall_back_to_passing_log():
    assert summarize_test({"output": {"results": "bad"}, "logs": [RESULT_MARK + json.dumps(GOOD)]}) is None


def test_well_formed_failed_report_is_preserved_as_failure(setup_cloud):
    cloud, fake = setup_cloud
    failed = {"passed": 0, "failed": 1, "cases": [{"name": "Empty.spec", "ok": False,
                                                    "message": "the spec has no callable cases"}]}
    fake.task_result = {"state": "COMPLETE", "output": {"results": [failed]}}
    fake.logs = []
    report = run_pipeline(cloud, EXAMPLE, publish_and_test=True)
    assert report["ok"] is False and report["stopped_at"] == "result"
    assert report["steps"][-1]["summary"] == failed


def test_valid_return_or_latest_log_is_sufficient_without_changing_counts():
    assert summarize_test({"output": {"results": [deepcopy(GOOD)]},
                           "logs": [RESULT_MARK + "malformed"]}) == GOOD
    assert summarize_test({"logs": ["diagnostic", RESULT_MARK + json.dumps(GOOD)]}) == GOOD
    current = {**deepcopy(GOOD), "executed": 1}
    assert summarize_test({"output": {"results": [current]}}) == current
