"""Offline creator-intelligence contracts: engines, rigs, clips, GLB and scope."""
import json
import struct

import pytest

from star.workspace import Workspace, TOOL_NAMES
from star import artifact_intelligence as assets
from star import engine_evidence


def gltf():
    return {
        "asset": {"version": "2.0"},
        "accessors": [
            {"count": 6, "type": "VEC3", "componentType": 5126,
             "min": [0, 0, 0], "max": [1, 1, 1]},
            {"count": 6, "type": "SCALAR", "componentType": 5123},
            {"count": 2, "type": "SCALAR", "componentType": 5126,
             "min": [0], "max": [1]},
            {"count": 2, "type": "VEC3", "componentType": 5126},
            {"count": 2, "type": "MAT4", "componentType": 5126},
        ],
        "materials": [{"name": "Paint", "pbrMetallicRoughness": {"roughnessFactor": 0.5}}],
        "meshes": [{"primitives": [{
            "attributes": {"POSITION": 0, "JOINTS_0": 1, "WEIGHTS_0": 1},
            "indices": 1, "material": 0,
        }]}],
        "nodes": [{"name": "Armature", "children": [1]},
                  {"name": "Bone"},
                  {"mesh": 0, "skin": 0}],
        "scenes": [{"nodes": [0, 2]}], "scene": 0,
        "skins": [{"joints": [1], "inverseBindMatrices": 4}],
        "animations": [{"name": "Walk", "samplers": [{"input": 2, "output": 3}],
                        "channels": [{"sampler": 0, "target": {"node": 1, "path": "translation"}}]}],
    }


def save_json(tmp_path, value, name="mesh.gltf"):
    p = tmp_path / name
    p.write_text(json.dumps(value), encoding="utf-8")
    return p


def glb_bytes(doc):
    data = json.dumps(doc).encode("utf-8")
    data += b" " * ((-len(data)) % 4)
    return struct.pack("<4sIII4s", b"glTF", 2, 20 + len(data), len(data), b"JSON") + data


def test_tools_are_read_only_and_do_not_require_a_model_or_installed_editor():
    assert {"workspace_asset_audit", "workspace_game_graph"} <= TOOL_NAMES
    assert assets.TARGETS == {"general", "roblox", "godot", "unity", "unreal"}


def test_rig_and_animation_evidence_from_gltf(tmp_path):
    save_json(tmp_path, gltf())
    work = Workspace(tmp_path)
    report = work.call("workspace_asset_audit",
                       {"path": "mesh.gltf", "target": "roblox", "triangle_budget": 1000})
    assert report["read_only"] and report["structure_checked"]
    stats = report["statistics"]
    assert stats["triangles_estimated"] == 2
    assert stats["skins"] == 1 and stats["joint_references"] == 1
    assert stats["animations"] == [{"name": "Walk", "channels": 1}]
    assert stats["materials"] == 1
    assert "No geometry buffers" in report["notice"]


def test_glb_is_supported_without_reading_binary_buffer(tmp_path):
    p = tmp_path / "rig.glb"
    p.write_bytes(glb_bytes(gltf()))
    report = Workspace(tmp_path).call("workspace_asset_audit", {"path": "rig.glb"})
    assert report["format"] == "glb"
    assert report["structure_checked"]
    assert report["statistics"]["triangles_estimated"] == 2


def test_oversize_bad_magic_and_length_are_rejected(tmp_path):
    p = tmp_path / "invalid.glb"
    p.write_bytes(b"fake")
    with pytest.raises(ValueError):
        Workspace(tmp_path).call("workspace_asset_audit", {"path": "invalid.glb"})
    data = bytearray(glb_bytes(gltf()))
    data[8:12] = (1).to_bytes(4, "little")
    p.write_bytes(data)
    with pytest.raises(ValueError, match="length"):
        Workspace(tmp_path).call("workspace_asset_audit", {"path": "invalid.glb"})
    huge = tmp_path / "too_big.gltf"
    huge.write_bytes(b"{" + b"x" * (assets.MAX_JSON_BYTES + 1))
    with pytest.raises(ValueError, match="2 MB"):
        Workspace(tmp_path).call("workspace_asset_audit", {"path": "too_big.gltf"})


def test_bad_indexes_cycles_and_skin_binding_do_not_pass(tmp_path):
    data = gltf()
    data["nodes"][1]["children"] = [0]
    data["meshes"][0]["primitives"][0]["indices"] = 99
    data["skins"][0]["joints"] = [999]
    data["skins"][0]["inverseBindMatrices"] = 3
    save_json(tmp_path, data)
    result = Workspace(tmp_path).call("workspace_asset_audit", {"path": "mesh.gltf"})
    assert not result["structure_checked"]
    assert any("cycle" in issue for issue in result["structural_issues"])
    assert any("indices" in issue for issue in result["structural_issues"])
    assert any("inverse bind" in issue for issue in result["structural_issues"])


def test_missing_animation_normals_uv_materials_and_overbudget_warn(tmp_path):
    obj = gltf()
    obj["animations"] = []
    obj["materials"] = []
    obj["meshes"][0]["primitives"][0].pop("material")
    obj["accessors"][1]["count"] = 6000
    save_json(tmp_path, obj)
    result = Workspace(tmp_path).call(
        "workspace_asset_audit", {"path": "mesh.gltf", "triangle_budget": 1000})
    assert result["statistics"]["triangles_estimated"] == 2000
    warnings = " ".join(result["quality_warnings"])
    for phrase in ("triangles", "normals", "TEXCOORD", "animation", "PBR"):
        assert phrase in warnings


