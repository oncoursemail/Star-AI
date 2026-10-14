"""Offline STAR Blender -> Roblox R15 animation draft, R6 separation and permission tests.

No actual Blender, Roblox Studio, token, machine, shell or network access.
Fake exporter artifacts only exercise STAR's guarded invocation plumbing.
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest

from star.blender_animation import (
    R15_HIERARCHY, R6_JOINTS, ANIMATION_SCHEMA, analyze_animation, validate_animation,
)
from star.blender_bridge import BlenderController
from star.blender_mcp import (
    ANIMATION_EXPORT, ANIMATION_PREFLIGHT, BUILD, INSPECT, NAMES, connect_blender, make_server,
)
from star.desktop_core import Settings

R15_WAVE = {
    "name": "GentleWave",
    "rig": "r15",
    "fps": 30,
    "frame_count": 30,
    "loop": True,
    "keyframes": [
        {"frame": 0, "bones": {"RightUpperArm": [0, 0, 0], "RightLowerArm": [0, 0, 0]}},
        {"frame": 8, "bones": {"RightUpperArm": [-25, 5, 15], "RightLowerArm": [30, 0, 0]}},
        {"frame": 16, "bones": {"RightUpperArm": [-35, 0, -10], "RightLowerArm": [12, 0, 0]}},
        {"frame": 30, "bones": {"RightUpperArm": [0, 0, 0], "RightLowerArm": [0, 0, 0]}},
    ],
}
R6_POSE = {
    "name": "R6Wave",
    "rig": "r6",
    "fps": 30,
    "frame_count": 15,
    "loop": False,
    "keyframes": [
        {"frame": 0, "bones": {"Right Arm": [0, 0, 0]}},
        {"frame": 15, "bones": {"Right Arm": [-40, 0, 20]}},
    ],
}


def test_rig_map_matches_separately_named_target_bone_families():
    assert len(R15_HIERARCHY) == 17
    assert R15_HIERARCHY["LeftLowerArm"] == "LeftUpperArm"
    assert R15_HIERARCHY["LowerTorso"] == "HumanoidRootNode"
    assert "Left Arm" in R6_JOINTS and "LeftUpperArm" not in R6_JOINTS


def test_roblox_animation_preflight_is_deterministic_and_immutable():
    clip = validate_animation(R15_WAVE)
    clip["keyframes"][0]["bones"]["RightUpperArm"][0] = -100
    assert R15_WAVE["keyframes"][0]["bones"]["RightUpperArm"][0] == 0
    result = analyze_animation(R15_WAVE)
    assert result["blender_export_supported"] is True
    assert result["rig"] == "r15"
    assert result["frame_count"] == 30 and result["seconds"] == 1.0
    assert result["pose_count"] == 4 and result["authored_joint_keys"] == 8
    assert len(result["recipe_sha256"]) == 64
    assert "native_studio_import_tested" not in result  # pure preflight never claims native QA
    assert "required_studio_check" in result
    assert "foot" in str(result["warnings"]).lower()


def test_r6_stays_preflight_only_and_is_not_mislabeled_a_skinned_r15():
    report = analyze_animation(R6_POSE)
    assert report["rig"] == "r6"
    assert report["blender_export_supported"] is False
    assert any("Motor6D" in x for x in report["warnings"])
    with pytest.raises(ValueError, match="different rig"):
        validate_animation({
            **R6_POSE,
            "keyframes": [
                {"frame": 0, "bones": {"LeftUpperArm": [0, 0, 0]}},
                R6_POSE["keyframes"][1],
            ],
        })


def test_rejects_unsafe_or_physically_ambiguous_recipes():
    changes = [
        {"python": "__import__('os').system('bad')"},
        {"file": "../../private.blend"},
        {"fps": 0}, {"fps": True}, {"frame_count": 240},
        {"keyframes": []},
        {"keyframes": list(reversed(R15_WAVE["keyframes"]))},
        {"keyframes": [R15_WAVE["keyframes"][0]] * 2},
        {"keyframes": [
            R15_WAVE["keyframes"][0],
            {"frame": 29, "bones": {"RightHand": [0, 0, 0]}}],
        },
        {"keyframes": [
            {"frame": 0, "bones": {"Root": [0, 0, 0]}},
            R15_WAVE["keyframes"][-1]],
        },
        {"keyframes": [
            {"frame": 0, "bones": {"NotARobloxJoint": [1, 2, 3]}},
            R15_WAVE["keyframes"][-1]],
        },
        {"keyframes": [
            {"frame": 0, "bones": {"RightUpperArm": [float("nan"), 0, 0]}},
            R15_WAVE["keyframes"][-1]],
        },
        {"keyframes": [
            {"frame": 0, "bones": {"RightUpperArm": [0, 0, 0]}},
            {"frame": 30, "bones": {"RightUpperArm": [80, 0, 0]}}],
        },
        {"keyframes": [
            {"frame": 0, "bones": {"RightUpperArm": [999, 0, 0]}},
            R15_WAVE["keyframes"][-1]],
        },
        {"keyframes": [
            {"frame": 0, "bones": {"RightUpperArm": [0, 0, 0]}},
            {"frame": 30, "bones": {"RightUpperArm": [0, 0, 0], "RightLowerArm": ["script", 0, 0]}}],
        },
    ]
    for change in changes:
        recipe = {**R15_WAVE, **change}
        with pytest.raises(ValueError):
            validate_animation(recipe)
    with pytest.raises(ValueError):
        validate_animation({**R15_WAVE, "new": "x" * 25000})
    with pytest.raises(ValueError):
        validate_animation(None)


def test_motion_angular_velocity_warns_without_claiming_blender_or_studio_qa():
    data = {**R15_WAVE, "loop": False, "frame_count": 2,
            "keyframes": [
                {"frame": 0, "bones": {"LeftUpperArm": [0, 0, 0]}},
                {"frame": 2, "bones": {"LeftUpperArm": [100, 0, 0]}},
            ]}
    report = analyze_animation(data)
    assert report["max_joint_axis_rate_deg_s"] >= 1500
    assert any("Rapid joint rotations" in warning for warning in report["warnings"])
    assert "NOT established" in report["limitations"]


class FakeAnimationProcess:
    def __init__(self, arguments):
        self.arguments = arguments
        self.returncode = 0

    async def communicate(self):
        args = self.arguments
        assert "--factory-startup" in args
        assert args[args.index("--python")+1].endswith("blender_animation_worker.py")
        assert args[-2] == "--"
        source = Path(args[-1])
        assert source.name == "animation.json"
        value = json.loads(source.read_text(encoding="utf-8"))
        assert value == validate_animation(R15_WAVE)
        folder = source.parent
        (folder / "scene.blend").write_bytes(b"BLENDER-FIXTURE")
        (folder / "animation.fbx").write_bytes(b"FBX-DRAFT-FIXTURE")
        (folder / "result.json").write_text(json.dumps({
            "job_id": folder.name, "status": "completed", "kind": "animation",
            "scene": value["name"], "rig": "r15",
            "fps": value["fps"], "frame_count": value["frame_count"],
            "keyed_joints": 2, "native_studio_import_tested": False,
        }), encoding="utf-8")
        return b"fake process only", b""


def fake_spawn(records):
    async def run(*args, **kwargs):
        records.append((args, kwargs))
        return FakeAnimationProcess(args)
    return run


def test_r15_export_requires_two_independent_opt_ins(tmp_path, monkeypatch):
    import star.blender_bridge as bridge
    fake_executable = tmp_path / "fake-bin" / ("blender.exe" if __import__("os").name == "nt" else "blender")
    fake_executable.parent.mkdir()
    fake_executable.write_text("fake executable for offline tests", encoding="utf-8")
    fake_executable.chmod(0o755)
    monkeypatch.setattr(bridge, "discover_blender", lambda _configured: fake_executable)
    monkeypatch.delenv("STAR_BLENDER_R15_ANIMATION_EXPERIMENT", raising=False)
    disabled = BlenderController(settings=Settings(blender_enabled=True, blender_edit=False), home=tmp_path)
    with pytest.raises(PermissionError, match="Allow Blender"):
        asyncio.run(disabled.animate(R15_WAVE))
    enabled = BlenderController(settings=Settings(blender_enabled=True, blender_edit=True), home=tmp_path)
    with pytest.raises(PermissionError, match="experimental"):
        asyncio.run(enabled.animate(R15_WAVE))
    assert not (tmp_path / "blender").exists()


def test_fake_animation_job_is_private_versioned_and_requires_native_studio_import(tmp_path, monkeypatch):
    import star.blender_bridge as bridge
    fake_executable = tmp_path / "fake-bin" / ("blender.exe" if __import__("os").name == "nt" else "blender")
    fake_executable.parent.mkdir()
    fake_executable.write_text("fake executable for offline tests", encoding="utf-8")
    fake_executable.chmod(0o755)
    monkeypatch.setattr(bridge, "discover_blender", lambda _configured: fake_executable)
    monkeypatch.setenv("STAR_BLENDER_R15_ANIMATION_EXPERIMENT", "on")
    requests = []
    options = Settings(project="R15Project", blender_enabled=True, blender_edit=True)
    host = BlenderController(settings=options, home=tmp_path, spawn=fake_spawn(requests))

    async def go():
        with pytest.raises(ValueError, match="R6"):
            await host.animate(R6_POSE)
        return await host.animate(R15_WAVE), await host.animate(R15_WAVE)

    first, second = asyncio.run(go())
    assert first["job_id"] != second["job_id"]
    assert first["kind"] == "animation" and first["rig"] == "r15"
    assert first["native_studio_import_tested"] is False
    assert "BONE-ONLY" in first["notice"]
    assert Path(first["fbx_file"]).read_bytes() == b"FBX-DRAFT-FIXTURE"
    assert Path(first["blend_file"]).read_bytes() == b"BLENDER-FIXTURE"
    assert host.inspect(first["job_id"]) == first
    assert len(requests) == 2
    assert all("OPENAI_API_KEY" not in x[1]["env"] for x in requests)
    assert all("STAR_ROBLOX_KEY" not in x[1]["env"] for x in requests)
    assert all("--factory-startup" in x[0] for x in requests)
    with pytest.raises(ValueError):
        host.inspect("../../secret")
    with pytest.raises(ValueError):
        BlenderController(settings=Settings(project="other", blender_enabled=True),
                          home=tmp_path).inspect(first["job_id"])


def test_mcp_memory_transport_supports_nonwriting_review_and_hides_export(tmp_path, monkeypatch):
    monkeypatch.delenv("STAR_BLENDER_R15_ANIMATION_EXPERIMENT", raising=False)
    settings = Settings(project="Lab", blender_enabled=True, blender_edit=False)
    async def check():
        async with connect_blender(settings, tmp_path) as client:
            names = {item["name"] for item in client.catalog}
            assert ANIMATION_PREFLIGHT in names
            assert ANIMATION_EXPORT not in names
            assert BUILD not in names
            preflight = await client.call(ANIMATION_PREFLIGHT, R6_POSE)
            assert preflight["isError"] is False
            with pytest.raises(PermissionError):
                await client.call(ANIMATION_EXPORT, R15_WAVE)
    asyncio.run(check())
    assert not list(tmp_path.iterdir())


def test_blender_animation_export_stays_hidden_until_exact_owner_opt_in(tmp_path, monkeypatch):
    settings = Settings(blender_enabled=True, blender_edit=True)
    controller = BlenderController(settings=settings, home=tmp_path)
    for value, expected in [("off", False), ("ON", False), ("on", True)]:
        monkeypatch.setenv("STAR_BLENDER_R15_ANIMATION_EXPERIMENT", value)
        _, catalog = make_server(controller)
        names = {entry["name"] for entry in catalog}
        assert (ANIMATION_EXPORT in names) == expected
        assert ANIMATION_PREFLIGHT in names
        assert BUILD in names
    assert not (tmp_path / "blender").exists()


def test_trusted_worker_contains_no_arbitrary_execution_or_asset_downloads():
    file = Path(__file__).resolve().parents[1] / "star" / "blender_animation_worker.py"
    text = file.read_text(encoding="utf-8")
    tree = ast.parse(text)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    assert roots <= {"__future__", "json", "math", "pathlib", "sys", "bpy"}
    direct = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not ({"exec", "eval", "__import__", "compile"} & direct)
    assert "subprocess" not in text and "http://" not in text


def test_packaged_windows_build_includes_trusted_worker():
    source = Path(__file__).resolve().parents[1] / "scripts" / "build_windows.ps1"
    text = source.read_text(encoding="utf-8")
    assert "star/blender_worker.py;star" in text
    assert "star/blender_animation_worker.py;star" in text


def test_clip_name_rejects_trailing_control_chars():
    for name in ("Wave\n", "Wave\r", "Wave\t", "Wave ", "\nWave"):
        # Do not allow regexp end-of-string newline allowances in file labels.
        with pytest.raises(ValueError):
            validate_animation({**R15_WAVE, "name": name})
