# STAR Asset Forge: Advanced 3D Architecture and World Intelligence
Research: 2026-10-11. Scope: implementation research and read-only planning layer, NOT finished meshes, Blender renders, Roblox world imports, or live GPU benchmarks.

## Audit of Star AI today
The project has official Roblox Studio MCP transport and policy-limited editing in star/studio.py and star/studio_loop.py, Roblox Open Cloud with a private-test approval queue in star/roblox_cloud.py and star/roblox_pipeline.py, an asset guidance starter skill in star/agent_skills.py, and read-only composable tool research in star/tool_workshop.py. None constitutes an end-to-end visual 3D geometry pipeline. The first asset-forge module introduces bounded official Poly Haven catalog discovery, modular building specifications, and seeded seam-stable heightfield samples, exposed through prompt-gated read-only LocalIntelligence functions.

## What a production 3D world builder needs

### Scene specification
Build a typed, versioned Scene/Asset Specification (JSON Schema or strict Pydantic models) to represent meters/studs, coordinate systems, camera, art direction, hierarchy, material slots, pivots, sockets, collisions, spawn/interaction graph, licenses, style-guide revision, seed, expected topology and performance budget. Do not equate a concept image to an editable 3D mesh. Every stage should produce tracked artifacts and provenance.

### Modular architecture and layout grammar
Represent buildings as footprint -> structural grid -> wall bays -> openings -> vertical circulation -> roof -> facade trim -> interior dressing. Snap sockets encode which neighbors are legal and where corner joins happen. Enforce usable entrances, aligned window apertures, stairwell openings through slabs, clearance/headroom and reachable rooms. Maintain authored proportions, real physical architecture, and consistent silhouettes; do not replace errors with random Roblox Parts. Deterministic Blender Python and Geometry Nodes are better fits for repeated structural elements than one-shot image-to-mesh generators.

### Mesh/material production
Generate authored geometry and procedurally instance repeatable pieces. UV unwrap or assign trimsheet/atlas coordinates, verify outward normals, watertightness where needed, non-degenerate faces, non-overlapping UVs where required, pivot position, scale, collision hulls and materials. Optimize and split meshes to meet Roblox's approximately 20,000-triangle per general mesh object cap; avatar mesh budgets differ. Preserve hierarchy for editable kits. For PBR use SurfaceAppearance/MaterialVariant where applicable and bake maps in repeatable Blender jobs. Roblox glTF, FBX and OBJ importer behavior should be checked on a real Windows/Studio device.

### Worlds and terrain
World-space seeded noise supplies height layers; then add erosion/hydrology, streams, lakes, roads, biome and climate masks, slope-aware foliage scattering, geological rules, caves, cliffs and points of interest. Choose multiresolution chunk seeds and a global coordinate-based height function to guarantee identical edge values. More complete planning requires reachability graph and environmental gameplay logic. Roblox terrain voxel operations use 4-stud resolution and must be bounded, grid aligned and gated by existing Studio owner permissions. Numeric heightfield samples alone do not produce terrain instances.

### Visual fidelity and creative direction
Store approved reference images and a measurable style bible for scale, silhouette, hue distribution, roughness, edges, ornament detail density and lighting. Use separate research, concept, modeling, material, environment composition and critic agents that exchange typed artifacts rather than shared unrestricted tool credentials. Compare source renders against references from fixed camera angles, review normal topology/collisions and game-camera readability; do not accept a self-rated beauty score as proof of quality.

### Free asset providers (terms vary by provider and asset)
| Provider | What it is useful for | License handling |
|---|---|---|
| Poly Haven — https://polyhaven.com/license | CC0 models, HDRIs, PBR textures | Official public API https://github.com/Poly-Haven/Public-API supports GET /search, GET /info/{id}, GET /files/{id}. Display “Powered by Poly Haven” in integrations; per API terms use bounded requests and preserve source URLs. MVP performs metadata lookups only. |
| Kenney — https://kenney.nl/support | Stylized props, modular kits, sprites | CC0 for Kenney asset packs; verify the individual pack and redistribution context. No unverified scraper/API. |
| Quaternius — https://quaternius.com/license.html | Buildings, environment kits and characters | As of August 28, 2026, Quaternius Asset License v1.0 (QAL), not blanket CC0. Commercial in-game use permitted under terms; standalone redistribution restricted. Verify asset-version terms. |
| ambientCG — https://ambientcg.com | Photogrammetry/PBR materials | Verify license/item and permitted automated access separately. |
| OpenGameArt — https://opengameart.org/content/faq | Art, textures, 3D and sound | Mixed CC0, attribution/share-alike licenses; do not assign a blanket license. |
| Roblox Creator Store — https://create.roblox.com | Native Roblox assets and plugins | Observe Roblox asset license and audit all embedded scripts. |
| USGS 3DEP — https://www.usgs.gov/3d-elevation-program | Public elevation/DEM reference | Verify datum, units, projection, resolution and local coverage; DEM is not finished game terrain. |
| OpenStreetMap — https://www.openstreetmap.org/copyright | Road and settlement reference | ODbL attribution and reuse/share-alike obligations. |

