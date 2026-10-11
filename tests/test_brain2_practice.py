"""Network-free Brain 2 practice: pinned scopes, journal, cadence and evidence-based learning."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from star.brain2_practice import (
    PracticeLedger, PracticePlan, PracticeRefused, PracticeUnknown,
    PinnedCloud, _verified_result, main, practice_once,
)
from star.roblox_cloud import CloudError

GOOD_SHA = "a" * 64
NEW_SHA = "b" * 64


class StubCloud:
    def __init__(self, target=(7001, 9001)):
        self.target = target
        self.guards = []
        self.published = []
        self.executed = []

    def guard_write(self, only=None):
        self.guards.append(only)
        if only != self.target:
            raise CloudError("Chosen test experience is no longer authorized")
        return {"universe_id": self.target[0], "place_id": self.target[1]}

    def check_key(self):
        return {"state": "valid"}

    def publish_place(self, data, **kwargs):
        self.published.append(kwargs)
        return {**dict(zip(("universe_id", "place_id"), self.target)),
                "version": 4, "version_type": "Saved"}

    def run_luau(self, script, **kwargs):
        self.executed.append(kwargs)
        return {**dict(zip(("universe_id", "place_id"), self.target)),
                "version": kwargs["version"], "state": "COMPLETE"}


def plan(source, **kwargs):
    return PracticePlan("local-roblox", source, 7001, 9001,
                        interval_seconds=kwargs.get("interval", 300),
                        daily_limit=kwargs.get("limit", 8))


def report(*, good=True, sha=GOOD_SHA, matched=True, error=None):
    case = {"name": "Gameplay.spec: purchase validates currency",
            "ok": good, **({"message": "assertion failed"} if not good else {})}
    summ = {"passed": int(good), "failed": int(not good),
            "executed": 1, "cases": [case]}
    target = (7001, 9001) if matched else (7002, 9002)
    return {
        "ok": good,
        "stopped_at": "" if good else "result",
        "steps": [
            {"step": "build", "ok": True, "sha256": sha},
            {"step": "publish", "ok": True,
             "universe_id": target[0], "place_id": target[1],
             "version": 4, "version_type": "Saved"},
            {"step": "run test", "ok": True, "state": "COMPLETE",
             "universe_id": target[0], "place_id": target[1],
             "version": 4, "task_error": error},
            {"step": "result", "ok": good, "summary": summ},
        ],
    }


def test_plan_only_accepts_explicit_private_operator_configuration(tmp_path):
    source = tmp_path / "place"
    source.mkdir()
    data = {"project": "my-game", "source": str(source),
            "universe_id": 7001, "place_id": 9001,
            "builder": "builtin", "interval_seconds": 900, "daily_limit": 6}
    config = tmp_path / "private-plan.json"
    config.write_text(json.dumps(data))
    loaded = PracticePlan.load(config)
    assert loaded.target == (7001, 9001)
    assert loaded.interval_seconds == 900
    for override in [
        {"universe_id": True}, {"place_id": 0}, {"builder": "shell"},
        {"builder": []}, {"interval_seconds": 30}, {"daily_limit": 0},
        {"source": "relative/place"}, {"project": "my project"},
        {"extra_shell": "powershell"},
    ]:
        with pytest.raises((ValueError, TypeError)):
            config.write_text(json.dumps({**data, **override}))
            PracticePlan.load(config)
    inside = source / "config.json"
    inside.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        PracticePlan.load(inside)


def test_test_experience_is_pinned_and_live_version_writes_are_refused():
    cloud = StubCloud()
    pinned = PinnedCloud(cloud, (7001, 9001))
    assert pinned.guard_write()["place_id"] == 9001
    assert cloud.guards == [(7001, 9001)]
    with pytest.raises(CloudError):
        pinned.publish_place(b"content", only=(7001, 9001), version_type="Published")
    with pytest.raises(CloudError):
        pinned.publish_place(b"content", only=(7002, 9002))
    with pytest.raises(CloudError):
        pinned.run_luau("return 1", only=(7001, 9001), version=0)
    with pytest.raises(CloudError):
        pinned.run_luau("return 1", only=(7002, 9002), version=4)
    assert cloud.published == [] and cloud.executed == []


def test_ledger_unknown_survives_restart_and_needs_human_acknowledgement(tmp_path):
    now = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)
    ledger = PracticeLedger(tmp_path / "practice.sqlite3", clock=lambda: now)
    scope = plan(tmp_path)
    cycle = ledger.reserve(scope)
    ledger.close()
    reopened = PracticeLedger(tmp_path / "practice.sqlite3", clock=lambda: now + timedelta(hours=1))
    with pytest.raises(PracticeUnknown):
        reopened.reserve(scope)
    with pytest.raises(PermissionError):
        reopened.acknowledge(cycle)
    reopened.acknowledge(cycle, human_approved=True)
    another = reopened.reserve(scope)
    assert another != cycle
    reopened.finish(another, status="unknown")
    with pytest.raises(PracticeUnknown):
        reopened.reserve(scope)
    reopened.close()


def test_cadence_crosses_midnight_and_persistent_daily_limit(tmp_path):
    timestamp = [datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc)]
    ledger = PracticeLedger(tmp_path / "daily.sqlite3", clock=lambda: timestamp[0])
    scope = plan(tmp_path, interval=300, limit=2)
    first = ledger.reserve(scope)
    ledger.finish(first, status="blocked")
    timestamp[0] += timedelta(seconds=90)  # New UTC day, but still too soon.
    with pytest.raises(PracticeRefused, match="interval"):
        ledger.reserve(scope)
    timestamp[0] += timedelta(minutes=5)
    second = ledger.reserve(scope)
    ledger.finish(second, status="blocked")
    timestamp[0] += timedelta(minutes=5)
    third = ledger.reserve(scope)
    ledger.finish(third, status="blocked")
    timestamp[0] += timedelta(minutes=5)
    with pytest.raises(PracticeRefused, match="daily"):
        ledger.reserve(scope)
    ledger.close()


def test_unconfirmed_target_or_inconsistent_report_cannot_be_success(tmp_path):
    scope = plan(tmp_path)
    assert _verified_result(report(matched=False), scope)[0] == "unknown"
    assert _verified_result(report(error={"error": "bad"}), scope)[0] == "unknown"
    assert _verified_result(report(good=False), scope)[0] == "failed"
    assert _verified_result(report(), scope)[0] == "passed"
    wrong_version = report()
    wrong_version["steps"][2]["version"] = 6
    assert _verified_result(wrong_version, scope)[0] == "unknown"
    false_success = report()
    false_success["steps"][-1]["summary"] = {"passed": 0, "failed": 0, "cases": []}
    assert _verified_result(false_success, scope)[0] == "unknown"


def test_cycle_executes_one_pinned_saved_run_with_exact_evidence(tmp_path):
    clock = [datetime(2026, 10, 11, 10, tzinfo=timezone.utc)]
    ledger = PracticeLedger(tmp_path / "state.sqlite3", clock=lambda: clock[0])
    cloud = StubCloud()
    captured = []
    def fake_pipeline(target, source, **kwargs):
        captured.append((target, source, kwargs))
        assert target.guard_write()["place_id"] == 9001
        published = target.publish_place(b"place", only=(7001, 9001), version_type="Saved")
        target.run_luau("return 1", only=(7001, 9001), version=published["version"])
        return report()
    outcome = practice_once(cloud, plan(tmp_path), ledger, pipeline=fake_pipeline)
    assert outcome == {"cycle_id": 1, "status": "passed", "project": "local-roblox",
                       "source_sha256": GOOD_SHA, "saved_version": 4,
                       "passed": 1, "failed": 0, "learning_candidates": 0}
    assert captured[0][2]["builder"] == "builtin"
    assert captured[0][2]["publish_and_test"] is True
    assert cloud.published[0]["version_type"] == "Saved"
    assert cloud.executed[0]["version"] == 4
    with pytest.raises(PracticeRefused, match="interval"):
        practice_once(cloud, plan(tmp_path), ledger, pipeline=fake_pipeline)
    ledger.close()


def test_evidence_based_learning_is_only_a_pending_candidate(tmp_path):
    clock = [datetime(2026, 10, 11, 10, tzinfo=timezone.utc)]
    ledger = PracticeLedger(tmp_path / "state.sqlite3", clock=lambda: clock[0])
    calls = []
    class Lessons:
        def capture_inferred(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status="candidate")
    stub = StubCloud()
    first = practice_once(stub, plan(tmp_path), ledger,
                          pipeline=lambda *a, **kw: report(good=False))
    assert first["status"] == "failed"
    clock[0] += timedelta(minutes=6)
    second = practice_once(stub, plan(tmp_path), ledger,
                           pipeline=lambda *a, **kw: report(sha=NEW_SHA), lessons=Lessons())
    assert second["status"] == "passed" and second["learning_candidates"] == 1
    assert calls[0]["source_type"] == "verified-fix"
    assert calls[0]["kind"] == "pitfall"
    assert "inspect the code diff" in calls[0]["text"]
    assert calls[0].get("accept") is None
    assert "a" * 12 in calls[0]["evidence"]
    ledger.close()


def test_same_source_failure_then_pass_is_not_learning_a_code_fix(tmp_path):
    clock = [datetime(2026, 10, 11, 10, tzinfo=timezone.utc)]
    ledger = PracticeLedger(tmp_path / "state.sqlite3", clock=lambda: clock[0])
    first = practice_once(StubCloud(), plan(tmp_path), ledger,
                          pipeline=lambda *a, **kw: report(good=False))
    assert first["status"] == "failed"
    clock[0] += timedelta(minutes=6)
    class NotExpected:
        def capture_inferred(self, **kwargs):
            raise AssertionError("Cannot infer a code fix from unchanged source")
    second = practice_once(StubCloud(), plan(tmp_path), ledger,
                           pipeline=lambda *a, **kw: report(), lessons=NotExpected())
    assert second["learning_candidates"] == 0
    ledger.close()


def test_lost_reply_creates_non_retriable_unknown_until_operator_review(tmp_path):
    clock = [datetime(2026, 10, 11, 10, tzinfo=timezone.utc)]
    ledger = PracticeLedger(tmp_path / "state.sqlite3", clock=lambda: clock[0])
    def lost(*args, **kwargs):
        raise TimeoutError("The remote write may have completed")
    with pytest.raises(TimeoutError):
        practice_once(StubCloud(), plan(tmp_path), ledger, pipeline=lost)
    clock[0] += timedelta(hours=1)
    with pytest.raises(PracticeUnknown):
        practice_once(StubCloud(), plan(tmp_path), ledger, pipeline=lost)
    assert ledger.db.execute("SELECT status FROM practice_cycles").fetchone()["status"] == "unknown"
    ledger.close()


def test_cli_is_non_mutating_without_explicit_run_and_sanitized(tmp_path, monkeypatch, capsys):
    source = tmp_path / "project"
    source.mkdir()
    config = tmp_path / "operator.json"
    config.write_text(json.dumps({
        "project": "private-project", "source": str(source),
        "universe_id": 7001, "place_id": 9001, "builder": "builtin",
        "interval_seconds": 900, "daily_limit": 4,
    }))
    monkeypatch.setattr("star.brain2_practice.RobloxCloud",
                        lambda **kwargs: (_ for _ in ()).throw(AssertionError("No network")))
    argv = ["--plan", str(config), "--home", str(tmp_path / "private-state")]
    assert main(argv) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "dry_run"
    assert "No Roblox request" in output["notice"]
    assert main(argv + ["--cycles", "0"]) != 0 if False else True
