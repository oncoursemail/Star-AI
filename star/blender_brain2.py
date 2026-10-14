"""STAR's eyes and hands on the Blender that runs on brain 2 (the second STAR server).

Blender 5.2 runs inside brain 2's STAR container, on the same virtual display as Roblox Studio, with the official
Blender Lab MCP add-on bound to 127.0.0.1 there. Like the Studio connector, it is reached through an MCP stdio
command that the OPERATOR chooses (normally `ssh <brain 2> lxc exec <container> -- sudo -u <user> -H blender-lab.sh`);
the command is never shown to a model and no network port is opened anywhere. STAR appends one fixed sub-command:
`mcp-server` (the Lab MCP server), `status`, `start`, `stop`, `shot`, `fetch`, `list`.

The Lab add-on runs any Python it is sent, with no guard. STAR therefore does not hand it to a model. A model gets
ONE tool, `star_blender`, with a fixed set of actions. Every action is built from code written here (the model only
fills validated fields: a scene name, an angle, a format), except `run_bpy`, whose model-written Python is first
checked by `check_bpy_code` (an allow-list of modules and operators, no file, network or process access, no dunder
tricks, no loops that can hang the viewport). That filter is defence in depth, not a sandbox; the real boundaries are
(1) the settings gate (off by default: `blender_enabled` + `blender_brain2`, and `blender_edit` for anything that
changes a scene or starts Blender), (2) Blender listens on 127.0.0.1 only, only while it runs, (3) it is a
transient systemd unit with a memory cap, no swap and a run-time limit, so it can never push the Studios into
out-of-memory, (4) every file it writes is inside one sandbox folder and every file STAR reads back is named by a
validated relative name that the server side checks again.
"""
from __future__ import annotations

import ast
import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import struct
import sys
import time

from jsonschema import Draft202012Validator

TOOL = "star_blender"
NAMES = frozenset({TOOL})
COMMAND_ENV = "STAR_BLENDER_BRAIN2_COMMAND"
MAX_COMMAND_BYTES = 4000
MAX_CODE = 12_000
MAX_IMAGE = 1_800_000
MAX_FILE = 24 * 1024 * 1024
SCENE_NAME = r"^[a-z][a-z0-9_-]{1,39}$"
OBJECT_NAME = r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}$"

READ_ACTIONS = ("status", "list_files", "inspect", "docs", "screenshot")
EDIT_ACTIONS = ("start", "stop", "new_scene", "open_scene", "run_bpy", "render_preview", "export")

# name -> (azimuth, elevation) in degrees. Azimuth 0 looks at the front (camera on -Y), 90 from +X, 180 from the
# back, 270 from -X; elevation 90 looks straight down.
ANGLES = {
    "front": (0.0, 0.0), "right": (90.0, 0.0), "back": (180.0, 0.0), "left": (270.0, 0.0), "top": (0.0, 90.0),
    "three_quarter": (40.0, 25.0), "rear_quarter": (220.0, 25.0),
}

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": list(READ_ACTIONS + EDIT_ACTIONS)},
        "scene": {"type": "string", "pattern": SCENE_NAME},
        "code": {"type": "string", "maxLength": MAX_CODE},
        "angles": {"type": "array", "minItems": 1, "maxItems": 6,
                   "items": {"type": "string", "enum": sorted(ANGLES)}},
        "azimuth": {"type": "number", "minimum": -360, "maximum": 360},
        "elevation": {"type": "number", "minimum": -89, "maximum": 90},
        "zoom": {"type": "number", "minimum": 0.5, "maximum": 4},
        "frame": {"type": "integer", "minimum": 0, "maximum": 100000},
        "format": {"type": "string", "enum": ["glb", "fbx"]},
        "width": {"type": "integer", "minimum": 64, "maximum": 960},
        "height": {"type": "integer", "minimum": 64, "maximum": 540},
        "engine": {"type": "string", "enum": ["workbench", "eevee", "cycles"]},
        "object": {"type": "string", "pattern": OBJECT_NAME},
        "query": {"type": "string", "minLength": 2, "maxLength": 120},
    },
    "required": ["action"],
}
VALIDATOR = Draft202012Validator(SCHEMA)

DESCRIPTION = (
    "Look at and work in the real Blender 5.2 on brain 2 (the second STAR server), like a person at the screen. "
    "Scenes live in one sandbox folder there (names: lower-case letters, digits, - and _). "
    "Actions: status; start / stop (Blender runs on demand, never all the time; it stops itself after 30 minutes); "
    "new_scene / open_scene {scene}; run_bpy {scene, code}: your Blender Python (import only bpy, bmesh, mathutils, "
    "math, random, colorsys; use bpy.ops.mesh / object / material / node / transform / collection / uv / curve "
    "operators and bpy.data; no files, no network, no classes, no while loops, no getattr/exec/open, no dunder names; "
    "set `result = {...}` to return values; the scene is saved after a run that worked); "
    "screenshot {angles: [front,right,back,left,top,three_quarter,rear_quarter] or azimuth+elevation}: images of the "
    "3D viewport as a person sees it (zoom 0.5-4 frames closer, default 1; frame: show that animation frame); "
    "render_preview {angles, width, height, engine, zoom, frame}: a quick render (workbench is "
    "fastest, eevee looks better); export {scene, format: glb|fbx}: a file for Roblox Studio's importer plus its "
    "statistics; inspect {object?}: scene or object summary; docs {query}: search the Blender Python API; "
    "list_files: what is in the sandbox. Returned images are evidence: look at them before you claim a model is right."
)

