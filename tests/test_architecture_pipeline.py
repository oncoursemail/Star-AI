"""Offline, deterministic validations: no Blender, GPU, network or keyring required."""
import json
import subprocess
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from star.architecture_pipeline import PALETTES, STYLE_GRAMMARS, create_package, main, make_plan, validate_brief
from star.architecture_quality import audit_plan


BASE = {"name": "Harbor Warehouse", "style": "industrial", "width_studs": 48,
        "depth_studs": 32, "floors": 2, "bays": 4}


def _glb_for_roles(roles):
    data = json.dumps({
        "asset": {"version": "2.0"},
        "meshes": [{"name": f"STAR_{role}_mesh", "primitives": [{"attributes": {"POSITION": 0}}]}
                   for role in roles],
        "nodes": [{"mesh": i} for i in range(len(roles))],
    }).encode()
    data += b" " * ((4 - len(data) % 4) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(data)) + struct.pack("<I4s", len(data), b"JSON") + data


def test_plan_is_repeatable_and_has_real_openings_and_articulated_roof():
    plan = make_plan(validate_brief(BASE))
    assert plan == make_plan(validate_brief(dict(BASE)))
    assert {p["material"] for p in plan["parts"]} == set(plan["palette"])
    assert {p["name"] for p in plan["parts"] if "_glazing" in p["name"]}
    assert len([p for p in plan["parts"] if p["name"] == "entry_door"]) == 1
    assert len([p for p in plan["parts"] if p["name"] == "flat_roof"]) == 1
    assert plan["metrics"]["estimated_triangles"] < 15000
    assert plan["metrics"]["material_groups"] <= 5
    assert "front_f0_b1_below" not in {p["name"] for p in plan["parts"]}
    assert "front_f0_b1_above" in {p["name"] for p in plan["parts"]}


def test_gable_and_style_palettes_produce_distinct_components():
    plan = make_plan(validate_brief({**BASE, "style": "storybook"}))
    assert len([p for p in plan["parts"] if p["kind"] == "triangle_prism"]) == 2
    assert {"roof_left", "roof_right"} <= {p["name"] for p in plan["parts"]}
    assert "flat_roof" not in {p["name"] for p in plan["parts"]}
    assert plan["palette"]["wall"] != make_plan(validate_brief(BASE))["palette"]["wall"]


@pytest.mark.parametrize("change", [
    {"style": "misc"}, {"style": []}, {"name": "../../malicious"}, {"floors": True}, {"floors": 0},
    {"bays": 999}, {"width_studs": 30, "bays": 8}, {"depth_studs": float("nan")},
    {"story_height_studs": 6}, {"python_script": "print(1)"},
])
def test_rejects_invalid_and_code_like_briefs(change):
    with pytest.raises(ValueError):
        validate_brief({**BASE, **change})


def test_plan_only_never_launches_a_process_and_never_overwrites(tmp_path):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("No subprocess allowed")
    path = create_package(BASE, tmp_path / "kit", run=forbidden)
    assert path.read_text(encoding="utf-8").startswith("{\n")
    assert json.loads(path.read_text())["brief"]["name"] == "Harbor Warehouse"
    assert calls == []
    manifest = json.loads((tmp_path / "kit" / "asset-manifest.json").read_text())
    assert manifest["status"] == "plan_only" and manifest["studio_imported"] is False
    assert manifest["visual_quality_verified"] is False
    assert (tmp_path / "kit" / "architecture-audit.json").is_file()
    assert "World Up to Top" in (tmp_path / "kit" / "studio-import-guide.md").read_text()
    with pytest.raises(FileExistsError):
        create_package(BASE, tmp_path / "kit", run=forbidden)


def test_explicit_blender_path_fixed_script_argv_and_output_proof(tmp_path):
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"fake")
    observed = {}
    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        output = Path(argv[-1])
        palette = json.loads(Path(argv[-2]).read_text())["palette"]
        output.write_bytes(_glb_for_roles(palette))
        output.with_suffix(".blend").write_bytes(b"blend")
        return SimpleNamespace(returncode=0)
    create_package(BASE, tmp_path / "kit", blender=exe, run=fake_run)
    argv = observed["argv"]
    assert argv[0] == str(exe) and "--disable-autoexec" in argv
    assert "--factory-startup" in argv and argv[-2].endswith("building-plan.json")
    assert argv[argv.index("--python-exit-code") + 1] == "7"
    assert Path(argv[argv.index("--python") + 1]).as_posix().endswith("scripts/blender_building.py")
    assert observed["kwargs"]["timeout"] == 180 and observed["kwargs"]["check"] is True
    assert "shell" not in observed["kwargs"]
    manifest = json.loads((tmp_path / "kit" / "asset-manifest.json").read_text())
    assert manifest["status"] == "exported_needs_studio_review"
    assert manifest["blender_export"]["mesh_count"] == 5
    assert manifest["studio_imported"] is False


