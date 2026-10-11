# Sources for roblox-building-layout

Official Roblox Creator Documentation (CC-BY-4.0), checked against the STAR Knowledge index (creator-docs af5f853).

| Claim in the skill | Documentation page |
|---|---|
| Models: moving models, PrimaryPart, PivotTo | https://create.roblox.com/docs/parts/models |
| Pivot tools: GetPivot, PivotTo, PivotOffset | https://create.roblox.com/docs/studio/pivot-tools |
| Global lighting: ClockTime, ambient | https://create.roblox.com/docs/environment/lighting |
| Post-processing effects: Bloom, Color correction | https://create.roblox.com/docs/environment/post-processing-effects |
| Assemble modular environments tutorial | https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments |
| Character body specifications (scale in studs) | https://create.roblox.com/docs/avatar/character-bodies/specifications |
| Atmosphere reference | https://create.roblox.com/docs/reference/engine/classes/Atmosphere |
| Lighting reference (Technology is non-scriptable) | https://create.roblox.com/docs/reference/engine/classes/Lighting |

API names verified with the knowledge service /api-lookup on 2026-10-11: PVInstance:PivotTo, PVInstance:GetPivot, Model:PivotTo, Lighting.ClockTime, Lighting.Brightness, Lighting.Ambient, Lighting.OutdoorAmbient, Lighting.ExposureCompensation, Atmosphere (Density, Offset, Color, Decay, Glare, Haze), BloomEffect (Intensity, Size, Threshold), ColorCorrectionEffect (Brightness, Contrast, Saturation, TintColor), SunRaysEffect, BasePart (Anchored, Size, CFrame, Material, CanCollide), Terrain:FillBlock, StudioService.GridSize. /api-lookup reports Model:SetPrimaryPartCFrame and Lighting.Technology as DEPRECATED; the Lighting page says Technology is non-scriptable and only modifiable in Studio. Character height of about 5 studs is the usual R15 figure; the body-specification page lists limits per body scale, so treat 5 studs as a rule of thumb.