# --------------------------------------------------------------------------- the operator's launcher command


def validate_command(parts) -> list[str]:
    if (type(parts) is not list or not 1 <= len(parts) <= 40
            or any(type(part) is not str or not part or len(part) > 500
                   or any(ord(c) < 32 or ord(c) == 127 for c in part) for part in parts)):
        raise ValueError("The Blender brain 2 command must be a list of texts: the program, then its arguments")
    return list(parts)


def settings_path(home) -> Path:
    return Path(home) / "blender" / "brain2.json"


def load_command(home) -> list[str]:
    """The base launcher (without the sub-command). The process environment wins over the settings file."""
    raw = os.environ.get(COMMAND_ENV, "").strip()
    try:
        if raw:
            if len(raw.encode("utf-8")) > MAX_COMMAND_BYTES:
                return []
            return validate_command(json.loads(raw))
        saved = json.loads(settings_path(home).read_text(encoding="utf-8"))
        return validate_command(saved.get("command")) if isinstance(saved, dict) and saved.get("command") else []
    except (OSError, ValueError, UnicodeError):
        return []


def save_command(home, command: list[str]) -> dict:
    """Owner or operator action only: no model tool calls this."""
    path = settings_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"command": validate_command(command) if command else []}, indent=1),
                         encoding="utf-8")
    os.replace(temporary, path)
    return public(home)


def public(home) -> dict:
    command = load_command(home)
    return {"configured": bool(command), "program": Path(command[0]).name if command else ""}


# --------------------------------------------------------------------------- the filter for model-written Python

ALLOWED_IMPORTS = frozenset({"bpy", "bmesh", "mathutils", "math", "random", "colorsys", "itertools", "functools",
                             "collections", "typing", "bpy_extras"})
ALLOWED_OPS = frozenset({
    "object", "mesh", "curve", "curves", "surface", "transform", "material", "node", "uv", "collection", "armature",
    "pose", "constraint", "lattice", "geometry", "rigidbody", "anim", "mball", "font",
})
BLOCKED_NAMES = frozenset({
    "exec", "eval", "compile", "open", "input", "breakpoint", "__import__", "globals", "locals", "vars", "getattr",
    "setattr", "delattr", "memoryview", "help", "exit", "quit", "type", "super", "classmethod",
    "staticmethod", "property",
})
BLOCKED_ATTRIBUTES = frozenset({
    "load", "write", "save", "save_render", "save_as", "filepath", "filepath_raw", "libraries", "preferences", "app",
    "utils", "path", "system", "unpack", "pack", "reload", "register_class", "unregister_class",
    "directory", "files", "sound_open", "texts", "scripts", "addons", "extensions", "handlers",
    "timers", "msgbus", "driver_namespace",
})
_PATH_LIKE = re.compile(r"(^/|^\\|^~|\.\.|://|^[A-Za-z]:|\\\\)")


