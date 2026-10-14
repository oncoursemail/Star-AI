# Chunk B: jaw, brows, eyes, horns, teeth, dorsal spikes, claws, tail spade. Placed on the real evaluated body
# surface with ray casts, so nothing floats.
M_SCALE = bpy.data.materials["Dragon_Scales"]
M_HORN = bpy.data.materials["Dragon_Horn"]
M_EYE = bpy.data.materials["Dragon_Eye"]
M_TOOTH = mat("Dragon_Teeth", (0.92, 0.88, 0.76), rough=0.4)
for name in ("Dragon_Jaw", "Dragon_Brow", "Dragon_Eyes", "Dragon_Horns", "Dragon_Spikes", "Dragon_Claws",
             "Dragon_TailSpade", "Dragon_Teeth"):
    if bpy.data.objects.get(name):
        bpy.data.objects.remove(bpy.data.objects[name])
body = bpy.data.objects["Dragon_Body"]
dg = bpy.context.evaluated_depsgraph_get()
body_eval = body.evaluated_get(dg)


def surface(origin, direction):
    hit, loc, nor, idx = body_eval.ray_cast(Vector(origin), Vector(direction).normalized(), distance=20.0)
    return (loc, nor) if hit else (None, None)


def new_obj(name, bm, material, subsurf=0, mirror=False, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = link(name, me)
    o.data.materials.append(material)
    for poly in o.data.polygons:
        poly.use_smooth = smooth
    if mirror:
        m = o.modifiers.new("Mirror", 'MIRROR')
        m.use_axis[0] = True
        m.use_mirror_merge = True
    if subsurf:
        s = o.modifiers.new("Subdivision", 'SUBSURF')
        s.levels = subsurf
        s.render_levels = subsurf
    return o


def bez(p0, p1, p2, n):
    return [Vector(p0) * (1 - t) ** 2 + Vector(p1) * 2 * t * (1 - t) + Vector(p2) * t * t for t in [i / (n - 1) for i in range(n)]]


# lower jaw: a flattened tapered loft from the hinge (inside the head) to the chin, slightly open
bm = bmesh.new()
pts = bez((0, -4.45, 4.20), (0, -5.15, 3.86), (0, -5.85, 3.80), 7)
rings = []
for i, p in enumerate(pts):
    t = i / (len(pts) - 1)
    rx, rz = 0.44 - 0.24 * t, 0.17 - 0.07 * t
    rings.append([bm.verts.new(p + Vector((math.cos(a) * rx, 0, math.sin(a) * rz))) for a in
                  [2 * math.pi * k / 8 for k in range(8)]])
for r0, r1 in zip(rings, rings[1:]):
    for k in range(8):
        bm.faces.new((r0[k], r1[k], r1[(k + 1) % 8], r0[(k + 1) % 8]))
bm.faces.new(list(reversed(rings[0])))
bm.faces.new(rings[-1])
jaw = new_obj("Dragon_Jaw", bm, M_SCALE, subsurf=2)
jaw.data.materials.append(bpy.data.materials["Dragon_Belly"])

# eyes on the side of the head, half sunk into the surface; angry brow ridge above each eye
loc, nor = surface((3.0, -4.95, 4.52), (-1, 0, 0))
eye_c = loc - nor * 0.06
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.145,
                          matrix=mathutils.Matrix.Translation(eye_c) @ mathutils.Matrix.Diagonal((0.8, 1.0, 0.85, 1.0)))
new_obj("Dragon_Eyes", bm, M_EYE, mirror=True)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0,
                          matrix=mathutils.Matrix.Translation(eye_c + Vector((-0.05, 0.03, 0.12)))
                          @ mathutils.Euler((math.radians(-18), math.radians(-25), 0)).to_matrix().to_4x4()
                          @ mathutils.Matrix.Diagonal((0.12, 0.25, 0.06, 1.0)))
new_obj("Dragon_Brow", bm, M_SCALE, mirror=True)

# horns: two big swept-back horns and a smaller lower pair (curved tapered tubes)
bm = bmesh.new()
for (p0, p1, p2, r0) in (((0.28, -4.42, 4.86), (0.42, -3.95, 5.42), (0.62, -3.15, 5.55), 0.17),
                         ((0.48, -4.25, 4.55), (0.80, -3.95, 4.72), (1.02, -3.55, 4.62), 0.10)):
    pts = bez(p0, p1, p2, 8)
    tube(bm, pts, [r0 * (1 - i / 7) ** 0.8 for i in range(8)], ring=8)
