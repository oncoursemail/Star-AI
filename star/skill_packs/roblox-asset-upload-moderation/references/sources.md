# Sources for roblox-asset-upload-moderation

Written 2026-10-13. The field evidence comes from the owner's private Paintball port project (Roblox Studio,
September and October 2026). It was read only and rewritten as general lessons; no game assets, asset IDs or code were
copied. The official pages are from the Roblox Creator Documentation (CC-BY-4.0), found through the STAR Knowledge
index. Roblox never confirmed which part of an image caused each removal. The barcode ban was the project's own rule,
not a stated Roblox policy.

| Label | Evidence |
|---|---|
| F1 | Project AGENTS.md upload rules and the asset-review agent: inspect the actual pixels, including rotated atlas text; reject links, codes, all barcodes, handles and off-platform instructions; approve by exact hash; check every returned ID; stop on moderation or account errors |
| F2 | Project ASSET_UPLOAD_RULES.md: two atlases were removed for "Directing Users Off-Platform" with no visible URL (they showed packaging text, barcodes and part numbers); a one-pixel map was blocked; a single retry returned the same blocked asset; a decal's thumbnail showed Completed while its image was blocked; constant maps were then built at runtime instead |
| F3 | Project PB_GATE_REVIEW.md: review sheets on white and black, rotated, contrast-boosted, with an alpha view and full tile coverage; a blocked hash overrides approval |
| S1 | https://create.roblox.com/docs/projects/assets |
| S2 | https://create.roblox.com/docs/reference/engine/classes/AssetService |
| S3 | https://create.roblox.com/docs/reference/engine/classes/EditableImage |
| S4 | https://create.roblox.com/docs/reference/engine/classes/ContentProvider |
| S5 | https://create.roblox.com/docs/reference/engine/enums/AssetFetchStatus |
| S6 | https://create.roblox.com/docs/marketplace/moderation |

API names verified with the knowledge service /api-lookup on 2026-10-13: AssetService:CreateEditableImageAsync,
AssetService:CreateEditableImage, Content.fromUri, Content.fromObject, EditableImage:WritePixelsBuffer,
EditableImage:Destroy, EditableImage.Size, ContentProvider:PreloadAsync, Enum.AssetFetchStatus, Sound.TimeLength.