def test_external_resources_are_not_fetched_or_claimed_checked(tmp_path):
    obj = gltf()
    obj["buffers"] = [{"uri": "https://example.invalid/private.bin", "byteLength": 1024}]
    obj["images"] = [{"uri": "../../creds.png"}]
    save_json(tmp_path, obj)
    result = Workspace(tmp_path).call("workspace_asset_audit", {"path": "mesh.gltf"})
    assert result["statistics"]["external_resources_unverified"] == 2
    assert "not opened" in " ".join(result["quality_warnings"])
    assert not (tmp_path / "creds.png").exists()



def test_malformed_node_collections_report_errors_not_uncaught_crashes(tmp_path):
    for broken in (
        lambda data: data["nodes"][0].update(children="1"),
        lambda data: data["scenes"][0].update(nodes={"bad": True}),
    ):
        data = gltf()
        broken(data)
        save_json(tmp_path, data)
        result = Workspace(tmp_path).call("workspace_asset_audit", {"path": "mesh.gltf"})
        assert not result["structure_checked"]
        assert any("array" in issue for issue in result["structural_issues"])



def test_bounds_and_workspace_symlinks_are_enforced(tmp_path):
    save_json(tmp_path, gltf())
    ws = Workspace(tmp_path)
    for args in ({"path": ".."},
                 {"path": "mesh.gltf", "target": "nintendo"},
                 {"path": "mesh.gltf", "triangle_budget": 0},
                 {"path": "mesh.gltf", "triangle_budget": True},
                 {"path": "mesh.gltf", "shell": "anything"}):
        with pytest.raises((ValueError, PermissionError)):
            ws.call("workspace_asset_audit", args)
    root = tmp_path / "real"
    root.mkdir()
    save_json(root, gltf(), "target.gltf")
    link = tmp_path / "link.gltf"
    try:
        link.symlink_to(root / "target.gltf")
    except (OSError, NotImplementedError):
        pass
    else:
        # Workspace.resolve canonicalizes the symlink; it remains inside scope.
        assert ws.call("workspace_asset_audit", {"path": "link.gltf"})["read_only"]


def godot(folder):
    folder.mkdir(parents=True)
    (folder / "project.godot").write_text('[application]\nconfig/name="Test"\n')
    (folder / "main.tscn").write_text(
        '[ext_resource type="Script" path="res://player.gd" id="1"]\n'
        '[ext_resource type="Texture2D" path="res://missing.png" id="2"]\n'
        '[ext_resource type="Script" path="res://../private.gd" id="3"]\n')
    (folder / "player.gd").write_text("extends Node\n")


def test_godot_trace_has_lines_and_missing_refs(tmp_path):
    godot(tmp_path / "project")
    result = Workspace(tmp_path).call("workspace_game_graph", {"path": "project"})
    assert result["read_only"] and not result["executed"]
    assert result["engine"] == "godot"
    assert [(edge["to"], edge["line"]) for edge in result["relationships"]] == [
        ("player.gd", 1), ("missing.png", 2)
    ]
    assert [e["to"] for e in result["missing_local_resources"]] == ["missing.png"]


def unity(folder):
    (folder / "ProjectSettings").mkdir(parents=True)
    (folder / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.1.0f1\n")
    (folder / "Assets").mkdir()
    (folder / "Assets" / "Hero.prefab").write_text("guid: " + "a" * 32 + "\nguid: " + "b" * 32)
    (folder / "Assets" / "Player.cs.meta").write_text("fileFormatVersion: 2\nguid: " + "a" * 32)
    (folder / "Assets" / "Player.cs").write_text("class Player {}")


def test_unity_guid_graph_and_external_mapping_are_reported(tmp_path):
    unity(tmp_path)
    result = Workspace(tmp_path).call("workspace_game_graph", {"path": "."})
    assert result["engine"] == "unity"
    assert len(result["relationships"]) == 2
    resolved = [e for e in result["relationships"] if e["resolved_in_project"]]
    assert len(resolved) == 1 and resolved[0]["to"] == "Assets/Player.cs"
    assert result["unity_external_or_unknown_guid_references"] == 1
    assert not result["missing_local_resources"]


def test_unreal_is_manifest_only_and_no_binary_parser(tmp_path):
    (tmp_path / "Arena.uproject").write_text(json.dumps({
        "EngineAssociation": "5.6", "Plugins": [{"Name": "EnhancedInput"}, {"Name": "GameplayAbilities"}]
    }))
    (tmp_path / "Arena.uasset").write_bytes(b"\x01\x02\x03")
    result = Workspace(tmp_path).call("workspace_game_graph", {"path": "."})
    assert result["engine"] == "unreal"
    assert result["unreal_declared_plugins"] == ["EnhancedInput", "GameplayAbilities"]
    assert not result["relationships"]
    assert any("Asset Registry" in note for note in result["notes"])


def test_graph_rejects_outside_and_nonprojects(tmp_path):
    (tmp_path / "unrelated").mkdir()
    ws = Workspace(tmp_path)
    for path in ("..", "unrelated"):
        with pytest.raises((ValueError, PermissionError)):
            ws.call("workspace_game_graph", {"path": path})
    with pytest.raises(ValueError):
        ws.call("workspace_game_graph", {"path": "unrelated", "command": "run"})
