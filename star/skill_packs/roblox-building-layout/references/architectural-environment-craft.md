# STAR Architectural Environment Craft — credible buildings and authored Roblox maps

Use this reference when STAR is asked to build a Roblox town, house, military base, sci-fi facility, cathedral, haunted building, lobby, city, arena, forest structure, landscape POI, dungeon, or any architecture/layout that must be visually convincing. This is **design reference material**; it does not itself install Blender, author an editable Roblox model, or prove rendering quality.

## Fundamental art-direction rule

A polished building is not a stack of cubes with window decals. Real architecture has **type, purpose, scale, structural order, circulation, foundations, facades, floor-to-floor levels, wall thickness, roof logic, material transitions and small story details**. Stylization changes proportions and abstraction, but does not excuse gaps, inconsistent construction or decorative primitives unrelated to function.

### Research and reference analysis

Before creating geometry, prepare a small evidence board with:
- Exact building purpose, climate, culture, period, intended inhabitant, gameplay use, camera distance and art style. A medieval forge, suburban house and industrial research lab cannot share one generic template.
- Front/side 3/4 silhouette references, interior reference, a floor plan, roof plan, materials, nearby structures and landscaping, annotated with source/rights.
- Architecture vocabulary. Example: cottage = overhang, porch, lintel, foundation, roof pitch, rafters, shutter, siding and framed fenestration. Industrial plant = structural grid, truss/bracing, loading bay, service pipe, vents, maintenance access and drainage.
- Material family: primary wall, secondary wall/trim, metal, glazing, roofing, ground/paving and accents. Keep a restrained palette, varied by physical material and environmental exposure rather than random colorized parts.
- Distinctive facade: entrance as focal point, repeated window rhythm, purposeful solid-to-void balance, offset of doors in structurally plausible locations and identifiable roof silhouette.
- Gameplay requirements: run/jump dimensions, occlusion, cover, routes, sightlines, chase loops, bottlenecks and spawn safety.

Quality gate 0: If the main shape cannot be recognized at 100px height in flat silhouette, polish is premature.

## Model correctly scaled from the player

Use the **actual target Roblox character** and camera as unit benchmark. R6, R15 and custom avatars differ; avoid assuming fixed player height or a magical studs-to-meters conversion. Measure avatar standing height and collision extents; allow head clearance, animation reach, camera peeking, collision and door swing clearance.

- Set a grid convention for authored kit seams, for example primary 4-stud structural increments, 1-stud detail increments, and custom offsets for purpose-built details. These are **project conventions**, not universal Roblox requirements.
- Mark floor elevation, wall thickness, doorway clear width/height, stair riser/run, handrail and roof thickness; these are deliberately chosen and tested with the actual playable rig.
- Plan entrances and axes before any heavy modeling. Doors must open into reachable circulation, stairs must connect believable levels, and upper floors need an understandable structural story.
- Always create greybox *interior and exterior* with temporary flat materials; inspect with avatar and camera from gameplay distances before meshing. See official free Roblox environmental art curriculum: https://create.roblox.com/docs/tutorials/curriculums/environmental-art .

## Reusable modular architectural kit

Make a kit specification in a text/JSON or design table, with visual sheets and consistent origin/pivot rules:
- foundation block, slab, wall straight, interior wall, exterior wall, corner in/out, support column
- half-wall, wall termination/cap, lintel, beam, arch, door opening, solid door, opening jamb, window module, sill, mullion
- floor tile, floor edge, stairs, landing, railing/post, trim, skirting/baseboard, cornice
- roof edge, ridge, pitch panel, dormer, gutter, fascia, chimney/vent, roof cap
- exposed cables, conduit, fixtures, drainage, maintenance panel as purpose-designed components.

All pieces must have consistent world axes, snapped dimensions, clean normals, UVs, nonconflicting face overlap, correct thickness, matching materials, predictable pivots and names. A kit only passes when a 3x3 construction and two irregular corners join *without holes, Z-fighting, seams or floating trims*.

