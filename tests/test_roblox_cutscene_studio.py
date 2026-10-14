"""STAR Cutscene Studio: the typed Luau modules, the timeline validator and craft check, Luau generation, the Studio
lab against a stand-in, console evidence parsing, frame alignment and the measured critique, the opt-in skill pack."""
import asyncio
import base64
import copy
import io
import json
import re

import pytest
from PIL import Image, ImageDraw

from star import luau_lint, skill_packs
from star import roblox_cutscene_studio as cut

LUAU = cut.LUAU_DIR


def luau(name: str) -> str:
    return (LUAU / f"{name}.luau").read_text(encoding="utf-8")


# ------------------------------------------------------------------ the Luau modules

def test_every_module_is_strict_and_passes_stars_luau_checks():
    sources = cut.pack_sources()
    assert set(sources) == {*cut.SHARED_MODULES, cut.SERVER_MODULE}
    for name, code in sources.items():
        assert code.startswith("--!strict"), name
    findings = cut.lint_sources({**sources, "CutsceneGenerated": cut.timeline_luau(cut.demo_timeline())})
    assert {name: items for name, items in findings.items() if items} == {}


def test_python_mirrors_match_the_luau_tables():
    types = luau("CutsceneTypes")
    kinds = set(re.findall(r"^\t(\w+) = true,", types.split("Types.KINDS = {")[1].split("}")[0], re.M))
    assert kinds == set(cut.KINDS)
    expressions = set(re.findall(r"(\w+) = true", types.split("Types.EXPRESSIONS = {")[1].split("}")[0]))
    assert expressions == set(cut.EXPRESSIONS)
    player = luau("ExpressionPlayer")
    block = player.split("ExpressionPlayer.PRESETS = {")[1].split("} :: {")[0]
    parsed = {}
    for name, body in re.findall(r"\t(\w+) = \{(.*?)\},", block, re.S):
        parsed[name] = {k: float(v) for k, v in re.findall(r"(\w+) = ([0-9.]+)", body)}
    assert parsed == cut.PRESETS
    for pose in cut.PRESETS.values():
        assert set(pose) <= cut.FACS and all(0 <= v <= 1 for v in pose.values())
    gestures = set(re.findall(r"^\t(\w+) = \{ --|^\t(\w+) = \{$", luau("ActorMotion"), re.M))
    assert {"recoil", "nod", "reach"} <= {g for pair in gestures for g in pair if g}


def test_server_module_trusts_the_client_with_nothing_but_a_finished_token():
    service = luau("CutsceneService")
    assert 'action ~= "finished"' in service and "entry.token ~= token" in service
    assert "lastMessage" in service and "cooldown" in service and "task.delay" in service
    assert "FireAllClients" not in service and "loadstring" not in service
    client = luau("CutsceneClient")
    assert "timelines[name]" in client and 'typeof(origin) ~= "CFrame"' in client
    assert "CreateHumanoidModelFromDescriptionAsync" in service and "CreateHumanoidModelFromDescription(" not in service


def test_player_restores_camera_controls_and_ui_and_never_tweens_the_camera():
    player = luau("CutscenePlayer")
    for needle in ("Enum.CameraType.Custom", "CameraSubject", "saved.fov", "controls:Enable()", "SetCoreGuiEnabled",
                   "UnbindFromRenderStep", "Camera.Value + 1", "folder:Destroy()", "ui:destroy()"):
        assert needle in player, needle
    assert "TweenService" not in player  # frame-driven camera: a skip never fights a running tween
    ui = luau("CutsceneUi")
    assert "IgnoreGuiInset = true" in ui and "BindAction" in ui and "UnbindAction" in ui and "fromOffset(112, 44)" in ui


# ------------------------------------------------------------------ timeline validation and craft

@pytest.mark.parametrize("version", [1, 2, 3])
def test_demo_timelines_are_valid_15_second_cutscenes_with_the_required_beats(version):
    timeline = cut.demo_timeline(version)
    assert cut.validate_timeline(timeline) == []
    assert 10 <= timeline["length"] <= 15 and len(timeline["shots"]) >= 3
    kinds = {c["kind"] for c in timeline["cues"]}
    assert {"spawn", "walk", "expression", "vfx", "caption", "letterbox"} <= kinds


