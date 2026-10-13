"""Studio Lab v3: measured jump thresholds, expected outcomes, UI fix loop, the 40-spec tree and the nightly job
(no Studio needed)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import copy
import json
from pathlib import Path

import pytest

from star import map_plan, roblox_ui_compiler, studio_lab, studio_lab_parallel

SPECS = Path(__file__).resolve().parents[1] / "star" / "studio_lab_specs"


def spec_named(name):
    specs, invalid = studio_lab_parallel.load_spec_tree(SPECS)
    assert not invalid
    return next(s for s in specs if s["name"] == name)


# --------------------------------------------------------------------------- thresholds

def test_fix_targets_sit_inside_what_real_physics_always_jumped():
    assert studio_lab.SAFE_GAP == 7.0 and studio_lab.SAFE_RISE == 6.0
    assert studio_lab.SAFE_GAP < studio_lab.REAL_JUMPED_GAP == 7.8
    assert studio_lab.SAFE_RISE < studio_lab.REAL_JUMPED_RISE == 7.6
    # the player-facing dry-run limits stay where they were: just inside the measured limits
    assert map_plan.DEFAULT_MAX_JUMP_GAP <= studio_lab.REAL_JUMPED_GAP + 0.5
    assert map_plan.DEFAULT_MAX_JUMP_RISE <= studio_lab.REAL_JUMPED_RISE


def test_lesson_texts_quote_the_new_numbers():
    assert "7 studs" in studio_lab.LESSON_TEXT["jump-too-far"]
    assert "6 studs" in studio_lab.LESSON_TEXT["jump-too-high"]


# --------------------------------------------------------------------------- the spec tree

def test_spec_tree_has_about_40_specs_maps_and_ui_all_with_expectations():
    specs, invalid = studio_lab_parallel.load_spec_tree(SPECS)
    assert not invalid
    assert 38 <= len(specs) <= 45
    kinds = [s["kind"] for s in specs]
    assert kinds.count("ui") == 5 and kinds.count("map") >= 33
    assert all(s.get("expect") for s in specs)
    assert len({s["name"] for s in specs}) == len(specs)
    styles = {s["plan"]["style"] for s in specs if s["kind"] == "map"}
    assert {"obby", "modern", "medieval"} <= styles


@pytest.mark.parametrize("name,target,fix", [
    ("V3WideGap", "P2", "extend-platform"), ("V3WideGapRise", "P3", "extend-platform"),
    ("V3Moat", "PlazaB", "extend-platform"), ("V3TallStep", "P2", "lower-target"),
    ("V3TallStepClimb", "P2", "add-step"), ("V3Terrace", "Terrace", "lower-target")])
def test_real_physics_defects_get_their_expected_fix_inside_the_new_limits(name, target, fix):
    spec = spec_named(name)
    plan = spec["plan"]
    legs = []
    for waypoint in plan["route"]["waypoints"][2:]:
        legs.append({"name": waypoint, "reached": waypoint != target, "highest": 10, "stood_on": []})
        if waypoint == target:
            break
    probe = {"finished": True, "started": True, "ok": False, "legs": legs, "problem": "", "failed_leg": legs[-1]}
    defects = studio_lab.diagnose(plan, {"ok": True}, probe, [])
    assert defects[0]["code"] in spec["expect"]["defects"]
    fixed, changes = studio_lab.fix_plan(plan, [d for d in defects if d.get("fix")])
    assert changes[0]["fix"] == fix and fix in spec["expect"]["fixes"]
    report = map_plan.dry_run(fixed, include_operations=False)
    assert report["ok"]
    for leg in report["route"]["legs"]:
        assert leg["gap"] <= studio_lab.SAFE_GAP + 1e-6 and leg["rise"] <= studio_lab.SAFE_RISE + 1e-6


def test_planted_real_physics_defects_are_beyond_what_was_ever_jumped():
    for name in ("V3WideGap", "V3WideGapRise", "V3Moat"):
        legs = map_plan.dry_run(spec_named(name)["plan"], include_operations=False)["route"]["legs"]
        assert max(leg["gap"] for leg in legs) >= 10.5          # 9.5 was jumped sometimes
    for name in ("V3TallStep", "V3TallStepClimb", "V3Terrace"):
        legs = map_plan.dry_run(spec_named(name)["plan"], include_operations=False)["route"]["legs"]
        assert max(leg["rise"] for leg in legs) >= 9.0          # 7.6 was the most ever jumped


# --------------------------------------------------------------------------- expected outcomes

def test_check_expect_validates_shape():
    assert studio_lab.check_expect(None) == ({}, "")
    good, problem = studio_lab.check_expect({"first_pass": False, "defects": ["jump-too-far"], "fixes": ["x"]})
    assert not problem and good["first_pass"] is False
    assert studio_lab.check_expect({"first_pass": "no"})[1]
    assert studio_lab.check_expect({"defects": "jump-too-far"})[1]
    assert studio_lab.check_expect({"surprise": 1})[1]
    bad = copy.deepcopy(spec_named("V3WideGap"))
    raw = {"name": bad["name"], "kind": "map", "plan": bad["plan"], "expect": {"first_pass": 3}}
    assert studio_lab.check_spec(raw)[0] is None


def _report(first_passed, defects=(), fixes=(), passed=True):
    first = {"index": 1, "passed": first_passed, "defects": [{"code": c} for c in defects],
             "fixes": [{"fix": f} for f in fixes]}
    iterations = [first] if first_passed else [first, {"index": 2, "passed": passed, "defects": [], "fixes": []}]
    return {"passed": passed, "iterations": iterations}


def test_expectation_reproduced_defect_with_the_expected_fix():
    spec = spec_named("V3WideGap")
    result = studio_lab.expectation(spec, _report(False, ["jump-too-far"], ["extend-platform"]))
    assert result["met"] and result["reproduced"] is True
    missed = studio_lab.expectation(spec, _report(True))
    assert missed["met"] is False and missed["reproduced"] is False
    wrong_fix = studio_lab.expectation(spec, _report(False, ["jump-too-far"], ["close-gap"]))
    assert wrong_fix["met"] is False and wrong_fix["checks"]["fix"] is False


def test_expectation_controls_and_either_way_specs():
    control = spec_named("V3CleanNearLimit")
    assert studio_lab.expectation(control, _report(True))["met"]
    assert not studio_lab.expectation(control, _report(False, ["route-failed"], [], passed=True))["met"]
    edge = spec_named("V2VeryFarGap")                          # 9.5 studs: either outcome is fine
    assert studio_lab.expectation(edge, _report(True))["met"]
    assert studio_lab.expectation(edge, _report(False, ["jump-too-far"], ["extend-platform"]))["met"]
    assert studio_lab.expectation({"name": "x"}, _report(True)) == {"declared": False}


# --------------------------------------------------------------------------- UI fixes

def _device(name, viewport, rows):
    layout = {"viewport": viewport, "rows": rows}
    return {"device": name, "layout": layout, "problems": studio_lab.ui_check(layout, name)}


def test_fix_ui_widens_a_clipped_label_when_it_fits_the_phone():
    spec = spec_named("V3UiLongButton")
    device = _device("phone", [666, 374], [["PlayButton", "TextButton", 253, 300, 160, 50, False, True]])
    fixed, changes = studio_lab.fix_ui(spec["ui"], [device])
    assert changes == [{"fix": "ui-widen-text", "object": "PlayButton", "width": changes[0]["width"]}]
    assert 160 < changes[0]["width"] <= 0.9 * 666
    roblox_ui_compiler.compile_ui(fixed)


def test_fix_ui_wraps_and_shrinks_text_too_long_for_any_screen():
    spec = spec_named("LabHud")
    rows = [["Title", "TextLabel", 183, 12, 300, 44, False, False]]
    fixed, changes = studio_lab.fix_ui(spec["ui"], [_device("phone", [666, 374], rows)])
    assert changes[0]["fix"] in ("ui-widen-text", "ui-wrap-text")
    long_ui = copy.deepcopy(spec["ui"])
    title = next(c for c in long_ui["root"]["children"] if c["id"] == "Title")
    title["text"] = "X" * 80
    fixed, changes = studio_lab.fix_ui(long_ui, [_device("phone", [666, 374], rows)])
    node = next(c for c in fixed["root"]["children"] if c["id"] == "Title")
    assert changes[0]["fix"] == "ui-wrap-text" and node["textWrapped"] is True and node["textSize"] < 28
    roblox_ui_compiler.compile_ui(fixed)


def test_fix_ui_clamps_an_off_screen_panel_and_skips_its_children():
    spec = spec_named("V3UiOffscreenPanel")
    rows = [["Inventory", "Frame", 760, 80, 220, 160, True, False],
            ["InvTitle", "TextLabel", 768, 88, 204, 30, True, False]]
    device = _device("phone", [666, 374], rows)
    assert {p["object"] for p in device["problems"]} == {"Inventory", "InvTitle"}
    fixed, changes = studio_lab.fix_ui(spec["ui"], [device])
    assert changes == [{"fix": "ui-clamp", "object": "Inventory", "edges": {"x": "right"}}]
    node = fixed["root"]["children"][0]
    assert node["anchor"]["x"] == {"scale": 1} and node["position"]["x"] == {"scale": 1, "offset": -12}
    roblox_ui_compiler.compile_ui(fixed)


def test_fix_ui_gives_an_oversized_dialog_a_scale_size_with_its_design_size_as_maximum():
    spec = spec_named("V3UiBigDialog")
    rows = [["Dialog", "Frame", -77, -53, 820, 480, True, False]]
    fixed, changes = studio_lab.fix_ui(spec["ui"], [_device("phone", [666, 374], rows)])
    assert changes[0]["fix"] == "ui-fit-scale" and changes[0]["maxSize"] == [820, 480]
    node = fixed["root"]["children"][0]
    assert node["size"] == {"x": {"scale": 0.9}, "y": {"scale": 0.9}}
    assert node["maxSize"] == {"x": {"offset": 820}, "y": {"offset": 480}}
    roblox_ui_compiler.compile_ui(fixed)


def test_fix_ui_without_viewports_or_known_objects_changes_nothing():
    spec = spec_named("V3UiClean")
    assert studio_lab.fix_ui(spec["ui"], [{"device": "phone", "layout": {}, "problems": []}])[1] == []
    device = _device("phone", [666, 374], [["Nobody", "Frame", 900, 0, 10, 10, True, False]])
    assert studio_lab.fix_ui(spec["ui"], [device])[1] == []


class ScriptedUiLab(studio_lab.UiLab):
    """UiLab with Studio replaced: the first build of the button is clipped on the phone, the fixed build fits."""

    def __init__(self, out):
        super().__init__(type("G", (), {"studio_id": "s", "verdict": None})(), out, log=lambda *_: None)
        self.applies, self.widths = 0, []

    async def _ui(self, code):
        if "STAR Studio Lab UI apply" in code:
            self.applies += 1
            run = code.split('"StarLabRun", "')[1].split('"')[0]
            return True, {"made": ["V3UiLongButton"], "removed": 0, "run": run, "handles": 0}
        if "device simulator" in code:
            return True, {"preset": "phone"}
        if "layout read-back" in code:
            fits = self.applies > 1
            return True, {"viewport": [666, 374], "rows": [["PlayButton", "TextButton", 253, 300, 160, 50, fits, True]]}
        return True, {}

    async def _read(self, name, **arguments):
        return {"content": [{"type": "image", "data": "aGVsbG8=", "mimeType": "image/png"}]}


def test_ui_lab_fixes_then_passes_and_writes_a_lesson(tmp_path):
    spec = spec_named("V3UiLongButton")
    lab = ScriptedUiLab(tmp_path)
    report = asyncio.run(lab.run(spec, run="abcd1234", keep=False))
    assert report["passed"] and len(report["iterations"]) == 2
    assert report["iterations"][0]["fixes"][0]["fix"] == "ui-widen-text"
    assert report["lesson"]["code"] == "ui-text-clipped" and report["lesson"]["reviewed"] is False
    assert studio_lab.lesson_evidence_text(report["lesson"])
    assert studio_lab.expectation(spec, report)["met"]
    row = studio_lab_parallel.row_of(1, spec, 1, report, 3.0)
    assert row["ui_checks"] == 6 and row["first_defects"] == ["ui-text-clipped"] * 3 and row["expect"]["met"]


# --------------------------------------------------------------------------- nightly

def test_rotation_wraps_and_advances(tmp_path):
    specs = [{"name": f"S{i}"} for i in range(5)]
    state = tmp_path / "rotation.json"
    chosen, start = studio_lab_parallel.rotation(specs, 3, state)
    assert [s["name"] for s in chosen] == ["S0", "S1", "S2"] and start == 0
    studio_lab_parallel.advance_rotation(state, start, 3, 5)
    chosen, start = studio_lab_parallel.rotation(specs, 3, state)
    assert [s["name"] for s in chosen] == ["S3", "S4", "S0"] and start == 3
    assert studio_lab_parallel.rotation([], 3, state) == ([], 0)


def test_prune_keeps_the_newest_nightly_folders_only(tmp_path):
    for stamp in ("20261010T033000Z", "20261011T033000Z", "20261012T033000Z"):
        (tmp_path / f"nightly-2studio-{stamp}").mkdir()
    (tmp_path / "suite-1studio-20261001T000000Z").mkdir()
    removed = studio_lab_parallel.prune_evidence(tmp_path, 2)
    assert removed == ["nightly-2studio-20261010T033000Z"]
    assert (tmp_path / "suite-1studio-20261001T000000Z").is_dir()


def test_nightly_runs_a_slice_writes_outbox_and_advances(tmp_path):
    folder = tmp_path / "nightly-2studio-20261014T033000Z"
    lesson = studio_lab.ui_lesson_record({"run": "r1", "passed": True, "final_ui": {}, "iterations": [
        {"index": 1, "problems": [{"code": "ui-off-screen", "object": "A", "device": "phone"}], "fixes": []},
        {"index": 2, "devices": [{"device": "phone", "screenshot": {"ok": True, "sha256": "x"}}], "fixes": []}]})
    seen = {}

    def fake_run():
        (folder / "01-A-s1").mkdir(parents=True)
        (folder / "01-A-s1" / "report.json").write_text(json.dumps({"lesson": lesson}), encoding="utf-8")
        return {"out": str(folder), "summary": {"specs_ran": 4, "passed": 4}, "rows": [{"spec": "A", "ran": True}]}

    result = studio_lab_parallel.nightly(SPECS, home=tmp_path, out=tmp_path, outbox=tmp_path / "outbox", studios=9,
                                         rotate=4, max_minutes=1, keep=14, run=fake_run)
    assert result["ok"] and len(result["chosen"]) == 4 and result["rotation_start"] == 0
    assert result["outbox"]["records"] == 1
    assert (tmp_path / "outbox" / "star-lessons-studio-lab.json").is_file()
    assert json.loads((tmp_path / "rotation.json").read_text())["next"] == 4
    assert json.loads((folder / "nightly.json").read_text())["chosen"] == result["chosen"]
    again = studio_lab_parallel.nightly(SPECS, home=tmp_path, out=tmp_path, outbox=None, studios=1, rotate=4,
                                        max_minutes=1, keep=14, run=lambda: {"problem": "no Studio"})
    assert again["ok"] is False and again["rotation_start"] == 4
    assert json.loads((tmp_path / "rotation.json").read_text())["next"] == 4     # a failed night does not advance


def test_nightly_without_a_connector_command_refuses(tmp_path, monkeypatch):
    monkeypatch.delenv(studio_lab_parallel.MULTI_COMMAND_ENV, raising=False)
    result = studio_lab_parallel.nightly(SPECS, home=tmp_path, out=tmp_path, outbox=None, studios=2, rotate=2,
                                         max_minutes=1, keep=3)
    assert result["ok"] is False and "connector" in result["problem"]


def test_runtime_cap_stops_new_specs(tmp_path, monkeypatch):
    ran = []

    async def fake_open(session, discovered, studio_id, *, home, own_account_id=None):
        return type("G", (), {"studio_id": studio_id})(), {"studio_id": studio_id, "verified": True}

    async def fake_wait(session, studio_id, **_):
        return True

    class SlowLab:
        def __init__(self, guarded, out, log=print, **kwargs):
            pass

        async def run(self, spec):
            ran.append(spec["name"])
            return {"passed": True, "iterations": [{"passed": True, "playtest": {"started": True, "stopped": True}}]}

        async def remove(self, names, root=map_plan.MANAGED_ROOT):
            return {"ok": True}

    @asynccontextmanager
    async def connect():
        yield object()

    async def tools(_session):
        return []

    ticks = iter(range(0, 10000, 50))
    monkeypatch.setattr(studio_lab_parallel, "open_instance", fake_open)
    monkeypatch.setattr(studio_lab_parallel, "wait_for_instance", fake_wait)
    monkeypatch.setattr(studio_lab, "Lab", SlowLab)
    import star.studio as studio_module
    monkeypatch.setattr(studio_module, "list_tools", tools)
    specs = [s for s in studio_lab_parallel.load_spec_tree(SPECS)[0] if s["kind"] == "map"][:6]
    report = asyncio.run(studio_lab_parallel.run_suite(specs, ["one"], connect, tmp_path, home=tmp_path,
                                                       log=lambda *_: None, admit=lambda slot: (None, None),
                                                       clock=lambda: next(ticks), max_seconds=120, anchored=True))
    assert 0 < len(ran) < 6
    capped = [r for r in report["rows"] if not r["ran"]]
    assert capped and all(r["problem"] == "runtime cap reached" for r in capped)


def test_cli_nightly_with_studios_uses_the_parallel_runner(tmp_path, monkeypatch, capsys):
    called = {}

    def fake_nightly(folder, **kwargs):
        called.update(kwargs, folder=folder)
        return {"ok": True, "invalid": [], "chosen": ["A"]}

    monkeypatch.setattr(studio_lab_parallel, "nightly", fake_nightly)
    code = studio_lab.main(["nightly", str(SPECS), "--home", str(tmp_path), "--out", str(tmp_path / "ev"),
                            "--outbox", str(tmp_path / "ob"), "--studios", "2", "--rotate", "16",
                            "--max-minutes", "45", "--keep", "14"])
    assert code == 0 and called["studios"] == 2 and called["rotate"] == 16 and called["max_minutes"] == 45.0
    assert called["keep"] == 14 and json.loads(capsys.readouterr().out)["invalid"] == 0
