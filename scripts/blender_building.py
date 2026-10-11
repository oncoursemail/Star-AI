"""Fixed Blender script, invoked only by star.architecture_pipeline with validated data.

Mesh geometry is batched by palette role to keep glTF objects and materials bounded.
No user-supplied Python, addon, remote URL, driver or blend file is executed.
"""
import json
from math import cos, isfinite, radians, sin
from pathlib import Path
import sys

import bpy
from mathutils import Vector


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


def _validate_input(plan):
    if (type(plan) is not dict or plan.get("schema_version") != 1
            or type(plan.get("palette")) is not dict
            or type(plan.get("parts")) is not list
            or not 1 <= len(plan["parts"]) <= 2500
            or not 1 <= len(plan["palette"]) <= 12):
        raise ValueError("Invalid or unbounded Blender building plan")
    for item in plan["parts"]:
        if type(item) is not dict or item.get("material") not in plan["palette"]:
            raise ValueError("Invalid material reference")
        if item.get("kind") == "box":
            if (type(item.get("center")) is not list or len(item["center"]) != 3
                    or type(item.get("size")) is not list or len(item["size"]) != 3
                    or any(type(v) not in (int, float) or not isfinite(v) or abs(v) > 10000
                           for v in item["center"] + item["size"])
                    or min(item["size"]) < 0.01
                    or type(item.get("angle_y")) not in (int, float)
                    or not isfinite(item["angle_y"])):
                raise ValueError("Invalid box geometry")
        elif item.get("kind") == "triangle_prism":
            vertices = item.get("vertices")
            if (type(vertices) is not list or len(vertices) != 6
                    or any(type(v) is not list or len(v) != 3
                           or any(type(x) not in (int, float) or not isfinite(x) or abs(x) > 10000
                                  for x in v) for v in vertices)):
                raise ValueError("Invalid prism geometry")
        else:
            raise ValueError("Unsupported geometry primitive")


def _unwrap_tiled(mesh, *, repeat_studs=4):
    """Simple consistent projection UVs; these are not authored texture atlases."""
    layer = mesh.uv_layers.new(name="STAR_TileUV")
    for polygon in mesh.polygons:
        normal = polygon.normal
        for index in polygon.loop_indices:
            v = mesh.vertices[mesh.loops[index].vertex_index].co
            if abs(normal.z) >= max(abs(normal.x), abs(normal.y)):
                uv = (v.x / repeat_studs, v.y / repeat_studs)
            elif abs(normal.y) >= abs(normal.x):
                uv = (v.x / repeat_studs, v.z / repeat_studs)
            else:
                uv = (v.y / repeat_studs, v.z / repeat_studs)
            layer.data[index].uv = uv


def _make_preview(plan, glb):
    """Owner-requested, low-resolution Workbench composition preview; not a quality verdict."""
    brief = plan["brief"]
    width, depth = brief["width_studs"], brief["depth_studs"]
    height = brief["floors"] * brief["story_height_studs"]
    cam_data = bpy.data.cameras.new("STAR_Preview_Camera")
    cam = bpy.data.objects.new("STAR_Preview_Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (width * 0.95, -depth * 1.8, max(18, height * 1.1))
    target = Vector((0, 0, height * 0.47))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(width * 1.9, depth * 2.4, height * 2.2)
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 75
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(glb.with_name("building-preview.png"))
    return scene.render.filepath


def build(plan, glb, *, preview=False):
    _validate_input(plan)
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
        _unwrap_tiled(mesh)
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
    if preview:
        _make_preview(plan, glb)
    bpy.ops.wm.save_as_mainfile(filepath=str(glb.with_suffix(".blend")), check_existing=False)
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_cameras=False,
                              export_lights=False, export_animations=False)
    if preview:
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) not in (2, 3) or (len(args) == 3 and args[2] != "--preview"):
        raise SystemExit("Expected -- <building-plan.json> <building.glb> [--preview]")
    plan_path, glb_path = map(Path, args[:2])
    build(json.loads(plan_path.read_text(encoding="utf-8")), glb_path,
          preview=len(args) == 3)