def test_craft_check_flags_the_first_draft_and_passes_the_final():
    first = cut.craft_check(cut.demo_timeline(1))
    assert any("linear easing" in n for n in first) and any("take the bars out" in n for n in first)
    assert cut.craft_check(cut.demo_timeline(3)) == []
    bad = cut.demo_timeline(3)
    for cue in bad["cues"]:
        if cue["kind"] == "expression" and cue["name"] == "happy":
            cue["at"] = 8.0  # during the crystal shot, which does not look at the hero
    bad["cues"].sort(key=lambda c: c["at"])
    assert any("off camera" in n for n in cut.craft_check(bad))
    short = cut.demo_timeline(3)
    short["cues"] = [dict(c, duration=0.5) if c["kind"] == "caption" else c for c in short["cues"]]
    assert any("reading needs" in n for n in cut.craft_check(short))


@pytest.mark.parametrize("change, expected", [
    (lambda t: t["shots"][1].update(start=4.5), "previous shot ends"),
    (lambda t: t["cues"].reverse(), "sorted"),
    (lambda t: t["cues"].append({"at": 14.9, "kind": "expression", "actor": "Hero", "name": "smug"}), "unknown expression"),
    (lambda t: t["cues"].append({"at": 14.9, "kind": "caption", "text": 'x"]] ; game:Destroy() --'}), "caption text"),
    (lambda t: t["cues"].append({"at": 14.9, "kind": "vfx", "ability": "a b", "style": "x"}), "vfx needs"),
    (lambda t: t["shots"][0].update(curve="spiral"), "unknown curve"),
    (lambda t: t["shots"][0].update(ease={"style": "Wobbly"}), "unknown easing"),
    (lambda t: t["shots"][0].update(fov=[200]), "FOV"),
    (lambda t: t["cues"].append({"at": 14.9, "kind": "anim", "actor": "Hero", "animation": "http://x"}), "rbxassetid"),
    (lambda t: t.update(length=200), "length"),
])
def test_validator_refuses_broken_or_unsafe_timelines(change, expected):
    timeline = copy.deepcopy(cut.demo_timeline())
    change(timeline)
    problems = cut.validate_timeline(timeline)
    assert any(expected in p for p in problems), problems
    with pytest.raises(ValueError):
        cut.timeline_luau(timeline)


def test_generated_luau_renders_vectors_lists_and_escaped_text():
    timeline = cut.demo_timeline()
    timeline["shots"][0]["fov"] = [55, 52, 50]  # three numbers must stay a list, not become a Vector3
    timeline["cues"].append({"at": 14.95, "kind": "caption", "speaker": "Hero", "text": 'He said "go" (now)!',
                             "duration": 0.05})
    code = cut.timeline_luau(timeline)
    assert code.startswith("--!strict") and "Vector3.new(-34, 9, -22)" in code
    assert "fov = { 55, 52, 50 }" in code and r'text = "He said \"go\" (now)!"' in code
    assert luau_lint.lint(code, safety_checks=True) == []


def test_plan_reports_craft_lint_and_luau():
    result = cut.plan()
    assert result["ok"] and result["lint_errors"] == 0 and result["shots"] == 5
    assert "CutsceneGenerated" in result["modules"] and "return timeline" in result["generated_luau"]
    assert cut.plan({"name": "x"})["ok"] is False


def test_apply_installs_only_the_lab_and_the_composer_and_survives_brackets():
    code = cut.apply_luau({"timeline": cut.demo_timeline(), "speed": 0.35, "head": 10687288296}, "abcd1234")
    for name in (*cut.SHARED_MODULES, "CutsceneGenerated", "CutsceneLabConfig", cut.SERVER_MODULE):
        assert f'"{name}"' in code
    assert '"StarVfx"' in code and '"VfxClient"' in code  # the VFX composer modules for vfx cues
    assert ":Publish" not in code and "SavePlace" not in code and "HttpService" not in code.split("lab.Source")[0]
    assert code.count("[==[") + code.count("[=[") >= 10
    assert "STARCUT_APPLY abcd1234" in code
    assert "head = 10687288296" in cut.lab_config({"head": 10687288296}, "r")
    removal = cut.remove_luau()
    assert cut.LAB_FOLDER in removal and cut.LAB_CLIENT in removal and "StarVfx" in removal


# ------------------------------------------------------------------ evidence

CONSOLE = """noise
STARCUT client-ready r1
STARCUT actor r1 ok=true facecontrols=true
STARCUT cue r1 0.008 spawn Hero face backend facs
STARCUT shot r1 4.007 reaction
STARCUT frame r1 4.600 reaction fov=34.000 head 0.390 0.540 true 0.259 face facs surprised JawDrop=0.550 LeftLipCornerPuller=0.000 LeftBrowLowerer=0.000 LeftInnerBrowRaiser=0.900 LeftEyeClosed=0.000 LeftEyeUpperLidRaiser=0.850 tracks idle:1.00,gesture:recoil:1.00,joint=AnimationConstraint,arm56
STARCUT frame other 1.0 establish fov=50 head none face  tracks
STARCUT client-finished r1 finished camera=Custom subject=Humanoid fov=70.000 bars=false
"""


