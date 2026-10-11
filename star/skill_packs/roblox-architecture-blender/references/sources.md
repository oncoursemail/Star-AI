# Grounding sources for roblox-architecture-blender

Reviewed public Creator Hub pages on 2026-10-11; API names not yet verified by STAR Knowledge /api-lookup in this change. The official public docs below support the cited workflows, not the aesthetic quality of generated meshes.

- Blender / Studio unit, axis and export settings: https://create.roblox.com/docs/art/blender
- Importing DCC assets: https://create.roblox.com/docs/art/overview-dcc
- Custom 3D meshes: https://create.roblox.com/docs/art/modeling
- Studio Reimport naming: https://create.roblox.com/docs/art/modeling/reimport
- Blender plugin via Open Cloud: https://create.roblox.com/docs/art/modeling/roblox-blender-plugin
- Reusable facade building kits: https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments
- PBR maps: https://create.roblox.com/docs/art/modeling/surface-appearance
- Texture specifications: https://create.roblox.com/docs/art/modeling/texture-specifications
- Performance optimization: https://create.roblox.com/docs/performance-optimization/improve
- Blender Python glTF operator (not a Roblox API): https://docs.blender.org/api/current/bpy.ops.export_scene.html

Related API names to verify in the installed tools before native integration: MeshPart, SurfaceAppearance, Model:PivotTo, BasePart.CanCollide, MeshPart.CollisionFidelity, Model.LevelOfDetail and Workspace.StreamingEnabled. The prototype's Blender API calls are in `scripts/blender_building.py`.
