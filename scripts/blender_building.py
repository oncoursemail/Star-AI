"""Fixed Blender script, invoked only by star.architecture_pipeline with validated data.

Mesh geometry is batched by palette role to keep glTF objects and materials bounded.
No user-supplied Python, addon, remote URL, driver or blend file is executed.
"""
import json
from math import cos, radians, sin
from pathlib import Path
import sys

import bpy


def cube_vertices(part):
    cx, cy, cz = part["center"]
    sx, sy, sz = (v / 2 for v in part["size"])
    angle = radians(part["angle_y"])
    vertices = []
    for x, y, z in ((-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
                    (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)):
        vertices.append((cx + x * cos(angle) + z * sin(angle), cy + y,
                         cz - x * sin(angle) + z * cos(angle)))
    return vertices, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                      (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def prism_vertices(part):
    verts = [tuple(v) for v in part["vertices"]]
    return verts, [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]


def build(plan, glb):
    if plan["schema_version"] != 1:
        raise ValueError("Unexpected plan schema")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "NONE"  # values are designed in Roblox studs
    for role, hexcolor in plan["palette"].items():
        group = [p for p in plan["parts"] if p["material"] == role]
        verts, faces = [], []
        for part in group:
            vs, fs = cube_vertices(part) if part["kind"] == "box" else prism_vertices(part)
            offset = len(verts)
            verts.extend(vs)
            faces.extend(tuple(i + offset for i in face) for face in fs)
        if not faces:
            continue
        mesh = bpy.data.meshes.new(f"STAR_{role}_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(f"STAR_{role}", mesh)
        bpy.context.collection.objects.link(obj)
        mat = bpy.data.materials.new(name=f"STAR_{role}")
        mat.use_nodes = True
        rgb = tuple(int(hexcolor[i:i+2], 16) / 255 for i in (1, 3, 5))
        mat.diffuse_color = (*rgb, 1.0)
        shader = mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (*rgb, 1.0)
        shader.inputs["Roughness"].default_value = 0.32 if role == "glass" else 0.8
        shader.inputs["Metallic"].default_value = 0.5 if role == "trim" and plan["brief"]["style"] == "spaceport" else 0.0
        obj.data.materials.append(mat)
    bpy.ops.wm.save_as_mainfile(filepath=str(glb.with_suffix(".blend")), check_existing=False)
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_cameras=False,
                              export_lights=False, export_animations=False)


if __name__ == "__main__":
    if "--" not in sys.argv or len(sys.argv[sys.argv.index("--") + 1:]) != 2:
        raise SystemExit("Expected -- <building-plan.json> <building.glb>")
    plan_path, glb_path = (Path(v) for v in sys.argv[sys.argv.index("--") + 1:])
    build(json.loads(plan_path.read_text(encoding="utf-8")), glb_path)