Never execute a downloaded Blender project/script, Roblox model script or installer without explicit review. A later downloader must verify allowlisted URLs, source identity, license, file type, size, cryptographic hashes and content scanning before quarantined user-approved import. Unknown license blocks automatic import.

### AI 3D systems to benchmark (not installed by this PR)
| Candidate | Role | Restrictions |
|---|---|---|
| Blender Python / Geometry Nodes — https://docs.blender.org/api/4.5 | Primary deterministic procedural building and mesh production | Pinned local Blender version, user-approved path, isolated job, timeout/VRAM budget, no untrusted script execution. |
| Microsoft TRELLIS.2 — https://github.com/microsoft/TRELLIS.2 | Single-image textured/PBR mesh draft | High quality, but example reported speeds use H100; benchmark actual Windows GPU and licensing/dependencies. |
| TripoSR — https://huggingface.co/stabilityai/TripoSR | Lower-cost single-image 3D draft | Evaluate exact weight and dependency licenses and output quality. |
| InstantMesh — https://github.com/TencentARC/InstantMesh | Reconstruction and mesh proposals | Evaluate model checkpoint licensing, CUDA, backface/manifold quality. |
| Hunyuan3D-2.1 — https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 | Alternative PBR candidate | Restrictive Tencent community license, geographic and use conditions; NOT enabled by default. |
| Meshy — https://docs.meshy.ai/en/api/pricing | Optional hosted provider | Paid API; not a free unlimited source; explicit budget/consent required. |

## Optional real mesh export (human-triggered CLI only)

A second, non-network module star/world_mesh.py converts bounded terrain heightfield previews into a real Wavefront OBJ triangle surface with UV coordinates. It guarantees seam-height consistency between same-seed adjacent chunks because vertices use shared world coordinates, and it emits upward-facing triangles. This is geometry-only output, not Blender rendering, terrain voxel authoring, authored meshes with architectural openings, or proof of Roblox usability.

Operator command from the repository root:

    python -m star.world_mesh --output terrain.obj --seed 42 --biome temperate --size 16 --step 16

Only an explicitly invoked CLI writes the selected .obj path. Agent-exposed tools stay read-only. OBJ exports have no textures or collisions and are intended for Blender inspection and a later importer validation step. The 16-by-16 preview yields 256 vertices and 450 triangles. Edge continuity and face winding are covered by new offline tests in tests/test_world_mesh.py.

## Delivery roadmap and acceptance gates
**Phase A — this draft PR:** safe attributed Poly Haven asset research; seeded and style-specific architecture manifests with walls, door/window apertures, roof and stairwell; seam-stable sampled terrain; and an optional manually invoked, untextured OBJ surface exporter for heightfields. Unit tests with offline mocked HTTP. Stage fields report metadata/planning and geometry prototypes, never Blender-rendered environments or Studio deployment.

**Phase B — geometry engine:** fixed Blender job definitions, native mesh export, real UVs, valid joins, GLB/FBX artifacts, asset hashing, GPU and wall-clock telemetry, no executing remote asset scripts.

**Phase C — architectural realism:** production modular wall/window/door kit, geometry cuts, stair circulation and connectivity, collision and UV/PBR LODs. Ship fixed-angle mesh render review and style-bible checks before judging quality.

**Phase D — large-world synthesis:** deterministic multilevel chunks, biome graphs, erosion and rivers, prop scatter rules, settlement zoning, POI path reachability, streaming and occlusion testing; guarded Roblox import into approved unpublished/private test place only.

**Phase E — iterative creative learning:** agent proposer/critic/validator, independent mesh and navigation checks, regression and blind reference-based human review, reviewed reusable recipes and measurable per-hardware improvements. No self-authorized tool privileges or automatic game publishing.

### Targets (NOT recorded results)
100% provenance before asset import. 0 conflicting seam samples. 0 general MeshParts exceeding applicable triangle caps. Every main room reachable through valid sized entrances. Measure actual frame time, memory, mobile draw calls, load latency, LOD transitions, crash rates and fidelity drift. Track exact Blender/engine versions and hardware. Release is conditioned on owner signoff and actual Studio/gameplay evidence, not model-generated claims.

## Test and safety boundaries
Offline: python -m pytest -q tests/test_asset_forge.py. This module does not download any model weights, run Blender, write workspace files, modify Studio, publish experiences, connect arbitrary remote APIs, or grant self-created tools new privileges. A draft PR is only a code review proposal; it is not shipped in the Windows installer.
