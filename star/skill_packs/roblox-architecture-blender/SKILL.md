---
name: roblox-architecture-blender
description: Plan Roblox architecture and generate a bounded Blender-to-Studio exterior prototype.
---
# Architectural design and Blender for Roblox
- Start from purpose, avatar scale, room circulation, silhouette, roof logic and approved references; do not add random shapes.
- Choose an intentional art grammar: storybook, industrial, modern, spaceport, gothic, brutalist, coastal or anime city. Real design requires more than palette changes.
- Use `star_architecture_preview` for an honest read-only plan. To make files, the owner runs `python -m star.architecture_pipeline <brief.json> --out <new-folder> --blender <exe>`; `--preview` adds a Workbench screenshot.
- Inspect the audit, asset manifest and collision hints. They are candidates, not verified Studio colliders. Never execute model-written Blender scripts.
- Use Studio Importer to check scale, axes, visual results and avatar access. Review materials, mesh reuse and device metrics. No 'finished' or AAA claim without evidence.
