# STAR architecture + Blender production pipeline — research and implementation (2026-10-11)

**Status:** a reviewable *first vertical slice*, not autonomous AAA environment production. This document separates platform-confirmed capabilities, shipped implementation, design judgments, and proposed work. It does not imply Blender or Roblox Studio ran in CI. No assets are uploaded or published by this work.

## 1. Research findings verified from primary documentation

| Finding | Source | Consequence for STAR |
|---|---|---|
| Studio's 3D Importer accepts FBX, glTF and OBJ; imported meshes become MeshParts. | [Roblox third-party DCC overview](https://create.roblox.com/docs/art/overview-dcc), [custom 3D assets](https://create.roblox.com/docs/art/modeling) | Generate editable source assets and an importer-compatible deliverable, not flat screenshots. |
| Blender-to-Studio orientation and scale differ; explicit importer settings are needed. | [Roblox Blender guide](https://create.roblox.com/docs/art/blender) | Record dimensions in studs; visually verify axis and avatar scale after each format/import setting change. |
| The documented official Blender plugin can transfer assets via Roblox Open Cloud, with authentication. | [Roblox Blender plugin](https://create.roblox.com/docs/art/modeling/roblox-blender-plugin) | Optional future owner-authorized transfer; **not** an excuse for silent uploads or handing credentials to a model. |
| Studio Reimport preserves existing properties and matches mesh paths/names, with caveats for missing names. | [Roblox Reimport](https://create.roblox.com/docs/art/modeling/reimport) | Stable output names are mandatory for revision loops. Inspect output and changes before accepting reimport. |
| Modular kits require compatible pivots, grid snapping and variation through materials/details. | [Assemble modular environments](https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments) | Establish one unit grid and a repeatable library of wall, roof, window and trim assemblies. |
| SurfaceAppearance supports color, normal, roughness, metalness and emissive maps; textures have limits. | [PBR textures](https://create.roblox.com/docs/art/modeling/surface-appearance), [texture specs](https://create.roblox.com/docs/art/modeling/texture-specifications) | Separate texture budget/authoring from mesh topology and prove imported material parity. |
| Reused mesh IDs aid instancing; high texture memory, streaming, physics and draw calls are important. | [Performance improvements](https://create.roblox.com/docs/performance-optimization/improve), [design for performance](https://create.roblox.com/docs/performance-optimization/design) | Do not repeatedly upload visually identical chunks; profile a representative scene on target devices. |
| Blender's Python API offers a glTF export operator. | [Blender Python API: export_scene.gltf](https://docs.blender.org/api/current/bpy.ops.export_scene.html) | Generate from a trusted, version-controlled script rather than allowing freeform model-authored execution. |

All references are *design and API grounding*; they are not evidence that STAR's exporter produces a good-looking Roblox building without a native visual test.

## 2. What makes a designed building look believable

An excellent environment is not a random set of boxes with windows. STAR should explicitly reason about:

1. **Place and purpose:** Is this a working warehouse, a home, a machine shop, a shrine, a spaceport, or a ruin? Climate, economy, occupants and gameplay justify the geometry.
2. **Hierarchy:** Readable primary mass, roof, entry, circulation path, subordinate wings, secondary volumes, trim and set dressing. The entrance should be legible at gameplay camera distance.
3. **Structural plausibility:** Walls stack sensibly; windows have jambs, headers and sills; roofs have a plausible load path, overhang and drainage. Fantasy details may exaggerate but should obey a consistent visual logic.
4. **Proportion, cadence and rhythm:** Define bay widths, story heights, window-to-wall relationships, solids versus voids, symmetry/asymmetry, focal entry and repetition broken by functional variation.
5. **Gameplay scale:** Use real avatar and camera walkthroughs for doors, stairs, corridors and sightlines. These are design heuristics, not claims of building-code compliance.
6. **Materials:** Concrete, masonry, timber, painted metal, stone, glass and fantasy surfaces need believable material boundaries, edge wear and texel density. Do not layer unrelated PBR maps indiscriminately.
7. **Context:** Street grade, pavement, drainage, terrain foundations, neighboring structures, vegetation, signage, lighting and clutter should reinforce the setting.
8. **Storytelling:** Occupation traces, repairs, tools, weathering, signage and circulation tell *who uses this place*. Detail should arise from function, not random decorations.
9. **Silhouette and composition:** Evaluate from the camera's usual viewing distance as well as near the asset. Use one focal read before micro-detail.
10. **Implementation:** Separate collision, visuals, streaming, reimport identities and LOD. Test whether the asset can actually be walked through and seen on mobile.

### Style families to teach and benchmark

| Family | Grammar examples | Failure checks |
|---|---|---|
| Storybook / hand-painted fantasy | Asymmetric gables, exposed framing where structurally plausible, softened stone, intentional warm/cool contrast, stylized eaves | Identical roof silhouettes; random timber beams without supports; overly noisy highlights |
| Industrial / working harbor | Large repeated bays, robust lintels, loading doors, functional ventilation, brick/steel interface | Tiny nonfunctional doors; fake facade depth; no believable loading path |
| Contemporary / minimal | Clear massing, facade setbacks, curtain-wall proportions, screened services, restrained palette | Generic white cubes; no depth; illogical uninterrupted glass |
| Gothic / historical-inspired | Vertical rhythm, buttress logic, pointed openings, legible masonry, coherent roof and ornament hierarchy | Decorative arches floating without loads; incompatible chronology/materials |
| Brutalist / civic | Expressed concrete structure, deep openings, ordered masses, sheltered entrances | Unreadable scale; no public access; same repeated block everywhere |
| Sci-fi / spaceport | Repeatable structural modules, believable vents, maintainable seams, ports, equipment/service volumes | Arbitrary glows and pipes; tiny controls; nonfunctional mechanical features |
| Stylized Roblox / studs | Deliberate visible grid, crisp silhouettes, gameplay legibility and real asset kits | Looks like random part art; gaps; unsuitable scale; excessive unique meshes |

These are **design constraints to research further**, not styles STAR already renders. The shipped generator has four named palette/roof presets (`storybook`, `industrial`, `modern`, `spaceport`). Gothic, brutalist, richly textured assets, interiors, terrain, props, irregular plans, animated building pieces and production-quality detail remain later work.

## 3. Implemented: controlled, reproducible prototype

Files:

- `star/architecture_pipeline.py` — strict JSON brief, procedural exterior shell with framed window openings, a doorway, floor slabs, facade bands and gabled/flat roof; deterministic face/triangle estimate; explicit plan-only or Blender build.
- `scripts/blender_building.py` — a **fixed** Blender `bpy` geometry/export script, joining generated subparts into a few stable material groups to avoid exporting hundreds of separate meshes. Writes `.blend` and `.glb` using Blender's built-in glTF exporter.
- `examples/architecture/*.json` — two safe, inspectable briefs.
- `tests/test_architecture_pipeline.py` — offline checks for validation, deterministic geometry, presence of physical openings, both roof families, forbidden raw code fields, no implicit process execution, safe argument-vector invocation and honest error reporting.

Example plan-only (works without Blender):

```powershell
python -m star.architecture_pipeline examples/architecture/harbor_warehouse.json --out .\out\harbor-plan
```

Example actual Blender build (requires a **locally installed**, trusted Blender executable):

```powershell
python -m star.architecture_pipeline examples/architecture/storybook_shop.json --out .\out\shop-v1 --blender "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
```

Choose the Blender path that exists on your own computer; the above is illustrative, not a version or install assertion. Paths in `--out` **must not already exist**: revisions create new folders and never silently overwrite earlier source assets. The build uses Blender in background mode, `--factory-startup`, `--disable-autoexec`, 2 threads and a 180-second timeout. It does *not* execute code supplied in the building JSON, invoke the official Studio uploader, publish assets, or change any open Roblox place. A standalone `.blend` and `.glb` are evidence of file generation, **not** evidence of Roblox import success or artistic quality.

Supported JSON schema:

```json
{
  "name": "Harbor Warehouse",
  "style": "industrial",
  "width_studs": 48,
  "depth_studs": 32,
  "floors": 2,
  "bays": 4,
  "story_height_studs": 13
}
```

Sizes: width 24–96, depth 16–80, 1–4 floors, 2–8 facade bays, 12–18 studs per story, at least 8 studs per bay. Other fields are rejected rather than silently ignored. Existing output folders are rejected. Plan mode has no Blender requirement, useful for comparing structured compositions before paying launch time. The prototype is deliberately limited; it is a baseline for visually judged upgrades, not a final art generator.

### Import into Roblox Studio

1. Open an **unpublished disposable test place** you own. In Blender, inspect the `.blend` scene with the intended camera, proportions, normals, glass and materials before import.
2. In Studio use the [3D Importer](https://create.roblox.com/docs/art/blender) to import `building.glb`. In the importer preview verify the world-forward/up transforms and `Scale Unit` (studs). Do not assume the conversion is correct from the manifest alone. Set **Import Only as a Model** if appropriate.
3. Compare the model beside a real R6/R15 avatar; measure the door and a 12–18-stud floor. Check roof continuity, reversed normals and whether glaze/door placeholders look correct under your game's lighting.
4. The output's `STAR_wall`, `STAR_trim`, `STAR_roof`, `STAR_glass`, `STAR_door` names are designed to stay stable. Preserve them when using Studio Reimport. Reimport behavior still needs native regression testing.
5. For playable interiors, use authored native invisible collision parts for floor/walls/doorways as needed, not arbitrary precise mesh collision. The sample's doors and tinted glazing are static placeholder geometry: replace/remove them when implementing functional entrances or glass.
6. Review SurfaceAppearance/material limits, instance duplication and client memory. Record the actual asset IDs before reuse; importing this exact GLB repeatedly as unrelated uploads is **not** an instancing optimization.

**Known limitations:** No automatic Studio upload, no completed interior layout, no UV atlases or textured PBR maps, no authored environment props, no navmesh/pathfinding, no LOD chain, no lightmap bake, no automatic image comparison, and no native Blender/Studio result verified in this task. The generated triangle estimate is *pre-import and topology-based*, not a measured GPU draw-call or memory result. Glass is a simple opaque colored material placeholder; mobile appearance must be judged after import.

## 4. A practical architecture quality gate

STAR should label every project stage as `planned`, `generated`, `opened in Blender`, `imported in Studio`, `visually reviewed`, `playtested`, `profiled`, `accepted` or `rejected` **only with corresponding artifacts**. The last four stages require Studio/human or approved visual tooling; Python unit tests are insufficient.

| Gate | Evidence | Suggested initial acceptance criterion (target, not measured) |
|---|---|---|
| Scope and intent | Human-approved design brief; reference/source/asset licenses | No ambiguous building purpose or mixed aesthetics |
| Geometry | Manifest, `.blend`, `.glb`; topology report | No zero-area faces, invalid dimensions, missing openings or silhouette gaps |
| Architecture | 4 orthographic/elevation views + first-person camera | Doors/circulation fit an avatar; structure/eaves consistent |
| Art direction | Style board and rendered before/after | Human approves at least 3 anchors: silhouette, materials, facade rhythm |
| Engine compatibility | Studio import log and screenshot | Scale/orientation correct; intact surfaces and import without warnings |
| Game function | Player walk-through and collision test | No trapped door, unseen barriers, unreachable required areas |
| Performance | Device / graphics settings, MicroProfiler, draw calls, memory, loading | Measured budgets selected for *that game's* target hardware |
| Improvement | Same-scene A/B previews, reviewer notes, elapsed time and profiler | Change improves a measurable property; never fake an improvement score |

Use `golden scene` fixtures with *independent evaluators*: 1) warehouse facade, 2) cozy house, 3) modern shop, 4) fantasy shrine, 5) woodland bridge, 6) sci-fi workshop. Hold out several entire designs so STAR cannot simply memorize exact reference images. Require art-direction reviewers to mark aesthetic failures rather than teaching STAR to optimize a self-written checklist alone.

