"""STAR Cutscene Studio: author, play and visually check Roblox cutscenes with facial expressions.

A cutscene is a *timeline* (data): camera shots back to back (a path of camera points, what to look at, FOV,
easing, depth of field) and cues at times (actors spawn and walk, gestures, facial expressions, blinks, talking,
captions, VFX composer cues, letterbox, fades). The typed Luau modules of the skill pack
star/skill_packs/roblox-cutscenes/luau/ play it: the server (CutsceneService) decides when and for whom, the
client (CutsceneClient -> CutscenePlayer) plays it with CameraPath, ExpressionPlayer, ActorMotion and CutsceneUi.

This module
  * validates a timeline (the same rules as CutsceneTypes.validate) and checks its craft (shot lengths, caption
    reading time, walk speed, letterbox in/out, expression changes that happen on camera),
  * renders it as a Luau ModuleScript and lints every pack module with STAR's Luau checks,
  * installs a lab in STAR Test Place through the guarded Studio path (studio_remote.PinnedSession ->
    studio_loop.GuardedStudio), playtests it in slow motion through the real server -> client RemoteEvent path,
    captures a frame sequence with the connector's screen_capture, stops, and
  * returns evidence: frames, a labelled contact sheet, the engine-side framing samples the lab client printed
    (where the subject's head is on screen, its size, the FOV, the FACS values) and a measured critique of framing,
    timing, easing, letterbox, VFX and return of control. All advisory; nothing is saved or published.

CLI: python -m star.roblox_cutscene_studio plan|run|remove ...
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import math
import re
import secrets
import time
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent / "skill_packs" / "roblox-cutscenes"
LUAU_DIR = PACK_DIR / "luau"
SHARED_MODULES = ("CutsceneTypes", "CameraPath", "ExpressionPlayer", "CutsceneUi", "ActorMotion", "CutscenePlayer",
                  "CutsceneClient")
SERVER_MODULE = "CutsceneService"
LAB_FOLDER = "StarCutsceneLab"          # ReplicatedStorage.StarCutsceneLab (modules), ServerScriptService (Script)
LAB_CLIENT = "StarCutsceneLabClient"    # StarterPlayer.StarterPlayerScripts.StarCutsceneLabClient
VFX_FOLDER = "StarVfx"                  # ReplicatedStorage.StarVfx: VFX composer modules for vfx cues
MARK = "STARCUT"
STAGE_ORIGIN = (-300.0, 0.0, 300.0)     # empty baseplate in STAR Test Place, away from the lobby and map drafts
MAX_FRAMES = 110

KINDS = ("spawn", "walk", "anim", "expression", "blink", "talk", "caption", "vfx", "letterbox", "fade", "despawn")
EXPRESSIONS = ("neutral", "happy", "angry", "surprised", "sad")
CURVES = ("catmull", "bezier", "linear")
EASING_STYLES = ("Linear", "Sine", "Back", "Quad", "Quart", "Quint", "Bounce", "Elastic", "Exponential", "Circular",
                 "Cubic")
EASING_DIRECTIONS = ("In", "Out", "InOut")
GESTURES = ("recoil", "nod", "reach", "wave", "point", "cheer")
# Python mirror of ExpressionPlayer.PRESETS (tests keep the two in step).
PRESETS: dict[str, dict[str, float]] = {
    "neutral": {},
    "happy": {"LeftLipCornerPuller": 0.85, "RightLipCornerPuller": 0.85, "LeftCheekRaiser": 0.6,
              "RightCheekRaiser": 0.6, "LeftEyeClosed": 0.2, "RightEyeClosed": 0.2, "LeftInnerBrowRaiser": 0.2,
              "RightInnerBrowRaiser": 0.2, "LeftDimpler": 0.3, "RightDimpler": 0.3, "JawDrop": 0.12},
    "angry": {"LeftBrowLowerer": 0.9, "RightBrowLowerer": 0.9, "Corrugator": 0.7, "LeftNoseWrinkler": 0.4,
              "RightNoseWrinkler": 0.4, "LipPresser": 0.6, "LeftUpperLipRaiser": 0.25, "RightUpperLipRaiser": 0.25,
              "LeftEyeUpperLidRaiser": 0.3, "RightEyeUpperLidRaiser": 0.3, "ChinRaiser": 0.3},
    "surprised": {"LeftInnerBrowRaiser": 0.9, "RightInnerBrowRaiser": 0.9, "LeftOuterBrowRaiser": 0.9,
                  "RightOuterBrowRaiser": 0.9, "LeftEyeUpperLidRaiser": 0.85, "RightEyeUpperLidRaiser": 0.85,
                  "JawDrop": 0.55, "Funneler": 0.25},
    "sad": {"LeftInnerBrowRaiser": 0.8, "RightInnerBrowRaiser": 0.8, "Corrugator": 0.35, "LeftLipCornerDown": 0.75,
            "RightLipCornerDown": 0.75, "ChinRaiser": 0.4, "LeftEyeClosed": 0.25, "RightEyeClosed": 0.25,
            "LeftLowerLipDepressor": 0.2, "RightLowerLipDepressor": 0.2, "EyesLookDown": 0.3},
}
# The 50 FaceControls properties (create.roblox.com FaceControls reference).
FACS = frozenset((
    "ChinRaiser", "ChinRaiserUpperLip", "Corrugator", "EyesLookDown", "EyesLookLeft", "EyesLookRight", "EyesLookUp",
    "FlatPucker", "Funneler", "JawDrop", "JawLeft", "JawRight", "LeftBrowLowerer", "LeftCheekPuff",
    "LeftCheekRaiser", "LeftDimpler", "LeftEyeClosed", "LeftEyeUpperLidRaiser", "LeftInnerBrowRaiser",
    "LeftLipCornerDown", "LeftLipCornerPuller", "LeftLipStretcher", "LeftLowerLipDepressor", "LeftNoseWrinkler",
    "LeftOuterBrowRaiser", "LeftUpperLipRaiser", "LipPresser", "LipsTogether", "LowerLipSuck", "MouthLeft",
    "MouthRight", "Pucker", "RightBrowLowerer", "RightCheekPuff", "RightCheekRaiser", "RightDimpler",
    "RightEyeClosed", "RightEyeUpperLidRaiser", "RightInnerBrowRaiser", "RightLipCornerDown",
    "RightLipCornerPuller", "RightLipStretcher", "RightLowerLipDepressor", "RightNoseWrinkler",
    "RightOuterBrowRaiser", "RightUpperLipRaiser", "TongueDown", "TongueOut", "TongueUp", "UpperLipSuck"))
# Key FACS values the lab client prints in every framing sample (to prove the engine took the values).
SAMPLE_FACS = ("JawDrop", "LeftLipCornerPuller", "LeftBrowLowerer", "LeftInnerBrowRaiser", "LeftEyeClosed",
               "LeftEyeUpperLidRaiser")

_TEXT = re.compile(r"[A-Za-z0-9 .,!?'\"\-:;()]{0,140}")  # printable, no brackets: rendered with json.dumps
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}")
_ASSET = re.compile(r"rbxassetid://[1-9][0-9]{0,18}")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# --------------------------------------------------------------------------- timeline: validation and craft

def _is_vec(value) -> bool:
    return (isinstance(value, (tuple, list)) and len(value) == 3
            and all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in value))


def validate_timeline(timeline: dict) -> list[str]:
    """Structural problems (the rules of CutsceneTypes.validate, plus the Luau-safe text and name rules)."""
    problems: list[str] = []
    if not isinstance(timeline, dict):
        return ["timeline is not a dict"]
    name = timeline.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        problems.append("name must be 1..40 letters, digits or _ and start with a letter")
    length = timeline.get("length")
    if not isinstance(length, (int, float)) or not 0 < length <= 120:
        return problems + ["length must be 0..120 seconds"]
    letterbox = timeline.get("letterbox", 0.11)
    if not isinstance(letterbox, (int, float)) or not 0 <= letterbox <= 0.2:
        problems.append("letterbox must be 0..0.2")
    shots = timeline.get("shots")
    if not isinstance(shots, list) or not 1 <= len(shots) <= 16:
        return problems + ["1..16 shots required"]
    cursor = 0.0
    for index, shot in enumerate(shots, 1):
        where = f"shot {index}"
        if not isinstance(shot, dict) or not isinstance(shot.get("name"), str) or not _NAME.fullmatch(shot["name"]):
            problems.append(f"{where}: needs a simple name")
            continue
        start, duration = shot.get("start"), shot.get("duration")
        if not isinstance(start, (int, float)) or not isinstance(duration, (int, float)) or duration <= 0:
            problems.append(f"{where}: start and a positive duration are required")
            continue
        if abs(start - cursor) > 1e-3:
            problems.append(f"{where}: starts at {start} but the previous shot ends at {cursor}")
        cursor = start + duration
        points = shot.get("points")
        if not isinstance(points, list) or not 1 <= len(points) <= 12 or not all(_is_vec(p) for p in points):
            problems.append(f"{where}: 1..12 camera points (x, y, z) required")
        look = shot.get("look")
        if look is not None and (not isinstance(look, list) or not look or not all(_is_vec(p) for p in look)):
            problems.append(f"{where}: look must be a list of (x, y, z)")
        if look is None and not shot.get("lookActor"):
            problems.append(f"{where}: needs look or lookActor")
        if shot.get("lookActor") is not None and not (isinstance(shot["lookActor"], str) and _NAME.fullmatch(shot["lookActor"])):
            problems.append(f"{where}: lookActor must be an actor name")
        if shot.get("lookOffset") is not None and not _is_vec(shot["lookOffset"]):
            problems.append(f"{where}: lookOffset must be (x, y, z)")
        if shot.get("curve", "catmull") not in CURVES:
            problems.append(f"{where}: unknown curve {shot.get('curve')!r}")
        fov = shot.get("fov")
        if fov is not None and (not isinstance(fov, list) or not fov
                                or not all(isinstance(f, (int, float)) and 1 <= f <= 120 for f in fov)):
            problems.append(f"{where}: FOV values must be 1..120")
        ease = shot.get("ease") or {}
        if ease.get("style", "Sine") not in EASING_STYLES or ease.get("direction", "InOut") not in EASING_DIRECTIONS:
            problems.append(f"{where}: unknown easing")
        roll = shot.get("roll", 0)
        if not isinstance(roll, (int, float)) or abs(roll) > 45:
            problems.append(f"{where}: roll must be within 45 degrees")
        dof = shot.get("dof")
        if dof is not None:
            if not isinstance(dof, dict) or set(dof) - {"focusActor", "distance", "radius", "far", "near"}:
                problems.append(f"{where}: dof has unknown fields")
            elif any(not isinstance(dof[k], (int, float)) or not 0 <= dof[k] <= 500
                     for k in ("distance", "radius", "far", "near") if k in dof):
                problems.append(f"{where}: dof numbers out of range")
    if abs(cursor - length) > 1e-3:
        problems.append(f"shots end at {cursor} but the timeline length is {length}")
    cues = timeline.get("cues")
    if not isinstance(cues, list) or len(cues) > 64:
        return problems + ["cues must be a list of at most 64"]
    last = 0.0
    for index, cue in enumerate(cues, 1):
        where = f"cue {index}"
        if not isinstance(cue, dict) or not isinstance(cue.get("at"), (int, float)) or cue.get("kind") not in KINDS:
            problems.append(f"{where}: needs a time and a known kind")
            continue
        if cue["at"] < last - 1e-6:
            problems.append(f"{where}: cues must be sorted by time")
        if not 0 <= cue["at"] <= length:
            problems.append(f"{where}: time outside the timeline")
        last = cue["at"]
        kind = cue["kind"]
        for key in ("actor", "template", "target"):
            if cue.get(key) is not None and not (isinstance(cue[key], str) and _NAME.fullmatch(cue[key])):
                problems.append(f"{where}: {key} must be a simple name")
        if kind == "expression" and cue.get("name") not in EXPRESSIONS:
            problems.append(f"{where}: unknown expression {cue.get('name')!r}")
        if kind == "caption":
            if not isinstance(cue.get("text"), str) or not _TEXT.fullmatch(cue["text"]):
                problems.append(f"{where}: caption text: at most 140 plain characters")
            if cue.get("speaker") is not None and not (isinstance(cue["speaker"], str) and _TEXT.fullmatch(cue["speaker"])
                                                       and len(cue["speaker"]) <= 30):
                problems.append(f"{where}: speaker: at most 30 plain characters")
        if kind == "walk" and not _is_vec(cue.get("to")):
            problems.append(f"{where}: walk needs to = (x, y, z)")
        if kind == "spawn" and (not isinstance(cue.get("template"), str) or not _is_vec(cue.get("position"))):
            problems.append(f"{where}: spawn needs a template and a position")
        if kind == "vfx":
            if not (isinstance(cue.get("ability"), str) and _NAME.fullmatch(cue["ability"])
                    and isinstance(cue.get("style"), str) and _NAME.fullmatch(cue["style"])):
                problems.append(f"{where}: vfx needs an ability and a style name")
            if cue.get("position") is not None and not _is_vec(cue["position"]):
                problems.append(f"{where}: vfx position must be (x, y, z)")
        if kind == "anim":
            if cue.get("animation") is not None and not (isinstance(cue["animation"], str) and _ASSET.fullmatch(cue["animation"])):
                problems.append(f"{where}: animation must be rbxassetid://<number>")
            if cue.get("animation") is None and cue.get("name") not in GESTURES:
                problems.append(f"{where}: unknown gesture {cue.get('name')!r}")
        for key in ("duration", "weight", "alpha", "facing"):
            value = cue.get(key)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)):
                problems.append(f"{where}: {key} must be a number")
        if cue.get("duration") is not None and isinstance(cue["duration"], (int, float)) and not 0 <= cue["duration"] <= 60:
            problems.append(f"{where}: duration must be 0..60 s")
    return problems


def _cues(timeline: dict, kind: str) -> list[dict]:
    return [c for c in timeline.get("cues", []) if c.get("kind") == kind]


def shot_at(timeline: dict, t: float) -> dict:
    for shot in timeline["shots"]:
        if t < shot["start"] + shot["duration"]:
            return shot
    return timeline["shots"][-1]


def craft_check(timeline: dict) -> list[str]:
    """Cinematography and pacing advice for a valid timeline (not errors)."""
    notes = []
    for shot in timeline["shots"]:
        if shot["duration"] < 1.2:
            notes.append(f"shot {shot['name']}: {shot['duration']:.2f}s is shorter than 1.2s: a cut this quick reads as a "
                         "jump unless it is a deliberate impact cut")
        fov = shot.get("fov") or [70]
        if max(fov) - min(fov) > 25:
            notes.append(f"shot {shot['name']}: FOV changes by more than 25 degrees: a zoom this big looks like a lens "
                         "breathing error; dolly the camera instead")
        if len(shot["points"]) > 1:
            span = max(math.dist(a, b) for a in shot["points"] for b in shot["points"])
            speed = span / shot["duration"]
            if speed > 25:
                notes.append(f"shot {shot['name']}: camera moves about {speed:.0f} studs/s: too fast to read the scene")
        if (shot.get("ease") or {}).get("style") == "Linear" and len(shot["points"]) > 1:
            notes.append(f"shot {shot['name']}: linear easing starts and stops the camera abruptly; Sine or Quad InOut")
    for cue in _cues(timeline, "caption"):
        need = len(cue["text"]) / 15 + 0.8
        if (cue.get("duration") or need) < need - 1e-6:
            notes.append(f"caption at {cue['at']}s: {cue['duration']}s on screen; reading needs about {need:.1f}s")
        if cue["at"] + (cue.get("duration") or need) > timeline["length"] + 0.01:
            notes.append(f"caption at {cue['at']}s runs past the end of the cutscene")
    starts = {c.get("actor"): c for c in _cues(timeline, "spawn")}
    for cue in _cues(timeline, "walk"):
        spawn = starts.get(cue.get("actor"))
        if spawn and cue.get("duration"):
            speed = math.dist(spawn["position"][::2], cue["to"][::2]) / cue["duration"]
            if not 3 <= speed <= 16:
                notes.append(f"walk at {cue['at']}s: {speed:.1f} studs/s; a believable walk is 4..10 (the default walk "
                             "cycle is authored for 16)")
    for cue in _cues(timeline, "expression"):
        shot = shot_at(timeline, cue["at"] + min(0.3, cue.get("duration") or 0.25))
        if shot.get("lookActor") != cue.get("actor"):
            notes.append(f"expression {cue['name']} at {cue['at']}s happens in shot {shot['name']}, which does not look "
                         f"at {cue.get('actor')}: the change may be off camera")
        if not 0.08 <= (cue.get("duration") or 0.25) <= 1.0:
            notes.append(f"expression {cue['name']} at {cue['at']}s: a blend outside 0.08..1.0s looks robotic or mushy")
    boxes = _cues(timeline, "letterbox")
    if timeline.get("letterbox", 0.11) > 0:
        if not boxes or boxes[0].get("show") is False or boxes[0]["at"] > 0.5:
            notes.append("letterbox: bring the bars in at the start (they tell the player control is taken)")
        if not any(b.get("show") is False for b in boxes):
            notes.append("letterbox: take the bars out before the end so the hand-back to gameplay is visible")
    if not timeline.get("skippable", True):
        notes.append("not skippable: always let players skip a cutscene they have seen")
    if timeline["length"] > 20:
        notes.append("longer than 20s: players skip long cutscenes; split it or let gameplay continue")
    return notes


# --------------------------------------------------------------------------- Luau rendering

def _num(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("non-finite number")
    text = repr(round(float(value), 4))
    return text[:-2] if text.endswith(".0") else text


def _vec(value) -> str:
    return "Vector3.new(" + ", ".join(_num(float(c)) for c in value) + ")"


def _str(value: str) -> str:
    if not (_TEXT.fullmatch(value) or _NAME.fullmatch(value) or _ASSET.fullmatch(value)):
        raise ValueError("unsafe text")
    return json.dumps(value)  # printable ASCII only: JSON string escapes are valid Luau escapes


def _field(key: str, value) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif key == "fov" and isinstance(value, list) and all(isinstance(v, (int, float)) for v in value):
        rendered = "{ " + ", ".join(_num(float(v)) for v in value) + " }"
    elif isinstance(value, (int, float)):
        rendered = _num(float(value))
    elif isinstance(value, str):
        rendered = _str(value)
    elif _is_vec(value):
        rendered = _vec(value)
    elif isinstance(value, list) and value and all(_is_vec(v) for v in value):
        rendered = "{ " + ", ".join(_vec(v) for v in value) + " }"
    elif isinstance(value, list) and all(isinstance(v, (int, float)) for v in value):
        rendered = "{ " + ", ".join(_num(float(v)) for v in value) + " }"
    elif isinstance(value, dict):
        rendered = "{ " + ", ".join(_field(k, v) for k, v in value.items()) + " }"
    else:
        raise ValueError(f"unsupported value for {key}")
    if not _NAME.fullmatch(key):
        raise ValueError(f"unsafe key {key!r}")
    return f"{key} = {rendered}"


def timeline_luau(timeline: dict) -> str:
    """A ModuleScript returning the timeline as a CutsceneTypes.Timeline table."""
    problems = validate_timeline(timeline)
    if problems:
        raise ValueError("; ".join(problems[:5]))
    lines = ["--!strict", "-- Generated by STAR (star/roblox_cutscene_studio.py). Positions are local to the play origin.",
             'local Types = require(script.Parent:WaitForChild("CutsceneTypes"))', "",
             "local timeline: Types.Timeline = {",
             f"\tname = {_str(timeline['name'])},", f"\tlength = {_num(timeline['length'])},",
             f"\tskippable = {'true' if timeline.get('skippable', True) else 'false'},",
             f"\tletterbox = {_num(timeline.get('letterbox', 0.11))},", "\tshots = {"]
    for shot in timeline["shots"]:
        lines.append("\t\t{ " + ", ".join(_field(k, v) for k, v in shot.items() if v is not None) + " },")
    lines.append("\t},")
    lines.append("\tcues = {")
    for cue in timeline["cues"]:
        lines.append("\t\t{ " + ", ".join(_field(k, v) for k, v in cue.items() if v is not None) + " },")
    lines += ["\t},", "}", "", "return timeline", ""]
    return "\n".join(lines)


def pack_sources() -> dict[str, str]:
    """The shipped Luau modules of the skill pack, by module name."""
    return {name: (LUAU_DIR / f"{name}.luau").read_text(encoding="utf-8") for name in (*SHARED_MODULES, SERVER_MODULE)}


def lint_sources(sources: dict[str, str]) -> dict[str, list[dict]]:
    """STAR's static Luau checks over every module (server-trust checks on the server module)."""
    from . import luau_lint
    out = {}
    for name, code in sources.items():
        findings = luau_lint.lint(code, safety_checks=True, server_security=name.endswith("Service"))
        out[name] = [{"rule": f.rule_id, "line": f.line, "severity": f.severity, "message": f.message} for f in findings]
    return out


