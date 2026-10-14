# Chunk A: clean scene, materials, the skin-modifier body (half skeleton + Mirror + Skin + Subdivision).
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.actions, bpy.data.lights):
    for d in list(coll):
        coll.remove(d)

M_SCALE = mat("Dragon_Scales", (0.06, 0.32, 0.22), rough=0.45)
M_BELLY = mat("Dragon_Belly", (0.86, 0.72, 0.38), rough=0.55)
M_BAND = mat("Dragon_BellyBand", (0.62, 0.48, 0.22), rough=0.6)
M_HORN = mat("Dragon_Horn", (0.10, 0.08, 0.07), rough=0.35)
M_EYE = mat("Dragon_Eye", (1.0, 0.75, 0.1), rough=0.2, emit=6.0)
M_WING = mat("Dragon_Membrane", (0.80, 0.24, 0.09), rough=0.6, alpha=0.92)

verts, edges, radii = [], [], []


def v(x, y, z, rx, rz):
    verts.append((x, y, z))
    radii.append((rx, rz))
    return len(verts) - 1


spine_ids = [v(0.0, y, z, rx, rz) for (y, z, rx, rz) in SPINE]
edges += [(a, b) for a, b in zip(spine_ids, spine_ids[1:])]

def leg(root, pts):
    prev = root
    for p in pts:
        cur = v(*p)
        edges.append((prev, cur))
        prev = cur


# front leg from the chest, hind leg from the hips (x > 0 only; Mirror makes the other side)
leg(spine_ids[I_CHEST], [(0.86, -2.10, 1.78, 0.50, 0.54), (0.98, -1.85, 1.15, 0.34, 0.34),
                   (0.95, -2.20, 0.45, 0.25, 0.25), (0.98, -2.42, 0.20, 0.32, 0.20), (0.98, -2.78, 0.16, 0.27, 0.15)])
leg(spine_ids[I_HIPS], [(0.82, 0.75, 1.90, 0.70, 0.74), (1.12, 0.20, 1.20, 0.44, 0.44),
                    (1.12, 0.95, 0.55, 0.27, 0.27), (1.12, 0.65, 0.20, 0.32, 0.20), (1.12, 0.25, 0.16, 0.27, 0.15)])

me = bpy.data.meshes.new("Dragon_Body")
me.from_pydata(verts, edges, [])
body = link("Dragon_Body", me)
activate(body)
mir = body.modifiers.new("Mirror", 'MIRROR')
mir.use_axis[0] = True
mir.use_mirror_merge = True
mir.merge_threshold = 0.001
bpy.ops.object.modifier_add(type='SKIN')
skin = body.modifiers[-1]
skin.use_smooth_shade = True
skin.branch_smoothing = 0.6
sv = body.data.skin_vertices[0].data
for i, (rx, rz) in enumerate(radii):
    sv[i].radius = (rx, rz)
    sv[i].use_root = (i == spine_ids[I_CHEST])
sub = body.modifiers.new("Subdivision", 'SUBSURF')
sub.levels = 2
sub.render_levels = 2
body.data.materials.append(M_SCALE)
body.data.materials.append(M_BELLY)
body.data.materials.append(M_BAND)
result = {"body_verts": len(verts), "edges": len(edges)}
