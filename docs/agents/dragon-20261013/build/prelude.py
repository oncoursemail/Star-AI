import bpy, bmesh, math, mathutils
from mathutils import Vector

# Spine of the dragon (head at -Y, tail at +Y), 1 Blender unit = 1 Roblox stud. (y, z, radius_x, radius_z)
SPINE = [
    (-6.00, 4.00, 0.27, 0.17), (-5.60, 4.12, 0.35, 0.24), (-5.20, 4.30, 0.44, 0.33), (-4.85, 4.50, 0.53, 0.43),
    (-4.50, 4.56, 0.57, 0.49), (-4.12, 4.42, 0.48, 0.47), (-3.84, 4.06, 0.45, 0.47), (-3.78, 3.60, 0.48, 0.50),
    (-3.60, 3.15, 0.56, 0.60), (-3.22, 2.76, 0.70, 0.76), (-2.72, 2.52, 0.88, 0.94), (-2.05, 2.36, 1.10, 1.22),
    (-1.20, 2.30, 1.16, 1.22), (-0.30, 2.30, 1.08, 1.10), (0.60, 2.28, 0.98, 1.00), (1.50, 2.10, 0.76, 0.78),
    (2.40, 1.80, 0.58, 0.60), (3.30, 1.45, 0.44, 0.45), (4.20, 1.12, 0.33, 0.34), (5.00, 0.90, 0.25, 0.26),
    (5.70, 0.84, 0.18, 0.19), (6.30, 0.92, 0.12, 0.12), (6.80, 1.06, 0.08, 0.08),
]
I_SKULL, I_CHEST, I_HIPS = 4, 11, 14


def mat(name, color, rough=0.5, metal=0.0, emit=0.0, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*color, 1.0)
        p.inputs["Emission Strength"].default_value = emit
    p.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*color, alpha)
    return m


def link(name, mesh):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(o)
    return o


def activate(o):
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def spine_at(t):
    """Point on the spine polyline, t in [0, len-1]."""
    i = min(int(t), len(SPINE) - 2)
    f = t - i
    a, b = SPINE[i], SPINE[i + 1]
    return tuple(a[k] + (b[k] - a[k]) * f for k in range(4))


def tube(bm, pts, radii, ring=6, close_tip=True):
    """Tapered tube through points (Vectors) with per-point radius; returns nothing (adds to bm)."""
    rings = []
    a = None
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = d.orthogonal().normalized() if a is None else (a - d * a.dot(d)).normalized()   # parallel transport
        b = d.cross(a).normalized()
        if radii[i] <= 0.0005:
            rings.append([bm.verts.new(p)])
            continue
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / ring) + b * math.sin(2 * math.pi * k / ring)) * radii[i])
                      for k in range(ring)])
    for r0, r1 in zip(rings, rings[1:]):
        if len(r1) == 1:
            for k in range(ring):
                bm.faces.new((r0[k], r0[(k + 1) % ring], r1[0]))
        else:
            for k in range(ring):
                bm.faces.new((r0[k], r0[(k + 1) % ring], r1[(k + 1) % ring], r1[k]))
    if len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
