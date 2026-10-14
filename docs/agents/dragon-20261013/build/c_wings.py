# Chunk C: bat wings (x > 0 half, mirrored): finger bones as tapered tubes + a scalloped, slightly billowing
# membrane built as Coons patches between the bones, given thickness by Solidify so it is visible from both sides.
M_SCALE = bpy.data.materials["Dragon_Scales"]
M_HORN = bpy.data.materials["Dragon_Horn"]
M_WING = bpy.data.materials["Dragon_Membrane"]
for name in ("Dragon_WingBones", "Dragon_WingMembrane"):
    if bpy.data.objects.get(name):
        bpy.data.objects.remove(bpy.data.objects[name])

WS = Vector((0.55, -1.85, 3.15))   # shoulder (sunk into the back)
WE = Vector((1.90, -1.05, 4.55))   # elbow
WW = Vector((3.30, -1.55, 5.35))   # wrist
WT = Vector((3.36, -1.95, 5.62))   # thumb claw tip
FINGERS = [Vector((6.30, -0.20, 6.10)), Vector((6.60, 1.60, 4.70)), Vector((5.50, 3.10, 3.40)), Vector((3.70, 3.40, 2.75))]
WB = Vector((0.50, 0.90, 2.85))    # where the trailing edge meets the back


def lerp(a, b, t):
    return a + (b - a) * t


def arm(u):  # S -> E -> W
    return lerp(WS, WE, u * 2) if u < 0.5 else lerp(WE, WW, (u - 0.5) * 2)


def coons(c0, c1, d0, d1, nu, nv, sag):
    P00, P10, P01, P11 = c0(0), c0(1), c1(0), c1(1)
    grid = []
    for j in range(nv + 1):
        v = j / nv
        row = []
        for i in range(nu + 1):
            u = i / nu
            p = ((1 - v) * c0(u) + v * c1(u) + (1 - u) * d0(v) + u * d1(v)
                 - ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 + (1 - u) * v * P01 + u * v * P11))
            p = p + Vector((0.0, 0.25, -1.0)).normalized() * sag * math.sin(math.pi * u) * math.sin(math.pi * v)
            row.append(p)
        grid.append(row)
    return grid


def scallop(a, b, depth, toward):
    def f(t):
        p = lerp(a, b, t)
        return p + (toward - p) * depth * math.sin(math.pi * t)
    return f


bm = bmesh.new()


def add_grid(grid):
    vs = [[bm.verts.new(p) for p in row] for row in grid]
    for j in range(len(vs) - 1):
        for i in range(len(vs[0]) - 1):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))


# arm panel: top = arm bones, right = 4th finger, bottom = scalloped trailing edge back to the body, left = body
F4 = FINGERS[3]
add_grid(coons(arm, scallop(WB, F4, 0.16, WW), lambda v: lerp(WS, WB, v), lambda v: lerp(WW, F4, v), 8, 6, 0.18))
# finger panels: fans from the wrist, outer edge scalloped toward the wrist
for a, b in zip(FINGERS, FINGERS[1:]):
    add_grid(coons(lambda u, a=a: lerp(WW, a, u), lambda u, b=b: lerp(WW, b, u), lambda v: WW,
                   scallop(a, b, 0.22, WW), 6, 4, 0.14))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.004)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.004)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mem = bpy.data.meshes.new("Dragon_WingMembrane")
bm.to_mesh(mem)
bm.free()
membrane = link("Dragon_WingMembrane", mem)
membrane.data.materials.append(M_WING)
for poly in membrane.data.polygons:
    poly.use_smooth = True
m = membrane.modifiers.new("Mirror", 'MIRROR')
m.use_axis[0] = True
sol = membrane.modifiers.new("Solidify", 'SOLIDIFY')
sol.thickness = 0.035
sol.offset = 0.0
sub = membrane.modifiers.new("Subdivision", 'SUBSURF')
sub.levels = 1
sub.render_levels = 1

# bones: upper arm, forearm, four fingers, thumb claw (horn material)
bm = bmesh.new()


def seg(points, r0, r1, n=5):
    pts = []
    for k in range(len(points) - 1):
        for i in range(n):
            pts.append(lerp(points[k], points[k + 1], i / n))
    pts.append(points[-1])
    tube(bm, pts, [r0 + (r1 - r0) * i / (len(pts) - 1) for i in range(len(pts))], ring=6)


seg([WS + (WS - WE).normalized() * 0.15, WE], 0.17, 0.12, n=3)
seg([WE, WW], 0.12, 0.10, n=3)
for f in FINGERS:
    seg([WW, f], 0.085, 0.0, n=4)
knob = len(bm.verts)
bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.15, matrix=mathutils.Matrix.Translation(WE))
bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.13, matrix=mathutils.Matrix.Translation(WW))
bm.faces.ensure_lookup_table()
n_bone_faces = len(bm.faces)
seg([WW, lerp(WW, WT, 0.6), WT + Vector((0, -0.05, -0.08))], 0.07, 0.0, n=3)
bm.faces.ensure_lookup_table()
claw_faces = list(range(n_bone_faces, len(bm.faces)))
bones = bpy.data.meshes.new("Dragon_WingBones")
bm.to_mesh(bones)
bm.free()
wb = link("Dragon_WingBones", bones)
wb.data.materials.append(M_SCALE)
wb.data.materials.append(M_HORN)
for poly in wb.data.polygons:
    poly.use_smooth = True
    if poly.index in claw_faces:
        poly.material_index = 1
m = wb.modifiers.new("Mirror", 'MIRROR')
m.use_axis[0] = True
sub = wb.modifiers.new("Subdivision", 'SUBSURF')
sub.levels = 1
sub.render_levels = 1
result = {"membrane_faces": len(mem.polygons), "bone_faces": len(bones.polygons)}