new_obj("Dragon_Horns", bm, M_HORN, mirror=True)

# teeth: small fangs along the upper jaw edge, pointing down into the open mouth
bm = bmesh.new()
for i in range(5):
    y = -5.78 + i * 0.22
    loc, nor = surface((2.0, y, 3.95 + i * 0.03), (-1, 0, 0))
    if loc is None:
        continue
    base = loc - nor * 0.03 + Vector((0, 0, -0.02))
    size = 0.07 if i else 0.10
    bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=size * 0.55, radius2=0.0, depth=size * 2.2,
                          matrix=mathutils.Matrix.Translation(base - Vector((0, 0, size * 0.9)))
                          @ mathutils.Euler((math.pi, 0, 0)).to_matrix().to_4x4())
new_obj("Dragon_Teeth", bm, M_TOOTH, mirror=True, smooth=False)

# dorsal spikes: flattened fins along the arc length of the spine, from behind the horns to the tail tip
lengths = [0.0]
for a, b in zip(SPINE, SPINE[1:]):
    lengths.append(lengths[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
bm = bmesh.new()
s = lengths[I_SKULL + 1] + 0.1
count = 0
for _ in range(60):
    if s > lengths[-1] - 0.35:
        break
    i = max(k for k in range(len(lengths) - 1) if lengths[k] <= s)
    f = (s - lengths[i]) / (lengths[i + 1] - lengths[i])
    y, z, rx, rz = spine_at(i + f)
    loc, nor = surface((0.0, y, z + 3.0), (0, 0, -1))
    if loc is not None:
        a, b = SPINE[i], SPINE[i + 1]
        tilt = math.atan2(b[1] - a[1], b[0] - a[0])  # spine slope in the y-z plane
        h = 0.18 + 0.42 * min(rz, 1.0)
        bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=h * 0.42, radius2=0.0, depth=h,
                              matrix=mathutils.Matrix.Translation(loc + Vector((0, 0.06, h * 0.32)))
                              @ mathutils.Euler((math.radians(-28) + tilt, 0, 0)).to_matrix().to_4x4()
                              @ mathutils.Matrix.Diagonal((0.38, 1.0, 1.0, 1.0)))
        count += 1
    s += 0.30 + 0.30 * min(rz, 1.0)
new_obj("Dragon_Spikes", bm, M_HORN, smooth=False)

# claws: three per foot, curved down to the ground (x > 0; mirrored)
bm = bmesh.new()
for (fx, fy) in ((0.98, -2.78), (1.12, 0.25)):
    for dx, ang in ((-0.16, -14), (0.0, 0), (0.16, 14)):
        loc, nor = surface((fx + dx, fy - 1.0, 0.13), (0, 1, 0))
        if loc is None:
            continue
        pts = bez(loc + Vector((0, 0.06, 0.02)), loc + Vector((0, -0.12, 0.02)), loc + Vector((0, -0.22, -0.11)), 5)
        rot = mathutils.Matrix.Rotation(math.radians(ang), 4, 'Z')
        c = pts[0]
        pts = [c + (rot @ (p - c)) for p in pts]
        tube(bm, pts, [0.075, 0.07, 0.055, 0.03, 0.0], ring=6)
new_obj("Dragon_Claws", bm, M_HORN, mirror=True)

# tail spade: a flat arrowhead at the tail tip
t0 = Vector((0, SPINE[-1][0] - 0.05, SPINE[-1][1]))
bm = bmesh.new()
outline = [(0, 0.85), (0.20, 0.38), (0.42, 0.05), (0.16, 0.14), (0, -0.05), (-0.16, 0.14), (-0.42, 0.05), (-0.20, 0.38)]
vs = [bm.verts.new(t0 + Vector((x, y, 0.06 * y))) for x, y in outline]
bm.faces.new(vs)
spade = new_obj("Dragon_TailSpade", bm, M_HORN)
sol = spade.modifiers.new("Solidify", 'SOLIDIFY')
sol.thickness = 0.09
sol.offset = 0.0
result = {"eye_center": [round(c, 3) for c in eye_c], "spikes": count}