# --------------------------------------------------------------------------- the demo cutscene (data)

HERO = "Hero"


def demo_timeline(version: int = 3) -> dict:
    """The 15-second lab cutscene: a hero walks to a crystal, is surprised, the crystal bursts (VFX), the hero
    smiles. Five shots: establishing tracking shot, medium close-up reaction, over-the-shoulder on the crystal,
    close-up smile, crane pull-back. `version` keeps the earlier iterations reproducible (see the notes file)."""
    v = int(_clamp(version, 1, 3))
    # Set: the hero enters at x = -26 and stops at x = 0; the crystal pedestal is at x = 8 (all local, studs).
    est_points = [(-30, 12, -26), (-20, 9, -24), (-8, 7, -20)] if v == 1 else [(-34, 9, -22), (-22, 7.5, -21), (-9, 6.5, -18)]
    shots = [
        {"name": "establish", "start": 0.0, "duration": 4.0, "curve": "catmull", "points": est_points,
         "lookActor": HERO, "lookOffset": (3, -0.5, 0) if v > 1 else (0, 0, 0), "fov": [55, 50] if v > 1 else [60, 55],
         "ease": {"style": "Sine", "direction": "InOut"}},
        {"name": "reaction", "start": 4.0, "duration": 3.5, "curve": "linear",
         "points": [(6.5, 5.1, 5.5), (5.5, 5, 4.6)] if v > 1 else [(9, 5.5, 1.5), (8, 5.5, 1)],
         "lookActor": HERO, "lookOffset": (1.2, 0.2, 0) if v > 2 else (0, 0.2, 0), "fov": [36, 30] if v > 1 else [40, 30],
         "ease": {"style": "Quad", "direction": "Out"} if v > 1 else {"style": "Linear", "direction": "InOut"},
         "dof": {"focusActor": HERO, "radius": 5, "far": 0.45, "near": 0.2}},
        {"name": "crystal", "start": 7.5, "duration": 3.0, "curve": "catmull",
         "points": [(-12, 8, -12), (-10, 7.5, -10.5)] if v > 1 else [(-3, 6, -4), (-2, 5.5, -3)],
         "look": [(8, 3.5, 0), (8, 4.5, 0)], "fov": [55, 50] if v > 1 else [55, 55],
         "ease": {"style": "Sine", "direction": "InOut"}},
        {"name": "smile", "start": 10.5, "duration": 2.5, "curve": "linear",
         "points": [(6.5, 5, -4.5), (5.6, 5, -3.6)] if v > 1 else [(7, 5, -4), (6.5, 5, -3.2)],
         "lookActor": HERO, "lookOffset": (0, 0.1, 0), "fov": [34, 30] if v > 1 else [38, 34],
         "ease": {"style": "Sine", "direction": "InOut"}, "roll": 0,
         "dof": {"focusActor": HERO, "radius": 4, "far": 0.4, "near": 0.2}},
        {"name": "pullback", "start": 13.0, "duration": 2.0, "curve": "bezier",
         "points": ([(2, 7, -10), (-2, 9.5, -14), (-5, 12, -17.5)] if v > 2 else [(2, 7, -10), (-4, 11, -16), (-8, 15, -21)])
         if v > 1 else [(2, 6, -8), (-6, 12, -16), (-14, 18, -24)],
         "look": [(4, 3, 0), (4, 2, 0)], "fov": [50, 58] if v > 1 else [55, 60],
         "ease": {"style": "Quad", "direction": "InOut"} if v > 1 else {"style": "Sine", "direction": "In"}},
    ]
    cues = [
        {"at": 0.0, "kind": "letterbox", "show": True, "duration": 0.6},
        {"at": 0.0, "kind": "spawn", "actor": HERO, "template": HERO, "position": (-26, 0, 0), "facing": -90},
        {"at": 0.3, "kind": "walk", "actor": HERO, "to": (0, 0, 0), "duration": 3.6},
        {"at": 2.0, "kind": "blink", "actor": HERO},
        {"at": 4.3 if v > 1 else 4.1, "kind": "expression", "actor": HERO, "name": "surprised",
         "duration": 0.18 if v > 1 else 0.4},
        {"at": 4.35 if v > 1 else 4.2, "kind": "anim", "actor": HERO, "name": "recoil"},
        {"at": 5.6, "kind": "blink", "actor": HERO},
        {"at": 5.7, "kind": "caption", "speaker": "Hero", "text": "The crystal... it is waking up!", "duration": 2.9},
        {"at": 5.8, "kind": "talk", "actor": HERO, "duration": 1.3},
        {"at": 7.8, "kind": "vfx", "ability": "energy_burst", "style": "anime_energy", "position": (8, 0, 0)},
        {"at": 10.6 if v > 1 else 10.9, "kind": "expression", "actor": HERO, "name": "happy", "duration": 0.35},
        {"at": 11.0, "kind": "caption", "speaker": "Hero", "text": "It chose me.", "duration": 1.8},
        {"at": 11.1, "kind": "talk", "actor": HERO, "duration": 0.6},
        {"at": 11.9, "kind": "blink", "actor": HERO},
        {"at": 12.2, "kind": "anim", "actor": HERO, "name": "nod"},
        {"at": 14.2, "kind": "letterbox", "show": False, "duration": 0.6},
    ]
    if v == 1:
        cues = [c for c in cues if not (c["kind"] == "letterbox" and c.get("show") is False)]
    cues.sort(key=lambda c: c["at"])
    return {"name": "crystal_wake", "length": 15.0, "skippable": True, "letterbox": 0.11, "shots": shots, "cues": cues}