The Roblox official modular environment tutorial: https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments . It uses a Modern City-style modular kit approach. Do not assume its specific kit dimensions are a requirement for the user's environment.

Use Lua `Model:PivotTo(CFrame)` for controlled placement, not dozens of per-part tweens. Native Parts are appropriate for walls/collision and some stylized geometry; **Blender mesh pieces** become valuable for crafted silhouettes, ornate trims, organically damaged walls, true sloped roofs, curved supports and detailed framing. Do not construct characters or sophisticated furniture from disconnected primitive blocks just because an AI can place them.

## Mesh/texture pipeline — editable real models, not screenshots

Primary external asset programs:
- Blender: https://www.blender.org/ ; modeling, UV, normals, pivot, silhouette, instancing, cleanup; official Blender manual https://docs.blender.org/manual/en/latest/modeling/index.html .
- Material Maker: https://www.materialmaker.org/ ; generate compatible PBR texture maps. Materials must be baked/exported appropriately; Roblox does not directly run Material Maker shader graphs.
- Krita: https://krita.org/ ; paint alpha decals, signs, authored wear and architectural trim.
- Inkscape: https://inkscape.org/ ; vector signage and ornament, rasterize or generate mesh as appropriate.
- Import via official Roblox 3D Importer: https://create.roblox.com/docs/studio/importer . Validate FBX/glTF/OBJ formats and assets against Studio's CURRENT settings and import warnings.
- For UV mesh materials use SurfaceAppearance: https://create.roblox.com/docs/art/modeling/surface-appearance .
- For repeatable native materials use MaterialVariant: https://create.roblox.com/docs/parts/materials .

**Texture sourcing**:
- Poly Haven (CC0; PBR maps, models, HDRIs): https://polyhaven.com/ and https://polyhaven.com/license .
- ambientCG (CC0 tiles, ground, wood, masonry): https://ambientcg.com/ .
- Kenney (many per-pack CC0 modular 3D assets; inspect specific pack): https://kenney.nl/assets and https://kenney.nl/support .
- Quaternius pack-specific licenses, **do not blanket classify all assets CC0**: https://quaternius.com/license.html has newer QAL; individual older pack listings may still say CC0.
- Roblox Creator Store is a source of licensed game assets, NOT automatically copyright-free or vetted: https://create.roblox.com/docs/production/creator-store . Audit scripts and permissions, do not auto-insert untrusted models.

Download provenance per asset: source URL, license URL and text, author, retrieval date, rights/redistribution status, original file hash, processed derived files, import asset ID, reviewer signoff. Reject unlicensed or unknown material, and never auto-redistribute raw third-party kits.

## Believable world building through spatial hierarchy

Start with a top-down **block plan**, even for a small building:
1. Primary place identity and silhouette: the landmark the player can recognize from far away.
2. Approach and reveal: path leading toward a clear entrance, controlled vistas, readable landmarks.
3. Grounding and context: foundation, soil contact, curb or path, drainage, adjacent vegetation/props.
4. Internal circulation: entry → transition → destination with returns/shortcuts intentionally planned for game loop.
5. Architectural repetition + controlled irregularity: windows follow a structural rhythm, but meaningful asymmetry reflects purpose.
6. Narrative dressing: items belong to spaces; e.g. chairs by desks, broken windows where an event happened, pipes leading to actual mechanical rooms.
7. Atmosphere: lighting reinforces geometry; ambient fog preserves depth, not a mask for poor building.
8. Final detail pass: selective small details at player eye height and near important interactions, not ubiquitous filler geometry.

**Do not** add floating pipes, unexplained rings, random spheres, identical symmetrical structures everywhere, light strips with no fixtures, wall stickers instead of relief, doors with no clearance, or disconnected decorative triangles. Each nonfunctional detail should still serve silhouette, storytelling, light response or material credibility.

## Lighting and ground

