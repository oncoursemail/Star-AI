"""STAR Studio Lab: the parts that need no Studio, and the loop against a stand-in for the guarded session."""
from __future__ import annotations

import asyncio
import base64
import copy
import json
from pathlib import Path
import re

import pytest

from star import map_plan, studio_lab
from star.studio_loop import EDIT_MARK, ChangeJournal

SPEC_FILE = Path(__file__).resolve().parents[1] / "star" / "studio_lab_specs" / "obby-banner.json"


def spec():
    checked, problems = studio_lab.check_spec(json.loads(SPEC_FILE.read_text(encoding="utf-8")))
    assert checked, problems
    return checked


def clean_plan():
    plan = copy.deepcopy(spec()["plan"])
    plan["parts"] = [p for p in plan["parts"] if p["name"] != "Banner"]
    return plan


# --------------------------------------------------------------------------- spec and Luau

def test_bundled_spec_passes_the_dry_run_and_the_lab_check():
    checked = spec()
    assert checked["kind"] == "map" and checked["maxIterations"] == 3
    assert map_plan.dry_run(checked["plan"])["ok"]


@pytest.mark.parametrize("change, word", [
    (lambda s: s.update(kind="ui"), "kind"),
    (lambda s: s.update(maxIterations=9), "maxIterations"),
    (lambda s: s.update(playSeconds=1), "playSeconds"),
    (lambda s: s["plan"].pop("route"), "route"),
    (lambda s: s["plan"]["route"].update(waypoints=["Start", "StartFloor", [70, 7, 3]]), "name objects"),
    (lambda s: s["plan"].update(rootPath="Workspace/Elsewhere"), "root-path"),
    (lambda s: s.update(extra=1), "unknown keys"),
    (lambda s: s["plan"].update(assets=[{"name": "A", "assetId": 5, "position": [80, 5, 0]}],
                                assetPolicy={"allowedAssetIds": [5]}), "assets"),
])
def test_check_spec_refuses(change, word):
    raw = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
    change(raw)
    checked, problems = studio_lab.check_spec(raw)
    assert checked is None and any(word in p for p in problems), problems


def test_apply_luau_builds_only_under_the_managed_root_and_carries_the_probe():
    plan = spec()["plan"]
    code = studio_lab.apply_luau(plan, "abcd1234")
    assert 'parent = folder(parent, "MapDrafts")' in code
    assert 'local old = parent:FindFirstChild("LabObbyBanner")' in code
    assert 'root:SetAttribute("StarLabRun", "abcd1234")' in code
    assert code.count('Instance.new("Part")') == 6 and 'Instance.new("SpawnLocation")' in code
    assert "probe.Source = " in code and "StarLabConfig" in code
    assert "other.Enabled = false" in code            # other drafts' probes cannot drive the character
    assert "ChangeHistoryService" not in code         # GuardedStudio's wrapper records the undo step
    # the only things destroyed are the old draft of this map (inside the drafts folder)
    assert code.count(":Destroy()") == 1
    config = json.loads(json.loads(re.search(r'probe:SetAttribute\("StarLabConfig", (".*")\)', code).group(1)))
    assert config["run"] == "abcd1234" and [w["name"] for w in config["waypoints"]] == ["StartFloor", "P1", "P2", "P3", "Goal"]


def test_apply_luau_refuses_a_bad_token():
    with pytest.raises(ValueError):
        studio_lab.apply_luau(spec()["plan"], 'x"); game:Destroy() --')


def test_probe_config_marks_jumps_and_start():
    config = studio_lab.probe_config(spec()["plan"], "00000000")
    assert config["start"] == [70.0, 7.5, 0.0]
    by_name = {w["name"]: w for w in config["waypoints"]}
    assert by_name["StartFloor"]["jump"] is False         # the spawn sits on the start floor
    assert by_name["P1"]["jump"] and by_name["P2"]["top"] == [93.0, 8.5, 0.0]
    assert config["killY"] < 0


