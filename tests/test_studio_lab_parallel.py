"""Studio Lab v2: fix strategies, the spec suite, UI specs and the parallel runner (no Studio needed)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import copy
import json
from pathlib import Path

import pytest

from star import map_plan, studio_lab, studio_lab_parallel

SUITE = Path(__file__).resolve().parents[1] / "star" / "studio_lab_specs" / "suite"


def suite():
    specs = []
    for path in sorted(SUITE.glob("*.json")):
        spec, problems = studio_lab.check_spec(json.loads(path.read_text(encoding="utf-8")))
        assert spec, (path.name, problems)
        specs.append(spec)
    return specs


def by_name(name):
    return next(s for s in suite() if s["name"] == name)


def failing(plan, target):
    legs = []
    for name in plan["route"]["waypoints"][2:]:
        legs.append({"name": name, "reached": name != target, "highest": 10, "stood_on": []})
        if name == target:
            break
    return {"finished": True, "started": True, "ok": False, "legs": legs, "problem": "",
            "failed_leg": next(l for l in legs if not l["reached"])}


def diagnose_and_fix(name, target):
    plan = by_name(name)["plan"]
    defects = studio_lab.diagnose(plan, {"ok": True}, failing(plan, target), [])
    fixed, changes = studio_lab.fix_plan(plan, [d for d in defects if d.get("fix")])
    assert map_plan.dry_run(fixed, include_operations=False)["ok"]
    return plan, defects, fixed, changes


# --------------------------------------------------------------------------- the suite

def test_suite_has_valid_specs_each_with_a_named_defect_and_an_expected_outcome():
    specs = suite()
    assert 35 <= len(specs) <= 45
    assert len({s["name"] for s in specs}) == len(specs)
    assert all(s["defect"] and s["expect"] for s in specs)
    # controls and limit checks must pass the first time; everything else names the defect it plants
    assert sum(s["defect"] in ("none", "limit-check") for s in specs) == 8
    assert all(s["expect"]["defects"] for s in specs if s["defect"] not in ("none", "limit-check"))
    for spec in specs:                      # away from the test place's lobby and the old demo draft
        assert spec["plan"]["bounds"]["center"][2] == 150.0


# --------------------------------------------------------------------------- fix strategies

def test_decor_in_a_gap_is_moved_aside_not_floated():
    plan, defects, fixed, changes = diagnose_and_fix("V2Banner", "P3")
    assert defects[0]["code"] == "jump-corridor-blocked" and changes[0]["fix"] == "move-aside"
    before = next(p for p in plan["parts"] if p["name"] == "Banner")
    after = next(p for p in fixed["parts"] if p["name"] == "Banner")
    assert after["position"][1] == before["position"][1] and after["size"] == before["size"]
    assert abs(after["position"][2] - before["position"][2]) <= studio_lab.MAX_ASIDE


def test_decor_standing_on_the_landing_is_removed_when_no_move_keeps_it_standing():
    plan, _defects, fixed, changes = diagnose_and_fix("V2PillarOnLanding", "P2")
    assert changes == [{"fix": "remove", "object": "Pillar", "why": changes[0]["why"]}]
    assert "Pillar" not in {p["name"] for p in fixed["parts"]}
    assert {p["name"] for p in plan["parts"]} - {p["name"] for p in fixed["parts"]} == {"Pillar"}


def test_decor_without_room_inside_the_bounds_is_removed():
    _plan, _defects, fixed, changes = diagnose_and_fix("V2WideSign", "P2")
    assert changes[0]["fix"] == "remove" and "Sign" not in {p["name"] for p in fixed["parts"]}


def test_moved_decor_keeps_resting_on_its_floor():
    _plan, _defects, fixed, changes = diagnose_and_fix("V2CrateWalk", "P1")
    assert changes[0]["fix"] == "move-aside" and studio_lab._rests_on(fixed, "Crate")


def test_a_roof_beam_is_raised_not_moved():
    plan, _defects, fixed, changes = diagnose_and_fix("V2LowBeam", "P2")
    assert changes[0]["fix"] == "raise-overhead"
    before = next(p for p in plan["parts"] if p["name"] == "Beam")
    after = next(p for p in fixed["parts"] if p["name"] == "Beam")
    assert after["position"][0] == before["position"][0] and after["position"][2] == before["position"][2]
    assert after["position"][1] - 0.5 >= 6.5 + studio_lab.JUMP_CLEARANCE


def test_route_surfaces_are_never_cleared():
    plan = by_name("V2Clean")["plan"]
    assert studio_lab.clearing_strategy(plan, "P2", "P1", "P3")["strategy"] is None


def test_far_gap_grows_the_landing_and_keeps_the_rest_of_the_route():
    plan = copy.deepcopy(by_name("V2VeryFarGap")["plan"])
    _plan, defects, fixed, changes = diagnose_and_fix("V2VeryFarGap", "P2")
    assert defects[0]["code"] == "jump-too-far" and changes[0]["fix"] == "extend-platform"
    goal_before = next(p for p in plan["parts"] if p["name"] == "Goal")["position"]
    assert next(p for p in fixed["parts"] if p["name"] == "Goal")["position"] == goal_before
    boxes = studio_lab._object_boxes(fixed)
    assert studio_lab._leg(boxes["P1"], boxes["P2"])[0] <= studio_lab.SAFE_GAP + 1e-6
    far_edge = lambda p: p["position"][0] + p["size"][0] / 2
    assert far_edge(next(p for p in fixed["parts"] if p["name"] == "P2")) == pytest.approx(
        far_edge(next(p for p in plan["parts"] if p["name"] == "P2")))


def test_high_rise_lowers_only_the_landing_when_the_next_leg_allows():
    _plan, _defects, fixed, changes = diagnose_and_fix("V2HighRise", "P2")
    assert changes[0]["fix"] == "lower-target"
    boxes = studio_lab._object_boxes(fixed)
    assert studio_lab._leg(boxes["P1"], boxes["P2"])[1] == pytest.approx(studio_lab.SAFE_RISE)


def test_high_rise_followed_by_a_climb_gets_one_step():
    _plan, _defects, fixed, changes = diagnose_and_fix("V3TallStepClimb", "P2")
    assert changes[0]["fix"] == "add-step" and changes[0]["object"] == "P2Step"
    route = fixed["route"]["waypoints"]
    assert route[route.index("P2") - 1] == "P2Step"
    boxes = studio_lab._object_boxes(fixed)
    assert studio_lab._leg(boxes["P1"], boxes["P2Step"])[1] <= studio_lab.SAFE_RISE
    assert studio_lab._leg(boxes["P2Step"], boxes["P2"])[1] <= studio_lab.SAFE_RISE


def test_unanchored_and_not_collidable_surfaces():
    _p, defects, fixed, changes = diagnose_and_fix("V2Unanchored", "P2")
    assert defects[0]["code"] == "route-surface-unanchored" and changes[0]["fix"] == "anchor"
    assert next(p for p in fixed["parts"] if p["name"] == "P2")["anchored"] is True
    _p, defects, _fixed, changes = diagnose_and_fix("V2NoCollide", "P2")
    assert changes[0]["fix"] == "make-collidable"


def test_too_high_with_nothing_in_the_corridor_is_not_a_pass():
    plan = by_name("V2Clean")["plan"]
    probe = failing(plan, "Goal")
    probe["failed_leg"] = None
    probe["legs"][-1].update(reached=True, highest=40)
    defects = studio_lab.diagnose(plan, {"ok": True}, probe, [])
    assert defects[0]["code"] == "route-unexplained-height" and defects[0]["fix"] is None


def test_new_lesson_texts_exist_and_fit():
    assert "route-surface-unanchored" in studio_lab.LESSON_TEXT
    assert all(len(t) <= 240 for t in studio_lab.LESSON_TEXT.values())


# --------------------------------------------------------------------------- UI specs

UI_SPEC = {"name": "LabHud", "kind": "ui", "devices": ["phone", "tablet", "desktop"],
           "ui": {"palette": {"bg": "#111111", "fg": "#FFFFFF"},
                  "root": {"type": "screen", "id": "hud", "children": [
                      {"type": "button", "id": "play", "text": "Play", "textColor": "fg", "background": "bg",
                       "size": {"x": {"offset": 160}, "y": {"offset": 50}}}]}}}


def test_ui_spec_check_and_apply_luau():
    spec, problems = studio_lab.check_spec(copy.deepcopy(UI_SPEC))
    assert spec and not problems and spec["devices"] == ["phone", "tablet", "desktop"]
    code = studio_lab.ui_apply_luau(spec, "abcd1234")
    assert studio_lab.PLAYER_GUI_LINE not in code and "local playerGui = __starLabParent" in code
    assert 'GetService("StarterGui")' in code and studio_lab.UI_ATTRIBUTE in code
    bad = copy.deepcopy(UI_SPEC)
    bad["devices"] = ["watch"]
    assert studio_lab.check_spec(bad)[0] is None


def test_ui_device_and_layout_luau_only_read_or_switch_the_simulator():
    phone = studio_lab.ui_device_luau("phone")
    assert "StudioDeviceSimulatorService" in phone and '"iPhone"' in phone
    assert "StopSimulationAsync" in studio_lab.ui_device_luau("desktop")
    with pytest.raises(ValueError):
        studio_lab.ui_device_luau("toaster")
    assert "Destroy" not in studio_lab.ui_layout_luau("LabHud")
    with pytest.raises(ValueError):
        studio_lab.ui_layout_luau("bad name!")


def test_ui_check_finds_off_screen_clipped_and_small_touch_targets():
    layout = {"viewport": [800, 400], "rows": [
        ["play", "TextButton", 10, 10, 160, 30, True, True],
        ["title", "TextLabel", 700, 10, 200, 40, False, False],
        ["ok", "Frame", 10, 100, 50, 50, True, False]]}
    codes = sorted(p["code"] for p in studio_lab.ui_check(layout, "phone"))
    assert codes == ["ui-off-screen", "ui-text-clipped", "ui-touch-target-small"]
    assert [p["code"] for p in studio_lab.ui_check(layout, "desktop")] == ["ui-off-screen", "ui-text-clipped"]
    assert studio_lab.ui_check(None, "phone")[0]["code"] == "ui-not-read"


# --------------------------------------------------------------------------- the parallel runner

class Identity:
    def __init__(self, place_id=128074805767678, game_id=10770312935):
        self.place_id, self.game_id = place_id, game_id


def test_farm_admits_only_verified_approved_places():
    assert studio_lab_parallel.farm_admits("s-1", Identity(), True, "t") == (True, "admitted")
    assert studio_lab_parallel.farm_admits("s-1", Identity(), False, "t")[1] == "identity_mismatch"
    assert studio_lab_parallel.farm_admits("s-1", Identity(129870808752914, 999), True, "t")[1] == "place_not_approved"
    assert studio_lab_parallel.farm_admits("s-1", Identity(0, 0), True, "t") == (True, "admitted")
    assert studio_lab_parallel.farm_admits("s-1", None, True, "t") == (False, "identity_unknown")


def test_for_slot_gives_each_worker_its_own_draft_root():
    spec = by_name("V2Clean")
    mine = studio_lab_parallel.for_slot(spec, 2)
    assert mine["plan"]["rootPath"] == "Workspace/MapDrafts/Slot2" and "rootPath" not in spec["plan"]
    assert map_plan.dry_run(mine["plan"], include_operations=False)["ok"]
    assert "parent = folder(parent, \"Slot2\")" in studio_lab.apply_luau(mine["plan"], "abcd1234")


def test_multi_command_from_env_or_home(tmp_path, monkeypatch):
    monkeypatch.delenv(studio_lab_parallel.MULTI_COMMAND_ENV, raising=False)
    assert studio_lab_parallel.multi_command(tmp_path) is None
    (tmp_path / "studio").mkdir()
    (tmp_path / "studio" / "lab-multi.json").write_text(json.dumps({"command": ["ssh", "host", "x.sh"]}))
    assert studio_lab_parallel.multi_command(tmp_path) == ["ssh", "host", "x.sh"]
    monkeypatch.setenv(studio_lab_parallel.MULTI_COMMAND_ENV, json.dumps(["other"]))
    assert studio_lab_parallel.multi_command(tmp_path) == ["other"]


def test_summarize_counts_tested_results_per_hour():
    rows = [{"ran": True, "passed": True, "first_pass": True, "playtests": 1, "seconds": 10.0, "lesson": None},
            {"ran": True, "passed": True, "first_pass": False, "playtests": 2, "seconds": 20.0, "lesson": "x"},
            {"ran": False}]
    summary = studio_lab_parallel.summarize(rows, 36.0, 2)
    assert summary["playtests_per_hour"] == 300.0 and summary["specs_per_hour"] == 200.0
    assert summary["fixed_then_passed"] == 1 and summary["lessons"] == 1 and summary["specs"] == 3


def test_run_suite_spreads_specs_and_refuses_unverified_studios(tmp_path, monkeypatch):
    """Two fake Studios: one verified, one answering with another place. Only the verified one runs specs."""
    opened = []

    async def fake_open(session, discovered, studio_id, *, home, own_account_id=None):
        good = studio_id == "good"
        return (FakeGuarded(studio_id) if good else None), {"studio_id": studio_id, "verified": good,
                                                             "farm": "admitted" if good else "place_not_approved"}

    async def fake_wait(session, studio_id, **_):
        return True

    class FakeLab:
        def __init__(self, guarded, out, log=print, **kwargs):
            self.guarded, self.kwargs = guarded, kwargs

        async def run(self, spec):
            opened.append((self.guarded.studio_id, spec["name"], spec["plan"].get("rootPath")))
            return {"passed": True, "iterations": [{"passed": True, "playtest": {"started": True, "stopped": True},
                                                    "defects": []}]}

        async def remove(self, names, root=map_plan.MANAGED_ROOT):
            return {"ok": True, "removed": [], "root": root}

    @asynccontextmanager
    async def connect():
        yield object()

    async def tools(_session):
        return []

    monkeypatch.setattr(studio_lab_parallel, "open_instance", fake_open)
    monkeypatch.setattr(studio_lab_parallel, "wait_for_instance", fake_wait)
    monkeypatch.setattr(studio_lab, "Lab", FakeLab)
    import star.studio as studio_module
    monkeypatch.setattr(studio_module, "list_tools", tools)
    specs = suite()[:5]
    report = asyncio.run(studio_lab_parallel.run_suite(specs, ["good", "bad"], connect, tmp_path, home=tmp_path,
                                                       log=lambda *_: None, admit=lambda slot: (None, None)))
    assert report["summary"]["specs_ran"] == 5 and report["summary"]["workers"] == 1
    assert {studio_id for studio_id, _n, _r in opened} == {"good"}
    assert all(root == "Workspace/MapDrafts/Slot1" for _s, _n, root in opened)
    assert [i["verified"] for i in report["instances"]] == [True, False]
    assert json.loads((tmp_path / "suite.json").read_text(encoding="utf-8"))["summary"]["specs"] == 5


def test_run_suite_rejects_bad_instance_lists(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(studio_lab_parallel.run_suite([], [], None, tmp_path, home=tmp_path))
    with pytest.raises(ValueError):
        asyncio.run(studio_lab_parallel.run_suite([], ["a", "a"], None, tmp_path, home=tmp_path))


class FakeGuarded:
    def __init__(self, studio_id):
        self.studio_id = studio_id


def test_lesson_text_follows_the_fix_that_really_worked():
    base = {"run": "r1", "passed": True, "place": None, "final_plan": {}}
    first = {"index": 1, "probe": {"failed_leg": {"name": "P2"}, "legs": []}, "verify": {},
             "defects": [{"code": "route-unintended-support", "evidence": {"leg": "P1 -> P2"}}],
             "fixes": [{"fix": "raise-overhead", "object": "Beam"}]}
    last = {"index": 2, "probe": {"legs": [{"reached": True}]}, "verify": {"build_hash": "abc"}, "screenshots": [],
            "defects": []}
    record = studio_lab.lesson_record({**base, "iterations": [first, last]})
    assert record["text"] == studio_lab.FIX_TEXT["raise-overhead"]
    first["fixes"] = [{"fix": "move-aside", "object": "Banner"}]
    assert studio_lab.lesson_record({**base, "iterations": [first, last]})["text"] == \
        studio_lab.LESSON_TEXT["route-unintended-support"]
