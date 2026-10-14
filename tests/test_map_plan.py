import copy
import re

import pytest

from star import map_plan
from star.map_plan import dry_run, to_luau


def obby():
    return {
        "version": 1, "mapName": "Training Yard", "style": "obby",
        "bounds": {"size": [200, 80, 200]},
        "parts": [
            {"name": "Floor", "position": [0, -0.5, 0], "size": [60, 1, 60], "material": "Grass", "color": "#5A8F3C",
             "role": "floor", "group": "Ground"},
            {"name": "P1", "position": [0, 3, 36], "size": [8, 1, 8], "role": "platform", "group": "Course"},
            {"name": "P2", "position": [0, 5, 46], "size": [8, 1, 8], "role": "platform", "group": "Course"},
            {"name": "Ramp", "class": "WedgePart", "position": [20, 2, 0], "size": [8, 4, 10], "rotation": [0, 90, 0]},
        ],
        "spawns": [{"name": "Spawn", "position": [0, 0.5, 0]}],
        "route": {"waypoints": ["Spawn", "Floor", "P1", "P2"]},
        "lighting": {"clockTime": 14, "ambient": "#808080"},
    }


def codes(items):
    return {item["code"] for item in items}


def test_clean_plan_reports_counts_bounds_route_and_operations():
    report = dry_run(obby())
    assert report["ok"], report["blockers"]
    assert report["root"] == "Workspace/MapDrafts/Training Yard"
    assert report["counts"] == {"parts": 4, "spawns": 1, "assets": 0, "groups": 2, "total_objects": 8}
    assert report["services"] == ["Workspace", "Lighting"]
    assert report["bounds"]["used"]["max"][2] == 50
    legs = report["route"]["legs"]
    assert [leg["ok"] for leg in legs] == [True, True, True]
    assert legs[1] == {"from": "Floor", "to": "P1", "gap": 2.0, "rise": 3.5, "ok": True}
    ops = report["operations"]
    assert ops[0] == {"op": "folder", "path": "Workspace/MapDrafts/Training Yard", "ifExists": "abort"}
    floor = next(op for op in ops if op.get("name") == "Floor")
    assert floor["parent"].endswith("/Ground")
    assert floor["properties"]["Material"] == {"type": "Enum", "value": "Enum.Material.Grass"}
    assert floor["properties"]["Color"]["type"] == "Color3"
    assert next(op for op in ops if op.get("name") == "Spawn")["class"] == "SpawnLocation"
    assert ops[-1]["op"] == "set" and ops[-1]["properties"]["ClockTime"] == 14
    assert "ShiroKSH" in report["credit"]


def test_rotation_is_included_in_bounds():
    plan = obby()
    plan["parts"][3]["position"] = [96, 2, 0]   # rotated 90 degrees: x half-extent is 5, not 4
    report = dry_run(plan)
    assert "out-of-bounds" in codes(report["blockers"])
    plan["parts"][3]["position"] = [94.5, 2, 0]
    assert dry_run(plan)["ok"]


def test_route_gap_and_rise_limits_and_truss_exception():
    plan = obby()
    plan["route"]["waypoints"] = ["Spawn", "P1"]   # skips the floor: 33-stud gap
    report = dry_run(plan)
    assert "route-gap" in codes(report["blockers"]) and "operations" not in report
    plan = obby()
    plan["parts"][2]["position"] = [0, 13, 46]   # +10 studs from P1
    assert "route-rise" in codes(dry_run(plan)["blockers"])
    plan["parts"][2]["class"] = "TrussPart"
    assert "route-rise" not in codes(dry_run(plan)["blockers"])
    plan = obby()
    plan["route"]["waypoints"] = ["Spawn", "Nowhere"]
    assert "route-unknown" in codes(dry_run(plan)["blockers"])
    plan = obby()
    plan["route"]["waypoints"] = ["Floor", "P1"]
    assert "route-start" in codes(dry_run(plan)["warnings"])


def test_spawn_rules():
    plan = obby()
    plan["spawns"] = []
    assert "no-spawn" in codes(dry_run(plan)["blockers"])
    plan = obby()
    plan["parts"].append({"name": "Ceiling", "position": [0, 4, 0], "size": [10, 1, 10]})
    assert "spawn-blocked" in codes(dry_run(plan)["blockers"])
    plan = obby()
    plan["spawns"].append({"name": "Sky", "position": [-20, 30, -20]})
    assert "spawn-floating" in codes(dry_run(plan)["warnings"])


