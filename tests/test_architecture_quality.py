"""Architecture audit and glTF packaging checks (offline, no Blender/Studio)."""
import json
from pathlib import Path
import struct

import pytest

from star.architecture_pipeline import make_plan, validate_brief
from star.architecture_quality import audit_plan, design_summary, inspect_glb

BRIEF = {"name": "Workshop", "style": "storybook", "width_studs": 36,
         "depth_studs": 24, "floors": 2, "bays": 3}


def fixture_plan():
    return make_plan(validate_brief(BRIEF))


def glb_bytes(*, names=("STAR_wall_mesh",), asset="2.0"):
    raw = json.dumps({
        "asset": {"version": asset},
        "meshes": [{"name": n, "primitives": [{"attributes": {"POSITION": 0}}]} for n in names],
        "nodes": [{"name": "Building", "mesh": 0}],
    }).encode()
    raw += b" " * ((4 - len(raw) % 4) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 20 + len(raw))
            + struct.pack("<I4s", len(raw), b"JSON") + raw)


def test_generated_plan_is_statically_valid_but_not_visually_certified():
    report = audit_plan(fixture_plan())
    assert report["valid"] is True, report
    assert report["status"] == "static_checks_passed_visual_review_required"
    assert report["metrics"]["parts"] > 100
    assert report["metrics"]["triangles"] < 100_000
    assert any("Upper floors" in item for item in report["warnings"])
    summary = design_summary(fixture_plan())
    assert summary["roof"] == "gable"
    assert summary["openings"]["entrances"] == 1
    assert summary["openings"]["glazed_windows"] >= 2
    assert summary["output"].startswith("PLAN_ONLY")


@pytest.mark.parametrize("corrupt", ["duplicate", "missing_door", "nan", "material", "metrics", "kind", "size"])
def test_geometry_gate_fails_closed_on_corrupt_plan(corrupt):
    plan = fixture_plan()
    if corrupt == "duplicate":
        plan["parts"][1]["name"] = plan["parts"][0]["name"]
    elif corrupt == "missing_door":
        plan["parts"] = [p for p in plan["parts"] if p["name"] != "entry_door"]
    elif corrupt == "nan":
        plan["parts"][0]["center"] = [float("nan"), 0, 0]
    elif corrupt == "material":
        plan["parts"][0]["material"] = "missing"
    elif corrupt == "metrics":
        plan["metrics"]["estimated_triangles"] = 0
    elif corrupt == "kind":
        plan["parts"][0]["kind"] = "python"
    elif corrupt == "size":
        plan["parts"][0]["size"] = [0, 1, 1]
    report = audit_plan(plan)
    assert not report["valid"] and report["status"] == "blocked"


def test_glb_inspector_checks_header_meshes_names_and_honest_status(tmp_path):
    file = tmp_path / "house.glb"
    file.write_bytes(glb_bytes())
    report = inspect_glb(file, expected_material_roles=("wall",))
    assert report["mesh_names"] == ["STAR_wall_mesh"]
    assert len(report["sha256"]) == 64
    assert report["studio_imported"] is False
    assert report["visual_quality_verified"] is False


@pytest.mark.parametrize("payload", [
    b"not a glb",
    b"glTF" + b"\x00" * 60,
    glb_bytes(asset="1.0"),
    glb_bytes(names=("renamed",)),
    glb_bytes(names=("STAR_wall_mesh", "STAR_wall_mesh")),
])
def test_glb_inspector_rejects_invalid_or_incompatible_exports(tmp_path, payload):
    file = tmp_path / "bad.glb"
    file.write_bytes(payload)
    with pytest.raises(ValueError):
        inspect_glb(file, expected_material_roles=("wall",))


def test_glb_inspector_rejects_symlink(tmp_path):
    real = tmp_path / "real.glb"
    real.write_bytes(glb_bytes())
    link = tmp_path / "link.glb"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="ordinary"):
        inspect_glb(link)
