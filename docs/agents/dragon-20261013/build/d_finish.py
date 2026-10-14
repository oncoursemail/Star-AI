USE_BOOLEAN = False
# Chunk D: make it game-ready. Apply modifiers, paint the belly plates on the real faces, fuse jaw + brows into
# the body (exact boolean union: no hidden intersecting parts), join same-material parts, put the origin at the
# base (centre of the footprint, z = 0), apply transforms, clean names.
M = bpy.data.materials


def apply_all(o):
    activate(o)
    for mod in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)


body = bpy.data.objects["Dragon_Body"]
jaw = bpy.data.objects["Dragon_Jaw"]
for o in [x for x in bpy.data.objects if x.type == 'MESH']:
    apply_all(o)

# lower jaw underside gets the belly colour before it is fused
for poly in jaw.data.polygons:
    if poly.normal.z < -0.35:
        poly.material_index = 1

# belly plates on the body: faces whose normal points to the spine's underside, close to the spine, banded by arc length
lengths = [0.0]
for a, b in zip(SPINE, SPINE[1:]):
    lengths.append(lengths[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
segs = []
for i, (a, b) in enumerate(zip(SPINE, SPINE[1:])):
    pa, pb = Vector((0, a[0], a[1])), Vector((0, b[0], b[1]))
    segs.append((pa, pb, i))
down = Vector((0, 0, -1))
belly = bands = 0
for poly in body.data.polygons:
    c, n = poly.center, poly.normal
    best = None
    for pa, pb, i in segs:
        d = pb - pa
        t = max(0.0, min(1.0, (Vector((0, c.y, c.z)) - pa).dot(d) / d.length_squared))
        q = pa + d * t
        dist = (Vector((0, c.y, c.z)) - q).length
        if best is None or dist < best[0]:
            best = (dist, i, t, d.normalized())
    dist, i, t, tan = best
    y, z, rx, rz = spine_at(i + t)
    bdir = (down - tan * down.dot(tan)).normalized()
    if i < I_SKULL - 1:          # snout: leave the head green, the jaw carries the light colour
        continue
    rel = Vector((0, c.y, c.z)) - Vector((0, y, z))
    side = rel.dot(bdir) / max(rel.length, 1e-6)
    if n.dot(bdir) > 0.2 and side > 0.55 and abs(c.x) < 0.55 * rx and dist < 1.2 * rz:
        s = lengths[i] + t * (lengths[i + 1] - lengths[i])
        phase = (s % 0.5) / 0.5
        poly.material_index = 2 if phase < 0.2 else 1
        belly += 1
        bands += phase < 0.2

# fuse jaw and brows into the body
fused = []
for name in ("Dragon_Jaw", "Dragon_Brow"):
    if not USE_BOOLEAN:
        break
    activate(body)
    mod = body.modifiers.new("Union_" + name, 'BOOLEAN')
    mod.operation = 'UNION'
    mod.solver = 'EXACT'
    mod.object = bpy.data.objects[name]
    mod.material_mode = 'TRANSFER'
    mod.use_self = True
    mod.use_hole_tolerant = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(bpy.data.objects[name])
    fused.append(name)


def join(names, new_name):
    objs = [bpy.data.objects[n] for n in names if bpy.data.objects.get(n)]
    activate(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = new_name
    o.data.name = new_name
    return o


if not USE_BOOLEAN:
    join(["Dragon_Body", "Dragon_Jaw", "Dragon_Brow"], "Dragon_Body")
join(["Dragon_Horns", "Dragon_Spikes", "Dragon_Claws", "Dragon_TailSpade"], "Dragon_HornsClaws")

# merge accidental duplicate materials created by the boolean transfer, then tidy slots
for o in [x for x in bpy.data.objects if x.type == 'MESH']:
    activate(o)
    bpy.ops.object.material_slot_remove_unused()

# origin at the base: centre of the footprint at z = 0
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
meshes = [x for x in bpy.data.objects if x.type == 'MESH']
for o in meshes:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        lo = Vector((min(lo[k], w[k]) for k in range(3)))
        hi = Vector((max(hi[k], w[k]) for k in range(3)))
shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
for o in meshes:
    o.data.transform(mathutils.Matrix.Translation(shift))
    o.matrix_world = mathutils.Matrix.Identity(4)
    o.data.update()
bpy.context.scene.cursor.location = (0, 0, 0)
bpy.context.scene["dragon_shift"] = list(shift)
tris = {}
for o in meshes:
    o.data.calc_loop_triangles()
    tris[o.name] = len(o.data.loop_triangles)
result = {"belly_faces": belly, "band_faces": bands, "shift": [round(v, 3) for v in shift], "tris": tris,
          "size": [round(hi[k] - lo[k], 3) for k in range(3)]}
