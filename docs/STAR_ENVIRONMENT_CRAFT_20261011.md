# STAR Environment Craft — reference-to-Roblox production research & executable previews

**Research:** 2026-10-11. **Status:** new offline reference diagnostics + authoring previews; not a finished 3D scene generator or autonomous Blender/Studio editor. This work extends existing visual-craft research and Studio guards rather than bypassing them.

## What the reference images actually teach

The owner provided twenty images spanning markedly different visual grammars. A model that simply chooses a color palette cannot reproduce them. The scene-building brief must capture **style family, geometry language, material response, shot composition, atmospheric depth, lighting motivation, environmental animation, interaction/UI, device limits and provenance** separately.

| Visible reference family | Reusable craft decisions | Common failure to detect | Starter preset |
| --- | --- | --- | --- |
| Snowy Japanese shrine, torii and lanterns | Receding gateways, white-on-gray foliage, thin warm red accents, snow cards and mist | Flat fog erases silhouette layers; uniform snow on vertical surfaces | winter-shrine |
| Lava-lit stone catacombs | Repeating arches with true voussoir profiles, rock breakage, cool shadow fill, warm local bounce | Flat emissive orange everywhere; floor debris blocking gameplay | volcanic-crypt |
| Egyptian column hall | Hieroglyphic trim sheets, long axial spaces, tall piers, dusty directional sun shafts | Lighting ignores window location; random/repeating text decals | sandstone-temple |
| Gothic magical library | Ribbed windows, library modular kits, secondary prop clusters, cool windows against warm candles | Excessively strong sunbeam fog, unreadable books, tile seams | gothic-library |
| Moonlit cottage/bridge and magical woodland | Canopy silhouettes, grasses with clear walkable ground, glowing tiny props, bright focal cottage | Identical trees, grass covering pathways, featureless blue wash | moonlit-forest |
| White bark trees with red leaves | Winding tree forms, directional framing, complementaries, far mist | Flat cutout bark or leaf planes clipping through trunks | crimson-snow |
| Classic bright blocky simulator UI | Bold native HUD, save slots, usable typography and interactive state | Screenshot pasted over GUI, labels colliding, tiny hit targets | UI skill pack |
| Midnight red barn and timber interior | Correct timber joinery, red siding, crates, hay, warm lamps, negative space | Floating trusses, mismatch between interior/exterior layout, fog through walls | misty-farm |
| Low-poly monochrome ruins | Silhouette-first faceting, graphic value shapes, economical geometry and heavy depth cues | Generic parts instead of intentional form language | custom |
| Bright city boulevard and pastel shopping street | Cohesive architectural period, street furniture, warm sun and sightlines | Cloned buildings and oversized road props | sunset-city |
| Dark abandoned urban street | Cracked pavement, believable barricades, narrative clutter, low-key lighting | Over-dark navigation and meaningless debris | ashfall-city |
| Cyan crystal wasteland | Hand-authored focal crystals, emissive accents, rock kits, bounded bloom | All-glowing scene with no value structure | crystal-wastes |
| Firelit medieval hall, winter settlement, longship port, golden tomb | Timbers/carved panels, snow hierarchy, landmarks, controlled fire | Invalid construction, repetitive lamps, poor traversal | custom |

**Do not treat the twenty user-provided pictures as an asset library.** No source meshes, rigs, PBR maps, scene cameras or source licenses are available. No reference screenshots are committed into this public repository.

## The actual production method