def test_readback_pages_and_merge():
    plan = spec()["plan"]
    head = studio_lab.readback_luau(plan, 0)
    assert "GetPartBoundsInBox" in head and "page 0" in head
    with pytest.raises(ValueError):
        studio_lab.readback_luau(plan, -1)
    merged = studio_lab.merge_readback([
        {"exists": True, "run": "r1", "total": 1, "scripts": [["StarLabProbe", "Script", True]],
         "foreign": [["Workspace.Other", "P1", 1, 2, 3, 4, 5, 6]]},
        {"exists": True, "page": 1, "total": 1, "rows": [["P1", "Part", 83, 6, 0, 6, 1, 6, 0, 0, 0, True, True]]}])
    assert merged["complete"] and merged["parts"][0]["position"] == [83, 6, 0]
    assert merged["foreign"][0] == {"name": "Workspace.Other", "with": "P1", "position": [1, 2, 3], "size": [4, 5, 6]}
    assert studio_lab.merge_readback([{"exists": False}]) == {"exists": False}


def test_remove_luau_names_only():
    code = studio_lab.remove_luau(["LabObbyBanner"])
    assert '"MapDrafts"' in code and "draft:IsA(\"Folder\")" in code
    with pytest.raises(ValueError):
        studio_lab.remove_luau(["../Workspace"])
    with pytest.raises(ValueError):
        studio_lab.remove_luau([])


# --------------------------------------------------------------------------- verify

def readback_for(plan, run, *, drop=None, move=None, foreign=()):
    parts = []
    for name, item in studio_lab.expected_parts(plan).items():
        if name == drop:
            continue
        position = list(item["position"])
        if name == move:
            position[0] += 1
        parts.append({"name": name, "class": item["class"], "position": position, "size": item["size"],
                      "anchored": True, "canCollide": item["canCollide"]})
    return {"exists": True, "run": run, "parts": parts, "complete": True, "foreign": list(foreign),
            "scripts": [{"name": "StarLabProbe", "class": "Script", "run": True}]}


def test_verify_accepts_an_exact_build_and_reports_differences():
    plan = spec()["plan"]
    good = studio_lab.verify(plan, readback_for(plan, "r1"), "r1")
    assert good["ok"] and good["parts_in_studio"] == 7 and len(good["build_hash"]) == 64
    bad = studio_lab.verify(plan, readback_for(plan, "r1", drop="P2", move="P1"), "r1")
    assert not bad["ok"] and bad["missing"] == ["P2"] and bad["mismatched"][0]["name"] == "P1"
    other = studio_lab.verify(plan, readback_for(plan, "r0"), "r1")
    assert not other["ok"] and "another run" in other["problems"][0]
    assert not studio_lab.verify(plan, {"exists": False}, "r1")["ok"]


# --------------------------------------------------------------------------- probe output

def probe_lines(run, legs, done=True):
    lines = ["Hello from another script", f'{studio_lab.PROBE_MARK}{json.dumps({"kind": "start", "run": run})}']
    for index, leg in enumerate(legs, 1):
        lines.append(studio_lab.PROBE_MARK + json.dumps({"kind": "leg", "run": run, "index": index, **leg}))
    if done:
        lines.append(studio_lab.PROBE_MARK + json.dumps({"kind": "done", "run": run,
                                                          "ok": all(leg.get("reached") for leg in legs)}))
    return "\n".join(lines)


def test_parse_probe_keeps_only_this_run():
    console = probe_lines("old", [{"name": "P1", "reached": False}]) + "\n" + probe_lines("new", [
        {"name": "StartFloor", "reached": True}, {"name": "P1", "reached": True}])
    parsed = studio_lab.parse_probe(console, "new")
    assert parsed["ok"] and parsed["finished"] and len(parsed["legs"]) == 2 and parsed["failed_leg"] is None
    old = studio_lab.parse_probe(console, "old")
    assert not old["ok"] and old["failed_leg"]["name"] == "P1"
    assert studio_lab.parse_probe("nothing", "new")["started"] is False


def test_console_errors_only_after_this_run():
    console = "Script error: earlier\n" + probe_lines("run1", [{"name": "P1", "reached": True}]) + "\nattempt to index nil"
    assert studio_lab.console_errors(console, "run1") == ["attempt to index nil"]