def plan(timeline: dict | None = None) -> dict:
    """Offline: validation, craft notes, the generated Luau and STAR's lint findings. Applies nothing."""
    timeline = timeline or demo_timeline()
    problems = validate_timeline(timeline)
    if problems:
        return {"ok": False, "problems": problems}
    generated = timeline_luau(timeline)
    sources = {**pack_sources(), "CutsceneGenerated": generated}
    findings = lint_sources(sources)
    return {"ok": True, "craft": craft_check(timeline), "generated_luau": generated, "lint": findings,
            "lint_errors": sum(1 for items in findings.values() for f in items if f["severity"] == "error"),
            "modules": sorted(sources), "length_seconds": timeline["length"], "shots": len(timeline["shots"])}


# --------------------------------------------------------------------------- the Studio lab (Luau)

def _long_string(text: str) -> str:
    level = 1
    while ("]" + "=" * level + "]") in text:
        level += 1
    return "[" + "=" * level + "[" + text + "]" + "=" * level + "]"


LAB_SERVER = r"""--!strict
-- STAR cutscene lab (Studio playtest only): builds a small set at the lab origin, builds the actor template on the
-- server, then asks CutsceneService to play the cutscene for the player (server triggers, client plays).
-- Remove with `python -m star.roblox_cutscene_studio remove`.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local CutsceneService = require(script:WaitForChild("CutsceneService"))
local folder = ReplicatedStorage:WaitForChild("__FOLDER__")
local config = require(folder:WaitForChild("CutsceneLabConfig")) :: any
local timeline = require(folder:WaitForChild("CutsceneGenerated")) :: any
CutsceneService.config.cutscenes[timeline.name] = { length = timeline.length / config.speed, cooldown = 1, freeze = true }
CutsceneService.start()
local origin = CFrame.new(config.origin[1], config.origin[2], config.origin[3])

local set = Instance.new("Model")
set.Name = "StarCutsceneSet"
local function part(name: string, size: Vector3, offset: CFrame, color: Color3, material: Enum.Material, shape: Enum.PartType?): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.Size = size
	p.CFrame = origin * offset
	p.Color = color
	p.Material = material
	if shape then
		p.Shape = shape
	end
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = set
	return p
end
local stone = Color3.fromRGB(120, 116, 110)
part("Ground", Vector3.new(90, 1, 50), CFrame.new(-6, -0.45, 0), Color3.fromRGB(70, 92, 60), Enum.Material.Grass)
for i = 0, 9 do
	part("PathTile" .. i, Vector3.new(3.2, 0.3, 4), CFrame.new(-27 + i * 3.4, 0.15, 0), stone, Enum.Material.Slate)
end
part("Pedestal", Vector3.new(3, 2.4, 3), CFrame.new(8, 1.2, 0), stone, Enum.Material.Cobblestone)
local crystal = part("Crystal", Vector3.new(1.4, 3.2, 1.4), CFrame.new(8, 4, 0) * CFrame.Angles(0, math.rad(45), math.rad(8)), Color3.fromRGB(90, 255, 140), Enum.Material.Neon)
local glow = Instance.new("PointLight")
glow.Color = Color3.fromRGB(90, 255, 140)
glow.Range = 14
glow.Brightness = 2
glow.Parent = crystal
for _, z in { -7, 7 } do
	part("Pillar", Vector3.new(2, 12, 2), CFrame.new(11, 6, z), stone, Enum.Material.Slate)
end
part("Lintel", Vector3.new(2.4, 1.6, 16.4), CFrame.new(11, 12.6, 0), stone, Enum.Material.Slate)
part("Backdrop", Vector3.new(2, 18, 46), CFrame.new(24, 9, 0), Color3.fromRGB(60, 64, 78), Enum.Material.Rock)
for i, at in { Vector3.new(-14, 0.8, 7), Vector3.new(-6, 0.6, -8), Vector3.new(4, 0.9, 9), Vector3.new(-20, 0.7, -6) } do
	part("Rock" .. i, Vector3.new(2.6, 1.8, 2.2), CFrame.new(at) * CFrame.Angles(0.3 * i, 0.7 * i, 0.2), Color3.fromRGB(96, 92, 88), Enum.Material.Rock)
end
set.Parent = workspace

local description = Instance.new("HumanoidDescription")
description.HeadColor = Color3.fromRGB(234, 184, 146)
description.LeftArmColor = description.HeadColor
description.RightArmColor = description.HeadColor
description.TorsoColor = Color3.fromRGB(52, 96, 200)
description.LeftLegColor = Color3.fromRGB(40, 40, 52)
description.RightLegColor = Color3.fromRGB(40, 40, 52)
if config.head > 0 then
	description.Head = config.head
end
local okActor, actor = pcall(CutsceneService.makeActor, "__HERO__", description)
if not okActor then
	print("__MARK__ actor-head-failed " .. config.run .. " " .. string.sub(tostring(actor), 1, 120))
	description.Head = 0
	okActor, actor = pcall(CutsceneService.makeActor, "__HERO__", description)
end
local faceControls = okActor and (actor :: Model):FindFirstChildWhichIsA("FaceControls", true)
print("__MARK__ actor " .. config.run .. " ok=" .. tostring(okActor) .. " facecontrols=" .. tostring(faceControls ~= nil))

local player = Players:GetPlayers()[1] or Players.PlayerAdded:Wait()
local character = player.Character or player.CharacterAdded:Wait()
local root = character:WaitForChild("HumanoidRootPart") :: BasePart
root.Anchored = true
character:PivotTo(origin * CFrame.new(0, -40, 0)) -- parked under the set, out of every shot (iter2 showed it at -40, -90)
CutsceneService.Finished:Connect(function(_p: Player, name: string, state: string)
	print("__MARK__ server-finished " .. config.run .. " " .. name .. " " .. state)
	character:PivotTo(origin * CFrame.new(-30, 3.5, -6) * CFrame.Angles(0, math.rad(-90), 0)) -- back on the set
	root.Anchored = false
end)
task.wait(config.lead) -- time for the lab client to load (client-made instances do not replicate, so no handshake)
local okPlay, why = CutsceneService.play(player, timeline.name, origin)
print("__MARK__ server-play " .. config.run .. " " .. tostring(okPlay) .. " " .. tostring(why))
"""

