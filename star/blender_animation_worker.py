"""Trusted, experimental Blender FBX animation worker for STAR's R15 prototype.

Invoked only by BlenderController.animate with a validated, private animation.json.
Uses a fixed, authored R15-like bone hierarchy and bounded Euler keyframes.
No model-written bpy, imported user files, Python addons, network, or publishing.

The resulting BONE-ONLY FBX is an authoring experiment, NOT a verified
standard avatar animation. Import onto the real R15 target via Studio's Clip
Editor and independently check mapping, rest pose, scale and motion quality.
R6 Motor6D rigs are intentionally excluded from this export path.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import bpy

# Parent, head, tail in editable Blender Z-up scene coordinates. This is a
# poseable proxy armature, not Roblox's official authored R15 avatar mesh.
JOINTS = (
    ("Root", None, (0, 0, 0), (0, 0, .18)),
    ("HumanoidRootNode", "Root", (0, 0, .18), (0, 0, .42)),
    ("LowerTorso", "HumanoidRootNode", (0, 0, .42), (0, 0, .95)),
    ("UpperTorso", "LowerTorso", (0, 0, .95), (0, 0, 1.53)),
    ("Head", "UpperTorso", (0, 0, 1.53), (0, 0, 2.04)),
    ("LeftUpperArm", "UpperTorso", (-.34, 0, 1.42), (-.70, 0, 1.18)),
    ("LeftLowerArm", "LeftUpperArm", (-.70, 0, 1.18), (-1.08, 0, .96)),
    ("LeftHand", "LeftLowerArm", (-1.08, 0, .96), (-1.26, 0, .86)),
    ("RightUpperArm", "UpperTorso", (.34, 0, 1.42), (.70, 0, 1.18)),
    ("RightLowerArm", "RightUpperArm", (.70, 0, 1.18), (1.08, 0, .96)),
    ("RightHand", "RightLowerArm", (1.08, 0, .96), (1.26, 0, .86)),
    ("LeftUpperLeg", "LowerTorso", (-.23, 0, .82), (-.23, 0, .45)),
    ("LeftLowerLeg", "LeftUpperLeg", (-.23, 0, .45), (-.23, 0, .13)),
    ("LeftFoot", "LeftLowerLeg", (-.23, 0, .13), (-.23, -.23, .08)),
    ("RightUpperLeg", "LowerTorso", (.23, 0, .82), (.23, 0, .45)),
    ("RightLowerLeg", "RightUpperLeg", (.23, 0, .45), (.23, 0, .13)),
    ("RightFoot", "RightLowerLeg", (.23, 0, .13), (.23, -.23, .08)),
)


def _create_r15_armature():
    bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = "STAR_R15_Prototype_Armature"
    rig.data.name = "STAR_R15_BoneDraft"
    rig.data.display_type = "STICK"
    rig.show_in_front = True
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    bones = rig.data.edit_bones
    for initial in list(bones):
        bones.remove(initial)
    for name, _parent, head, tail in JOINTS:
        bone = bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.use_deform = name not in {"Root", "HumanoidRootNode"}
    for name, parent, _head, _tail in JOINTS:
        if parent:
            bone = bones[name]
            bone.parent = bones[parent]
            bone.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def _key_actions(armature, spec):
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = spec["frame_count"] + 1
    scene.render.fps = spec["fps"]
    scene.name = spec["name"]
    animated = sorted(set().union(*(set(p["bones"]) for p in spec["keyframes"])))
    state = {bone: (0, 0, 0) for bone in animated}
    for bone_name in animated:
        armature.pose.bones[bone_name].rotation_mode = "XYZ"
    for pose in spec["keyframes"]:
        # Hold the preceding keyed angle for bones omitted at a given frame.
        state.update(pose["bones"])
        frame = pose["frame"] + 1
        scene.frame_set(frame)
        for name in animated:
            node = armature.pose.bones[name]
            node.rotation_euler = tuple(math.radians(v) for v in state[name])
            node.keyframe_insert("rotation_euler", frame=frame, group=name)
    scene.frame_set(1)
    return len(animated)


def main():
    if "--" not in sys.argv:
        raise ValueError("STAR Blender animation worker needs one approved recipe")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 1:
        raise ValueError("STAR Blender animation worker expects exactly one path")
    requested = Path(args[0])
    if requested.is_symlink() or requested.name != "animation.json":
        raise ValueError("STAR Blender animation recipe cannot be a symlink or arbitrary input")
    spec_file = requested.resolve(strict=True)
    folder = spec_file.parent
    if spec_file.name != "animation.json":
        raise ValueError("STAR Blender animation recipe must be in its immutable job directory")
    if spec_file.stat().st_size > 24_000:
        raise ValueError("STAR Blender animation recipe exceeds its bound")
    clip = json.loads(spec_file.read_text(encoding="utf-8"))
    # The host validated schema before invoking us; fail closed on malformed
    # handed-off data as a second defense without importing STAR into Blender.
    if (type(clip) is not dict or clip.get("rig") != "r15" or
            not isinstance(clip.get("keyframes"), list) or
            not 2 <= len(clip["keyframes"]) <= 16):
        raise ValueError("Only validated R15 animation drafts are supported")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    armature = _create_r15_armature()
    joint_count = _key_actions(armature, clip)
    # Keep an editable Blender master separate from the FBX interchange file.
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / "scene.blend"))
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(
        filepath=str(folder / "animation.fbx"),
        use_selection=True,
        object_types={"ARMATURE"},
        axis_forward="Z", axis_up="Y",
        apply_scale_options="FBX_SCALE_UNITS",
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=False,
        bake_anim_simplify_factor=0.0,
        bake_anim_step=1.0,
    )
    if not (folder / "scene.blend").is_file() or not (folder / "animation.fbx").is_file():
        raise RuntimeError("Blender did not export both expected animation files")
    summary = {
        "job_id": folder.name, "status": "completed", "kind": "animation",
        "scene": clip["name"], "rig": "r15", "fps": clip["fps"],
        "frame_count": clip["frame_count"], "keyed_joints": joint_count,
        "observed_blender_version": bpy.app.version_string,
        "native_studio_import_tested": False,
        "limitations": "Bone-only Blender R15 draft, not a validated Roblox avatar/Studio AnimationClip.",
    }
    (folder / "result.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