def test_overlap_z_fighting_and_allow_overlap():
    plan = obby()
    plan["parts"].append({"name": "Patch", "position": [5, -0.5, 5], "size": [4, 1, 4]})
    report = dry_run(plan)
    warnings = {item["code"]: item for item in report["warnings"]}
    assert warnings["overlap"]["pairs"][0]["a"] in {"Floor", "Patch"}
    assert "z-fighting" in warnings
    assert report["ok"]   # overlaps warn; they do not block
    plan["parts"][-1]["allowOverlap"] = True
    assert "overlap" not in codes(dry_run(plan)["warnings"])


def test_names_root_limits_assets_and_anchoring():
    plan = obby()
    plan["parts"].append({"name": "Floor", "position": [0, 20, 0], "size": [1, 1, 1]})
    assert "duplicate-name" in codes(dry_run(plan)["blockers"])
    plan = obby()
    plan["rootPath"] = "Workspace"
    assert "root-path" in codes(dry_run(plan)["blockers"])
    plan["rootPath"] = "Workspace/MapDrafts/Area 1"
    assert dry_run(plan)["root"] == "Workspace/MapDrafts/Area 1/Training Yard"
    plan = obby()
    plan["limits"] = {"maxObjects": 5}
    assert "object-limit" in codes(dry_run(plan)["blockers"])
    plan = obby()
    plan["assets"] = [{"name": "Tree", "assetId": 123456, "position": [10, 0, 10]}]
    report = dry_run(plan)
    assert "asset-not-allowed" in codes(report["blockers"]) and "asset-unsized" in codes(report["warnings"])
    plan["assetPolicy"] = {"allowedAssetIds": [123456]}
    report = dry_run(plan)
    assert report["ok"] and any(op["op"] == "insert_asset" for op in report["operations"])
    plan = obby()
    plan["parts"][1]["anchored"] = False
    assert "unanchored" in codes(dry_run(plan)["warnings"])


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("bounds"),
    lambda p: p.update(mapName='Bad"; os.exit()'),
    lambda p: p["parts"][0].update(material="Lava"),
    lambda p: p["parts"][0].update(size=[0, 1, 1]),
    lambda p: p["parts"][0].update(color="red"),
    lambda p: p.update(extra=True),
    lambda p: p["parts"][0].update(name="x" * 80),
])
def test_schema_violations_block(mutate):
    plan = obby()
    mutate(plan)
    report = dry_run(plan)
    assert not report["ok"] and codes(report["blockers"]) == {"schema"}


def test_non_object_and_non_finite_input():
    assert not dry_run([1, 2])["ok"]
    plan = obby()
    plan["parts"][0]["position"] = [float("nan"), 0, 0]
    assert not dry_run(plan)["ok"]


def test_luau_is_generated_only_for_clean_plans_and_is_one_undo_step():
    script = to_luau(obby())
    assert script.count("TryBeginRecording") == 1 and "FinishRecording" in script
    assert 'Instance.new("SpawnLocation")' in script and 'Instance.new("WedgePart")' in script
    assert "Enum.Material.Grass" in script and "Orientation = Vector3.new(0, 90, 0)" in script
    assert 'parent = folder(parent, "MapDrafts")' in script and "already exists" in script
    assert 'game:GetService("Lighting").ClockTime = 14' in script
    # every string literal is a validated name or a fixed message: no quotes injected
    for literal in re.findall(r'"([^"]*)"', script):
        assert "\\" not in literal
    bad = copy.deepcopy(obby())
    bad["spawns"] = []
    with pytest.raises(ValueError):
        to_luau(bad)


def test_large_plan_dry_run_is_fast_enough():
    plan = {"mapName": "Grid", "bounds": {"size": [2000, 50, 2000]},
            "parts": [{"name": f"Tile {i}", "position": [(i % 60) * 10 - 300, 0, (i // 60) * 10 - 300],
                       "size": [8, 1, 8]} for i in range(1400)],
            "spawns": [{"name": "Spawn", "position": [0, 20, 0]}]}
    report = dry_run(plan)
    assert report["ok"] and report["counts"]["parts"] == 1400 and report["batches"] == 15
    assert map_plan.SCHEMA["properties"]["parts"]["maxItems"] == 5000