# --------------------------------------------------------------------------- cameras, diagnosis, fixes

def test_cameras_are_fixed_and_look_at_the_build():
    shots = studio_lab.cameras(spec()["plan"])
    assert [s["id"] for s in shots] == ["overview", "side", "top", "route"]
    assert shots == studio_lab.cameras(spec()["plan"])          # deterministic
    route = shots[-1]
    assert route["position"][0] < 70 and route["look_at"][0] == 114.0


def leg(name, *, reached=True, highest=None, stood=()):
    return {"name": name, "reached": reached, "highest": highest if highest is not None else 16.0, "stood_on": list(stood)}


def passing_probe(plan, *, high_on=None, fail_on=None):
    legs = []
    for name in plan["route"]["waypoints"][1:]:
        if name == fail_on:
            legs.append(leg(name, reached=False))
            break
        legs.append(leg(name, highest=27.0 if name == high_on else 16.0))
    return {"finished": True, "started": True, "ok": fail_on is None, "legs": legs,
            "failed_leg": next((l for l in legs if not l["reached"]), None), "problem": ""}


def test_diagnose_unintended_support_from_height_and_fix_raises_the_banner():
    plan = spec()["plan"]
    defects = studio_lab.diagnose(plan, {"ok": True}, passing_probe(plan, high_on="P3"), [])
    assert [d["code"] for d in defects] == ["route-unintended-support"]
    assert defects[0]["objects"] == ["Banner"] and defects[0]["evidence"]["leg"] == "P2 -> P3"
    fixed, changes = studio_lab.fix_plan(plan, defects)
    banner = next(p for p in fixed["parts"] if p["name"] == "Banner")
    assert changes[0]["object"] == "Banner" and banner["position"][1] - 5 >= 8.5 + studio_lab.JUMP_CLEARANCE
    assert map_plan.dry_run(fixed)["ok"]
    assert plan["parts"][4]["position"] == [98, 12, 0]          # the input plan is not changed
    assert studio_lab.diagnose(fixed, {"ok": True}, passing_probe(fixed), []) == []


def test_diagnose_unintended_support_from_stood_on():
    plan = spec()["plan"]
    probe = passing_probe(plan)
    probe["legs"][3]["stood_on"] = ["Workspace.MapDrafts.LabObbyBanner.P2", "Workspace.MapDrafts.LabObbyBanner.Banner"]
    defects = studio_lab.diagnose(plan, {"ok": True}, probe, [])
    assert defects[0]["code"] == "route-unintended-support" and defects[0]["objects"] == ["Banner"]


def test_diagnose_blocked_corridor_on_a_failed_leg():
    plan = spec()["plan"]
    defects = studio_lab.diagnose(plan, {"ok": True}, passing_probe(plan, fail_on="P3"), [])
    assert defects[0]["code"] == "jump-corridor-blocked" and defects[0]["objects"] == ["Banner"]


def test_diagnose_spawn_on_the_take_off_floor_is_not_a_blocker():
    plan = clean_plan()
    defects = studio_lab.diagnose(plan, {"ok": True}, passing_probe(plan, fail_on="P1"), [])
    assert defects[0]["code"] == "route-failed" and defects[0]["heuristic"] is True


def test_diagnose_not_collidable_and_fix():
    plan = clean_plan()
    next(p for p in plan["parts"] if p["name"] == "P2")["canCollide"] = False
    defects = studio_lab.diagnose(plan, {"ok": True}, passing_probe(plan, fail_on="P2"), [])
    assert defects[0]["code"] == "route-surface-not-collidable"
    fixed, _ = studio_lab.fix_plan(plan, defects)
    assert next(p for p in fixed["parts"] if p["name"] == "P2")["canCollide"] is True


