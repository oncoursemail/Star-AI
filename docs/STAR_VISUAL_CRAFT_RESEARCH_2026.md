# STAR Visual Craft Research — VFX, animation, native UI, architectural environments

Research date: 2026-10-11. Branch base: star/claude-integration-20261010 (PR #40). This is **reviewable reference material**, not proof that STAR has built or rendered any effect, scene, animation or interface. No permissions, automatic agent actions, model weights, runtime routing, or evaluation fixtures are changed.

## Goals and non-goals

STAR should be able to take a user-approved visual reference, analyze it at useful timestamps and angles, plan a deliberate editable implementation, choose only licensed source assets, generate proper meshes/textures/keyframes/native UI/Luau, test in an authorized disposable Studio place, and visibly self-critique before asking for approval. Do not promise "perfect", "AAA", "identical", "safe", or "optimized" without measurements and artist review.

Five separate capabilities are needed: (1) **art direction** (reference, silhouette, composition, material vocabulary), (2) **asset construction** (Blender, image editors, keyframe/mesh sources), (3) **engine authoring** (Studio objects and Luau, not screenshot substitution), (4) **rendered QA** (screenshots and filmed sequences, rig checks, device checks), (5) **licensing/security** (source provenance, unknown licenses quarantined, code inspection).

## Core verified Roblox resources

| Discipline | Primary documentation | Main lesson |
| --- | --- | --- |
| Effects | https://create.roblox.com/docs/effects | Use the right native primitive and attachment topology. |
| Particles and flipbooks | https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter | Emitter rate, lifetime, particle layout, one-shot Emit, color/size curves. |
| Beams | https://create.roblox.com/docs/effects/beams | Textured curved strip between two attachments; different viewpoints matter. |
| Trails | https://create.roblox.com/docs/effects/trails | Motion history between two attachments; tune lifetime and transparency. |
| Animation | https://create.roblox.com/docs/animation | Rig animation, events, IK and motion systems. |
| Animation Editor | https://create.roblox.com/docs/animation/editor | Rig-specific keyframes, clip priorities and authoring. |
| Curve Editor | https://create.roblox.com/docs/animation/curve-editor | Tangents, interpolation, easing and keyframe control. |
| Animation Graph | https://create.roblox.com/docs/animation/graph-editor | State transition/blend graphs; check current Studio support before using. |
| Animation events | https://create.roblox.com/docs/animation/events | Synchronize markers and runtime sound/VFX to authored clips. |
| Animation capture | https://create.roblox.com/docs/animation/capture | Video/face capture when available; restrictions and rig requirements. |
| AnimationTrack | https://create.roblox.com/docs/reference/engine/classes/AnimationTrack | Crossfade priorities, weights and speed. |
| IK | https://create.roblox.com/docs/reference/engine/classes/IKControl | Position, Transform, LookAt and blend strength. |
| UI | https://create.roblox.com/docs/ui | Native editable GUI objects and UI hierarchy. |
| UI list/flex | https://create.roblox.com/docs/ui/list-flex-layouts | Responsive container-based layout. |
| UI constraints | https://create.roblox.com/docs/ui/size-modifiers | Minimum/maximum dimensions and aspect ratios. |
| Style Editor | https://create.roblox.com/docs/ui/styling/editor | Native stylesheets, tokens and themes. |
| Adaptive layout | https://create.roblox.com/docs/production/publishing/adaptive-design | Touch, keyboard, gamepad and different screens. |
| Accessibility | https://create.roblox.com/docs/production/publishing/accessibility | PreferredTextSize, reduced motion, color and sound redundancy. |
| Architectural kit | https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments | Reusable, grid-aligned, coherent building kits. |
| Environment art curriculum | https://create.roblox.com/docs/tutorials/curriculums/environmental-art | Greybox, polish, asset library, construction, optimization. |
| Importer | https://create.roblox.com/docs/studio/importer | Import supported OBJ/FBX/glTF meshes, textures, rigs and animations. |
| PBR / mesh materials | https://create.roblox.com/docs/art/modeling/surface-appearance | SurfaceAppearance on UV meshes. |
| Tile materials | https://create.roblox.com/docs/parts/materials | MaterialVariant for reusable tileable parts/terrain. |
| Lighting | https://create.roblox.com/docs/environment | Atmosphere, sources, mood and environment. |
| Post effects | https://create.roblox.com/docs/environment/post-processing-effects | Roblox-approved post effects; no invented custom GPU shader API. |
| Performance | https://create.roblox.com/docs/performance-optimization/design | Device budgets, transparency overdraw, duplication, streaming. |
| Store | https://create.roblox.com/docs/production/creator-store | Asset availability, permissions and rights. |
| Third-party security | https://create.roblox.com/docs/scripting/security/third-party-vulnerabilities | Untrusted models/scripts can hide malicious behavior. |
| Studio MCP | https://create.roblox.com/docs/studio/mcp | Actual available tool list and guarded Studio operations. |

## Free/open production tooling (tool suitability; no installation claim)

- **Roblox Studio** — native Animation Editor, Curve Editor, rig tools, Style Editor, Terrain Editor, Asset Manager, Creator Store, Device Emulator, MicroProfiler. Most direct validation is here; availability can depend on feature rollout.
- **Blender** — https://www.blender.org/ — free open-source modeling, rigging, UV unwrapping, animation, Python and geometry nodes. Blender's procedural materials are NOT automatically Roblox shaders: bake compatible textures and inspect import.
- **Blender Rigify** — https://docs.blender.org/manual/en/latest/addons/rigging/rigify/ — rig authoring helper; exported skeleton must be tested against target Roblox rig.
- **Material Maker** — https://www.materialmaker.org/ — open-source node-based procedural PBR material creation; export compatible texture maps, not its runtime shader graph.
- **Krita** — https://krita.org/ — free image editor useful for concept paintovers, alpha textures, flipbook frames.
- **Inkscape** — https://inkscape.org/ — open-source vector UI icon/panel asset creation; export raster images acceptable to Studio.
- **Penpot** — https://penpot.app/ — free/open source component-oriented UI prototypes.
- **Figma** — https://www.figma.com/ — design systems and prototyping; free tier has limits. Do not treat an exported PNG as interactive Roblox UI.
- **FFmpeg** — https://ffmpeg.org/ — bounded offline sampling, frame extraction, cuts and spritesheet prep. Uploaded/reference footage must be authorized.
- **Roblox VFX Studio plugin** — https://create.roblox.com/store/asset/135581141962270/vfx — Creator Store listing shows Get Plugin (review ownership, version, scripts, and safety before use; do not imply tool automation API).
- **React Luau** — https://github.com/Roblox/react-lua — component library concept. The older Roact repository https://github.com/Roblox/roact explicitly says deprecated; do not recommend Roact as a new default without reviewing ecosystem.
- **Lucide** — https://lucide.dev/ — icon design references and SVG; currently ISC license with embedded Feather-derived MIT notices; keep applicable notices when redistributing files.
- **Roblox Studio Importer** — https://create.roblox.com/docs/studio/importer — first choice for previewing imported geometry and catching warnings.

## Free assets, licenses and compatibility

**Verified CC0 libraries**:
- Poly Haven: https://polyhaven.com/ (models, HDRIs, PBR), license https://polyhaven.com/license .
- ambientCG: https://ambientcg.com/ (tileable PBR, some meshes/HDRIs), site explicitly states CC0 even commercially.
- Kenney individual asset pages: https://kenney.nl/assets ; licensing FAQ https://kenney.nl/support (individual packs and standalone downloadable assets are CC0; optional All-in-1 bundle is paid).
- OpenGameArt individual CC0 selections only: https://opengameart.org/content/animated-particle-effects-1 (a 1024², 8x8 sheet); https://opengameart.org/content/light-magic-effect ; https://opengameart.org/content/nature-magic-effect . The site itself hosts other licenses, so inspect each item.
- Quaternius Universal Animation Library standard: https://quaternius.itch.io/universal-animation-library says CC0 and name-your-price free Standard; the Pro and Source packages have prices. Retargeting is required for the actual Roblox skeleton.

**License cautions**:
- Quaternius currently advertises the *Quaternius Asset License (QAL) v1.0*, dated 2026-08-28, https://quaternius.com/license.html . It allows free/commercial incorporation in products but prohibits raw-asset redistribution. Some individual older packs advertise CC0. Record exact pack, URL, acquisition date, and operative license; do not blanket-label all Quaternius downloads CC0.
- Adobe Mixamo: https://www.mixamo.com/ ; Adobe FAQ https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html states free with Adobe ID and games allowed. Adobe's licensing explanation forbids reselling/redistributing raw animation sets and using Mixamo content to train ML models: https://community.adobe.com/questions-696/mixamo-faq-licensing-royalties-ownership-eula-and-tos-589400 . Retarget FBX motions before import, verify feet and hand grip, never assume direct R6 compatibility.
- Roblox Creator Store assets are not public-domain by default. Inspect item permissions and dependencies, and audit any embedded Lua/ModuleScript on a non-production place.
- Concept image references and real architecture photos may guide original work but are not redistributable stock textures or training data by default.

Asset manifest schema recommendation (per acquisition): source_url, asset_name, author, acquired_at, license_name, license_url, attribution_text, allowed_game_incorporation, allowed_redistribution, allowed_ml_training (nullable), file_sha256, approved_by, import_status, version. Unknown or ambiguous license remains pending review; never auto-download/extract/code-import arbitrary storefront packages.

## The four authoring recipes

### A. Layered cinematic VFX

1. Reference brief: action purpose, target platform, frame range, approved style, palette, duration, rig, camera and exclusions. Observe footage at meaningful short intervals and cut boundaries, label observed vs inferred.
2. A timed shot sheet: windup → buildup → focal release → impact → dissipation. Create silhouette readability and a focal point before adding particles.
3. Author 3–8 conceptual layers: primary textured curved beam/mesh, supporting emitter flipbooks, fast sharp accents, delayed debris/smoke, impact light, camera/FOV cue and sound.
4. Bake transparent textures and authored mesh silhouettes in external software. Import through Studio with asset IDs and provenance. Do not rely on unsupported arbitrary runtime pixel shaders.
5. Synchronize to named AnimationTrack markers; keep server-authoritative damage and client visual timing distinct. Validate remote inputs on the server; never compute damage from particles.
6. Run a disposable Studio playtest, review front/back/side views, multiple distances and camera tracking; check marker timing, particle cleanup, audio sync and simultaneous effects.
7. Profile mobile/desktop and low/high graphics settings. Prefer fewer well-chosen particles to transparent full-screen stacks. Fix the highest measured costs.

### B. Professional character animation

1. Character contract: R6, R15, skinned custom rig, or animator-specific skeleton; exact required attachments and weapons. Real rigs, no fake block-character substitutes.
2. Pose thumbnails: starting silhouette, anticipation, action extreme, contact, overshoot, recovery. Use physically legible center-of-mass and intentional arcs; distinguish stylized animation from realism.
3. Rig authoring: use Studio Editor, curves and verified markers; or Blender with IK/FK controls and retargeted baked export. Verify export orientation, bone names, animation ownership and version.
4. Playback: Animator:LoadAnimation; explicit priority; reusable track; cancellation/respawn cleanup; cross-fades. Animation markers trigger display events and allow measured sync checks.
5. Inspect a frame-by-frame contact sheet for foot skating, pops, intersecting limbs, prop offsets, missing poses, abrupt looping and camera clipping.
6. Preview in actual movement and multiplayer contexts, not an isolated static viewport alone.

### C. Native UI visual design

1. Design brief before code: gameplay action priority, platform set, approved image, typography/color tokens, icon family and forbidden motifs.
2. Low-fidelity wireframe only for hierarchy, then a reference-matched component specification (measured margins/padding, typographic scale, color/contrast, radius, stroke and hover).
3. Use genuine ScreenGui hierarchy: frames/labels/buttons, list/flex/grid, UIPadding, constraints, activated actions, focus order; never flatten functional screen into a single picture.
4. For scalable themes, prefer native Style Editor tokens, style rules and themes where appropriate; one source of truth, not a different color table in every script.
5. Test 16:9 desktop, mobile portrait/landscape and gamepad focus. Respect GuiService.ReducedMotionEnabled, PreferredTextSize and safe areas. Readability and no clipping outrank decorative animation.
6. Compare with approved reference by measured geometry and designer inspection, not only image similarity percentage. Recheck after localization and content changes.

### D. Credible architectural world building

1. Choose architectural typology with references and structural logic: where load, circulation, entrances, windows, roofs, stairs and service routes make sense. Determine Roblox scale from actual playable rig dimensions.
2. **Greybox** floor plan and elevations before detailing. Mark gameplay paths, landmarks, visibility, access and facade proportions. Do not call greybox the finished art.
3. Build a modular kit with consistent units, pivots and thickness: wall, corner, doorframe, window, trim, roof edge, stair, railing, foundation, intersection and endcap pieces. Match real structural support and fenestration.
4. Model distinctive silhouettes and bespoke highlights in Blender, not uniform cube stacks or filler spheres. Establish coherent art direction and a controlled material/trim-sheet palette. Apply PBR only where style warrants it.
5. Dress by narrative logic and scene hierarchy: essential props first, wear/dirt only where physically plausible, believable vegetation and lighting, negative space, useful vistas and purposeful clutter.
6. Test doors, stairs, camera routes, collision, occlusion, streaming and per-scene budget across target devices.
7. Review from the player's eyes: scale, sightlines and visual identity. Reject holes, snapped gaps, paper-thin walls, roof intersections and decorative geometry without purpose.

## Proposed quality gates (human-oriented rubrics, not a magical AI judge)

Use 0–4 for each dimension, with evidence attached; 4 = verified high standard in real gameplay, 0 = blocked/missing. Quality is project-specific and cannot be measured entirely by CLIP/SSIM.

| Deliverable | Dimensions to assess |
| --- | --- |
| VFX | Silhouette/readability, staged timing, compositing, camera/animation sync, lifecycle, device performance |
| Animation | Pose clarity, timing/easing, arc and weight, rig safety, contacts/foot drift, blending and cleanup |
| UI | Reference fidelity, hierarchy, alignment and text overflow, responsive layout, focus/accessibility, functional states |
| Architecture | Typology/proportion, believable construction, modular join quality, material discipline, storytelling, navigation/performance |

**Hard stop conditions**: inaccessible gameplay actions; persistent connection/asset leaks; source or ownership violations; unknown animation rigs; avatar props floating off the hand; unwanted neon/shape spam contradicting the approved style; GUI text overlapping icons; untested live execution claimed as success.

Visual baselines: screenshot dimensions+viewport+DPI+graphics quality, three camera angles, render snapshots at named marker timestamps, art-director annotated differences, test device, per-scene memory and frame time. Store examples only with owner permission.

## STAR-specific feasibility and measured current limits

Inspected on branch star/claude-integration-20261010:
- star/skill_packs/__init__.py chooses at most one short guide in relevant Roblox turns. Current evaluation-gated default packs include roblox-animation-craft, roblox-vfx and roblox-building-layout; many alternatives ship but are off by default. Adding reference documents does **not** itself turn them into runtime instructions.
- docs/evals.md reports baseline creation-v1 **11/23**, old evaluated v2 **18/34**, and reports limited logic/API/citation tests, **not rendered visual quality**. The gate is not to be edited or bypassed for this research.
- docs/STAR_MEDIA.md documents only four sampled video frames per message (so fast effects are frequently missed), and reference image comparisons. It is not a full video-understanding, temporal tracking or Blender-render loop.
- star/studio_loop.py guards source and instance changes, records history, previews and screenshots. Available capabilities must be discovered on the running Studio connector; do not fabricate a Blender MCP or arbitrary Studio import function.
- star/agent_skills.py SkillLibrary discovers bundled skill packs' references/ text. Four deep references added with this PR can be read when selected but do not alter the current model/tool dispatch or automatically activate anything.

### Suggested future engineering stages, separately reviewed

1. **Curated visual references and permissions:** source metadata, license review, approved project style boards, corpus freshness and retrieval provenance.
2. **Temporal analysis:** owner-supplied MP4 decoding into bounded scene-aware contact sheets; event detection at frame timestamps, no claim of inspecting unexamined moments.
3. **Asset pipeline:** constrained external Blender job descriptors and operator-approved artifact import; signed/hashed inputs, sandbox, no model-supplied arbitrary shell commands.
4. **Studio build loop:** exact tool discovery, original/native GUI hierarchies, model/animation import preview and source checking, disposable-place edits with owner approval.
5. **Visual evaluation:** Studio screenshots and optionally verified authorized video capture; deterministic aspect/placement/clipping checks plus separate expert human aesthetic scoring.
6. **Performance:** measurable GPU/CPU/frame time/streaming/mobile tests; fallback low-end effects levels and finite cleanup.
7. **Held-out creator benchmarks:** one 2-second VFX effect, one R15 synced animation, one 3-screen fully functioning native GUI and one modular building, each assessed on both code tests and genuine rendered screenshots. Compare candidate against the preserved baseline; only enable skills/models after evaluation gate + human visual review.

## Learning and deliberate practice

- Week 1: Roblox primitives, native UI containers, Blender basics, sketch silhouettes; one single layered hit spark; one menu card; one simple room.
- Week 2: particle flipbooks, beam curves, light balance; 8 poses of a short animation; mobile UI constraints; wall/door/window modular kit.
- Week 3: timed combat skill with markers and camera; Mixamo/Quaternius retargeted *practice* animation; menu with keyboard/gamepad states; reference-based facade.
- Week 4: recorded A/B critique against references and device-profile results; cleanup, text overflow, collision, audio/animation sync.
- Weeks 5–6: 4–6 second multi-stage attack, a walk/attack/recovery state machine, full HUD/shop/settings set, small playable block with day/night variants.
- Weeks 7–8: reproduce within explicit constraints with different aesthetics, pass expert review on unseen holdout tasks, and record failures in versioned candidate lessons.

## Research ethics and repeatability

Sources may change; especially licenses, prices, Studio beta APIs and plugin availability. Recheck before download/use. Keep CC0, QAL, Mixamo and Creator Store rights separate. Linking a YouTube page does not mean STAR watched it; reference videos need authorized local files. A tool claiming to auto-create meshes/animations must produce actual editable geometry/keyframes and evidence, not a static concept rendering. Any new code/execution, Blender connector, input permission or evaluation route requires a separate reviewable patch and live end-to-end Studio testing.