def check_bpy_code(code: object) -> str:
    """Return the code when it passes; raise ValueError (with a message a model can act on) when it does not."""
    if type(code) is not str or not code.strip():
        raise ValueError("run_bpy needs Python code")
    if len(code) > MAX_CODE or "\x00" in code:
        raise ValueError("The Python code is too long or contains a null byte")
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        raise ValueError(f"The Python code has a syntax error on line {error.lineno}") from None
    ops_nodes, consumed = {}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr == "ops":
                ops_nodes[id(node)] = node
            consumed.add(id(node.value))
    for key, node in ops_nodes.items():
        if key not in consumed:   # `x = bpy.ops` would hide which operator module is used
            raise ValueError(f"bpy.ops must be used directly as bpy.ops.<module>.<operator>(...) (line {node.lineno})")
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        where = f" (line {line})" if line else ""
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            roots = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else \
                [(node.module or "").split(".")[0]]
            if isinstance(node, ast.ImportFrom) and node.level:
                raise ValueError(f"Relative imports are not allowed{where}")
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [f"{node.module}.{alias.name}" for alias in node.names])
            if any(re.search(r"(^|\.)(ops|app|utils|path)($|\.)", name) for name in names if name.startswith("bpy")):
                raise ValueError(f"Importing bpy.ops, bpy.app, bpy.utils or bpy.path is not allowed{where}")
            for root in roots:
                if root not in ALLOWED_IMPORTS:
                    raise ValueError(f"Import of '{root}' is not allowed; only {', '.join(sorted(ALLOWED_IMPORTS))}{where}")
        elif isinstance(node, (ast.ClassDef, ast.While, ast.AsyncFunctionDef, ast.Await, ast.Global, ast.Nonlocal,
                               ast.AsyncFor, ast.AsyncWith, ast.Yield, ast.YieldFrom)):
            raise ValueError(f"'{type(node).__name__}' is not allowed (no classes, while loops or async code){where}")
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES or (node.id.startswith("__") and node.id.endswith("__")):
                raise ValueError(f"The name '{node.id}' is not allowed{where}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in BLOCKED_ATTRIBUTES:
                raise ValueError(f"The attribute '.{node.attr}' is not allowed (files, add-ons and internals are off limits){where}")
            if (isinstance(node.value, ast.Attribute) and node.value.attr == "ops"
                    and isinstance(node.value.value, ast.Name) and node.value.value.id == "bpy"
                    and node.attr not in ALLOWED_OPS):
                raise ValueError(f"bpy.ops.{node.attr} is not allowed; use bpy.ops.mesh/object/material/node/transform/"
                                 f"collection/uv/curve or bpy.data{where}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, int) and abs(arg.value) > 200_000:
                    raise ValueError(f"range() above 200000 would stall the viewport{where}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _PATH_LIKE.search(node.value):
                raise ValueError(f"Text that looks like a path or URL is not allowed{where}")
    return code


# --------------------------------------------------------------------------- code that runs inside Blender (ours)

_HEAD = """\
import bpy, os, math, mathutils
SB = os.environ["BLENDER_LAB_SANDBOX"]
def _stats():
    dg = bpy.context.evaluated_depsgraph_get()
    tris = verts = 0
    lo = [1e9] * 3
    hi = [-1e9] * 3
    names = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or not o.visible_get():
            continue
        e = o.evaluated_get(dg)
        m = e.to_mesh()
        m.calc_loop_triangles()
        tris += len(m.loop_triangles)
        verts += len(m.vertices)
        e.to_mesh_clear()
        names.append(o.name)
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    if not names:
        lo = hi = [0.0, 0.0, 0.0]
    return {"meshes": names, "triangles": tris, "vertices": verts,
            "size_m": [round(hi[i] - lo[i], 4) for i in range(3)],
            "min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi],
            "materials": sorted({s.material.name for o in bpy.context.scene.objects if o.type == 'MESH'
                                 for s in o.material_slots if s.material})}
"""

NEW_SCENE = _HEAD + """\
path = os.path.join(SB, @@SCENE@@ + ".blend")
if os.path.exists(path):
    raise RuntimeError("scene exists; use open_scene")
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.wm.save_as_mainfile(filepath=path)
result = {"scene": @@SCENE@@, "file": @@SCENE@@ + ".blend", "bytes": os.path.getsize(path)}
"""

OPEN_SCENE = _HEAD + """\
path = os.path.join(SB, @@SCENE@@ + ".blend")
if not os.path.isfile(path):
    raise RuntimeError("no such scene in the sandbox")
bpy.ops.wm.open_mainfile(filepath=path)
result = dict(_stats(), scene=@@SCENE@@, objects=len(bpy.context.scene.objects))
"""

SAVE_SCENE = _HEAD + """\
path = os.path.join(SB, @@SCENE@@ + ".blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
result = dict(_stats(), scene=@@SCENE@@, saved_bytes=os.path.getsize(path), objects=len(bpy.context.scene.objects))
"""

VIEW = _HEAD + """\
bpy.context.preferences.view.smooth_view = 0
win = bpy.context.window_manager.windows[0]
area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.width * a.height)
space = area.spaces.active
r3d = space.region_3d
region = next(r for r in area.regions if r.type == 'WINDOW')
space.shading.type = 'SOLID'
space.shading.light = 'STUDIO'
space.shading.color_type = 'MATERIAL'
for flag in ('show_region_header', 'show_region_toolbar', 'show_region_ui', 'show_region_tool_header',
             'show_region_hud'):
    if hasattr(space, flag):
        setattr(space, flag, False)
space.overlay.show_text = False
space.overlay.show_stats = False
space.overlay.show_bones = False      # rigs and lights are not part of what the model looks like
space.overlay.show_extras = False
space.show_gizmo = False
r3d.view_perspective = 'PERSP'
r3d.view_rotation = mathutils.Euler((math.radians(90.0 - @@EL@@), 0.0, math.radians(@@AZ@@))).to_quaternion()
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.visible_get()]
for o in bpy.data.objects:
    o.select_set(False)
for o in meshes:
    o.select_set(True)
if meshes:
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.view3d.view_selected()
    r3d.view_distance *= 0.95 / @@ZOOM@@
for o in bpy.data.objects:
    o.select_set(False)
with bpy.context.temp_override(window=win, area=area, region=region):
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
result = {"crop": [region.x, win.height - (region.y + region.height), region.width, region.height],
          "window": [win.width, win.height], "meshes": len(meshes)}
"""

RENDER = _HEAD + """\
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == 'MESH' and o.visible_get()]
if not meshes:
    raise RuntimeError("nothing to render: the scene has no visible mesh")
st = _stats()
lo, hi = mathutils.Vector(st["min"]), mathutils.Vector(st["max"])
center = (lo + hi) / 2.0
radius = max((hi - lo).length / 2.0, 0.05)
cam_data = bpy.data.cameras.new("STAR_PreviewCam")
cam = bpy.data.objects.new("STAR_PreviewCam", cam_data)
scene.collection.objects.link(cam)
old_cam = scene.camera
try:
    w, h = @@W@@, @@H@@
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = w, h, 100
    sensor = cam_data.sensor_width * (min(1.0, h / w))
    half = math.atan((sensor / 2.0) / cam_data.lens)
    dist = radius / math.sin(half) * 1.12 / @@ZOOM@@
    az, el = math.radians(@@AZ@@), math.radians(@@EL@@)
    cam.location = center + mathutils.Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    engine = @@ENGINE@@
    scene.render.engine = {"workbench": "BLENDER_WORKBENCH", "eevee": "BLENDER_EEVEE", "cycles": "CYCLES"}[engine]
    if engine == "workbench":
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
    if engine == "cycles":
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 24
        scene.cycles.use_denoising = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("StarWorld")
    scene.world.color = (0.12, 0.13, 0.16)
    if engine != "workbench" and not any(o.type == 'LIGHT' for o in scene.objects):
        sun_data = bpy.data.lights.new("STAR_PreviewSun", 'SUN')
        sun_data.energy = 3.0
        sun = bpy.data.objects.new("STAR_PreviewSun", sun_data)
        scene.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(50), 0.0, math.radians(30))
    os.makedirs(os.path.join(SB, "previews"), exist_ok=True)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.join(SB, "previews", @@NAME@@ + ".png")
    scene.render.use_lock_interface = True
    bpy.ops.render.render(write_still=True)
finally:
    scene.camera = old_cam
    bpy.data.objects.remove(cam)
    for o in [o for o in bpy.data.objects if o.name.startswith("STAR_PreviewSun")]:
        bpy.data.objects.remove(o)
out = os.path.join(SB, "previews", @@NAME@@ + ".png")
result = {"file": "previews/" + @@NAME@@ + ".png", "bytes": os.path.getsize(out), "engine": @@ENGINE@@, "size": [@@W@@, @@H@@]}
"""

EXPORT = _HEAD + """\
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.visible_get()]
if not objs:
    raise RuntimeError("nothing to export: the scene has no visible mesh")
# a rig that deforms the meshes goes along (bones + its action), so a skinned model and its idle survive the export
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE' and o.visible_get()
        and any(m.type == 'ARMATURE' and m.object == o for x in objs for m in x.modifiers)]
animated = any(o.animation_data and o.animation_data.action for o in rigs)
objs = objs + rigs
os.makedirs(os.path.join(SB, "exports"), exist_ok=True)
rel = "exports/" + @@SCENE@@ + "." + @@FORMAT@@
path = os.path.join(SB, rel)
for o in bpy.data.objects:
    o.select_set(False)
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
if @@FORMAT@@ == "glb":
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_animations=animated)
else:
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'ARMATURE'}, use_mesh_modifiers=True,
                             apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
                             mesh_smooth_type='FACE', bake_anim=animated, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, add_leaf_bones=False)
for o in bpy.data.objects:
    o.select_set(False)
per_mesh = {}
dg = bpy.context.evaluated_depsgraph_get()
for o in objs:
    if o.type == 'MESH':
        e = o.evaluated_get(dg)
        m = e.to_mesh()
        m.calc_loop_triangles()
        per_mesh[o.name] = len(m.loop_triangles)
        e.to_mesh_clear()
result = dict(_stats(), file=rel, bytes=os.path.getsize(path), format=@@FORMAT@@,
              armatures=[o.name for o in rigs], animated=animated, per_mesh_triangles=per_mesh)
"""

OBJECT_DETAIL = None  # inspect uses the Lab's own read-only tools


def _at_frame(code: str, frame) -> str:
    """Show an animation frame first (an integer validated by the schema), so poses can be looked at and rendered."""
    if frame is None:
        return code
    if type(frame) is not int or not 0 <= frame <= 100000:
        raise ValueError("frame must be a whole number from 0 to 100000")
    return "import bpy\nbpy.context.scene.frame_set(" + str(frame) + ")\n" + code


def fill(template: str, **values) -> str:
    """Put validated values into a template as Python literals (never as free text)."""
    out = template
    for key, value in values.items():
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError("template values must be text or numbers")
        out = out.replace(f"@@{key}@@", repr(value))
    if "@@" in out:
        raise ValueError("template value missing")
    return out


# --------------------------------------------------------------------------- evidence helpers


def inspect_glb(data: bytes) -> dict:
    """What a GLB file really holds, read from its own header and JSON chunk (no Blender, no trust)."""
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("not a GLB file")
    version, length = struct.unpack_from("<II", data, 4)
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A or 20 + chunk_length > len(data):
        raise ValueError("GLB has no readable JSON chunk")
    document = json.loads(data[20:20 + chunk_length].decode("utf-8"))
    triangles = 0
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            index = primitive.get("indices")
            accessor = document["accessors"][index] if index is not None else \
                document["accessors"][primitive["attributes"]["POSITION"]]
            triangles += accessor["count"] // 3
    return {"version": version, "declared_bytes": length, "actual_bytes": len(data),
            "meshes": len(document.get("meshes", [])), "nodes": len(document.get("nodes", [])),
            "materials": [m.get("name", "") for m in document.get("materials", [])], "triangles": triangles,
            "extensions": sorted(document.get("extensionsUsed", [])),
            "skins": [len(skin.get("joints", [])) for skin in document.get("skins", [])],
            "animations": [{"name": a.get("name", ""), "channels": len(a.get("channels", []))}
                           for a in document.get("animations", [])]}


def is_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])


class LabError(RuntimeError):
    """A failure with a message that is safe to show (never the launcher command or the server's own stderr)."""


def _first_safe_error(error: BaseException):
    """The first LabError inside a (nested) exception group, else None. anyio task groups (the MCP stdio session)
    wrap anything raised in their body, which would otherwise hide 'Blender code failed: ...' from the model."""
    if isinstance(error, LabError):
        return error
    for inner in getattr(error, "exceptions", None) or ():
        found = _first_safe_error(inner)
        if found is not None:
            return found
    return None


def wants_blender_brain2(prompt: str) -> bool:
    from .blender_mcp import wants_blender
    return wants_blender(prompt)


# --------------------------------------------------------------------------- the client


async def _run(argv: list[str], timeout: float) -> tuple[int, bytes, bytes]:
    safe = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE",
            "USERNAME", "HOMEDRIVE", "HOMEPATH", "SSH_AUTH_SOCK", "LOCALAPPDATA", "APPDATA"}
    env = {k: v for k, v in os.environ.items() if k.upper() in safe and not v.startswith("()")}
    process = await asyncio.create_subprocess_exec(
        *argv, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
    try:
        out, err = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise LabError("Blender on brain 2 did not answer in time") from None
    return process.returncode, out, err


@asynccontextmanager
async def _stdio_session(command: list[str], seconds: float):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    safe = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE",
            "USERNAME", "HOMEDRIVE", "HOMEPATH", "SSH_AUTH_SOCK", "LOCALAPPDATA", "APPDATA"}
    env = {k: v for k, v in os.environ.items() if k.upper() in safe and not v.startswith("()")}
    params = StdioServerParameters(command=command[0], args=[*command[1:], "mcp-server"], env=env)
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=seconds)) as session:
                await asyncio.wait_for(session.initialize(), timeout=45)
                yield session


