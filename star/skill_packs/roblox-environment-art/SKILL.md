---
name: roblox-environment-art
description: Reference-driven Roblox environment art, lighting, foliage motion, PBR architecture and screenshot quality review.
---
# Roblox environment art direction
- Read the actual image first: camera/FOV, focal landmark, foreground/midground/background, palette, value-grouping, scale, materials and negative space. Keep the reference separate from reusable licensed source assets. Do not infer hidden geometry or exact lighting settings from one shot.
- Greybox walkability and sightlines before polishing. Design modular architecture with consistent scale/pivots; use Blender assets, authored UV/trim sheets and tested SurfaceAppearance maps. Avoid decorative part clutter or unverified asset IDs.
- Light intentionally: global ambient/time/shadows, Atmosphere for distance, local point/spot/surface lights from plausible sources and restrained post-processing. A bright emissive mesh is not a replacement for a motivated local light. Recheck low/high graphics quality.
- Workspace.GlobalWind moves terrain grass and clouds, not custom foliage meshes automatically. Rig/skinning required for per-tree Bone.Transform sway; use client-side bounded updates, artist-authored bone weights, camera culling and a reduced-motion alternative.
- Layer particles, beams and trails where appropriate, including matching attachment topology, coherent timing and GPU overdraw limits. UI stays native, responsive, accessible and visibly aligned.
- Run offline reference inspect/compare for screenshot proxies, or preview lighting and foliage Luau for explicit review. These helpers never edit Studio. Inspect geometry, multi-angle views, mesh import, performance, material rights and interaction separately.
- Stop before changing a place without the owner's existing scoped consent. Keep a before/after capture and test log; feed only explicitly reviewed and licensed examples into STAR's learning pipeline, never auto-train from scraped artist images.