def test_console_evidence_is_parsed_per_run():
    evidence = cut.parse_console(CONSOLE, "r1")
    assert evidence["flags"]["actor"] == "ok=true facecontrols=true"
    assert evidence["cues"][0] == {"t": 0.008, "kind": "spawn", "name": "Hero", "detail": "face backend facs"}
    assert len(evidence["samples"]) == 1
    sample = evidence["samples"][0]
    assert sample["x"] == 0.39 and sample["on_screen"] and sample["backend"] == "facs"
    assert sample["facs"]["JawDrop"] == 0.55 and "gesture:recoil:1.00" in sample["tracks"]


def _frame(index, t, *, colour=(90, 120, 90), bars=True, shift=0, size=(192, 108)):
    image = Image.new("RGB", size, colour)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60 + shift, 40, 90 + shift, 70), fill=(230, 200, 160))
    if bars:
        draw.rectangle((0, 0, size[0], 11), fill=(0, 0, 0))
        draw.rectangle((0, size[1] - 12, size[0], size[1]), fill=(0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return {"index": index, "t": t, "data": buffer.getvalue()}


def _clip(timeline, offset=0.0):
    colours = {"establish": (90, 140, 90), "reaction": (160, 170, 200), "crystal": (40, 200, 90), "smile": (200, 150, 120),
               "pullback": (120, 100, 160)}
    frames = []
    for i in range(90):
        t = -0.5 + i * 0.2
        true_t = t + offset
        name = cut.shot_at(timeline, true_t)["name"] if 0 <= true_t <= timeline["length"] else None
        colour = colours.get(name, (110, 110, 110))
        frames.append(_frame(i, t, colour=colour, bars=0 <= true_t <= 14.6, shift=int(i % 4)))
    return frames


def _evidence(timeline, *, finished="finished camera=Custom subject=Humanoid fov=70.000 bars=false", on=True):
    samples = []
    for k in range(60):
        t = k * 0.25
        shot = cut.shot_at(timeline, t)
        expression = "neutral"
        facs = {name: 0.0 for name in cut.SAMPLE_FACS}
        for cue in cut._cues(timeline, "expression"):
            if t >= cue["at"] + (cue.get("duration") or 0.25):
                expression = cue["name"]
                facs = {name: cut.PRESETS[cue["name"]].get(name, 0.0) for name in cut.SAMPLE_FACS}
        samples.append({"t": t, "shot": shot["name"], "x": 0.4, "y": 0.5, "on_screen": on, "head_size": 0.25,
                        "backend": "facs", "expression": expression, "facs": facs})
    cues = [{"t": c["at"] + 0.01, "kind": c["kind"], "name": "-", "detail": "played" if c["kind"] == "vfx" else ""}
            for c in timeline["cues"]]
    return {"samples": samples, "cues": cues, "flags": {"client-finished": finished}, "shots": [], "vfx": []}


def test_critique_passes_a_good_capture_and_names_real_problems():
    timeline = cut.demo_timeline(3)
    good = cut.critique(_clip(timeline), _evidence(timeline), timeline)
    assert good["ok"], good["findings"]
    assert good["scores"]["letterbox_during"] > 0.8 and good["scores"]["letterbox_after"] == 0
    assert all(e.get("facs_match") for e in good["scores"]["expressions"])
    bad = cut.critique(_clip(timeline), _evidence(timeline, finished="finished camera=Scriptable subject=nil fov=40 "
                                                                       "bars=true", on=False), timeline)
    text = " ".join(bad["findings"])
    assert "off screen" in text and "control not fully returned" in text and "not readable on camera" in text


def test_frames_are_aligned_to_the_shot_cuts():
    timeline = cut.demo_timeline(3)
    frames = _clip(timeline, offset=0.4)  # the PC clock says t, the cutscene was really at t + 0.4
    shift = cut.align_frames(frames, timeline)
    assert 0.25 <= shift <= 0.55
    report = cut.critique(frames, _evidence(timeline), timeline)
    assert report["scores"]["cuts_seen"] == "4/4"


def test_contact_sheet_labels_time_and_shot(tmp_path):
    timeline = cut.demo_timeline(3)
    info = cut.contact_sheet(_clip(timeline), timeline, tmp_path / "sheet.jpg", title="t")
    assert (tmp_path / "sheet.jpg").is_file() and len(info["frames"]) == 20


# ------------------------------------------------------------------ the lab against a stand-in

class FakeJournal:
    def report(self):
        return {"edits": 2}


class FakeGuarded:
    studio_id = "studio-1"

    def __init__(self):
        self.journal = FakeJournal()
        self.calls = []
        self.run = None
        self.playing = False
        self.reads = 0

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "execute_luau":
            code = arguments["code"]
            found = re.search(r"STARCUT_(APPLY|CHECK) (\w+)", code)
            if found:
                self.run = found.group(2)
                result = (f"STARCUT_APPLY {self.run} 9 vfx=true" if found.group(1) == "APPLY"
                          else f"STARCUT_CHECK {self.run} CutsceneTypes=table; timeline=true nil")
            else:
                result = "STARCUT_REMOVED 4"
            return {"content": [{"type": "text", "text": "STAR_EDIT " + json.dumps({"ok": True, "result": result})}]}
        if name == "start_stop_play":
            self.playing = arguments["is_start"]
            return {"content": [{"type": "text", "text": "ok"}]}
        if name == "get_console_output":
            self.reads += 1
            lines = [f"STARCUT client-ready {self.run}"]
            if self.reads > 2:
                lines += [f"STARCUT client-play {self.run} crystal_wake length 15.000",
                          f"STARCUT cue {self.run} 0.008 spawn Hero face backend facs",
                          f"STARCUT client-finished {self.run} finished camera=Custom subject=Humanoid fov=70.000 bars=false"]
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        if name == "screen_capture":
            data = _frame(0, 0, colour=(40 + (len(self.calls) * 9) % 200, 120, 90))["data"]
            return {"content": [{"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/png"}]}
        return {"isError": True, "content": [{"type": "text", "text": "unknown"}]}


def test_the_lab_applies_checks_plays_captures_and_stops(tmp_path):
    clock = {"t": 0.0}

    async def sleep(seconds):
        clock["t"] += seconds

    def now():
        clock["t"] += 0.5
        return clock["t"]

    guarded = FakeGuarded()
    lab = cut.CutsceneLab(guarded, tmp_path, log=lambda *_: None, sleep=sleep, clock=now)
    report = asyncio.run(lab.run({"timeline": cut.demo_timeline(), "speed": 0.5}))
    assert report["apply"]["ok"] and report["check"]["ok"]
    play = report["playtest"]
    assert play["client_ready"] and play["played"] and play["frames"] >= 5 and play["stopped"]
    assert guarded.calls.count("start_stop_play") == 2 and not guarded.playing
    for name in ("sheet.jpg", "report.json", "evidence.json", "timeline.json", "CutsceneGenerated.luau"):
        assert (tmp_path / name).is_file(), name
    assert report["evidence"]["flags"]["client-finished"].startswith("finished camera=Custom")
    summary = cut.public_summary({"ok": True, "results": [report, {"removed": {"ok": True}}]})
    assert summary["runs"][0]["sheet"] == "sheet.jpg" and "data" not in json.dumps(summary)
    again = cut.reanalyse(tmp_path)
    assert (tmp_path / "critique.json").is_file() and "critique" in again


def test_the_lab_stops_play_even_when_the_client_never_starts(tmp_path):
    clock = {"t": 0.0}

    async def sleep(seconds):
        clock["t"] += seconds

    guarded = FakeGuarded()

    async def silent(name, arguments, original=guarded.call_tool):
        if name == "get_console_output":
            return {"content": [{"type": "text", "text": ""}]}
        return await original(name, arguments)

    guarded.call_tool = silent
    lab = cut.CutsceneLab(guarded, tmp_path, log=lambda *_: None, sleep=sleep, clock=lambda: clock["t"])
    report = asyncio.run(lab.run({"timeline": cut.demo_timeline()}))
    assert report["playtest"]["client_ready"] is False and report["playtest"]["stopped"] and not guarded.playing


# ------------------------------------------------------------------ the skill pack

def test_the_cutscene_pack_is_opt_in_bounded_and_chosen_for_cutscene_words():
    assert "roblox-cutscenes" not in skill_packs.DEFAULT_ENABLED
    pack = next(p for p in skill_packs.available() if p.name == "roblox-cutscenes")
    assert len(pack.body) <= skill_packs.MAX_BODY_CHARS
    names = [p.name for p in skill_packs.available()]
    prompt = "In my Roblox game: a boss intro cutscene with a letterbox, a skip button and FaceControls expressions."
    assert skill_packs.matching_names(prompt, enabled=names) == ["roblox-cutscenes"]
    assert skill_packs.matching_names("Plan a cinematic camera path for my film.", enabled=names) == []