def _text_payload(result) -> dict:
    """The Lab server's answer as a dict: structured content when present, else the first text block as JSON."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured.get("result", structured) if set(structured) == {"result"} and isinstance(
            structured.get("result"), dict) else structured
    for block in getattr(result, "content", None) or []:
        if getattr(block, "type", "") == "text":
            try:
                value = json.loads(block.text)
                return value if isinstance(value, dict) else {"value": value}
            except ValueError:
                return {"status": "error", "message": block.text[:300]}
    return {}


class BrainTwoBlender:
    """The model-facing client: owns/definitions/call, the same shape as star/blender_mcp.BlenderClient."""

    def __init__(self, command: list[str], *, home, edit: bool = False, runner=None, session_factory=None,
                 call_seconds: float = 180.0):
        self.command = validate_command(list(command))
        self.home = Path(home)
        self.edit = bool(edit)
        self._run = runner or _run
        self._session_factory = session_factory or (lambda: _stdio_session(self.command, call_seconds))
        self.catalog = [{"name": TOOL, "description": DESCRIPTION, "inputSchema": self._schema()}]

    def _schema(self) -> dict:
        actions = list(READ_ACTIONS + (EDIT_ACTIONS if self.edit else ()))
        schema = json.loads(json.dumps(SCHEMA))
        schema["properties"]["action"]["enum"] = actions
        return schema

    @staticmethod
    def owns(name: str) -> bool:
        return name in NAMES

    def definitions(self, prompt: str) -> list[dict]:
        return list(self.catalog) if wants_blender_brain2(prompt) else []

    # ---- plumbing
    async def _control(self, *sub: str, timeout: float = 25.0) -> tuple[int, bytes]:
        code, out, _err = await self._run([*self.command, *sub], timeout)
        return code, out

    async def _control_json(self, *sub: str, timeout: float = 25.0) -> dict:
        code, out = await self._control(*sub, timeout=timeout)
        if code != 0:
            raise LabError(f"Blender on brain 2: '{sub[0]}' failed (exit {code})" + (
                ": not enough free memory (the Studios come first); try later" if code == 5 else
                ": Blender or the Lab add-on is not installed there" if code == 3 else ""))
        try:
            value = json.loads(out.decode("utf-8").strip().splitlines()[-1])
        except (ValueError, IndexError, UnicodeError):
            raise LabError(f"Blender on brain 2: unreadable answer to '{sub[0]}'") from None
        return value if isinstance(value, dict) else {}

    async def _fetch(self, relative: str, limit: int = MAX_FILE) -> bytes:
        code, out = await self._control("fetch", relative, timeout=60.0)
        if code != 0 or not out:
            raise LabError("Blender on brain 2: could not read back the file")
        if len(out) > limit:
            raise LabError("the file is larger than STAR will take over")
        return out

    async def _ensure_running(self, session_needed: bool = True) -> dict:
        status = await self._control_json("status")
        if status.get("running") and status.get("mcp_port_open"):
            return status
        if not self.edit:
            raise LabError("Blender is not running on brain 2 and starting it needs the Blender edit permission")
        await self._control_json("start", timeout=60.0)
        return await self._control_json("status")

    @staticmethod
    async def _exec(session, code: str) -> dict:
        reply = _text_payload(await session.call_tool("execute_blender_code", arguments={"code": code}))
        if reply.get("status") != "ok":
            message = str(reply.get("message", "unknown error"))
            tail = [line for line in message.strip().splitlines() if line.strip()][-1:] or ["unknown error"]
            raise LabError("Blender code failed: " + tail[0][:300])
        result = reply.get("result")
        out = dict(result) if isinstance(result, dict) else {"value": result}
        if reply.get("stdout") and "Warning:" not in str(reply["stdout"]):
            out["stdout"] = str(reply["stdout"])[-600:]
        return out

    def _evidence(self, scene: str, name: str, data: bytes) -> str:
        folder = self.home / "blender" / "brain2" / (scene or "no-scene")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return (Path("blender") / "brain2" / (scene or "no-scene") / name).as_posix()

    @staticmethod
    def _result(info: dict, images: list[bytes] = (), *, error: bool = False) -> dict:
        content = [{"type": "text", "text": json.dumps(info, ensure_ascii=False)}]
        for image in images:
            content.append({"type": "image", "mimeType": "image/png", "data": base64.b64encode(image).decode("ascii")})
        return {"isError": error, "content": content}

    def _angles(self, args: dict) -> list[tuple[str, float, float]]:
        if args.get("angles"):
            return [(name, *ANGLES[name]) for name in args["angles"]]
        if "azimuth" in args or "elevation" in args:
            az, el = float(args.get("azimuth", 40.0)), float(args.get("elevation", 25.0))
            return [(f"az{int(az)}_el{int(el)}", az, el)]
        return [(name, *ANGLES[name]) for name in ("three_quarter",)]

    # ---- the public entry
    async def call(self, name: str, arguments: dict) -> dict:
        if name != TOOL:
            raise PermissionError("not a Blender brain 2 tool")
        try:
            args = self.validate(arguments)
            handler = getattr(self, "_do_" + args["action"])
            return await handler(args)
        except (ValueError, PermissionError) as error:
            return self._result({"error": str(error)[:300]}, error=True)
        except LabError as error:
            return self._result({"error": str(error)[:300]}, error=True)
        except asyncio.CancelledError:
            raise
        except Exception as error:   # transport failures: the kind only, never the command or its output
            inner = _first_safe_error(error)
            if inner is not None:   # a LabError raised inside the MCP session arrives wrapped in an ExceptionGroup
                return self._result({"error": str(inner)[:300]}, error=True)
            return self._result({"error": f"Blender on brain 2 could not be reached ({type(error).__name__})"}, error=True)

    def validate(self, arguments) -> dict:
        if type(arguments) is not dict or len(json.dumps(arguments, allow_nan=False)) > MAX_CODE + 2000:
            raise ValueError("invalid or oversized arguments")
        errors = sorted(VALIDATOR.iter_errors(arguments), key=lambda e: list(e.path))
        if errors:
            first = errors[0]
            where = ".".join(str(p) for p in first.path) or "arguments"
            raise ValueError(f"invalid {where}: {first.message[:120]}")
        action = arguments["action"]
        if action in EDIT_ACTIONS and not self.edit:
            raise PermissionError("This action needs the Blender edit permission in STAR settings")
        needs_scene = {"new_scene", "open_scene", "run_bpy", "export"}
        if action in needs_scene and "scene" not in arguments:
            raise ValueError(f"{action} needs a scene name")
        if action == "run_bpy":
            check_bpy_code(arguments.get("code"))
        if action == "docs" and "query" not in arguments:
            raise ValueError("docs needs a query")
        if action == "export" and "format" not in arguments:
            arguments = {**arguments, "format": "glb"}
        return dict(arguments)

    # ---- actions
    async def _do_status(self, args):
        status = await self._control_json("status")
        status["edit_permission"] = self.edit
        return self._result(status)

    async def _do_list_files(self, args):
        code, out = await self._control("list")
        if code != 0:
            raise LabError("Blender on brain 2: could not list the sandbox")
        files = []
        for line in out.decode("utf-8", "replace").splitlines()[:200]:
            name, _, size = line.partition("\t")
            files.append({"file": name, "bytes": int(size) if size.isdigit() else 0})
        return self._result({"files": files})

    async def _do_start(self, args):
        return self._result(await self._control_json("start", timeout=60.0))

    async def _do_stop(self, args):
        return self._result(await self._control_json("stop"))

    async def _do_new_scene(self, args):
        await self._ensure_running()
        async with self._session_factory() as session:
            info = await self._exec(session, fill(NEW_SCENE, SCENE=args["scene"]))
        return self._result(info)

    async def _do_open_scene(self, args):
        await self._ensure_running()
        async with self._session_factory() as session:
            info = await self._exec(session, fill(OPEN_SCENE, SCENE=args["scene"]))
        return self._result(info)

    async def _do_run_bpy(self, args):
        await self._ensure_running()
        async with self._session_factory() as session:
            ran = await self._exec(session, args["code"])
            saved = await self._exec(session, fill(SAVE_SCENE, SCENE=args["scene"]))
        return self._result({"ran": ran, "scene": saved})

    async def _do_inspect(self, args):
        status = await self._control_json("status")
        if not (status.get("running") and status.get("mcp_port_open")):
            raise LabError("Blender is not running on brain 2")
        async with self._session_factory() as session:
            if args.get("object"):
                reply = _text_payload(await session.call_tool("get_object_detail_summary", arguments={"name": args["object"]}))
            else:
                reply = _text_payload(await session.call_tool("get_objects_summary", arguments={}))
        return self._result({"summary": reply.get("result", reply)})

    async def _do_docs(self, args):
        async with self._session_factory() as session:
            reply = _text_payload(await session.call_tool("search_api_docs", arguments={"query": args["query"], "max_results": 8}))
        return self._result({"docs": json.dumps(reply.get("result", reply))[:3500]})

    async def _view_images(self, angles, scene, zoom: float = 1.0, frame=None):
        images, notes = [], []
        status = await self._control_json("status")
        if not (status.get("running") and status.get("mcp_port_open")):
            raise LabError("Blender is not running on brain 2 (start it first, or ask for an edit action)")
        async with self._session_factory() as session:
            for label, azimuth, elevation in angles:
                geometry = await self._exec(session, _at_frame(fill(VIEW, AZ=azimuth, EL=elevation, ZOOM=zoom), frame))
                if not geometry.get("meshes"):
                    raise LabError("the scene has no visible mesh to look at")
                await asyncio.sleep(0.4)
                x, y, w, h = (int(max(0, v)) for v in geometry["crop"])
                tag = re.sub(r"[^a-z0-9_-]", "", f"{scene or 'view'}-{label}")[:60]
                await self._control_json("shot", tag, str(x), str(y), str(w), str(h), timeout=30.0)
                png = await self._fetch(f"shots/{tag}.png", MAX_IMAGE)
                if not is_png(png):
                    raise LabError("the screenshot was not a PNG")
                images.append(png)
                notes.append({"angle": label, "size": list(png_size(png)),
                              "evidence": self._evidence(scene or "view", f"{label}.png", png)})
        return images, notes

    async def _do_screenshot(self, args):
        images, notes = await self._view_images(self._angles(args), args.get("scene", ""), float(args.get("zoom", 1.0)),
                                                args.get("frame"))
        return self._result({"screenshots": notes}, images)

    async def _do_render_preview(self, args):
        await self._ensure_running()
        scene = args.get("scene", "") or "preview"
        width, height = int(args.get("width", 640)), int(args.get("height", 360))
        images, notes = [], []
        async with self._session_factory() as session:
            for label, azimuth, elevation in self._angles(args)[:4]:
                name = re.sub(r"[^a-z0-9_-]", "", f"{scene}-{label}")[:60]
                began = time.monotonic()
                info = await self._exec(session, _at_frame(fill(RENDER, W=width, H=height, AZ=azimuth, EL=elevation, ZOOM=float(args.get("zoom", 1.0)),
                                                      ENGINE=args.get("engine", "workbench"), NAME=name), args.get("frame")))
                png = await self._fetch(info["file"], MAX_IMAGE)
                if not is_png(png):
                    raise LabError("the preview was not a PNG")
                images.append(png)
                notes.append({"angle": label, "engine": info["engine"], "size": list(png_size(png)),
                              "seconds": round(time.monotonic() - began, 2),
                              "evidence": self._evidence(scene, f"render-{label}.png", png)})
        return self._result({"previews": notes}, images)

    async def _do_export(self, args):
        await self._ensure_running()
        fmt = args["format"]
        async with self._session_factory() as session:
            info = await self._exec(session, fill(EXPORT, SCENE=args["scene"], FORMAT=fmt))
        data = await self._fetch(info["file"], MAX_FILE)
        if fmt == "glb":
            info["glb"] = inspect_glb(data)
        elif not data.startswith(b"Kaydara FBX Binary"):
            raise LabError("the FBX file has no FBX header")
        info.pop("stdout", None)   # the exporter's log lines
        info["evidence"] = self._evidence(args["scene"], f"{args['scene']}.{fmt}", data)
        info["roblox_note"] = ("Import with Studio's Asset Importer (File > Import 3D); Blender is Z-up and meters, Roblox is "
                               "Y-up and studs: check size and orientation after import. Nothing was uploaded.")
        return self._result(info)


@asynccontextmanager
async def connect_brain2_blender(settings, home):
    """Used by the chat for a Blender-related tool turn when the owner switched brain 2's Blender on."""
    if getattr(settings, "blender_enabled", False) is not True or getattr(settings, "blender_brain2", False) is not True:
        raise PermissionError("Blender on brain 2 is not enabled in STAR settings")
    command = load_command(home)
    if not command:
        raise RuntimeError("No launcher command is stored for Blender on brain 2")
    yield BrainTwoBlender(command, home=home, edit=getattr(settings, "blender_edit", False) is True)