LAB_CLIENT_SRC = r"""--!strict
-- STAR cutscene lab client (Studio playtest only): registers the generated timeline, plays what the server asks
-- for in slow motion, prints engine-side evidence (cues, shots, framing samples with FACS values) and shows the
-- cutscene time in a corner of the frame.
local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local folder = ReplicatedStorage:WaitForChild("__FOLDER__")
local CutsceneClient = require(folder:WaitForChild("CutsceneClient")) :: any
local timeline = require(folder:WaitForChild("CutsceneGenerated")) :: any
local config = require(folder:WaitForChild("CutsceneLabConfig")) :: any
if config.clock then
	Lighting.ClockTime = config.clock
end
local ok, problem = CutsceneClient.register(timeline)
print("__MARK__ register " .. config.run .. " " .. tostring(ok) .. " " .. tostring(problem))
CutsceneClient.speed = config.speed
CutsceneClient.options.faceBackend = config.faceBackend
local vfxFolder = ReplicatedStorage:FindFirstChild("__VFX__")
if vfxFolder then
	local VfxClient = require(vfxFolder:WaitForChild("VfxClient")) :: any
	CutsceneClient.options.vfx = function(cue: any, at: CFrame, speed: number)
		local handle = VfxClient.preview(cue.ability, cue.style, at, speed)
		print("__MARK__ vfx " .. config.run .. " " .. tostring(cue.ability) .. " " .. tostring(handle ~= nil))
	end
end
local active: any = nil
local nextSample = 0
local function f3(x: number): string
	return string.format("%.3f", x)
end
CutsceneClient.options.onCue = function(cue: any, t: number, detail: string?)
	print("__MARK__ cue " .. config.run .. " " .. f3(t) .. " " .. cue.kind .. " " .. tostring(cue.name or cue.actor or "-") .. " " .. tostring(detail or ""))
end
CutsceneClient.options.onShot = function(shot: any, t: number)
	print("__MARK__ shot " .. config.run .. " " .. f3(t) .. " " .. shot.name)
end
local facsNames = { __FACS__ }
CutsceneClient.options.onFrame = function(t: number, shot: any, cam: Camera)
	if t + 1e-6 < nextSample then
		return
	end
	nextSample = t + config.sampleEvery
	local actors = workspace:FindFirstChild("StarCutsceneActors")
	local hero = actors and actors:FindFirstChild("__HERO__")
	local head = hero and hero:FindFirstChild("Head")
	local vp = cam.ViewportSize
	local framing = "none"
	if head and head:IsA("BasePart") then
		local p, onScreen = cam:WorldToViewportPoint(head.Position)
		local top = cam:WorldToViewportPoint(head.Position + Vector3.new(0, head.Size.Y / 2, 0))
		local bottom = cam:WorldToViewportPoint(head.Position - Vector3.new(0, head.Size.Y / 2, 0))
		framing = f3(p.X / vp.X) .. " " .. f3(p.Y / vp.Y) .. " " .. tostring(onScreen and p.Z > 0) .. " " .. f3(math.abs(bottom.Y - top.Y) / vp.Y)
	end
	local facs = ""
	local face = active and active.faces["__HERO__"]
	if face then
		local snap = face:snapshot()
		local parts = { face.backend, face.current }
		for _, name in facsNames do
			table.insert(parts, name .. "=" .. f3(snap[name] or 0))
		end
		facs = table.concat(parts, " ")
	end
	local tracks = {}
	local actor = active and active.actors["__HERO__"]
	if actor and actor.animator then
		for _, track in actor.animator:GetPlayingAnimationTracks() do
			table.insert(tracks, track.Animation.Name .. ":" .. string.format("%.2f", track.WeightCurrent))
		end
	end
	local arm = -1
	local shoulder = hero and hero:FindFirstChild("RightShoulder", true)
	if shoulder and (shoulder:IsA("Motor6D") or shoulder:IsA("AnimationConstraint")) then
		local _axis, angle = (shoulder :: any).Transform:ToAxisAngle()
		arm = math.deg(angle)
	end
	table.insert(tracks, "joint=" .. (if shoulder then shoulder.ClassName else "none"))
	table.insert(tracks, "arm" .. string.format("%.0f", arm))
	print("__MARK__ frame " .. config.run .. " " .. f3(t) .. " " .. shot.name .. " fov=" .. f3(cam.FieldOfView) .. " head " .. framing .. " face " .. facs .. " tracks " .. table.concat(tracks, ","))
end
CutsceneClient.onPlay = function(name: string, handle: any)
	active = handle
	print("__MARK__ client-play " .. config.run .. " " .. name .. " length " .. f3(handle.length))
	local label: TextLabel? = nil
	if config.timer then
		local gui = Instance.new("ScreenGui")
		gui.Name = "StarCutsceneLabTimer"
		gui.ResetOnSpawn = false
		gui.IgnoreGuiInset = true
		gui.DisplayOrder = 60
		local text = Instance.new("TextLabel")
		text.BackgroundTransparency = 0.5
		text.BackgroundColor3 = Color3.new(0, 0, 0)
		text.TextColor3 = Color3.new(1, 1, 1)
		text.Font = Enum.Font.Code
		text.TextSize = 13
		text.Size = UDim2.fromOffset(190, 18)
		text.Position = UDim2.fromOffset(6, 6)
		text.ZIndex = 10
		text.Parent = gui
		gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
		label = text
	end
	local conn = RunService.RenderStepped:Connect(function()
		local l = label
		if l and handle.state() == "playing" then
			local t = handle.time()
			local shotName = "?"
			for _, shot in timeline.shots do
				if t < shot.start + shot.duration then
					shotName = shot.name
					break
				end
			end
			l.Text = string.format("t=%.2fs %s", t, shotName)
		end
	end)
	if config.skipAt and config.skipAt > 0 then
		task.delay(config.skipAt / config.speed, function()
			print("__MARK__ skip-pressed " .. config.run .. " " .. f3(handle.time()))
			handle.skip()
		end)
	end
	handle.finished:Once(function(state: string)
		conn:Disconnect()
		local l = label
		if l then
			l.Text = "ended: " .. state
		end
		task.wait(0.2)
		local cam = workspace.CurrentCamera
		local subject = cam.CameraSubject
		print("__MARK__ client-finished " .. config.run .. " " .. state .. " camera=" .. cam.CameraType.Name .. " subject=" .. (if subject then subject.ClassName else "nil") .. " fov=" .. f3(cam.FieldOfView) .. " bars=" .. tostring(Players.LocalPlayer.PlayerGui:FindFirstChild("StarCutsceneUi") ~= nil))
	end)
end
CutsceneClient.start()
print("__MARK__ client-ready " .. config.run)
"""