def test_fix_close_gap_moves_the_rest_of_the_route():
    plan = clean_plan()
    next(p for p in plan["parts"] if p["name"] == "P2")["position"][0] = 94.5    # gap 5.5 -> still under 8
    defects = [{"code": "jump-too-far", "fix": "close-gap", "object": "P2"}]
    fixed, changes = studio_lab.fix_plan(plan, defects)
    assert changes[0]["objects"] == ["P2", "P3", "Goal"] and changes[0]["delta"][0] == -1.5
    moved = {p["name"]: p["position"][0] for p in fixed["parts"]}
    assert moved["P1"] == 83 and moved["P2"] == 93.0 and moved["Goal"] == 112.5


def test_failed_first_leg_from_the_spawn_is_reported_not_fixed():
    # A route that starts on a part (not the spawn): the probe's first leg is spawn -> StartFloor. A failure there has
    # no previous route surface; the fixer must not wrap around to the LAST surface and move the whole course.
    plan = clean_plan()
    plan["route"]["waypoints"] = ["StartFloor", "P1", "P2", "P3", "Goal"]
    probe = studio_lab.parse_probe(probe_lines("abcd1234", [{"name": "StartFloor", "reached": False}]), "abcd1234")
    defects = studio_lab.diagnose(plan, {"ok": True}, probe, [])
    assert [d["code"] for d in defects] == ["route-failed"] and defects[0]["fix"] is None
    for fix in ("close-gap", "lower-rest"):
        fixed, changes = studio_lab.fix_plan(plan, [{"code": "x", "fix": fix, "object": "StartFloor"}])
        assert fixed == plan and changes[0]["fix"] is None


def test_fix_shift_map_clears_foreign_parts():
    plan = clean_plan()
    defects = [{"code": "foreign-overlap", "fix": "shift-map",
                "evidence": [{"name": "Workspace.StarLobby.Floor", "with": "StartFloor", "position": [70, 1, 0], "size": [48, 2, 48]}]}]
    fixed, changes = studio_lab.fix_plan(plan, defects)
    assert changes[0]["delta"][0] == 94 - 64 + 6
    assert map_plan.dry_run(fixed)["ok"]


def test_diagnose_reports_silent_probe_and_errors_without_fix():
    plan = clean_plan()
    defects = studio_lab.diagnose(plan, {"ok": True}, {"finished": False, "started": False}, ["boom"])
    assert [(d["code"], d["fix"]) for d in defects] == [("runtime-error", None), ("probe-silent", None)]


# --------------------------------------------------------------------------- lesson records and outbox

def fake_report(passed=True):
    return {"run": "abcd1234", "passed": passed, "place": {"place_id": 128074805767678, "universe_id": 10770312935},
            "final_plan": {"x": 1}, "iterations": [
                {"index": 1, "probe": passing_probe(spec()["plan"], high_on="P3"), "verify": {"build_hash": "a" * 64},
                 "defects": [{"code": "route-unintended-support", "evidence": {"leg": "P2 -> P3"}}],
                 "fixes": [{"fix": "raise-blockers", "object": "Banner", "raised_by": 15.5}]},
                {"index": 2, "probe": passing_probe(spec()["plan"]), "verify": {"build_hash": "b" * 64},
                 "defects": [], "screenshots": [{"camera": "overview", "ok": True, "sha256": "c" * 64}]}]}


def test_lesson_record_needs_fail_then_pass_with_a_known_defect():
    record = studio_lab.lesson_record(fake_report())
    assert record["source_type"] == "verified-fix" and record["reviewed"] is False
    assert record["evidence"]["kind"] == "studio-verified" and record["evidence"]["after"]["legs_reached"] == 5
    assert record["evidence"]["screenshots"][0]["build_hash"] == "b" * 64
    assert len(record["text"]) <= 240
    assert studio_lab.lesson_record(fake_report(passed=False)) is None
    single = fake_report()
    single["iterations"] = single["iterations"][1:]
    assert studio_lab.lesson_record(single) is None


def test_lesson_texts_fit_a_turn():
    assert all(len(text) <= 240 for text in studio_lab.LESSON_TEXT.values())