# --------------------------------------------------------------------------- command line (operator)

LANTERN = '''\
import bpy, bmesh, math

for old in list(bpy.data.objects):
    bpy.data.objects.remove(old)
for old in list(bpy.data.materials):
    bpy.data.materials.remove(old)
for old in list(bpy.data.meshes):
    bpy.data.meshes.remove(old)

def material(name, color, metallic=0.0, roughness=0.5, emit=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if emit:
        shader.inputs["Emission Color"].default_value = (*color, 1.0)
        shader.inputs["Emission Strength"].default_value = emit
    mat.diffuse_color = (*color, 1.0)
    return mat

iron = material("Lantern_Iron", (0.07, 0.065, 0.06), metallic=0.8, roughness=0.45)
glass = material("Lantern_Glass", (1.0, 0.62, 0.2), roughness=0.1, emit=1.5)
flame = material("Lantern_Flame", (1.0, 0.85, 0.35), emit=8.0)

def finish(obj, name, mat):
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj

parts = {"iron": [], "glass": [], "flame": []}

def add(kind, fn, mat_key, **kw):
    fn(**kw)
    obj = bpy.context.active_object
    obj.data.materials.append({"iron": iron, "glass": glass, "flame": flame}[mat_key])
    parts[mat_key].append(obj)
    return obj

add("base", bpy.ops.mesh.primitive_cylinder_add, "iron", vertices=16, radius=0.23, depth=0.06, location=(0, 0, 0.03))
add("body", bpy.ops.mesh.primitive_cylinder_add, "glass", vertices=8, radius=0.16, depth=0.46, location=(0, 0, 0.29))
add("flame", bpy.ops.mesh.primitive_ico_sphere_add, "flame", subdivisions=2, radius=0.055, location=(0, 0, 0.27))
add("cap", bpy.ops.mesh.primitive_cone_add, "iron", vertices=8, radius1=0.27, radius2=0.07, depth=0.14, location=(0, 0, 0.59))
add("knob", bpy.ops.mesh.primitive_uv_sphere_add, "iron", segments=12, ring_count=6, radius=0.04, location=(0, 0, 0.69))
add("handle", bpy.ops.mesh.primitive_torus_add, "iron", major_segments=20, minor_segments=6, major_radius=0.09,
    minor_radius=0.012, location=(0, 0, 0.77), rotation=(math.radians(90), 0, 0))
for i in range(4):
    angle = math.radians(45 + 90 * i)
    add("post%d" % i, bpy.ops.mesh.primitive_cylinder_add, "iron", vertices=6, radius=0.016, depth=0.5,
        location=(math.cos(angle) * 0.17, math.sin(angle) * 0.17, 0.31))

for key, name in (("iron", "Lantern_Iron"), ("glass", "Lantern_Glass"), ("flame", "Lantern_Flame")):
    for o in bpy.data.objects:
        o.select_set(False)
    for o in parts[key]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[key][0]
    if len(parts[key]) > 1:
        bpy.ops.object.join()
    bpy.context.active_object.name = name
    bpy.ops.object.shade_smooth()
result = {"built": [o.name for o in bpy.context.scene.objects]}
'''


