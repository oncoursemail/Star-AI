"""Offline geometry contract tests for explicit local OBJ export."""
import math
from pathlib import Path

import pytest

from star.asset_forge import preview_terrain
from star.world_mesh import main, terrain_obj


def _rows(text, mark):
    return [line for line in text.splitlines() if line.startswith(mark + " ")]


def test_obj_terrain_geometry_uvs_and_two_upward_faces_per_quad():
    mesh = terrain_obj(preview_terrain(seed=2, biome="temperate", size=4, step=16))
    v, uv, faces = _rows(mesh, "v"), _rows(mesh, "vt"), _rows(mesh, "f")
    assert len(v) == len(uv) == 16
    assert len(faces) == 18
    a, c, b = (int(point.split("/")[0]) for point in faces[0].split()[1:])
    coords = [list(map(float, row.split()[1:])) for row in v]
    p0, p1, p2 = coords[a - 1], coords[c - 1], coords[b - 1]
    u = [p1[i] - p0[i] for i in range(3)]
    v1 = [p2[i] - p0[i] for i in range(3)]
    assert u[2] * v1[0] - u[0] * v1[2] > 0
    assert "o STAR_terrain" in mesh


def test_obj_chunks_have_matching_world_edges_and_different_interior():
    left = terrain_obj(preview_terrain(seed=19, biome="alpine", size=4, origin_x=0, step=16))
    right = terrain_obj(preview_terrain(seed=19, biome="alpine", size=4, origin_x=48, step=16))
    a, b = _rows(left, "v"), _rows(right, "v")
    assert [a[i * 4 + 3] for i in range(4)] == [b[i * 4] for i in range(4)]
    assert a[0] != b[0]


def test_obj_is_reproducible_and_small_enough_for_single_roblox_mesh():
    preview = preview_terrain(seed=10, biome="alien", size=16)
    output = terrain_obj(preview)
    assert output == terrain_obj(preview)
    assert len(_rows(output, "f")) == 450 < 20000


@pytest.mark.parametrize("change", [
    {"heights_studs": None}, {"heights_studs": [[0, 1], [2]]},
    {"heights_studs": [[0, float("nan")], [1, 2]]},
    {"heights_studs": [[0, True], [1, 2]]},
    {"heights_studs": [[0, -1], [1, 2]]},
    {"origin_studs": [0, "evil"]}, {"step_studs": 0}, {"biome": "https://example.com"},
])
def test_obj_validation_rejects_corrupt_input(change):
    preview = preview_terrain(size=4)
    preview.update(change)
    with pytest.raises(ValueError):
        terrain_obj(preview)


def test_obj_export_requires_explicit_cli_output(tmp_path, capsys):
    output = tmp_path / "terrain.obj"
    assert main(["--output", str(output), "--size", "4", "--seed", "11"]) == 0
    data = output.read_text()
    assert len(_rows(data, "v")) == 16
    assert len(_rows(data, "f")) == 18
    assert "Wrote" in capsys.readouterr().out


def test_obj_export_rejects_wrong_suffix_and_does_not_write(tmp_path):
    output = tmp_path / "test.py"
    with pytest.raises(SystemExit):
        main(["--output", str(output)])
    assert not output.exists()


def test_cli_refuses_overwriting_existing_obj_unless_explicit_force(tmp_path):
    output = tmp_path / "terrain.obj"
    output.write_text("keep existing geometry", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--output", str(output), "--size", "4"])
    assert exc.value.code == 2
    assert output.read_text(encoding="utf-8") == "keep existing geometry"
    assert main(["--output", str(output), "--size", "4", "--force"]) == 0
    assert output.read_text(encoding="utf-8").startswith("# STAR Asset Forge")


@pytest.mark.parametrize("flag,value", [("--size", "99"), ("--step", "2"), ("--origin-x", "1000001")])
def test_cli_bad_sampling_range_is_argparse_error_and_never_writes(tmp_path, capsys, flag, value):
    output = tmp_path / "terrain.obj"
    with pytest.raises(SystemExit) as exc:
        main(["--output", str(output), flag, value])
    assert exc.value.code == 2
    assert not output.exists()
    assert "error:" in capsys.readouterr().err
