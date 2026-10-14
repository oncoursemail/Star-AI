# Rendering, physics and animation fundamentals

Researched 2026-10-13. Conceptual, engine-independent. Sources at the end.

## 1. Rendering pipeline

### The frame
CPU: visibility (frustum + occlusion culling, LOD selection) -> build draw lists sorted by state -> submit command
buffers. GPU: vertex stage -> rasterization -> pixel/fragment stage -> output merge; plus compute passes (culling,
particles, post-processing). Modern engines do GPU-driven rendering (culling and draw generation on the GPU,
indirect draws) and mesh shaders / virtualized geometry (Nanite) to decouple triangle count from draw-call count.

### Lighting architectures
| Approach | How | Strengths | Weaknesses |
|---|---|---|---|
| Forward | Shade every lit object per light in its pixel shader | MSAA, transparency, varied materials, low bandwidth | Cost scales objects x lights; overdraw |
| Deferred | Write a G-buffer (albedo, normal, roughness, depth...), then light in screen space | Many lights, lighting cost per pixel | Fat G-buffer bandwidth, MSAA hard, transparency needs a forward pass, limited material variety |
| Tiled (forward+ / tiled deferred) | Divide screen into 2D tiles, build per-tile light lists using min/max depth | Light culling per tile | Depth discontinuities make tiles carry many lights |
| Clustered (forward or deferred) | Divide the view frustum into 3D clusters (tiles x depth slices), assign lights per cluster | Robust with depth discontinuities, scales to very many lights, supports transparency in forward | Cluster build cost, memory |