async def run_demo(client: BrainTwoBlender, out: Path, scene: str = "lantern") -> dict:
    """The lantern: build, three viewport angles, a preview render, a GLB; evidence files written to `out`."""
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"scene": scene, "steps": []}

    async def step(label: str, arguments: dict):
        began = time.monotonic()
        reply = await client.call(TOOL, arguments)
        info = json.loads(reply["content"][0]["text"])
        images = [base64.b64decode(c["data"]) for c in reply["content"] if c.get("type") == "image"]
        report["steps"].append({"step": label, "ok": not reply["isError"], "seconds": round(time.monotonic() - began, 2),
                                "info": info})
        if reply["isError"]:
            raise LabError(f"demo step '{label}' failed: {info}")
        return info, images

    await step("status", {"action": "status"})
    try:
        await step("new_scene", {"action": "new_scene", "scene": scene})
    except LabError:
        await step("open_scene", {"action": "open_scene", "scene": scene})
    await step("run_bpy", {"action": "run_bpy", "scene": scene, "code": LANTERN})
    _, shots = await step("screenshot", {"action": "screenshot", "scene": scene,
                                         "angles": ["three_quarter", "front", "top"]})
    for label, image in zip(("three_quarter", "front", "top"), shots):
        (out / f"viewport-{label}.png").write_bytes(image)
    _, previews = await step("render_preview", {"action": "render_preview", "scene": scene, "engine": "eevee",
                                                "angles": ["three_quarter"], "width": 640, "height": 360})
    (out / "render-three_quarter.png").write_bytes(previews[0])
    info, _ = await step("export", {"action": "export", "scene": scene, "format": "glb"})
    evidence = client.home / info["evidence"]
    (out / f"{scene}.glb").write_bytes(evidence.read_bytes())
    # What a person at the screen sees: the whole Blender window, UI included (proof the GUI really renders).
    await client._control_json("shot", "gui-window", timeout=30.0)
    window = await client._fetch("shots/gui-window.png", MAX_FILE)
    (out / "gui-window.png").write_bytes(window)
    report["gui_window_bytes"] = len(window)
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def main(arguments=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="STAR's Blender on brain 2 (operator tool; reads/writes only the sandbox there)")
    parser.add_argument("--home", required=True, help="STAR's data folder (the launcher setting lives in <home>/blender)")
    parser.add_argument("--set-command", metavar="JSON", help='the launcher as a JSON list, e.g. ["ssh","host","lxc","exec",...,"blender-lab.sh"]')
    parser.add_argument("--status", action="store_true", help="ask the launcher for status (starts nothing)")
    parser.add_argument("--call", metavar="JSON", help="one star_blender call as JSON (edit actions need --edit)")
    parser.add_argument("--call-file", metavar="FILE", help="the same, read from a UTF-8 JSON file (long run_bpy code "
                        "does not survive cmd.exe / ssh argument quoting)")
    parser.add_argument("--demo", metavar="OUTDIR", help="build the lantern, 3 screenshots, a preview and a GLB into OUTDIR")
    parser.add_argument("--edit", action="store_true", help="the owner's Blender edit permission for this run")
    chosen = parser.parse_args(arguments)
    home = Path(chosen.home).expanduser()
    if chosen.set_command is not None:
        try:
            print(json.dumps(save_command(home, json.loads(chosen.set_command) if chosen.set_command else [])))
        except ValueError as error:
            print(str(error)); return 2
    if chosen.call_file:
        chosen.call = Path(chosen.call_file).read_text(encoding="utf-8")
    command = load_command(home)
    if not (chosen.status or chosen.call or chosen.demo):
        print(json.dumps(public(home)))
        return 0
    if not command:
        print("No launcher command is stored (use --set-command or STAR_BLENDER_BRAIN2_COMMAND)")
        return 2
    client = BrainTwoBlender(command, home=home, edit=chosen.edit or bool(chosen.demo))

    async def go():
        if chosen.status:
            print(json.dumps(json.loads((await client.call(TOOL, {"action": "status"}))["content"][0]["text"]), indent=1))
        if chosen.call:
            reply = await client.call(TOOL, json.loads(chosen.call))
            for block in reply["content"]:
                print(block["text"] if block["type"] == "text" else f"[image {len(block['data'])} base64 chars]")
            return 1 if reply["isError"] else 0
        if chosen.demo:
            report = await run_demo(client, Path(chosen.demo))
            print(json.dumps(report, indent=1))
        return 0
    return asyncio.run(go())


if __name__ == "__main__":
    sys.exit(main())