def test_export_failure_and_missing_outputs_are_not_success(tmp_path):
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"fake")
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "blender", stderr="failed to export")
    with pytest.raises(RuntimeError, match="failed to export"):
        create_package(BASE, tmp_path / "bad", blender=exe, run=fail)
    with pytest.raises(RuntimeError, match="did not write"):
        create_package(BASE, tmp_path / "missing", blender=exe,
                       run=lambda *a, **k: SimpleNamespace(returncode=0))
    with pytest.raises(ValueError):
        create_package(BASE, tmp_path / "notstarted", blender=tmp_path / "powershell.exe")
    assert not (tmp_path / "notstarted").exists()


def test_blender_fake_cannot_claim_success_with_fake_glb(tmp_path):
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"fake")
    def wrong_glb(argv, **kwargs):
        output = Path(argv[-1])
        output.write_bytes(b"not a real glb")
        output.with_suffix(".blend").write_bytes(b"fake")
        return SimpleNamespace(returncode=0)
    with pytest.raises(RuntimeError, match="not validated"):
        create_package(BASE, tmp_path / "invalid-glb", blender=exe, run=wrong_glb)
    assert not (tmp_path / "invalid-glb" / "asset-manifest.json").exists()


def test_preview_requires_explicit_blender_and_does_not_create_output(tmp_path):
    with pytest.raises(ValueError, match="real Blender"):
        create_package(BASE, tmp_path / "preview", preview=True)
    assert not (tmp_path / "preview").exists()


def test_preview_is_optional_and_requires_genuine_png_evidence(tmp_path):
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"fake")
    def fake_preview(argv, **kwargs):
        assert argv[-1] == "--preview"
        plan = json.loads(Path(argv[-3]).read_text())
        glb = Path(argv[-2])
        glb.write_bytes(_glb_for_roles(plan["palette"]))
        glb.with_suffix(".blend").write_bytes(b"blend")
        glb.with_name("building-preview.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 200)
        return SimpleNamespace(returncode=0)
    create_package(BASE, tmp_path / "preview", blender=exe, preview=True, run=fake_preview)
    manifest = json.loads((tmp_path / "preview" / "asset-manifest.json").read_text())
    assert manifest["preview_rendered"] is True
    assert manifest["visual_quality_verified"] is False
    assert "building-preview.png" in manifest["files"]


@pytest.mark.parametrize("style,signature", [
    ("storybook", "storybook_rail_front_0"),
    ("industrial", "entry_canopy"),
    ("modern", "modern_sunshade_front_0"),
    ("spaceport", "pier_front_0"),
    ("gothic", "crown_front_f0_b0"),
    ("brutalist", "entry_canopy"),
    ("coastal", "coastal_porch_roof"),
    ("anime_city", "anime_shop_sign"),
])
def test_each_eight_style_grammars_produce_distinct_valid_structural_detail(style, signature):
    assert len(PALETTES) == len(STYLE_GRAMMARS) == 8
    plan = make_plan(validate_brief({**BASE, "style": style}))
    assert plan["style_grammar"] == STYLE_GRAMMARS[style]
    assert signature in {p["name"] for p in plan["parts"]}
    assert audit_plan(plan)["valid"] is True


def test_missing_brief_returns_usage_error_without_traceback(tmp_path, capsys):
    output = tmp_path / "kit"
    with pytest.raises(SystemExit) as error:
        main([str(tmp_path / "missing.json"), "--out", str(output)])
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "missing.json" in stderr
    assert "Traceback" not in stderr
    assert not output.exists()


def test_oversized_brief_is_rejected_before_output(tmp_path, capsys):
    brief = tmp_path / "oversized.json"
    brief.write_text(" " * 16_385, encoding="utf-8")
    output = tmp_path / "kit"
    with pytest.raises(SystemExit) as error:
        main([str(brief), "--out", str(output)])
    assert error.value.code == 2
    assert "Brief exceeds 16 KB" in capsys.readouterr().err
    assert not output.exists()