## 5. Research-to-engineering roadmap (ordered by gain and feasibility)

**A. First: safe Blender execution and import.** Native Windows/Blender validation; fixture screenshots; glTF inspection; mesh/material budgets; separate low-end-mobile benchmark. Add an explicit, user-approved read-only `inspect_building` tool, followed by an approval-gated `generate_building` tool using this fixed script. A script that executes any LLM-authored arbitrary Blender Python should not be a default agent tool.

**B. Improve architectural geometry.** Stable procedural **kit grammars**, not unconstrained random polygons: footprints from room adjacency, corridors/doors, wall thickness, staircase headroom, structural grids, roof junctions, facade patterns, bays, cornices, stairs, balcony rails, gutter/detail systems, intentional asymmetry. Each generator needs valid topology and a fixture showing where repeated components meet.

**C. Professional art styles.** Per-project `art_direction.json`: mood, palette, silhouette vocabulary, material library, texture density, reusable trim-sheet channels, reference rights, prohibited motifs, scale conventions, approved hero assets. Train/test *style identity preservation*, not merely matching color names. Use external textures and asset libraries only when licenses allow redistribution and provenance is recorded.

**D. Visual critique.** Capture Blender orthographic and three-quarter shots and matching Studio camera shots. Pair color histogram/edge map as low-cost checks with image-vision comparison of approved references for missing openings, wrong door sizes, clipping and geometry artifacts. Vision suggestions remain candidates; manual reviewer approves a concrete edit. Visual quality scoring cannot be inferred from triangle count.

