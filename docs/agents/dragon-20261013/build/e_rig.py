# Chunk E: a small rig (Body + 3 bones per wing) with smooth wing weights, and a looping wing-flap idle (48 frames).
SH = Vector(bpy.context.scene["dragon_shift"])
WS = Vector((0.55, -1.85, 3.15)) + SH
WE = Vector((1.90, -1.05, 4.55)) + SH
WW = Vector((3.30, -1.55, 5.35)) + SH
F2 = Vector((6.60, 1.60, 4.70)) + SH
WB = Vector((0.50, 0.90, 2.85)) + SH
HAND_TIP = WW + (F2 - WW) * 0.55

old = bpy.data.objects.get("Dragon_Rig")
if old:
    bpy.data.objects.remove(old)
arm = bpy.data.armatures.new("Dragon_Rig")
rig = link("Dragon_Rig", arm)
arm.display_type = 'STICK'
rig.show_in_front = True
activate(rig)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.edit_bones
body_bone = eb.new("Body")
body_bone.head = Vector((0, -1.6, 2.3)) + SH
body_bone.tail = Vector((0, 1.0, 2.3)) + SH
body_bone.roll = 0.0
CHAIN = (("Wing_Upper", WS, WE), ("Wing_Fore", WE, WW), ("Wing_Hand", WW, HAND_TIP))
for side, sx in (("L", 1.0), ("R", -1.0)):
    parent = body_bone
    for name, h, t in CHAIN:
        b = eb.new(name + "." + side)
        b.head = Vector((h.x * sx, h.y, h.z))
        b.tail = Vector((t.x * sx, t.y, t.z))
        b.parent = parent
        b.use_connect = parent is not body_bone
        parent = b
bpy.ops.object.mode_set(mode='OBJECT')


def seg_dist(p, a, b):
    d = b - a
    t = max(0.0, min(1.0, (p - a).dot(d) / d.length_squared))
    return (p - (a + d * t)).length


def skin(o, wing):
    o.vertex_groups.clear()
    groups = {n: o.vertex_groups.new(name=n) for n in
              ["Body"] + [c[0] + "." + s for s in ("L", "R") for c in CHAIN]}
    for v in o.data.vertices:
        if not wing:
            groups["Body"].add([v.index], 1.0, 'REPLACE')
            continue
        p = v.co
        side = "L" if p.x >= 0 else "R"
        q = Vector((abs(p.x), p.y, p.z))
        d = {"Body": seg_dist(q, WS, WB) * 1.6,
             "Wing_Upper." + side: seg_dist(q, WS, WE),
             "Wing_Fore." + side: seg_dist(q, WE, WW),
             "Wing_Hand." + side: seg_dist(q, WW, HAND_TIP) * 0.8}
        w = {k: 1.0 / (x ** 4 + 1e-4) for k, x in d.items()}
        total = sum(w.values())
        for k, x in w.items():
            if x / total > 0.03:
                groups[k].add([v.index], x / total, 'REPLACE')
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    o.parent = rig


for o in [x for x in bpy.data.objects if x.type == 'MESH']:
    skin(o, o.name.startswith("Dragon_Wing"))

# animation: wings flap about the body's long axis, forearms lag a little, the body bobs on the down-stroke
activate(rig)
bpy.ops.object.mode_set(mode='POSE')
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, 48
scene.render.fps = 24
if rig.animation_data is None:
    rig.animation_data_create()
rig.animation_data.action = bpy.data.actions.new("Dragon_WingFlap")


def world_rot_local(pb, axis, angle):
    rest = pb.bone.matrix_local.to_3x3()
    r = mathutils.Matrix.Rotation(angle, 3, axis)
    return (rest.inverted() @ r @ rest).to_quaternion()


KEYS = [(1, 22.0, -8.0, 0.0), (13, 0.0, 6.0, 0.06), (25, -26.0, 14.0, 0.10), (37, 0.0, 2.0, 0.04), (49, 22.0, -8.0, 0.0)]
for frame, up, fold, bob in KEYS:
    pbb = rig.pose.bones["Body"]
    pbb.location = (0.0, 0.0, bob)
    pbb.keyframe_insert("location", frame=frame)
    for side, sx in (("L", 1.0), ("R", -1.0)):
        for name, ang in (("Wing_Upper", up), ("Wing_Fore", fold), ("Wing_Hand", fold * 0.8)):
            pb = rig.pose.bones[name + "." + side]
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = world_rot_local(pb, 'Y', math.radians(-ang * sx))
            pb.keyframe_insert("rotation_quaternion", frame=frame)
scene.frame_set(1)
bpy.ops.object.mode_set(mode='OBJECT')
result = {"bones": [b.name for b in arm.bones], "frames": [scene.frame_start, scene.frame_end]}
