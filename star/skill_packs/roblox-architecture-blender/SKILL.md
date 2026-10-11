---
name: roblox-architecture-blender
description: Design Roblox buildings with architectural composition and use a controlled Blender-to-Studio mesh workflow.
---
# Architectural design and Blender for Roblox
- Begin with purpose, human/rig scale, silhouette, massing, entrances, roof/load paths, rooms and circulation; use real approved references, not random shapes.
- Choose one coherent art grammar: storybook, industrial, modern or sci-fi. Define facade bays, hierarchy, window rhythm, material transitions and plausible trim before details.
- For an exterior starter kit, validate a JSON brief with `python -m star.architecture_pipeline <brief.json> --out <new-folder>`; the optional `--blender <installed executable>` runs STAR's fixed generator and writes .blend/.glb. No model-written Python.
- Inspect in Blender, import glTF using Studio 3D Importer and verify scale/orientation, normals, openings and avatar access. Reimport using stable names.
- Review collisions, textured PBR, mesh reuse and device performance. A palette prototype is NOT finished game art; require screenshots, playtests and human visual acceptance.