**E. Fast intelligent iteration.** Cache validated brief signatures, reuse materials/meshes, regenerate only changed modules, batch Blender object creation by material, render low-resolution previews early and full renders only for finalists. Profile startup, geometry build, export, Studio import and screenshot timing separately. Report actual median/p95 rather than announcing speedups without a baseline.

**F. Generalizable learning.** STAR already has project-scoped reviewed lessons (`star/lessons.py`) and independent evaluation gates (`docs/evals.md`). Add structured candidate lessons for *specific visual faults* with image refs, build hash, reviewer score, fix and follow-up render. Promote only after human approval and held-out evaluations; do not auto-edit eval checks, silently fine-tune on private/user assets, or treat unverified model speculation as learned truth.

**G. Multi-specialist design review.** An architecture planner owns scale and room relationships, an art director owns silhouette/materials, a modeling specialist produces candidate geometry, a technical artist audits UV/LOD/collision, and a QA reviewer checks screenshots and performance. Use independent bounded tasks on real project data; a solo deterministic tool is faster than a swarm when it suffices. Tool execution privileges stay outside specialist prompts.

**H. Broad creation scope.** Extend the same reviewed pipeline to interiors, furniture, roads, landscaping, ruins, terrain, destructible prefabs, vehicles and creatures *without* pretending they are all the same geometry generator. Each domain needs its own rigging/topology/physics benchmarks and engine compatibility tests.

## 6. What would constitute a major advancement?

Success is not a claim of being 'smarter than every AI.' A measurable milestone is: from a new approved reference board and building brief, STAR creates an editable `.blend`, makes an importable `.glb`, produces a Studio screenshot, identifies architectural flaws, repairs them, and finishes with acceptable gameplay and mobile metrics **without unapproved publishing**. Repeat across unseen style families, with a time budget and an independent human aesthetic assessment. Report pass rate, human edit count, latency, load-time/memory and failure categories across *multiple* projects. Only then promote that workflow to default.

### Test and review checklist for this PR

- [x] Local Python compile of newly added modules.
- [x] Offline isolated unit tests of the bounded generator and subprocess contract.
- [ ] Full repository pytest/TypeScript suites on a checkout of the target branch (not available in the current isolated test environment).
- [ ] Actual Blender binary export + Blender GUI screenshot on Windows.
- [ ] Roblox Studio importer and reimport acceptance, functional collision/playtest.
- [ ] Rendering and mobile profiling on real hardware.
- [ ] Gate a new opt-in skill pack against STAR's existing creation evaluation suite before enabling it by default.
