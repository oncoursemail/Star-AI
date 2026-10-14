# Sources for roblox-editable-memory-streaming

Written 2026-10-13. The field evidence comes from the owner's private Paintball port project (Roblox Studio,
September and October 2026). It was read only and rewritten as general lessons; no game assets or code were copied. The
official pages are from the Roblox Creator Documentation (CC-BY-4.0), found through the STAR Knowledge index. The
editable memory budget depends on the device, and the project's figures come from one PC.

| Label | Evidence |
|---|---|
| F1 | Project ROBLOX_IMPORT_LIMITS_2026.md (September 24 check): the first live test used up the dynamic editable budget; creating copies one at a time with fixed sizes fixed it |
| F2 | Project CODEX_BRIEFING.md and handoff log: preallocated fade copies used about 24 of 80 MiB; holding first-person and third-person avatar copies made the second player's avatar fail; the fix was one shared core plus extras |
| F3 | Project RIVER_NORMAL_RUNTIME_FIXES_QA.md: keep finished avatar buffers across death; keep collision loaded near unanchored bodies at rest |
| F4 | Project BEST_SOLUTIONS_RESEARCH_CLAUDE.md: SurfaceAppearance TintMask instead of one image per team; batched EditableMesh writes; constant maps generated at runtime |
| F5 | Project OPT_OPT_STREAMING_20261008.md and RIVER_TERRAIN_EDIT_REPARENT_QA.md: Persistent only for small critical models (about 1.7% of map parts), Atomic pickups, subscribe before scanning, workspace streaming properties set in the Properties panel |
| S1 | https://create.roblox.com/docs/reference/engine/classes/EditableMesh |
| S2 | https://create.roblox.com/docs/reference/engine/classes/EditableImage |
| S3 | https://create.roblox.com/docs/art/modeling/surface-appearance |
| S4 | https://create.roblox.com/docs/reference/engine/classes/AssetService |
| S5 | https://create.roblox.com/docs/workspace/streaming |
| S6 | https://create.roblox.com/docs/reference/engine/classes/CollectionService |

API names verified with the knowledge service /api-lookup on 2026-10-13: AssetService:CreateEditableMeshAsync,
AssetService:CreateEditableImage, EditableImage:WritePixelsBuffer, EditableImage.Size, Content.fromObject,
MeshPart.MeshContent, ImageLabel.ImageContent, SurfaceAppearance.AlphaMode, SurfaceAppearance.Color, Enum.AlphaMode,
EditableMesh:BatchSetValues, Model.ModelStreamingMode, Enum.ModelStreamingMode, CollectionService:GetInstanceAddedSignal,
CollectionService:GetTagged, RunService:IsServer, Vector2.zero.
