"""Self-play: deterministic offline specs, real-evidence requirements and locks."""
from __future__ import annotations

import asyncio
import hashlib

import pytest

from star import map_plan, selfplay_curriculum as sp


def test_selfplay_generates_small_valid_varied_maps():
    seen = set()
    for level in (1, 2, 3):
        for seed in range(12):
            spec = sp.build_obstacle_course(seed, difficulty=level)
            plan = spec["plan"]
            check = map_plan.dry_run(plan, include_operations=False)
            assert check["ok"], check.get("blockers")
            assert len(plan["parts"]) <= 6
            assert not plan.get("assets")
            assert plan["mapName"] == "SelfPlayCourse"
            assert plan["route"]["waypoints"][-1] == "Goal"
            seen.add(sp.digest(spec))
    assert len(seen) > 5
    assert not any("published" in k for k in spec)


def test_preview_is_pure_and_invalid_budgets_rejected(tmp_path):
    cfg = sp.Curriculum(project="test", seed=2, rounds=3, difficulty=2)
    first, second = sp.preview(cfg), sp.preview(cfg)
    assert first == second
    assert len(first["specs"]) == 3
    assert first["studio_started"] is False
    assert not list(tmp_path.iterdir())
    for args in ({"rounds": 0}, {"rounds": 7}, {"difficulty": 4},
                 {"seed": -1}, {"seed": True}, {"play_seconds": 1000},
                 {"max_iterations": 6}, {"project": "../evil"}):
        with pytest.raises(ValueError):
            sp.Curriculum(project="test", **args) if "project" not in args else sp.Curriculum(**args)


def good_report(target=(10770312935, 128074805767678)):
    return {"ok": True, "passed": True,
            "place": {"universe_id": target[0], "place_id": target[1]},
            "iterations": [
                {"passed": True, "verify": {"ok": True, "build_hash": "a" * 64},
                 "playtest": {"ok": True, "started": True, "stopped": True,
                              "errors": []},
                 "probe": {"finished": True, "ok": True},
                 "screenshots": [{"ok": True, "sha256": "b" * 64}]},
            ]}


def test_studio_proof_needs_real_lab_structure_and_target():
    target = (10770312935, 128074805767678)
    good = good_report()
    result = sp.studio_proof(good, target)
    assert result["studio_verified"] is True and result["screenshot_evidence"] is True
    assert result["visual_reviewed"] is False  # a screenshot alone is not a human art review
    assert sp.studio_proof(good, (1, 2))["studio_verified"] is False
    for path, value in (
        ("probe", {"finished": False, "ok": True}),
        ("playtest", {"ok": True, "started": True, "stopped": False, "errors": []}),
        ("verify", {"ok": True, "build_hash": "bad"}),
    ):
        damaged = good_report()
        damaged["iterations"][-1][path] = value
        assert sp.studio_proof(damaged, target)["studio_verified"] is False
    claimed = {"passed": True, "ok": True, "place": good["place"],
               "iterations": [{"passed": True}]}
    assert sp.studio_proof(claimed, target)["studio_verified"] is False


def test_ledger_serializes_and_never_retries_uncertain_status(tmp_path):
    file = tmp_path / "records" / "campaigns.sqlite3"
    cfg = sp.Curriculum(project="one")
    target = (2, 3)
    ledger = sp.CampaignLedger(file)
    try:
        first = ledger.reserve(cfg, target, now=2_000_000)
        with pytest.raises(sp.CampaignRefused):
            ledger.reserve(sp.Curriculum(project="other"), target, now=2_000_001)
        ledger.finish(first, status="unknown", results=[])
        with pytest.raises(sp.CampaignRefused):
            ledger.reserve(cfg, target, now=2_000_002)
        with pytest.raises(PermissionError):
            ledger.acknowledge_unknown(first, human_approved=False)
        ledger.acknowledge_unknown(first, human_approved=True)
        second = ledger.reserve(cfg, target, now=2_000_003)
        ledger.finish(second, status="failed", results=[])
        for i in range(sp.MAX_DAILY_CAMPAIGNS - 2):
            entry = ledger.reserve(cfg, target, now=2_000_004 + i)
            ledger.finish(entry, status="passed", results=[])
        with pytest.raises(sp.CampaignRefused):
            ledger.reserve(cfg, target, now=2_000_008)
    finally:
        ledger.close()


def test_owner_permission_and_missing_studio_lab_are_honest(tmp_path):
    cfg = sp.Curriculum(project="studio", rounds=1)
    with pytest.raises(PermissionError):
        asyncio.run(sp.run_approved_campaign(cfg, tmp_path))
    result = asyncio.run(sp.run_approved_campaign(cfg, tmp_path, approved=True))
    assert result["status"] == "unavailable"
    assert result["studio_verified"] is False
    assert not (tmp_path / "selfplay").exists()


def test_trusted_runner_output_classification_and_bounded_rounds(tmp_path):
    cfg = sp.Curriculum(project="test", rounds=2, difficulty=1)
    calls = []

    async def fake_runner(home, spec, directory, log):
        calls.append((spec["plan"]["mapName"], directory))
        return good_report()

    result = asyncio.run(sp.run_approved_campaign(
        cfg, tmp_path, approved=True, lab_runner=fake_runner, clock=lambda: 2_000_000))
    assert result["status"] == "passed" and len(result["rounds"]) == 2
    assert result["promoted_lessons"] == 0 and result["trained_weights"] is False
    assert len(calls) == 2
    assert all("selfplay/runs/campaign-" in str(directory).replace("\\", "/") for _, directory in calls)


def test_unknown_remote_state_aborts_without_retry(tmp_path):
    called = []

    async def uncertain(*args, **kwargs):
        called.append(1)
        raise TimeoutError("remote status may have changed")

    cfg = sp.Curriculum(project="project", rounds=3)
    result = asyncio.run(sp.run_approved_campaign(
        cfg, tmp_path, approved=True, lab_runner=uncertain, clock=lambda: 2_000_000))
    assert result["status"] == "unknown"
    assert len(called) == 1
    with pytest.raises(sp.CampaignRefused):
        asyncio.run(sp.run_approved_campaign(
            cfg, tmp_path, approved=True, lab_runner=uncertain, clock=lambda: 2_000_001))
