# Chunk F: render look. Procedural scales (Voronoi bump + darker back via the surface normal), translucent wing
# membrane, glowing eyes, a dusk world and a three-light rig. (Roblox only takes the base colours; this is for renders.)
def nodes_of(m):
    nt = m.node_tree
    return nt, nt.nodes, nt.links, nt.nodes["Principled BSDF"]


def scales(m, top, side, scale_size, bump):
    nt, n, l, p = nodes_of(m)
    for x in [x for x in n if x.name.startswith("STAR_")]:
        n.remove(x)
    tc = n.new("ShaderNodeTexCoord"); tc.name = "STAR_tc"
    vor = n.new("ShaderNodeTexVoronoi"); vor.name = "STAR_vor"
    vor.inputs["Scale"].default_value = scale_size
    vor.feature = 'DISTANCE_TO_EDGE'
    l.new(tc.outputs["Object"], vor.inputs["Vector"])
    bm = n.new("ShaderNodeBump"); bm.name = "STAR_bump"
    bm.inputs["Strength"].default_value = bump
    bm.inputs["Distance"].default_value = 0.02
    l.new(vor.outputs["Distance"], bm.inputs["Height"])
    l.new(bm.outputs["Normal"], p.inputs["Normal"])
    if top is not None:
        geo = n.new("ShaderNodeNewGeometry"); geo.name = "STAR_geo"
        sep = n.new("ShaderNodeSeparateXYZ"); sep.name = "STAR_sep"
        l.new(geo.outputs["Normal"], sep.inputs["Vector"])
        ramp = n.new("ShaderNodeValToRGB"); ramp.name = "STAR_ramp"
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = (*side, 1.0)
        ramp.color_ramp.elements[1].position = 0.85
        ramp.color_ramp.elements[1].color = (*top, 1.0)
        l.new(sep.outputs["Z"], ramp.inputs["Fac"])
        mix = n.new("ShaderNodeMix"); mix.name = "STAR_mix"
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs["Factor"].default_value = 1.0
        l.new(ramp.outputs["Color"], mix.inputs["A"])
        dark = n.new("ShaderNodeMapRange"); dark.name = "STAR_dark"
        dark.inputs["From Min"].default_value = 0.0
        dark.inputs["From Max"].default_value = 0.12
        dark.inputs["To Min"].default_value = 0.45
        dark.inputs["To Max"].default_value = 1.0
        l.new(vor.outputs["Distance"], dark.inputs["Value"])
        l.new(dark.outputs["Result"], mix.inputs["B"])
        l.new(mix.outputs["Result"], p.inputs["Base Color"])


M = bpy.data.materials
scales(M["Dragon_Scales"], (0.03, 0.20, 0.16), (0.10, 0.42, 0.24), 12.0, 0.5)
scales(M["Dragon_Belly"], None, None, 6.0, 0.25)
scales(M["Dragon_BellyBand"], None, None, 6.0, 0.25)
M["Dragon_Scales"].node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.6

# wing membrane: principled + translucent mix, slightly see-through
wm = M["Dragon_Membrane"]
nt, n, l, p = nodes_of(wm)
for x in [x for x in n if x.name.startswith("STAR_")]:
    n.remove(x)
out = n["Material Output"]
tr = n.new("ShaderNodeBsdfTranslucent"); tr.name = "STAR_tr"
tr.inputs["Color"].default_value = (1.0, 0.35, 0.12, 1.0)
mixs = n.new("ShaderNodeMixShader"); mixs.name = "STAR_mixs"
mixs.inputs["Fac"].default_value = 0.45
l.new(p.outputs["BSDF"], mixs.inputs[1])
l.new(tr.outputs["BSDF"], mixs.inputs[2])
l.new(mixs.outputs["Shader"], out.inputs["Surface"])
p.inputs["Alpha"].default_value = 0.93
wm.use_backface_culling = False

M["Dragon_Eye"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.5
M["Dragon_Eye"].node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1.0, 0.55, 0.05, 1.0)
M["Dragon_Horn"].node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.3

# world: dusk gradient-ish flat colour (the camera framing comes from the tool)
world = bpy.context.scene.world or bpy.data.worlds.new("Dragon_World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.035, 0.045, 0.075, 1.0)
bg.inputs["Strength"].default_value = 1.0

# lights: warm key, cool rim from behind (shows the membranes), soft fill
for o in [x for x in bpy.data.objects if x.type == 'LIGHT']:
    bpy.data.objects.remove(o)


def light(name, kind, energy, color, rot, loc=(0, 0, 0), size=None):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    d.color = color
    if size is not None:
        if kind == 'SUN':
            d.angle = size
        else:
            d.size = size
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]
    o.location = loc
    return o


light("Key_Sun", 'SUN', 4.0, (1.0, 0.86, 0.68), (52, 0, -35), size=math.radians(4))
light("Rim_Sun", 'SUN', 6.0, (0.55, 0.75, 1.0), (115, 0, 160), size=math.radians(6))
light("Fill_Area", 'AREA', 900.0, (0.8, 0.85, 1.0), (70, 0, 40), loc=(14, -14, 9), size=8.0)
sc = bpy.context.scene
sc.view_settings.view_transform = 'AgX'
try:
    sc.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass
sc.frame_set(13)
result = {"lights": [o.name for o in bpy.data.objects if o.type == 'LIGHT'], "world": world.name}