def lab_config(spec: dict, run: str) -> str:
    values = {"run": run, "speed": float(_clamp(spec.get("speed", 0.35), 0.05, 1)),
              "lead": float(spec.get("lead", 6)), "sampleEvery": float(spec.get("sample_every", 0.25)),
              "head": int(spec.get("head") or 0), "timer": bool(spec.get("timer", True)),
              "skipAt": float(spec.get("skip_at") or 0),
              "faceBackend": spec.get("face_backend") if spec.get("face_backend") in ("facs", "gui") else "auto"}
    lines = ["--!strict", "return {"]
    for key, value in values.items():
        rendered = ("true" if value else "false") if isinstance(value, bool) else (
            json.dumps(value) if isinstance(value, str) else _num(float(value)))
        lines.append(f"\t{key} = {rendered},")
    lines.append(f"\torigin = {{ {', '.join(_num(float(c)) for c in spec.get('origin', STAGE_ORIGIN))} }},")
    clock = spec.get("clock")
    lines.append(f"\tclock = {_num(float(clock)) if isinstance(clock, (int, float)) else 'nil'},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _vfx_sources() -> dict[str, str]:
    """The VFX composer client modules (roblox-vfx-composer pack), when that pack is present."""
    try:
        from . import roblox_vfx_studio
        sources = roblox_vfx_studio.pack_sources()
        return {name: sources[name] for name in roblox_vfx_studio.SHARED_MODULES}
    except (ImportError, OSError, KeyError):
        return {}


def apply_luau(spec: dict, run: str) -> str:
    """Edit-DataModel Luau that installs the lab (one undo step through GuardedStudio): pack modules, the generated
    timeline and the lab config in ReplicatedStorage.StarCutsceneLab, the VFX composer client modules in
    ReplicatedStorage.StarVfx, the lab Script (with CutsceneService inside) in ServerScriptService and the lab client
    in StarterPlayerScripts. Earlier lab copies are replaced; nothing else is touched."""
    sources = pack_sources()
    modules = {name: sources[name] for name in SHARED_MODULES}
    modules["CutsceneGenerated"] = timeline_luau(spec["timeline"])
    modules["CutsceneLabConfig"] = lab_config(spec, run)
    vfx = _vfx_sources()
    facs = ", ".join(json.dumps(n) for n in SAMPLE_FACS)
    server = LAB_SERVER.replace("__FOLDER__", LAB_FOLDER).replace("__MARK__", MARK).replace("__HERO__", HERO)
    client = (LAB_CLIENT_SRC.replace("__FOLDER__", LAB_FOLDER).replace("__MARK__", MARK).replace("__HERO__", HERO)
              .replace("__VFX__", VFX_FOLDER).replace("__FACS__", facs))
    out = ['local RS = game:GetService("ReplicatedStorage")',
           'local SSS = game:GetService("ServerScriptService")',
           'local SPS = game:GetService("StarterPlayer"):WaitForChild("StarterPlayerScripts")',
           f'for _, parent in {{ RS, SSS, SPS }} do for _, name in {{ "{LAB_FOLDER}", "{LAB_CLIENT}", "{VFX_FOLDER}" }} do',
           '\tlocal old = parent:FindFirstChild(name) if old then old:Destroy() end end end',
           'local function module(folder, name, source) local m = Instance.new("ModuleScript") m.Name = name m.Source = source m.Parent = folder end',
           f'local folder = Instance.new("Folder") folder.Name = "{LAB_FOLDER}"']
    for name, code in modules.items():
        out.append(f'module(folder, "{name}", {_long_string(code)})')
    out.append('folder.Parent = RS')
    if vfx:
        out.append(f'local vfx = Instance.new("Folder") vfx.Name = "{VFX_FOLDER}"')
        for name, code in vfx.items():
            out.append(f'module(vfx, "{name}", {_long_string(code)})')
        out.append('vfx.Parent = RS')
    out += [f'local lab = Instance.new("Script") lab.Name = "{LAB_FOLDER}" lab.Source = {_long_string(server)}',
            f'module(lab, "{SERVER_MODULE}", {_long_string(sources[SERVER_MODULE])})',
            'lab.Parent = SSS',
            f'local client = Instance.new("LocalScript") client.Name = "{LAB_CLIENT}" client.Source = {_long_string(client)}',
            'client.Parent = SPS',
            f'return "{MARK}_APPLY {run} " .. #folder:GetChildren() .. " vfx=" .. tostring(RS:FindFirstChild("{VFX_FOLDER}") ~= nil)']
    return "\n".join(out)


def check_luau(run: str) -> str:
    """Edit-DataModel Luau that requires the shared modules once (real Luau parse and load) and validates the
    generated timeline with CutsceneTypes.validate. Client-only modules are required for their shape only."""
    names = ", ".join(json.dumps(n) for n in ("CutsceneTypes", "CameraPath", "CutsceneGenerated", "CutsceneLabConfig"))
    return (f'local folder = game:GetService("ReplicatedStorage"):FindFirstChild("{LAB_FOLDER}")\n'
            'if not folder then return "missing" end\n'
            'local out = {}\n'
            f'for _, name in {{ {names} }} do\n'
            '\tlocal ok, result = pcall(require, folder:FindFirstChild(name))\n'
            '\ttable.insert(out, name .. "=" .. (ok and type(result) or ("ERR " .. string.sub(tostring(result), 1, 160))))\n'
            'end\n'
            'local okT, Types = pcall(require, folder.CutsceneTypes)\n'
            'local okG, timeline = pcall(require, folder.CutsceneGenerated)\n'
            'if okT and okG then local fine, why = Types.validate(timeline) table.insert(out, "timeline=" .. tostring(fine) .. " " .. tostring(why)) end\n'
            'local okP, CameraPath = pcall(require, folder.CameraPath)\n'
            'if okP and okG then local p = CameraPath.new(timeline.shots[1]) local cf, fov = p:sample(timeline.shots[1].start + 0.5, CFrame.new(), nil) '
            'table.insert(out, "path=" .. string.format("%.2f,%.2f,%.2f fov %.1f", cf.X, cf.Y, cf.Z, fov)) end\n'
            f'return "{MARK}_CHECK {run} " .. table.concat(out, "; ")')


def remove_luau() -> str:
    return ('local n = 0\n'
            'for _, parent in { game:GetService("ReplicatedStorage"), game:GetService("ServerScriptService"), '
            'game:GetService("StarterPlayer"):WaitForChild("StarterPlayerScripts") } do\n'
            f'\tfor _, name in {{ "{LAB_FOLDER}", "{LAB_CLIENT}", "{VFX_FOLDER}" }} do local old = parent:FindFirstChild(name) '
            'if old then old:Destroy() n += 1 end end\nend\n'
            f'return "{MARK}_REMOVED " .. n')


# --------------------------------------------------------------------------- evidence: console parsing

_LINE = re.compile(rf"{MARK} (\S+) (\S+)(.*)")


def parse_console(text: str, run: str) -> dict:
    """The lab's printed evidence for one run: cues, shots, framing samples, finish lines."""
    out = {"cues": [], "shots": [], "samples": [], "flags": {}, "vfx": []}
    for raw in text.splitlines():
        at = raw.find(MARK + " ")
        if at < 0:
            continue
        match = _LINE.match(raw[at:].strip())
        if not match or match.group(2) != run:
            continue
        kind, rest = match.group(1), match.group(3).strip()
        parts = rest.split()
        try:
            if kind == "cue" and len(parts) >= 3:
                out["cues"].append({"t": float(parts[0]), "kind": parts[1], "name": parts[2], "detail": " ".join(parts[3:])})
            elif kind == "shot" and len(parts) >= 2:
                out["shots"].append({"t": float(parts[0]), "name": parts[1]})
            elif kind == "frame" and len(parts) >= 3:
                sample = {"t": float(parts[0]), "shot": parts[1]}
                fields = rest.split(" head ", 1)
                sample["fov"] = float(fields[0].split("fov=")[1]) if "fov=" in fields[0] else None
                head, _, face = (fields[1] if len(fields) > 1 else "none").partition(" face ")
                hp = head.split()
                if len(hp) == 4:
                    sample.update({"x": float(hp[0]), "y": float(hp[1]), "on_screen": hp[2] == "true", "head_size": float(hp[3])})
                face, _, tracks = face.partition(" tracks ")
                sample["tracks"] = [x for x in tracks.split(",") if x]
                fp = face.split()
                if len(fp) >= 2:
                    sample["backend"], sample["expression"] = fp[0], fp[1]
                    sample["facs"] = {k: float(v) for k, v in (p.split("=", 1) for p in fp[2:] if "=" in p)}
                out["samples"].append(sample)
            elif kind == "vfx":
                out["vfx"].append(rest)
            else:
                out["flags"][kind] = rest
        except (ValueError, IndexError):
            continue
    return out


# --------------------------------------------------------------------------- evidence: frames and critique

def _gray(data: bytes, width: int = 200):
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert("L")
    return image.resize((width, max(1, round(image.height * width / image.width))))


def _diff(a, b) -> float:
    from PIL import ImageChops, ImageStat
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0] / 255