- Build lighting by scene purpose: window apertures bring plausible daylight, interior fixtures produce localized light, nighttime readability is planned rather than fixed by extreme bloom.
- Atmosphere https://create.roblox.com/docs/environment/atmosphere for haze and depth; evaluate how far silhouettes remain readable.
- Post effects https://create.roblox.com/docs/environment/post-processing-effects need small, purposeful values rather than neon bloom on every edge.
- Studio Terrain Editor https://create.roblox.com/docs/studio/terrain-editor for hills, coastlines, erosion and ground; use terrain/material transitions that explain drainage and walking routes.
- Vegetation should fit biome/climate/scale and avoid repeated same-angle trees; wind and atmosphere must not dominate gameplay cues.
- Use consistent soundscapes: room tone, outdoor air, machines, footsteps material and weather sound where authorized audio assets exist.

## Geometry and style QA

Evaluate a *specific* built scene, not a text description:

| Check | Pass evidence |
| --- | --- |
| Correct building typology | Annotated facade reference + matching proportions and purpose |
| Scale/circulation | Walk/playtest with target R6/R15/custom rig; door, roof, stair and navigation tests |
| Mesh fidelity | Native hierarchy, import logs, source mesh/UV files, pivots/orientations |
| Modular joins | closeups at corner/roof/door/window seams and 3x3 kit tile test |
| Structural believability | foundation, load path/beam placement, roof pitch, support pattern, thickness |
| Materials | 3-angle screenshots in bright and dark lighting; coherent roughness/normal/trim usage |
| Storytelling | logical props and wear, readable focal landmarks, no unrelated filler |
| Streaming/performance | tested on representative hardware with profiler and StreamingEnabled |
| Collision/security | walkable floor and stairs, no trapped players, unintended falls, excessive physics parts |

Minimum render reviews: top-down plan, hero angle, street-level player eye, interior entrance, interior long view, side elevation, roof corner and dusk/night. Include exact viewport, lighting, hardware and graphics quality; no false claim of actual testing.

## Scene-design anti-patterns

- **Primitive spam**: lots of unscaled parts used instead of a distinctive authored silhouette.
- **Perfectly repetitive windows**: no building purpose, floor levels, structural grids or believable variation.
- **Paper-thin walls / unsupported upper floors**: geometry lacks construction logic.
- **Generic styling collision**: medieval brick, glossy sci-fi doors and Japanese eaves without an intentional hybrid brief.
- **Skybox-dependent beauty**: attractive backdrop conceals terrible playable-level flow.
- **Texture laundering**: low-quality repeated color noise misrepresented as convincing PBR texture.
- **Oversaturation and Bloom hiding seams**: lighting hides rather than improves asset quality.
- **Fake completeness**: a still concept image or parts-in-the-air screenshot labeled as a finished building.
- **Destruction without authored states**: merely deleting a wall chunk with no fractured silhouette, debris, support effects, audio or collision update. Use a deliberate staged destruction kit when that is the intended gameplay.

## Repeatable practice assignments

1. Reproduce *one original real-world reference* as stylized Roblox entrance (not a copied protected asset): orthographic proportions, sign/roof/doorframe, four matched textures.
2. Build 12-piece modular wall kit with door, window, corners and endings; prove seam test before room assembly.
3. Build two-story playable building with purposeful furniture/interior transitions; run R6/R15 and mobile camera through it.
4. Build a scene three times with same geometry but dramatically different lighting goals (morning quiet, evening welcoming, horror night) and compare readability.
5. Create a small village/district with coherent visual language, ground routes, landmarks, and asset provenance, then profile.
6. Have an independent artist score before/after annotated screenshots for construction logic, recognizability, consistency and gameplay readability.

## Relationship to STAR's existing skill pack

The current short `roblox-building-layout/SKILL.md` contains grid snapping, rough character scale suggestions, `Model:PivotTo` and Lighting settings. This reference adds **architecture art direction, deep mesh and material creation, environmental storytelling, kit validation, scale reasoning and visual QA**, which are missing from short procedural scripting reminders.

This is a manually retrievable reference, not an auto-injected runbook. Exposing it through the model runtime or tools requires an independently reviewed change and holdout + human-evaluated Studio creation tests. Do not edit the harness or bypass `star/eval_gate.py`.
