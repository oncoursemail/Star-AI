"""Trusted Blender background worker. Run ONLY with Blender --factory-startup.

This is not an addon or a Python REPL. It reads STAR's validated JSON scene recipe
from a private job folder and writes only fixed filenames into that same folder.
Do not add eval/exec, external asset downloads or arbitrary import paths here.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

MATERIALS = {}


def _color(hex_rgb):
    return tuple(int(hex_rgb[i:i + 2], 16) / 255 for i in (1, 3, 5))


def material(color):
    if color not in MATERIALS:
        rgb = _color(color)
        mat = bpy.data.materials.new("STAR_Mat_" + color[1:].upper())
        mat.diffuse_color = (*rgb, 1)
        mat.use_nodes = True
        principled = mat.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = (*rgb, 1)
            principled.inputs["Roughness"].default_value = .72
        MATERIALS[color] = mat
    return MATERIALS[color]


def _finish_mesh(name, color, parent=None):
    item = bpy.context.object
    item.name = name
    item.data.materials.append(material(color))
    if parent is not None:
        item.parent = parent
    return item


def _cube(name, position, size, color, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = _finish_mesh(name, color, parent)
    obj.dimensions = size
    return obj


def _cylinder(name, position, radius, depth, color, parent=None, vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=position)
    return _finish_mesh(name, color, parent)


def _cone(name, position, radius, depth, color, parent=None):
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=radius, radius2=0, depth=depth, location=position)
    return _finish_mesh(name, color, parent)


def _sphere(name, position, radius, color, parent=None, subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=radius, location=position)
    return _finish_mesh(name, color, parent)


def _empty(entry):
    node = bpy.data.objects.new(entry["name"], None)
    bpy.context.collection.objects.link(node)
    node.location = entry["location"]
    node.rotation_euler = tuple(math.radians(v) for v in entry.get("rotation", (0, 0, 0)))
    return node


def _tree(entry, parent, color):
    sx, sy, sz = entry["scale"]
    trunk = "#5B4334"
    _cylinder(entry["name"] + "_Trunk", (0, 0, sz * .65), sx * .17, sz * 1.3, trunk, parent)
    for idx, (x, y, z, factor) in enumerate(((-.24, 0, 1.45, .55), (.25, .07, 1.7, .65),
                                               (0, -.16, 1.95, .55), (0, .08, 2.3, .40))):
        obj = _sphere(entry["name"] + "_Leaf_" + str(idx), (x * sx, y * sy, z * sz),
                      sx * factor, color, parent, subdivisions=2)
        obj.scale.y = max(.3, sy / max(sx, .001))
        obj.scale.z = 1.0 + idx * .04


def _rock(entry, parent, color):
    sx, sy, sz = entry["scale"]
    obj = _sphere(entry["name"] + "_Rock", (0, 0, sz * .4), 1, color, parent)
    # Intentional planar faceting; deterministic and cheaper than subdivided boulders.
    for index, point in enumerate(obj.data.vertices):
        tweak = .92 + .13 * math.sin(index * 2.6 + sx)
        point.co.x *= sx * tweak
        point.co.y *= sy * (1 + .1 * math.cos(index * 1.9))
        point.co.z *= sz * .85


def _arch(entry, parent, color):
    sx, sy, sz = entry["scale"]
    # Two pilasters and eight radial keystones. The central opening remains clear.
    for side, x in (("L", -sx), ("R", sx)):
        _cube(entry["name"] + "_Pier_" + side, (x, 0, sz * .50),
              (sx * .40, sy * 1.8, sz), color, parent)
    radius = sx
    for index in range(9):
        angle = math.pi * index / 8
        x = radius * math.cos(angle)
        z = sz + radius * math.sin(angle)
        obj = _cube(entry["name"] + "_Voussoir_" + str(index), (x, 0, z),
                    (sx * .35, sy * 1.8, sx * .42), color, parent)
        obj.rotation_euler.y = -angle


def _roof(entry, parent, color):
    sx, sy, sz = entry["scale"]
    vertices = [(-sx, -sy, 0), (sx, -sy, 0), (0, -sy, sz),
                (-sx, sy, 0), (sx, sy, 0), (0, sy, sz)]
    faces = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (0, 2, 5, 3), (1, 4, 5, 2)]
    mesh = bpy.data.meshes.new(entry["name"] + "_RoofMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(entry["name"] + "_Roof", mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(material(color))


def add_object(entry):
    parent = _empty(entry)
    kind = entry["kind"]
    color = entry.get("color", "#8797A5")
    sx, sy, sz = entry["scale"]
    name = entry["name"]
    if kind == "cube":
        _cube(name + "_Mesh", (0, 0, 0), (sx * 2, sy * 2, sz * 2), color, parent)
    elif kind == "cylinder":
        _cylinder(name + "_Mesh", (0, 0, 0), max(sx, sy), sz * 2, color, parent)
    elif kind == "cone":
        _cone(name + "_Mesh", (0, 0, 0), max(sx, sy), sz * 2, color, parent)
    elif kind == "sphere":
        _sphere(name + "_Mesh", (0, 0, 0), 1, color, parent, subdivisions=2)
        bpy.context.object.scale = (sx, sy, sz)
    elif kind == "rock":
        _rock(entry, parent, color)
    elif kind == "tree":
        _tree(entry, parent, color)
    elif kind == "arch":
        _arch(entry, parent, color)
    elif kind == "roof":
        _roof(entry, parent, color)
    else:
        raise ValueError("Unsupported STAR scene primitive")


def _camera(spec):
    config = spec.get("camera") or {"location": [18, -24, 15], "target": [0, 0, 2]}
    source = Vector(config["location"])
    target = Vector(config["target"])
    if (source - target).length < .01:
        raise ValueError("Camera location and target must differ")
    bpy.ops.object.camera_add(location=source)
    camera = bpy.context.object
    camera.name = "STAR_ReviewCamera"
    camera.rotation_euler = (target - source).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 32
    bpy.context.scene.camera = camera


def _environment(spec):
    scene = bpy.context.scene
    scene.name = spec["name"]
    world = bpy.data.worlds.new("STAR_World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (*_color(spec.get("sky_color", "#8693AC")), 1)
    background.inputs["Strength"].default_value = .7

    bpy.ops.object.light_add(type="SUN", location=(8, -10, 17))
    sun = bpy.context.object
    sun.name = "STAR_PrimarySun"
    sun.data.energy = 1.7
    sun.rotation_euler = (math.radians(35), math.radians(-23), math.radians(-35))

    bpy.ops.object.light_add(type="AREA", location=(-7, 5, 9))
    fill = bpy.context.object
    fill.name = "STAR_AreaFill"
    fill.data.energy = 650
    fill.data.shape = "DISK"
    fill.data.size = 12
    fill.rotation_euler = (math.radians(5), math.radians(-25), math.radians(150))

    _cube("STAR_Ground", (0, 0, -.3), (90, 90, .5), spec.get("ground_color", "#66736E"))
    _camera(spec)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.engine = "BLENDER_EEVEE_NEXT" if bpy.app.version >= (4, 2, 0) else "BLENDER_EEVEE"
    scene.render.filepath = str(Path(bpy.data.filepath).parent / "preview.png")


def main():
    if "--" not in sys.argv:
        raise ValueError("STAR Blender worker requires a fixed job specification")
    arguments = sys.argv[sys.argv.index("--") + 1:]
    if len(arguments) != 1:
        raise ValueError("STAR Blender worker requires exactly one scene JSON path")
    specification = Path(arguments[0]).resolve(strict=True)
    folder = specification.parent
    if specification.name != "scene.json" or folder.name == "":
        raise ValueError("STAR Blender job path is invalid")
    if specification.stat().st_size > 24_000:
        raise ValueError("STAR Blender job size exceeds limit")
    spec = json.loads(specification.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _environment(spec)
    for item in spec["objects"]:
        add_object(item)
    scene = bpy.context.scene
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / "scene.blend"))
    bpy.ops.export_scene.gltf(filepath=str(folder / "scene.glb"), export_format="GLB",
                              export_apply=True, use_selection=False)
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    summary = {
        "job_id": folder.name, "status": "completed", "scene": spec["name"],
        "objects": len(spec["objects"]), "mesh_count": len(meshes),
        "triangle_count": sum(sum(len(face.vertices) - 2 for face in obj.data.polygons) for obj in meshes),
    }
    if spec.get("render_preview", False):
        scene.render.filepath = str(folder / "preview.png")
        bpy.ops.render.render(write_still=True)
    (folder / "result.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