1. **Rights + source record.** Label each asset user-owned, licensed, reference-only or unknown; record exact URL, author, license text/date and source digest. Unknown license does not grant copying, hosting or training permission.
2. **Art brief.** Record camera projection/FOV, foreground/middle/background, 3×3 luminance map, palette, architectural grid, silhouettes, motifs, gameplay clearances and player scale. Distinguish observations from inferred parts.
3. **Greybox first.** Validate traversal, frame, cover, navigation and visibility at correct scale. Establish modular architecture, pivots, asset kits and deliberately controlled repetition before decorative dressing.
4. **Model / bake.** Blender high-to-low where warranted, correct normals, UVs, trims and texture density. FBX/glTF or OBJ through the Studio importer; inspect failures. Use SurfaceAppearance albedo/normal/roughness/metallic channels when supported; match texture types to hardware budgets.
5. **Lighting.** Determine physical sources before adjusting exposure: skylight, ambient, time, shadows, Atmosphere, local practical lights, color correction, restrained bloom and optional effect-based sun shafts. Atmosphere is not an unrestricted volumetric ray-tracer. Lighting.Technology is not generally script-writable.
6. **Organic motion.** GlobalWind automatically influences terrain grass and clouds, not all custom trees. For custom trees, authored skinned mesh Bone.Transform gives client-side weighted sway with stable phase variation, quality caps, distance culling and state resets; protect against Animator bone conflicts. Wind-following particles require drag and WindAffectsDrag.
7. **VFX.** Dust, embers, snow, debris, magic motes and sparks use ParticleEmitter with appropriate Attachments; beams connect two attachments, trails collect motion history. Layer start/impact/aftermath, limit overdraw, and verify mobile cost.
8. **Native UI.** Components/tokens, spacing, input state and gamepad/touch, text scaling, UIListLayout, constraints, 9-slice and Style Editor. A screenshot cannot replace a functional GUI; test focus, safe areas, readability and reduced-motion.
9. **Render/critique.** Capture matched camera, aspect, light/time and graphics quality; run offline inspect/compare, then inspect multi-view geometry, material appearance, motion, collisions and interaction. Lower image error alone never certifies likeness or scene quality.
10. **QA/learning.** Measure memory, script time, rendering and streaming on representative devices. Record reviewed fixes and evidence in existing STAR lessons/training pipelines. Human approvals remain required for live Studio mutation, publishing and training-data promotion.

## Offline commands

The module uses Pillow, local still images and no network, GPU or Studio credentials.

~~~bash
python -m star.environment_craft inspect path/to/reference.png --out scene_reference.json
python -m star.environment_craft compare path/to/reference.png path/to/studio_screenshot.png --out render_review.json
python -m star.environment_craft lighting winter-shrine --out lighting_review.luau
python -m star.environment_craft foliage --quality medium --out foliage_review.client.luau
python -m star.environment_craft vfx falling-snow --out snow_review.luau
~~~

- Inspect: source SHA256, image dimensions, six-color palette, mean RGB, 3×3 luminance grid and coarse edge-density proxy.
- Compare: per-pixel RGB MAE, luminance, grid and detail change, with context-specific review suggestions. Rejects camera aspect differences >3%. Not semantic image similarity, segmentation, photogrammetry or exact geometry analysis.
- Lighting: ten artist-authored starting points using Atmosphere, ColorCorrection and Bloom; not measured values extracted from the source artist scene. No auto execution.
- Ambient VFX: three review-only ParticleEmitter templates for falling snow, floating embers and dust motes. Create a STAR_FX_Anchor yourself; add approved textures and profile transparency/overdraw before use.
- Foliage: preview-only client LocalScript for tagged static Model trees. Tag as STAR_WindTree; weight manually rigged Bone descendants with a WindWeight (0..1). Low/medium/high caps: 128/256/512 participating bones, 10/15/20 Hz, 100/160/220 stud cull distance. Budgets require device benchmarks.
- Safety: accepts local PNG/JPEG/WebP at most 20 MB and 32 megapixels, rejects symlinks and overwrite targets. No DataModel reads/writes, network, model weight changes or tool grants.

The roblox-environment-art skill pack is bundled but opt-in. Enable only for tests with STAR_SKILL_PACKS=roblox-environment-art; it must clear the existing eval gate before default rollout.

## Primary engine documentation: confirmed public references

| Subject | Official documentation |
| --- | --- |
| Environmental art curriculum | https://create.roblox.com/docs/tutorials/curriculums/environmental-art |
| Modular environments | https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments |
| Global Lighting | https://create.roblox.com/docs/environment/lighting |
| Atmosphere | https://create.roblox.com/docs/environment/atmosphere |
| Post effects | https://create.roblox.com/docs/environment/post-processing-effects |
| Global wind and affected objects | https://create.roblox.com/docs/environment/global-wind |
| Bone transform and replication | https://create.roblox.com/docs/reference/engine/classes/Bone/Transform |
| VFX overview / Beams / Trails | https://create.roblox.com/docs/effects ; https://create.roblox.com/docs/effects/beams ; https://create.roblox.com/docs/effects/trails |
| Blender/import | https://create.roblox.com/docs/art/blender ; https://create.roblox.com/docs/studio/importer |
| PBR | https://create.roblox.com/docs/art/modeling/surface-appearance |
| UI style/layout/constraints/9slice | https://create.roblox.com/docs/ui/styling/editor ; https://create.roblox.com/docs/ui/list-flex-layouts ; https://create.roblox.com/docs/ui/size-modifiers ; https://create.roblox.com/docs/ui/9-slice |
| Animation editor and events | https://create.roblox.com/docs/animation/editor ; https://create.roblox.com/docs/animation/events |
| Official Studio MCP | https://create.roblox.com/docs/studio/mcp |
| Performance / MicroProfiler | https://create.roblox.com/docs/performance-optimization/improve ; https://create.roblox.com/docs/performance-optimization/microprofiler/use-microprofiler |
| Creator Store | https://create.roblox.com/docs/production/creator-store |

