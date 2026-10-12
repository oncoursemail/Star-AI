# Sources for roblox-environment-art

Roblox Creator Hub pages independently read online on 2026-10-11. Source material is guidance, not permission to import third-party works or execute new scripts.

| Subject | Official source |
| --- | --- |
| Global lighting | https://create.roblox.com/docs/environment/lighting |
| Atmosphere | https://create.roblox.com/docs/environment/atmosphere |
| Post effects | https://create.roblox.com/docs/environment/post-processing-effects |
| GlobalWind scope | https://create.roblox.com/docs/environment/global-wind |
| Bone Transform | https://create.roblox.com/docs/reference/engine/classes/Bone/Transform |
| Modular environment construction | https://create.roblox.com/docs/tutorials/use-case-tutorials/modeling/assemble-modular-environments |
| Import mesh and skins | https://create.roblox.com/docs/studio/importer |
| PBR materials | https://create.roblox.com/docs/art/modeling/surface-appearance |
| Effects | https://create.roblox.com/docs/effects |
| Responsive UI | https://create.roblox.com/docs/ui/size-modifiers |
| Rendering costs | https://create.roblox.com/docs/performance-optimization/improve |

API names checked against pages above: Lighting.ClockTime, Lighting.Brightness, Lighting.ExposureCompensation, Lighting.Ambient, Lighting.OutdoorAmbient, Atmosphere.Density/Haze/Glare/Color/Decay, ColorCorrectionEffect.Contrast/Saturation/TintColor, BloomEffect.Intensity/Size/Threshold, Workspace.GlobalWind, Bone.Transform, CollectionService:GetTagged/GetInstanceAddedSignal/GetInstanceRemovedSignal, RunService.Heartbeat, Model:GetPivot, and Instance:GetAttribute. Several shared lighting APIs were previously verified with the knowledge service /api-lookup in the existing roblox-building-layout sources; this new pack's independent online verification is not a fresh knowledge-service run. Keep this pack opt-in until the eval gate approves it.
