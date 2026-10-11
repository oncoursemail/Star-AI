"""Offline, deterministic validations: no Blender, GPU, network or keyring required."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from star.architecture_pipeline import create_package, make_plan, validate_brief


BASE = {"name": "Harbor Warehouse", "style": "industrial", "width_studs": 48,
        "depth_studs": 32, "floors": 2, "bays": 4}


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
        output.write_bytes(b"glb")
        output.with_suffix(".blend").write_bytes(b"blend")
        return SimpleNamespace(returncode=0)
    create_package(BASE, tmp_path / "kit", blender=exe, run=fake_run)
    argv = observed["argv"]
    assert argv[0] == str(exe) and "--disable-autoexec" in argv
    assert "--factory-startup" in argv and argv[-2].endswith("building-plan.json")
    assert argv[argv.index("--python") + 1].endswith("scripts/blender_building.py")
    assert observed["kwargs"]["timeout"] == 180 and observed["kwargs"]["check"] is True
    assert "shell" not in observed["kwargs"]


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
