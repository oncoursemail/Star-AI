"""STAR Blender-to-Roblox animation recipe validation and honest motion diagnostics.

A safe, editable *draft* for the official Blender -> FBX -> Studio Clip Editor
workflow. This never executes Blender, opens user assets, trains on artwork or
uploads/publishes to Roblox. R6 has a distinct Motor6D import path and is
preflight-only until a real R6 Studio importer is independently verified.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import re

from jsonschema import Draft202012Validator

MAX_BYTES = 24_000
CLIP_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,39}$")
R15_HIERARCHY = {
    "Root": None,
    "HumanoidRootNode": "Root",
    "LowerTorso": "HumanoidRootNode",
    "UpperTorso": "LowerTorso",
    "Head": "UpperTorso",
    "LeftUpperArm": "UpperTorso",
    "LeftLowerArm": "LeftUpperArm",
    "LeftHand": "LeftLowerArm",
    "RightUpperArm": "UpperTorso",
    "RightLowerArm": "RightUpperArm",
    "RightHand": "RightLowerArm",
    "LeftUpperLeg": "LowerTorso",
    "LeftLowerLeg": "LeftUpperLeg",
    "LeftFoot": "LeftLowerLeg",
    "RightUpperLeg": "LowerTorso",
    "RightLowerLeg": "RightUpperLeg",
    "RightFoot": "RightLowerLeg",
}
# The R6 rig is Roblox's six rigid parts with Motor6D joints, *not* the
# standard skinned R15 avatar skeleton. A generic skinned FBX is no substitute.
R6_JOINTS = ("Torso", "Head", "Left Arm", "Right Arm", "Left Leg", "Right Leg")
ROOTS = frozenset({"Root", "HumanoidRootNode", "HumanoidRootPart"})
ROTATION = {
    "type": "array", "minItems": 3, "maxItems": 3,
    "items": {"type": "number", "minimum": -120, "maximum": 120},
}
POSE = {
    "type": "object", "additionalProperties": False,
    "required": ["frame", "bones"],
    "properties": {
        "frame": {"type": "integer", "minimum": 0, "maximum": 120},
        "bones": {
            "type": "object", "minProperties": 1, "maxProperties": 15,
            "propertyNames": {"enum": list(R15_HIERARCHY) + list(R6_JOINTS)},
            "additionalProperties": ROTATION,
        },
    },
}
ANIMATION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["name", "rig", "fps", "frame_count", "loop", "keyframes"],
    "properties": {
        "name": {"type": "string", "pattern": CLIP_NAME.pattern},
        "rig": {"type": "string", "enum": ["r15", "r6"]},
        "fps": {"type": "integer", "enum": [24, 30, 60]},
        "frame_count": {"type": "integer", "minimum": 2, "maximum": 120},
        "loop": {"type": "boolean"},
        "keyframes": {"type": "array", "minItems": 2, "maxItems": 16, "items": POSE},
    },
}
VALIDATOR = Draft202012Validator(ANIMATION_SCHEMA)
MOTION_RATE_WARNING = 540.0  # degrees per second; advisory, NOT engine accuracy proof.


def validate_animation(value: object) -> dict:
    """Validate a bounded immutable representation, never executable Blender bpy.

    Frames count from 0; the Blender worker maps them to 1-based frames.
    Unmentioned joints retain their preceding pose, initially (0,0,0).
    First/last frames are mandatory. A looping clip must close all keyed
    rotations at the seam. Root translations are intentionally unsupported.
    """
    if type(value) is not dict:
        raise ValueError("Animation recipe must be a JSON object")
    try:
        payload = json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Animation recipe contains invalid or non-finite JSON") from exc
    if len(payload.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Animation recipe is larger than the approved limit")
    if any(True for _ in VALIDATOR.iter_errors(value)):
        raise ValueError("Unsupported animation field, bone name or value")
    frames = [pose["frame"] for pose in value["keyframes"]]
    if frames != sorted(set(frames)) or frames[0] != 0 or frames[-1] != value["frame_count"]:
        raise ValueError("Animation keyframes must be strictly increasing and cover frames 0 to frame_count")
    supported = set(R15_HIERARCHY) if value["rig"] == "r15" else set(R6_JOINTS)
    for pose in value["keyframes"]:
        if not set(pose["bones"]) <= supported:
            raise ValueError("An animation pose contains bones from a different rig")
        if ROOTS.intersection(pose["bones"]):
            raise ValueError("Root joints must remain in-place; author body movement on non-root joints")
    # Effective pose: missing joints hold their last specified rotation.
    if value["loop"]:
        first = {name: (0.0, 0.0, 0.0) for name in supported}
        first.update(value["keyframes"][0]["bones"])
        last = dict(first)
        for pose in value["keyframes"][1:]:
            last.update(pose["bones"])
        for name in supported:
            if any(abs(float(a) - float(b)) > .01 for a, b in zip(first[name], last[name])):
                raise ValueError("Looping clips must close the first/last keyed joint poses")
    # JSON copy: no caller mutation can alter the validated worker payload.
    return json.loads(payload)


def analyze_animation(value: object) -> dict:
    """Pure motion, data and compatibility checks, not Studio import success."""
    clip = validate_animation(value)
    rig = clip["rig"]
    names = set(R15_HIERARCHY) if rig == "r15" else set(R6_JOINTS)
    recorded = {name: (0.0, 0.0, 0.0) for name in names}
    total_keys, rapid, highest = 0, [], 0.0
    previous_frame = 0
    for index, pose in enumerate(clip["keyframes"]):
        current = dict(recorded)
        current.update(pose["bones"])
        total_keys += len(pose["bones"])
        if index:
            dt = (pose["frame"] - previous_frame) / clip["fps"]
            for name in names:
                change = max(abs(float(a)-float(b)) for a,b in zip(recorded[name], current[name]))
                rate = change / dt
                highest = max(highest, rate)
                if rate > MOTION_RATE_WARNING:
                    rapid.append((name, pose["frame"]))
        previous_frame = pose["frame"]
        recorded = current
    warnings = []
    if rig == "r6":
        warnings.append(
            "R6 is a Motor6D character, not an R15 skeleton. R6 FBX export/import "
            "and joint mapping require a separately validated Studio workflow. No FBX build for R6.")
    if rapid:
        short = ", ".join(f"{b}@{frame}" for b, frame in rapid[:5])
        warnings.append(
            f"Rapid joint rotations ({short}): inspect angular velocity and motion continuity in Studio.")
    if clip["loop"]:
        warnings.append("Loop seam matches keyed rotations only; velocity and foot contact still require review.")
    if not any("Foot" in name for p in clip["keyframes"] for name in p["bones"]):
        warnings.append("No foot keys provided; test leg contacts and foot sliding in an actual animated rig.")
    if rig == "r15" and len({bone for p in clip["keyframes"] for bone in p["bones"]}) <= 2:
        warnings.append("Only a few joints are animated; validate the intended expressive pose and silhouette.")
    frame_count = clip["frame_count"]
    return {
        "name": clip["name"],
        "rig": rig,
        "fps": clip["fps"],
        "frame_count": frame_count,
        "seconds": round(frame_count / clip["fps"], 3),
        "loop": clip["loop"],
        "pose_count": len(clip["keyframes"]),
        "authored_joint_keys": total_keys,
        "max_joint_axis_rate_deg_s": round(highest, 2),
        "recipe_sha256": sha256(json.dumps(clip, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "blender_export_supported": rig == "r15",
        "warnings": warnings,
        "required_studio_check": (
            "Import FBX via the Animation Editor into the ACTUAL target rig, "
            "inspect joint mapping, root motion, hand grips, pose blending, contact and scale, "
            "then playtest and review multiple camera/timed frames. No automatic publishing."),
        "limitations": (
            "Static draft preflight only. Real R15 avatar body mesh, facial animation, "
            "R6 Motor6D compatibility, smooth motion, VFX synchronization and native Studio import "
            "are NOT established by a validator or file export."),
    }