Re-verify specific engine property names with the currently installed Roblox Studio before automating writes; platform APIs evolve.

## Free asset/tool research: evaluate before importing

- https://www.blender.org/ — free open-source meshes, baking, rigging, geometry nodes and Python (procedural shaders require conversion or texture baking).
- https://polyhaven.com/license — CC0 materials/models/HDRIs; import capability and texture budgets differ from Blender.
- https://ambientcg.com/ and https://docs.ambientcg.com/license/ — CC0 PBR materials; verify packaging.
- https://kenney.nl/assets — low-poly/game UI packs; read exact asset pack license.
- https://www.materialmaker.org/ — material synthesis and export to texture maps.
- https://krita.org/ and https://inkscape.org/ — paint textures and vector UI assets.
- https://penpot.app/ — design tokens, prototype/editable UI mockups, then implement as native Roblox GUI.

Downloading an asset is not proof of reuse rights. Source-specific licensing/provenance must be attached to the project.

## Owner's fifteen artist references: access audit (2026-10-11)

These portfolios are art-direction sources only, not source asset or training grants.

| Submitted URL | Research observation |
| --- | --- |
| https://ricky557-portfolio.netlify.app/ | Readable; artist describes 3D modeling, lighting, terrain, optimization, consultation/concept/development workflow. |
| https://www.artstation.com/builderoblox | Artist heading resolves, individual projects not consistently accessible. |
| https://www.artstation.com/artwork/P6DZl1 | Content not retrievable; unknown asset details. |
| https://arioflexport.framer.website/works | Content not retrievable. |
| https://www.hassanmusaddaq.com/work | Gallery and clean UI/UX portfolio description readable; work pieces poorly described in accessible text. |
| https://maryam-portfolio.framer.website/work | UI image gallery readable, limited image-specific metadata. |
| https://x.com/_frostoriginal | Not retrievable. |
| https://ellaluxe.artstation.com/projects | Not retrievable. |
| https://www.artstation.com/artwork/eglKQ6 | Not retrievable. |
| https://x.com/albertdevv | Not retrievable. |
| https://www.artstation.com/artwork/lGPVw5 | Not retrievable. |
| https://x.com/SUPER7208/status/2104930581008289928 | Not retrievable; the post's content/existence is unverified. |
| https://x.com/curxed_benimaru | Not retrievable. |
| https://www.artstation.com/riptide3ds/albums/14169707 | Album not retrievable. |
| https://www.artstation.com/kedson | Artist landing page resolves but work details are inaccessible. |

**Additional Roblox art examples, for reference studies, not redistribution:** https://www.artstation.com/artwork/wO80d9 (stylized lobby), https://www.artstation.com/artwork/1L4kq3 (future Tokyo), https://www.artstation.com/artwork/149Q5L (low-poly haunted island), https://maxflubber.artstation.com/ , https://hovenx9.artstation.com/ . Exact techniques still require breakdown/tutorial sources and permission where applicable.

## Next engineering stages (not yet built)

- **B: Studio inspection.** Read-only discovery of the authorized scene graph, lighting instances, environment inventory, material/mesh counts, with camera-locked render captures. Existing scope and journal checks apply to every write.
- **C: Reusable Blender asset workflow.** Modular scene specification, explicit trusted Blender tool/script allowlist, mesh/rig provenance manifests, validation of UVs/normals/texture rights and Roblox Importer errors. No unrestricted generator-executed Python.
- **D: Stronger visual benchmarks.** Artist-approved golden camera views; perceptual/semantic metrics plus collision, navigation, object counts and video/temporal motion. Avoid teaching a model to game a palette score.
- **E: Review-led self-improvement.** Human-reviewed, rights-confirmed success/failure artifacts, per-skill benchmark gates, holdout evaluation and ability to roll back. Never secretly change the policy engine, licenses, source citations or test goldens.

## Evidence and acceptance

Local synthetic-fixture tests were run on the code preview and image-statistics functions. This is **not proof of real Studio or Blender rendering**, accurate resemblance, animation performance or 1:1 results. The standalone code and any future use of generated Luau still require reviewed Studio/device acceptance; no Roblox API key, account access or place changes were used in this work.