Olsson, Billeter and Assarsson (HPG 2012) introduced clustered shading; most current engines (Doom 2016 onward,
Unity HDRP/URP Forward+, Godot 4 Forward+, Bevy) use a clustered forward or hybrid. Ray-traced direct lighting
(stochastic light sampling, ReSTIR; Unreal MegaLights, production-ready in 5.8 per Epic's announcement) is the 2025-2026
frontier for thousands of shadowed lights.

### Physically based rendering (PBR)
- Energy conservation and the microfacet BRDF: Cook-Torrance specular with a normal distribution function (GGX /
  Trowbridge-Reitz), geometry/shadowing term (Smith), Fresnel (Schlick approximation); Lambert (or Burley) diffuse.
- **Metallic/roughness** workflow: base color, metallic (0 or 1 for real materials), roughness (perceptual, squared
  before use), normal map, ambient occlusion. Dielectric F0 ~ 0.04.
- **Image-based lighting**: prefiltered environment map (split-sum approximation: prefiltered radiance by roughness +
  BRDF integration LUT), diffuse irradiance as spherical harmonics.
- Work in **linear** color space; textures authored in sRGB are converted on sampling; tone map HDR to the display
  (ACES, AgX, Khronos PBR Neutral), then apply output transform. Physical light units and exposure make lighting
  portable between scenes.

### Shadows
- **Shadow maps**: render depth from the light; compare. Problems: acne (depth bias, slope-scaled and normal-offset
  bias), peter-panning (too much bias), aliasing.
- **Cascaded shadow maps (CSM)** for directional lights: split the view frustum by distance, stabilise cascades
  (snap to texel grid, fit to bounding sphere) to stop shimmering.
- **Filtering**: PCF, PCSS (contact-hardening soft shadows), VSM/EVSM/MSM (filterable, light bleeding).
- **Virtual shadow maps** (very large virtual resolution with page caching: Unreal 5) and **ray-traced shadows**.
- Point lights use cube maps or dual-paraboloid maps; spot lights a single perspective map.

### Global illumination (GI)
- **Baked**: lightmaps and light probes / irradiance volumes: highest quality per cost, static only.
- **Screen-space**: SSAO / GTAO, SSR, SSGI: cheap, but only knows what is on screen.
- **Probe-based dynamic**: DDGI (ray-traced irradiance probes with visibility), probe volumes.
- **Voxel / distance field**: voxel cone tracing; signed distance field tracing (Lumen's software path).
- **Hybrid ray tracing**: Lumen (surface cache + screen traces + SDF or hardware rays; infinite diffuse bounces),
  ReSTIR GI, path tracing with denoisers for high-end. Lumen Lite in Unreal 5.8 is Epic's cheaper preset (vendor claim
  of up to 2x).
- Choose by target hardware, how dynamic the lighting is, and whether geometry is destructible.

### Anti-aliasing and temporal techniques
MSAA (geometry edges, forward), FXAA/SMAA (post), TAA (jittered history, blur/ghosting risks), and temporal upscalers
(DLSS, FSR, XeSS, TSR) that now carry most of the image quality budget. Anything temporal needs correct motion vectors
for every moving thing, including animated materials and particles.

### Rendering performance reasoning
GPU-bound vs CPU-bound first (does lowering resolution help? then pixel-bound). Draw calls / state changes (batch,
instance, sort by material), overdraw (front-to-back opaque, depth pre-pass), bandwidth (G-buffer, texture
compression BCn/ASTC, mipmaps), vertex cost (LODs, impostors), shadow cost (cascade count/size, caching), and
transparent overdraw (particles: fewer, larger, cheaper shaders). Always capture a GPU frame (RenderDoc, PIX, Nsight,
engine profilers) before guessing.

## 2. Physics

### Collision detection
- **Broadphase**: find candidate pairs cheaply: sweep and prune (sort AABB endpoints on an axis), uniform grid /
  spatial hash, dynamic AABB tree (BVH with fattened AABBs; Box2D, Bullet, Jolt).
- **Narrowphase**: exact tests: SAT (separating axis theorem) for convex polygons/boxes, GJK (distance between convex
  shapes via Minkowski difference) + EPA (penetration depth), specialised sphere/capsule tests, triangle meshes via a
  BVH. Output: contact manifold (points, normal, depth), kept persistent between frames for stability.
- **Continuous collision detection (CCD)**: fast small objects tunnel through thin walls with discrete steps; use
  swept tests / conservative advancement / speculative contacts, or raycast bullets instead of simulating them.

### Dynamics and solvers
- Rigid body state: position, orientation (quaternion), linear and angular velocity, mass, inertia tensor (in body
  space; transform to world).
- Integrate with semi-implicit Euler at a fixed timestep; sub-stepping increases stiffness/stability.
- Contacts and joints are constraints; most game engines use **sequential impulses / projected Gauss-Seidel** with
  warm starting, restitution and friction cones (Catto). Box2D v3 uses a "soft step" solver (soft constraints with
  sub-stepping and relaxation); Catto's Solver2D post compares eight solvers.
- **Position-based dynamics / XPBD**: project positions to satisfy constraints with compliance; stable for cloth,
  ropes, soft bodies; used by many modern engines for these.
- **Sleeping/islands**: bodies at rest go to sleep; islands of touching bodies are solved together and in parallel.
- Common problems: jitter (too few iterations, no warm start, mass ratios > 1:10), objects exploding (overlap
  correction too aggressive: use Baumgarte or split impulses / soft constraints), stacking instability, tunnelling.

### Determinism
- Same binary + same platform + same inputs + fixed dt + same order of operations -> same results with most engines.
- Cross-platform determinism needs special care: Jolt has a cross-platform determinism build option; Box2D v3 aims
  for cross-platform determinism; Unity Physics (DOTS) is deterministic on the same architecture; PhysX is not
  guaranteed across platforms.
- Required for lockstep and rollback netcode; checksum the state each tick to detect desyncs early.

### Character controllers
Kinematic capsule with collide-and-slide (sweep, slide along the plane, repeat 3-4 times), step-up/step-down, slope
limits, ground snapping, coyote time and jump buffering for feel. Dynamic (physics-driven) controllers for ragdolls
or vehicles only.

## 3. Animation

- **Skeletal animation**: joint hierarchy, bind pose, skinning (linear blend skinning; dual quaternion skinning avoids
  candy-wrapper artefacts on twisting). Store local transforms; compute model space once per frame.
- **Sampling and compression**: keyframes per channel, quantized rotations (smallest-three), curve fitting
  (ACL library).
- **Blending**: cross-fade (lerp/nlerp per joint), additive layers (aim offsets, breathing, hit reactions = pose minus
  reference pose), masked layers (upper body shooting while legs run).
- **Blend spaces / blend trees**: parameters (speed, direction) select and weight clips; sync groups / phase matching
  keep footfalls aligned when blending walk and run.
- **Animation state machines**: states = clips or blend trees; transitions with durations and conditions; avoid
  transition spaghetti with layered/hierarchical machines.
- **Root motion vs in-place**: root motion moves the character by the animation (no foot sliding, less control);
  in-place animation follows gameplay movement (responsive; fix sliding with stride warping / speed matching).
- **Inverse kinematics (IK)**: two-bone analytic IK (law of cosines) for arms and legs; CCD (cyclic coordinate
  descent) and **FABRIK** (Aristidou and Lasenby 2011: forward and backward reaching along the chain, no matrices,
  fast convergence) for chains; full-body IK solvers for whole characters. Uses: foot placement on slopes, hand
  placement on weapons/ledges, look-at.
- **Procedural animation**: springs and damped secondary motion, ragdoll blending (active ragdolls / powered ragdolls).
- **Motion matching** (Clavet, Ubisoft, GDC 2016, For Honor): search a large unstructured mocap database every few
  frames for the pose + future trajectory that best matches the current pose and the desired path; blend to it.
  Learned motion matching (Holden et al. 2020) compresses the database with neural networks. Now shipped in Unreal
  (Pose Search) and many AAA titles.
- **Animation events / notifies** drive gameplay (footstep sounds, hit windows) but gameplay authority (damage) should
  be decided by gameplay timing on the server, not by client-side animation playback.

## 4. What STAR should do with a rendering/physics/animation question
1. Classify: correctness bug (wrong space, missing normalize, bias), performance (which bound: CPU, GPU, memory,
   bandwidth), or design choice (pipeline, solver, technique).
2. For design choices give the decision variables (light count, transparency, platform, dynamic vs static,
   determinism) and the recommended default.
3. For physics bugs check timestep, mass ratios, solver iterations, CCD and units first.
4. For animation bugs check spaces (local vs model), blend weights summing to 1, quaternion hemisphere, and root
   motion ownership.

## Sources
- Akenine-Moeller, Haines, Hoffman et al., *Real-Time Rendering*, 4th ed. (resources): https://www.realtimerendering.com/
- Olsson, Billeter, Assarsson, "Clustered Deferred and Forward Shading" (HPG 2012), preprint: https://www.cse.chalmers.se/~uffe/clustered_shading_preprint.pdf
- Olsson et al., "Tiled and clustered forward shading: supporting transparency and MSAA": https://research.chalmers.se/en/publication/161726
- Brian Karis, "Real Shading in Unreal Engine 4" (SIGGRAPH 2013 course notes): https://cdn2.unrealengine.com/Resources/files/2013SiggraphPresentationsNotes-26915738.pdf
- LearnOpenGL, PBR theory: https://learnopengl.com/PBR/Theory
- Physically Based Rendering: From Theory to Implementation, 4th ed. (free online): https://pbr-book.org/
- Microsoft, "Common Techniques to Improve Shadow Depth Maps": https://learn.microsoft.com/en-us/windows/win32/dxtecharts/common-techniques-to-improve-shadow-depth-maps
- Microsoft, "Cascaded Shadow Maps": https://learn.microsoft.com/en-us/windows/win32/dxtecharts/cascaded-shadow-maps
- Epic Games, "Unreal Engine 5 goes all-in on dynamic global illumination with Lumen": https://www.unrealengine.com/en-US/tech-blog/unreal-engine-5-goes-all-in-on-dynamic-global-illumination-with-lumen
- Epic Games, MegaLights documentation: https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine
- Guru3D (secondary), "Unreal Engine 5.8 Debuts Lumen Lite and Production-Ready MegaLights": https://www.guru3d.com/story/unreal-engine-58-debuts-lumen-lite-and-productionready-megalights/
- Bitterli et al., ReSTIR (SIGGRAPH 2020): https://benedikt-bitterli.me/restir/
- Majercik et al., DDGI (JCGT 2019): https://jcgt.org/published/0008/02/01/
- Erin Catto, Box2D publications and GDC talks: https://box2d.org/publications/
- Erin Catto, "Solver2D" (2024): https://box2d.org/posts/2024/02/solver2d/
- Erin Catto, "Soft Constraints" (GDC 2011): https://box2d.org/files/ErinCatto_SoftConstraints_GDC2011.pdf
- Jolt Physics documentation (architecture, deterministic simulation): https://jrouwe.github.io/JoltPhysics/
- Christer Ericson, *Real-Time Collision Detection*: https://realtimecollisiondetection.net/
- Glenn Fiedler, "Integration Basics": https://gafferongames.com/post/integration_basics/
- Mueller et al., XPBD: https://matthias-research.github.io/pages/publications/XPBD.pdf
- Aristidou and Lasenby, FABRIK: https://www.andreasaristidou.com/FABRIK
- Simon Clavet, "Motion Matching and The Road to Next-Gen Animation" (GDC 2016): https://gdcvault.com/play/1023280/Motion-Matching-and-The-Road
- Holden, Kanoun, Perepichka, Popa, "Learned Motion Matching" (SIGGRAPH 2020): https://theorangeduck.com/page/learned-motion-matching
- Daniel Holden, "Code vs Data Driven Displacement" and other animation articles: https://theorangeduck.com/page/code-vs-data-driven-displacement
- Animation Compression Library (ACL): https://github.com/nfrechette/acl
- Kavan et al., dual quaternion skinning: https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.html