def letterbox_score(image, fraction: float = 0.11) -> float:
    """Share of the top and bottom bands (half the bar height) that is near black."""
    w, h = image.size
    band = max(1, int(h * fraction * 0.5))
    dark = total = 0
    for box in ((0, 0, w, band), (0, h - band, w, h)):
        histogram = image.crop(box).histogram()
        dark += sum(histogram[:12])
        total += sum(histogram)
    return dark / max(1, total)


def critique(frames: list[dict], evidence: dict, timeline: dict) -> dict:
    """A measured, advisory critique of a captured cutscene: framing (engine samples of where the subject's head is
    on screen), timing (shots and cues happened when the timeline says; expression changes on camera), easing
    (camera motion at the start and end of each moving shot vs its middle), cuts (big picture changes only at shot
    boundaries or the VFX impact), letterbox in/out, VFX played, and return of control."""
    findings: list[str] = []
    scores: dict = {}
    bar = float(timeline.get("letterbox", 0.11))
    shots = {s["name"]: s for s in timeline["shots"]}
    samples = evidence.get("samples", [])
    scores["samples"] = len(samples)
    # framing
    framing = {}
    for name, shot in shots.items():
        mine = [s for s in samples if s["shot"] == name and "x" in s]
        if not mine:
            continue
        on = [s for s in mine if s["on_screen"]]
        info = {"samples": len(mine), "on_screen": round(len(on) / len(mine), 2)}
        if on:
            info["x"] = [round(min(s["x"] for s in on), 2), round(max(s["x"] for s in on), 2)]
            info["y"] = [round(min(s["y"] for s in on), 2), round(max(s["y"] for s in on), 2)]
            info["head_size"] = round(sum(s["head_size"] for s in on) / len(on), 3)
        framing[name] = info
        if shot.get("lookActor"):
            if info["on_screen"] < 0.9:
                findings.append(f"{name}: the subject is off screen in {100 - info['on_screen'] * 100:.0f}% of samples")
            if on and (info["x"][0] < 0.12 or info["x"][1] > 0.88):
                findings.append(f"{name}: the subject's head reaches the frame edge (x {info['x']})")
            if on and info["y"][0] < bar + 0.04:
                findings.append(f"{name}: the head is cut by the top letterbox bar (y {info['y']})")
            if on and min(shot.get("fov") or [70]) <= 40 and info["head_size"] < 0.07:
                findings.append(f"{name}: a close-up FOV but the head is only {info['head_size']:.0%} of the frame height")
    scores["framing"] = framing
    # expressions on camera, FACS taken by the engine
    expr = []
    skipped_at = None
    try:
        skipped_at = float(evidence.get("flags", {}).get("skip-pressed", "").split()[0])
    except (ValueError, IndexError):
        skipped_at = None
    for cue in _cues(timeline, "expression"):
        if skipped_at is not None and cue["at"] >= skipped_at:
            continue
        end = cue["at"] + (cue.get("duration") or 0.25)
        after = [s for s in samples if end + 0.05 <= s["t"] <= end + 0.8 and s.get("facs") is not None]
        visible = [s for s in samples if cue["at"] <= s["t"] <= end + 0.8 and s.get("on_screen")]
        entry = {"name": cue["name"], "at": cue["at"], "on_camera": bool(visible),
                 "head_size": round(max((s["head_size"] for s in visible), default=0), 3)}
        if after:
            snap = after[0]
            entry["backend"], entry["expression_seen"] = snap.get("backend"), snap.get("expression")
            preset = PRESETS[cue["name"]]
            t0 = snap["t"]
            overlay = set()
            for other in timeline["cues"]:
                span = other.get("duration") or (0.22 if other["kind"] == "blink" else 1.0)
                if other.get("actor") == cue.get("actor") and other["at"] - 0.05 <= t0 <= other["at"] + span + 0.1:
                    if other["kind"] == "talk":
                        overlay |= {"JawDrop", "Funneler"}
                    elif other["kind"] == "blink":
                        overlay |= {"LeftEyeClosed", "RightEyeClosed"}
            keys = [k for k in SAMPLE_FACS if k in preset and k not in overlay]
            if keys:
                entry["facs_match"] = all(abs(snap["facs"].get(k, 0) - preset[k]) < 0.2 for k in keys)
                if not entry["facs_match"]:
                    findings.append(f"expression {cue['name']} at {cue['at']}s: the face values did not reach the preset "
                                    f"({ {k: snap['facs'].get(k) for k in keys} })")
        if not visible or entry["head_size"] < 0.04:
            findings.append(f"expression {cue['name']} at {cue['at']}s is not readable on camera (head size "
                            f"{entry['head_size']:.0%})")
        expr.append(entry)
    scores["expressions"] = expr
    # cues fired
    fired = {(c["kind"], round(c["t"], 1)) for c in evidence.get("cues", [])}
    scores["cues_fired"] = len(evidence.get("cues", []))
    late = [c for c in evidence.get("cues", []) for want in timeline["cues"]
            if want["kind"] == c["kind"] and abs(want["at"] - c["t"]) < 0.5 and c["t"] - want["at"] > 0.1]
    if late:
        findings.append(f"{len(late)} cues fired more than 0.1s late (frame-rate bound)")
    if len(evidence.get("cues", [])) < len(timeline["cues"]) and not evidence.get("flags", {}).get("skip-pressed"):
        findings.append(f"only {len(evidence.get('cues', []))} of {len(timeline['cues'])} cues fired")
    vfx_cues = [c for c in evidence.get("cues", []) if c["kind"] == "vfx"]
    scores["vfx"] = [c["detail"] for c in vfx_cues]
    if _cues(timeline, "vfx") and not any("played" in c["detail"] for c in vfx_cues):
        findings.append("the VFX cue did not play")
    del fired
    # frames: letterbox, cuts, easing
    if len(frames) >= 3:
        grays = [_gray(f["data"]) for f in frames]
        ts = [float(f.get("t", -1)) for f in frames]
        boxes = [letterbox_score(g, bar) for g in grays]
        shown = [b for b, t in zip(boxes, ts) if 1.0 <= t <= min(timeline["length"] - 1.5, 13.5)]
        ended = [b for b, t in zip(boxes, ts) if t > timeline["length"] + 0.6]
        scores["letterbox_during"] = round(sum(shown) / len(shown), 2) if shown else None
        scores["letterbox_after"] = round(sum(ended) / len(ended), 2) if ended else None
        if shown and scores["letterbox_during"] < 0.8:
            findings.append("letterbox bars not visible during the cutscene")
        if ended and scores["letterbox_after"] > 0.5:
            findings.append("letterbox bars still on screen after the cutscene")
        diffs = [_diff(a, b) for a, b in zip(grays, grays[1:])]
        mids = [(ts[i] + ts[i + 1]) / 2 for i in range(len(diffs))]
        bounds = [s["start"] for s in timeline["shots"][1:]]
        vfx_at = [c["at"] for c in _cues(timeline, "vfx")]
        gestures = [c["at"] for c in timeline["cues"] if c["kind"] in ("anim", "expression")]
        bars = [(c["at"], c["at"] + (c.get("duration") or 0.6) + 0.3) for c in _cues(timeline, "letterbox")]
        positive = sorted(d for d in diffs if d > 0) or [0.0]
        median = positive[len(positive) // 2]
        pops = []
        end_t = skipped_at if skipped_at is not None else timeline["length"]
        for d, m, a, b in zip(diffs, mids, ts, ts[1:]):
            if a < 0 or b > end_t - 0.1:
                continue
            near_cut = any(a - 0.25 <= x <= b + 0.25 for x in bounds)
            near_vfx = any(x - 0.2 <= m <= x + 3.6 for x in vfx_at)
            near_gesture = any(x - 0.1 <= m <= x + 0.8 for x in gestures)
            near_bars = any(x0 <= m <= x1 for x0, x1 in bars)
            if m < 0.4 or near_cut or near_vfx or near_gesture or near_bars:
                continue
            if d > max(0.06, 3 * median):
                pops.append(round(m, 2))
        scores["pops_inside_shots"] = pops
        if pops:
            findings.append(f"sudden picture changes inside shots at t = {pops}: a camera jump or a pop")
        bounds = [x for x in bounds if x < end_t - 0.1]
        cuts_seen = sum(1 for x in bounds if any(a - 0.15 <= x <= b + 0.15 and d > max(0.04, 2 * median)
                                                for d, a, b in zip(diffs, ts, ts[1:])))
        scores["cuts_seen"] = f"{cuts_seen}/{len(bounds)}"
        easing = {}
        for shot in timeline["shots"]:
            if len(shot["points"]) < 2:
                continue
            s0, d0 = shot["start"], shot["duration"]
            inside = [(m, d) for m, d, a, b in zip(mids, diffs, ts, ts[1:]) if s0 + 0.25 <= a and b <= s0 + d0 - 0.25]
            if len(inside) < 5:
                continue
            edge = [d for m, d in inside if m < s0 + 0.2 * d0 or m > s0 + 0.8 * d0]
            mid = [d for m, d in inside if s0 + 0.3 * d0 <= m <= s0 + 0.7 * d0]
            if edge and mid:
                e, c = sum(edge) / len(edge), sum(mid) / len(mid)
                easing[shot["name"]] = {"edge": round(e, 4), "middle": round(c, 4)}
                style = (shot.get("ease") or {}).get("style", "Sine")
                if style != "Linear" and c > 0.01 and e > 1.35 * c and not shot.get("lookActor"):
                    findings.append(f"{shot['name']}: the camera moves faster at the shot's ends than in its middle; "
                                    "the easing does not read")
        scores["easing"] = easing
    # return of control
    flags = evidence.get("flags", {})
    finished = flags.get("client-finished", "")
    scores["client_finished"] = finished
    scores["server_finished"] = flags.get("server-finished", "")
    if not finished:
        findings.append("the client never reported the end of the cutscene")
    elif "camera=Custom" not in finished or "subject=Humanoid" not in finished or "bars=false" not in finished:
        findings.append(f"control not fully returned: {finished}")
    return {"ok": not findings, "findings": findings, "scores": scores}


def align_frames(frames: list[dict], timeline: dict, *, window: float = 0.6, step: float = 0.02) -> float:
    """Frame times come from the PC's clock and the moment the console showed the play marker, so they can be off
    by a few tenths of a second. Shift them so the biggest picture changes line up with the shot cuts (a cut changes
    the whole frame). Returns the shift applied (0 when there are no cuts or too few frames)."""
    bounds = [s["start"] for s in timeline["shots"][1:]]
    if len(frames) < 6 or not bounds:
        return 0.0
    grays = [_gray(f["data"], 120) for f in frames]
    diffs = [_diff(a, b) for a, b in zip(grays, grays[1:])]
    ts = [float(f.get("t", -1)) for f in frames]

    def score(shift: float) -> float:
        total = 0.0
        for x in bounds:
            hits = [d for d, a, b in zip(diffs, ts, ts[1:]) if a >= 0 and a + shift <= x <= b + shift]
            total += max(hits, default=0.0)
        return total

    best, best_score = 0.0, score(0.0)
    steps = int(window / step)
    for i in range(-steps, steps + 1):
        shift = i * step
        value = score(shift)
        if value > best_score * 1.05 + 1e-9:
            best, best_score = shift, value
    if best:
        for f in frames:
            f["t"] = f["t"] + best
    return round(best, 3)


def reanalyse(folder: Path) -> dict:
    """Re-run alignment, critique and the contact sheet on a saved lab run (frames, evidence.json, timeline.json,
    report.json); writes sheet.jpg and critique.json next to them. No Studio needed."""
    folder = Path(folder)
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    timeline = json.loads((folder / "timeline.json").read_text(encoding="utf-8"))
    evidence = json.loads((folder / "evidence.json").read_text(encoding="utf-8"))
    frames = []
    for i, item in enumerate(report.get("playtest", {}).get("frame_files", [])):
        data = (folder / item["file"]).read_bytes()
        frames.append({"index": int(re.sub(r"\D", "", item["file"]) or i), "data": data, "t": float(item["t"]),
                       "file": item["file"]})
    original = [f["t"] for f in frames]
    shift = align_frames(frames, timeline) if not report.get("time_shift") else 0.0
    out = {"time_shift": shift, "critique": critique(frames, evidence, timeline),
           "sheet": contact_sheet(frames, timeline, folder / "sheet.jpg",
                                  title=f"{report.get('label')} | {timeline['name']} | run {report.get('run')} | aligned {shift:+.2f}s"),
           "frame_times": [{"file": f["file"], "t_before": round(a, 3), "t": round(f["t"], 3)} for f, a in zip(frames, original)]}
    (folder / "critique.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def contact_sheet(frames: list[dict], timeline: dict, target: Path, *, columns: int = 5, width: int = 384,
                  title: str = "", count: int = 20) -> dict:
    """A labelled grid of frames: index, cutscene time and the shot each frame belongs to."""
    from PIL import Image, ImageDraw
    playing = [f for f in frames if 0 <= f.get("t", -1) <= timeline["length"] + 1.0] or frames
    picked = playing
    if len(playing) > count:
        step = (len(playing) - 1) / (count - 1)
        picked = [playing[round(i * step)] for i in range(count)]
    tiles = []
    for f in picked:
        image = Image.open(io.BytesIO(f["data"])).convert("RGB")
        h = round(image.height * width / image.width)
        tile = image.resize((width, h))
        draw = ImageDraw.Draw(tile)
        t = f.get("t", -1)
        shot = shot_at(timeline, t)["name"] if 0 <= t <= timeline["length"] else ("end" if t > 0 else "pre")
        text = f"#{f['index']} t={t:.2f}s {shot}"
        draw.rectangle((0, h - 18, 7 * len(text) + 8, h), fill=(0, 0, 0))
        draw.text((4, h - 16), text, fill=(255, 255, 255))
        tiles.append(tile)
    rows = math.ceil(len(tiles) / columns)
    th = tiles[0].height
    header = 24 if title else 0
    sheet = Image.new("RGB", (columns * width, rows * th + header), (12, 12, 16))
    if title:
        ImageDraw.Draw(sheet).text((8, 5), title[:160], fill=(230, 230, 230))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * width, header + (i // columns) * th))
    sheet.save(target, quality=88)
    return {"file": target.name, "frames": [f["index"] for f in picked]}


# --------------------------------------------------------------------------- the Studio lab (driver)

def _text(result) -> str:
    from .studio_loop import result_text
    return result_text(result)


def _failed(result) -> bool:
    from .studio_loop import result_failed
    return result_failed(result)


class CutsceneLab:
    """Apply -> check -> playtest -> capture -> critique on an already opened GuardedStudio."""

    def __init__(self, guarded, out: Path, *, log=print, sleep=asyncio.sleep, clock=time.monotonic):
        self.guarded, self.out, self.log, self.sleep, self.clock = guarded, Path(out), log, sleep, clock

    async def _luau(self, code: str) -> tuple[bool, str]:
        from .studio_loop import EDIT_MARK, _marked_json
        result = await self.guarded.call_tool("execute_luau", {"studio_id": self.guarded.studio_id,
                                                               "datamodel_type": "Edit", "code": code})
        receipt = _marked_json(_text(result), EDIT_MARK) or {}
        answer = receipt.get("result") if isinstance(receipt.get("result"), str) else _text(result)
        return (not _failed(result) and receipt.get("ok") is True), answer

    async def _call(self, name: str, **arguments):
        return await self.guarded.call_tool(name, {"studio_id": self.guarded.studio_id, **arguments})

    async def remove(self) -> dict:
        ok, text = await self._luau(remove_luau())
        return {"ok": ok, "detail": text[:200]}

    async def run(self, spec: dict, *, run: str | None = None, label: str = "") -> dict:
        run = run or secrets.token_hex(4)
        timeline = spec["timeline"]
        self.out.mkdir(parents=True, exist_ok=True)
        report = {"run": run, "label": label, "speed": spec.get("speed"), "head": spec.get("head"),
                  "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "craft": craft_check(timeline)}
        generated = timeline_luau(timeline)
        (self.out / "CutsceneGenerated.luau").write_text(generated, encoding="utf-8")
        (self.out / "timeline.json").write_text(json.dumps(timeline, indent=1), encoding="utf-8")
        report["lint"] = {k: v for k, v in lint_sources({**pack_sources(), "CutsceneGenerated": generated}).items() if v}
        ok, text = await self._luau(apply_luau(spec, run))
        report["apply"] = {"ok": ok and f"{MARK}_APPLY {run}" in text, "detail": text[:200]}
        if not report["apply"]["ok"]:
            return self._finish(report)
        ok, text = await self._luau(check_luau(run))
        report["check"] = {"ok": ok and "ERR" not in text and "timeline=true" in text, "detail": text[:600]}
        self.log(f"check: {report['check']}")
        if not report["check"]["ok"]:
            return self._finish(report)
        report["playtest"] = await self._playtest(spec, run)
        frames = report["playtest"].pop("_frames", [])
        console = report["playtest"].pop("_console", "")
        evidence = parse_console(console, run)
        (self.out / "evidence.json").write_text(json.dumps(evidence, indent=1), encoding="utf-8")
        report["evidence"] = {"cues": len(evidence["cues"]), "shots": [s["name"] for s in evidence["shots"]],
                              "samples": len(evidence["samples"]), "flags": evidence["flags"]}
        if frames:
            report["time_shift"] = align_frames(frames, timeline)
            report["playtest"]["frame_files"] = [{"file": f["file"], "t": round(f["t"], 3), "sha256": f["sha256"]}
                                                 for f in frames]
            report["sheet"] = contact_sheet(frames, timeline, self.out / "sheet.jpg",
                                            title=f"{label} | {timeline['name']} | speed {spec.get('speed')} | run {run}")
        report["critique"] = critique(frames, evidence, timeline)
        return self._finish(report)

    def _finish(self, report: dict) -> dict:
        report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        report["changes"] = self.guarded.journal.report() if hasattr(self.guarded.journal, "report") else {}
        (self.out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        return report

    async def _console(self) -> str:
        return _text(await self._call("get_console_output"))

    async def _playtest(self, spec: dict, run: str) -> dict:
        speed = float(_clamp(spec.get("speed", 0.35), 0.05, 1))
        length = spec["timeline"]["length"]
        if spec.get("skip_at"):
            length = min(length, float(spec["skip_at"]))
        wall = length / speed
        started = await self.guarded.call_tool("start_stop_play", {"studio_id": self.guarded.studio_id, "is_start": True})
        if _failed(started):
            return {"ok": False, "started": False, "detail": _text(started)[:300]}
        frames: list[dict] = []
        console = ""
        play_at = None
        info = {"ok": False, "started": True}
        try:
            deadline = self.clock() + 45
            while self.clock() < deadline and f"{MARK} client-ready {run}" not in console:
                await self.sleep(0.5)
                console = await self._console()
            info["client_ready"] = f"{MARK} client-ready {run}" in console
            if not info["client_ready"]:
                info["detail"] = "the lab client did not start"
                return info
            stop_at = self.clock() + float(spec.get("lead", 6)) + wall + 8
            index = 0
            while self.clock() < stop_at and len(frames) < MAX_FRAMES:
                before = self.clock()
                shot = await self._call("screen_capture", capture_id=f"StarCut_{run}_{index}")
                from .roblox_vfx_studio import _images
                images = _images(shot)
                if play_at is None:
                    console = await self._console()
                    if f"{MARK} client-play {run}" in console:
                        play_at = before if frames else (before + self.clock()) / 2
                if images:
                    data, mime = images[0]
                    now = self.clock()
                    frames.append({"index": index, "data": data, "mime": mime, "wall": now})
                    index += 1
                if play_at and self.clock() > play_at + wall + 3.0:
                    break
            await self.sleep(1.0)
            console = await self._console()
        finally:
            stopped = await self.guarded.call_tool("start_stop_play", {"studio_id": self.guarded.studio_id,
                                                                       "is_start": False})
            info["stopped"] = not _failed(stopped)
        at = console.find(f"{MARK} client-ready {run}")
        kept = console[max(0, at - 3000):] if at >= 0 else console[-12000:]
        (self.out / "playtest-output.txt").write_text(kept, encoding="utf-8")
        info["errors"] = [line for line in console.splitlines()
                          if ("StarCutscene" in line and ("rror" in line or "failed" in line.lower()))
                          or ("[StarCutscene]" in line)][:20]
        for f in frames:
            f["t"] = ((f["wall"] - play_at) * speed) if play_at else -1.0
            name = f"frame-{f['index']:03d}.{'jpg' if 'jpeg' in f['mime'] else 'png'}"
            (self.out / name).write_bytes(f["data"])
            f["file"] = name
            f["sha256"] = hashlib.sha256(f["data"]).hexdigest()
        info.update({"ok": bool(frames) and play_at is not None, "frames": len(frames), "played": play_at is not None,
                     "frame_files": [{"file": f["file"], "t": round(f["t"], 3), "sha256": f["sha256"]} for f in frames],
                     "_frames": frames, "_console": console})
        return info


async def run_cutscene_lab(home, specs: list[dict], out: Path, *, connector=None, log=print, keep: bool = False) -> dict:
    """Connect to the Studio target (STAR Test Place only), run each spec, remove the lab afterwards."""
    from . import studio, studio_remote
    results = []
    async with (connector or studio_remote.connect)(home) as session:
        discovered = await studio.list_tools(session)
        guarded, facts = await studio_remote.open_server(session, discovered, home=home, opted_in=True)
        if guarded is None:
            return {"ok": False, "problem": facts.get("problem")}
        if not (guarded.verdict.editable and facts.get("is_test_place")):
            return {"ok": False, "problem": "the open place is not STAR Test Place or edits are not allowed"}
        lab = CutsceneLab(guarded, out, log=log)
        for index, spec in enumerate(specs):
            lab.out = Path(out) / (spec.get("label") or f"run-{index + 1}")
            results.append(await lab.run(spec, label=spec.get("label", "")))
        if not keep:
            results.append({"removed": await lab.remove()})
    return {"ok": True, "results": results}


def public_summary(report: dict) -> dict:
    """No frame bytes: paths, scores and findings."""
    out = {"ok": report.get("ok"), "problem": report.get("problem"), "runs": []}
    for item in report.get("results", []):
        if "run" not in item:
            out["removed"] = item.get("removed")
            continue
        out["runs"].append({
            "label": item.get("label"), "apply_ok": item.get("apply", {}).get("ok"),
            "check": item.get("check", {}).get("detail"), "frames": item.get("playtest", {}).get("frames"),
            "sheet": item.get("sheet", {}).get("file"), "evidence": item.get("evidence"),
            "critique": item.get("critique"), "errors": item.get("playtest", {}).get("errors"),
            "craft": item.get("craft")})
    return out


# --------------------------------------------------------------------------- CLI

def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.roblox_cutscene_studio", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--timeline", help="timeline JSON file (default: the built-in demo)")
        p.add_argument("--version", type=int, default=3, help="demo timeline version (1..3)")
        if name == "run":
            p.add_argument("--home", required=True)
            p.add_argument("--out", required=True)
            p.add_argument("--speed", type=float, default=0.35, help="playback speed for capture (1 = real time)")
            p.add_argument("--clock", type=float, help="Lighting.ClockTime during the playtest (client only)")
            p.add_argument("--head", type=int, default=0, help="HumanoidDescription.Head asset id (a Dynamic Head)")
            p.add_argument("--skip-at", type=float, default=0, help="press Skip at this cutscene time")
            p.add_argument("--face", choices=("auto", "facs", "gui"), default="auto", help="expression backend")
            p.add_argument("--label", default="")
            p.add_argument("--keep", action="store_true", help="leave the lab installed (unsaved) after the run")
    r = sub.add_parser("remove")
    r.add_argument("--home", required=True)
    again = sub.add_parser("reanalyse", help="re-run alignment, critique and sheet on a saved run folder")
    again.add_argument("folder")
    args = parser.parse_args(arguments)
    if args.command == "reanalyse":
        result = reanalyse(Path(args.folder))
        print(json.dumps({k: v for k, v in result.items() if k != "frame_times"}, indent=1))
        return 0
    if args.command == "remove":
        async def go():
            from . import studio, studio_remote
            async with studio_remote.connect(Path(args.home)) as session:
                discovered = await studio.list_tools(session)
                guarded, facts = await studio_remote.open_server(session, discovered, home=Path(args.home))
                if guarded is None or not facts.get("is_test_place"):
                    return {"ok": False, "problem": "not STAR Test Place"}
                return await CutsceneLab(guarded, Path(".")).remove()
        print(json.dumps(asyncio.run(go())))
        return 0
    timeline = json.loads(Path(args.timeline).read_text(encoding="utf-8")) if args.timeline else demo_timeline(args.version)
    if args.command == "plan":
        result = plan(timeline)
        print(json.dumps({k: v for k, v in result.items() if k != "generated_luau"}, indent=1))
        if result.get("generated_luau"):
            print(result["generated_luau"])
        return 0 if result.get("ok") else 1
    spec = {"timeline": timeline, "speed": args.speed, "clock": args.clock, "head": args.head,
            "skip_at": args.skip_at, "label": args.label, "face_backend": args.face}
    report = asyncio.run(run_cutscene_lab(Path(args.home), [spec], Path(args.out), keep=args.keep))
    print(json.dumps(public_summary(report), indent=1, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
