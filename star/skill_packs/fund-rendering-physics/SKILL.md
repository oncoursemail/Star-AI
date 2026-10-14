---
name: fund-rendering-physics
description: Engine-independent rendering, physics and animation concepts - forward, deferred and clustered shading, PBR, shadows, global illumination, collision detection, integrators and solvers, determinism, IK, blend trees and motion matching.
---
# Rendering, physics and animation (engine-independent)
## Rendering
- Pipelines: forward (MSAA, transparency, cost grows with objects x lights), deferred (G-buffer, many lights, hard MSAA, transparency needs a forward pass), tiled and clustered (per-tile or per-3D-cluster light lists). Clustered forward+ is the common modern default; ray-traced many-light sampling (ReSTIR-style) is the high end.
- PBR: metallic/roughness, GGX distribution, Smith geometry, Schlick Fresnel, dielectric F0 about 0.04, energy conservation. Light in linear space, then tone map HDR to the display.
- Shadows: shadow maps need slope-scaled and normal-offset bias (acne vs peter-panning); cascaded shadow maps for the sun, stabilised by texel snapping; PCF/PCSS filtering; virtual or ray-traced shadows on high-end targets.
- Global illumination: baked lightmaps and probes (static, cheapest per quality), screen-space AO/SSR/SSGI (on-screen only), probe-based dynamic GI, distance-field or hardware ray tracing. Choose by hardware and how dynamic the lighting is.
- Temporal AA and upscalers need correct motion vectors for everything that moves.
- Performance: first find the bound (CPU submission, GPU vertex, GPU pixel, bandwidth, memory); then batch/instance, cull, LOD, reduce overdraw and particle fill. Capture a frame with a GPU profiler before guessing.
## Physics
- Broadphase (sweep and prune, grid, dynamic AABB tree) then narrowphase (SAT, GJK + EPA, specialised sphere/capsule tests) produce persistent contact manifolds.
- Fast small objects tunnel: use continuous collision detection, speculative contacts or raycasts for bullets.
- Fixed timestep, semi-implicit Euler, sequential-impulse / Gauss-Seidel solvers with warm starting; sub-stepping or soft constraints for stiffness; XPBD for cloth and ropes; sleeping and islands.
- Instability checklist: variable dt, mass ratios above about 1:10, too few iterations, aggressive overlap correction, missing CCD, wrong units or scale.
- Determinism holds for the same binary, platform, inputs, dt and order; cross-platform determinism needs an engine built for it. Checksum state per tick when lockstep or rollback depends on it.
- Character controllers: kinematic capsule with collide-and-slide (3-4 iterations), step-up, slope limit, ground snap, coyote time and jump buffering.
## Animation
- Skeletal: local joint transforms -> model space once per frame; linear blend skinning (dual quaternion skinning avoids twist collapse).
- Blending: cross-fade per joint with nlerp (fix the quaternion hemisphere first), additive layers (pose minus reference), masked layers (upper body). Blend weights sum to 1.
- Blend spaces/trees driven by speed and direction with phase sync; animation state machines with layered or hierarchical structure.
- Root motion (animation moves the character, no sliding) vs in-place (gameplay moves it, responsive; fix sliding with stride warping).
- IK: analytic two-bone IK (law of cosines) for limbs; FABRIK or CCD for chains; foot placement via ground raycasts; look-at with joint limits (swing-twist).
- Motion matching searches mocap for the pose plus future trajectory that best fits the desired path, then blends.
- Animation events can trigger effects, but damage and hit windows are decided by authoritative gameplay timing, not by client animation playback.
## Answer checklist
Classify the question (correctness bug, performance bound, design choice), list the deciding variables (light count, transparency, platform, dynamic vs static, determinism) and check spaces, units, dt and normalisation before deeper theories.