def test_write_outbox_makes_candidates_only(tmp_path):
    record = studio_lab.lesson_record(fake_report())
    result = studio_lab.write_outbox(tmp_path, [record])
    assert result["records"] == 1
    data = json.loads((tmp_path / "star-lessons-studio-lab.json").read_text(encoding="utf-8"))
    assert data["format"] == "star-lessons-v1"
    assert [lesson["status"] for lesson in data["lessons"]] == ["candidate"]
    assert "studio-lab: real Studio playtest" in data["lessons"][0]["evidence"]
    studio_lab.write_outbox(tmp_path, [record])                 # the same record again is not doubled
    data = json.loads((tmp_path / "star-lessons-studio-lab.json").read_text(encoding="utf-8"))
    assert len(data["lessons"]) == 1


# --------------------------------------------------------------------------- vision critic

class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_critic_sends_images_and_parses_json(tmp_path):
    seen = {}

    def opener(request, timeout):
        seen["body"] = json.loads(request.data)
        seen["auth"] = request.headers.get("Authorization")
        return FakeResponse({"choices": [{"message": {"content": '<think>x</think> {"defects": [{"code": "blocked-path", '
                                                                 '"object": "Banner", "detail": "wall in the gap"}], "looks_ok": false}'}}]})

    key = tmp_path / "key"
    key.write_text("secret-key\n")
    critic = studio_lab.BrainCritic("http://brain:8080", key_file=str(key), opener=opener)
    result = critic([("overview", b"\x89PNGdata", "image/png")] * 5, "summary")
    assert result["ok"] and result["advisory"] and result["defects"][0]["object"] == "Banner"
    images = [c for c in seen["body"]["messages"][0]["content"] if c["type"] == "image_url"]
    assert len(images) == 3 and images[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert seen["auth"] == "Bearer secret-key" and seen["body"]["model"] == "star-vision"


def test_critic_failure_never_leaks_the_address(tmp_path):
    def opener(request, timeout):
        raise OSError("connection refused to http://brain.invalid:8080")

    result = studio_lab.BrainCritic("http://brain.invalid:8080", key_file=str(tmp_path / "none"), opener=opener)(
        [("a", b"x", "image/png")], "s")
    assert result == {"ok": False, "error": "OSError", "seconds": result["seconds"]}


def test_critic_disabled_without_url(monkeypatch):
    monkeypatch.delenv("STAR_LAB_VISION_URL", raising=False)
    monkeypatch.delenv("STAR_BRAIN_URL", raising=False)
    assert not studio_lab.BrainCritic().enabled


# --------------------------------------------------------------------------- the loop against a stand-in

class Verdict:
    identity = type("I", (), {"place_id": 128074805767678, "game_id": 10770312935})()
    editable = True


class StandInStudio:
    """Speaks the GuardedStudio interface. Simulates what the real runs showed: a character climbs onto a decor
    part standing in a jump (root far higher than a jump), and passes once it is out of the way."""

    def __init__(self):
        self.studio_id, self.verdict, self.journal = "s1", Verdict(), ChangeJournal()
        self.parts, self.token, self.config, self.calls, self.playing = {}, None, None, [], False
        self.console = "old output\n"

    def _receipt(self, answer, added=0, removed=0):
        tag = f"StarEdit_{len(self.journal.entries):08x}"
        self.journal.entries.append({"kind": "luau", "tag": tag, "known": True, "ok": True, "recorded": True,
                                     "connector_recorded": False, "added": [], "added_count": added, "removed": removed})
        receipt = {"tag": tag, "ok": True, "recorded": True, "connectorRecorded": False, "added": [],
                   "addedCount": added, "removed": removed, "result": answer}
        return {"content": [{"type": "text", "text": EDIT_MARK + json.dumps(receipt)}]}

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "execute_luau":
            code = arguments["code"]
            assert arguments["datamodel_type"] == "Edit"
            if "STAR Studio Lab apply" in code:
                self.token = re.search(r'root:SetAttribute\("StarLabRun", "([0-9a-f]+)"\)', code).group(1)
                self.config = json.loads(json.loads(re.search(r'probe:SetAttribute\("StarLabConfig", (".*")\)', code).group(1)))
                self.parts = {}
                for block in code.split("\ndo\n")[1:]:
                    name_ = re.search(r'object.Name = "([^"]+)"', block)
                    if not name_:
                        continue
                    vec = lambda prop: [float(v) for v in re.search(prop + r" = Vector3.new\(([^)]*)\)", block).group(1).split(",")]
                    self.parts[name_.group(1)] = {"position": vec("Position"), "size": vec("Size"),
                                                  "class": re.search(r'Instance.new\("([A-Za-z]+)"\)', block).group(1),
                                                  "canCollide": "CanCollide = false" not in block}
                answer = studio_lab.APPLY_MARK + json.dumps({"parts": len(self.parts), "replaced": True, "run": self.token})
                return self._receipt(answer, added=len(self.parts) + 2, removed=0)
            if "read-back" in code:
                page = int(re.search(r"page (\d+)", code).group(1))
                names = sorted(self.parts)
                if page == 0:
                    data = {"exists": True, "run": self.token, "total": len(names),
                            "scripts": [["StarLabProbe", "Script", True]], "foreign": []}
                else:
                    rows = [[n, self.parts[n]["class"], *self.parts[n]["position"], *self.parts[n]["size"], 0, 0, 0, True,
                             self.parts[n]["canCollide"]] for n in names[(page - 1) * studio_lab.READ_PAGE:page * studio_lab.READ_PAGE]]
                    data = {"exists": True, "page": page, "total": len(names), "rows": rows}
                return self._receipt(studio_lab.READ_MARK + json.dumps(data))
            raise AssertionError("unexpected Luau")
        if name == "screen_capture":
            assert arguments["camera_position"] and arguments["look_at_position"]
            return {"content": [{"type": "image", "data": base64.b64encode(b"\xff\xd8jpeg").decode(), "mimeType": "image/jpeg"}]}
        if name == "start_stop_play":
            self.playing = arguments["is_start"]
            if self.playing:
                banner = self.parts.get("Banner")
                legs = []
                for point in self.config["waypoints"]:
                    high = banner is not None and point["name"] == "P3" and banner["position"][1] - banner["size"][1] / 2 < 22
                    legs.append({"name": point["name"], "reached": True, "highest": 27.1 if high else point["top"][1] + 7,
                                 "stood_on": []})
                self.console += probe_lines(self.token, legs) + "\n"
            return {"content": [{"type": "text", "text": "ok"}]}
        if name == "get_console_output":
            return {"content": [{"type": "text", "text": self.console}]}
        raise AssertionError(name)


def test_lab_loop_finds_fixes_and_proves_the_banner_defect(tmp_path):
    studio = StandInStudio()

    async def no_sleep(_):
        return None

    lab = studio_lab.Lab(studio, tmp_path, log=lambda *_: None, sleep=no_sleep, poll=0)
    report = asyncio.run(lab.run(spec(), run="feedbeef"))
    assert report["passed"] and len(report["iterations"]) == 2
    first, second = report["iterations"]
    assert first["verify"]["ok"] and [d["code"] for d in first["defects"]] == ["route-unintended-support"]
    assert first["fixes"][0]["object"] == "Banner" and second["defects"] == []
    assert first["token"] != second["token"] and first["token"].startswith("feedbeef")
    assert all(s["ok"] and s["file"].endswith(".jpg") for s in second["screenshots"])
    assert (tmp_path / "iteration-2" / "it2-route.jpg").read_bytes() == b"\xff\xd8jpeg"
    assert report["lesson"]["code"] == "route-unintended-support"
    assert studio.calls.count("start_stop_play") == 4          # start + stop per iteration
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["passed"] is True
    summary = studio_lab.public_summary(report, tmp_path)
    assert summary["passed"] and summary["iterations"][0]["defects"] == ["route-unintended-support"]


def test_lab_loop_stops_at_the_cap(tmp_path):
    studio = StandInStudio()

    async def no_sleep(_):
        return None

    capped = spec()
    capped["maxIterations"] = 1
    report = asyncio.run(studio_lab.Lab(studio, tmp_path, log=lambda *_: None, sleep=no_sleep, poll=0).run(capped))
    assert not report["passed"] and len(report["iterations"]) == 1 and report["lesson"] is None


def test_run_lab_sync_reports_a_failure_without_raising(tmp_path, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("boom with secret path C:/x")

    monkeypatch.setattr(studio_lab, "run_lab", broken)
    result = studio_lab.run_lab_sync(tmp_path, spec(), tmp_path / "out", timeout=10)
    assert result == {"ok": False, "passed": False, "problem": "lab run failed (RuntimeError)"}


# --------------------------------------------------------------------------- the STAR tool (opt-in)

def lab_hub(tmp_path, **kwargs):
    from star.intelligence import LocalIntelligence
    return LocalIntelligence(home=tmp_path / "home", skills_enabled=False, graphify_enabled=False, **kwargs)


def test_tool_is_off_by_default_and_offered_only_when_enabled(tmp_path):
    from star import intelligence
    schema = intelligence.ALL_TOOLS["star_roblox_studio_lab"]["inputSchema"]
    assert schema["additionalProperties"] is False and schema["required"] == ["plan"]
    prompt = "Plan a Roblox obby map blockout and test it"
    off = lab_hub(tmp_path)
    assert "star_roblox_studio_lab" not in {t["name"] for t in off.definitions(prompt)}
    assert off.status()["studio_lab"]["enabled"] is False
    with pytest.raises(PermissionError):
        off.call("star_roblox_studio_lab", {"plan": spec()["plan"]}, enabled={"star_roblox_studio_lab"})
    on = lab_hub(tmp_path, studio_lab_enabled=True)
    assert "star_roblox_studio_lab" in {t["name"] for t in on.definitions(prompt)}
    assert "star_roblox_studio_lab" not in {t["name"] for t in on.definitions("How are you?")}


def test_tool_refuses_a_bad_plan_without_connecting(tmp_path, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("must not connect")

    monkeypatch.setattr(studio_lab, "run_lab_sync", never)
    bad = copy.deepcopy(spec()["plan"])
    bad.pop("route")
    result = lab_hub(tmp_path, studio_lab_enabled=True).call(
        "star_roblox_studio_lab", {"plan": bad}, enabled={"star_roblox_studio_lab"})
    assert result["ok"] is False and result["applied"] is False and any("route" in p for p in result["problems"])


def test_tool_runs_the_lab_and_writes_the_outbox(tmp_path, monkeypatch):
    seen = {}

    def fake_run(home, spec_, out, **kwargs):
        seen.update(home=home, spec=spec_, out=out, critic=kwargs.get("critic"))
        report = fake_report()
        report["ok"] = True
        report["lesson"] = studio_lab.lesson_record(report)
        return report

    monkeypatch.setattr(studio_lab, "run_lab_sync", fake_run)
    result = lab_hub(tmp_path, studio_lab_enabled=True).call(
        "star_roblox_studio_lab", {"plan": spec()["plan"], "max_iterations": 2}, enabled={"star_roblox_studio_lab"})
    assert result["passed"] and seen["spec"]["maxIterations"] == 2 and seen["critic"] is None
    assert seen["out"].parent == tmp_path / "home" / "studio-lab" / "runs"
    assert result["outbox"]["records"] == 1
    assert (tmp_path / "home" / "studio-lab" / "outbox" / "star-lessons-studio-lab.json").is_file()


def test_for_settings_switch(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from star import intelligence
    settings = SimpleNamespace(workspace="", obsidian_vault="", obsidian_enabled=False, skills_enabled=False,
                               graphify_enabled=False, roblox_research_enabled=True)
    monkeypatch.setattr(intelligence, "client_for", lambda s: None)
    monkeypatch.delenv("STAR_STUDIO_LAB", raising=False)
    assert intelligence.for_settings(settings, tmp_path).studio_lab_enabled is False
    monkeypatch.setenv("STAR_STUDIO_LAB", "1")
    assert intelligence.for_settings(settings, tmp_path).studio_lab_enabled is True
