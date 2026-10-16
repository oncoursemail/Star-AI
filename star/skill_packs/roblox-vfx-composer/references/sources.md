# Sources for roblox-vfx-composer

Official Roblox Creator Documentation (CC-BY-4.0) and the creator-docs source repository; community techniques are
marked as such. Read on 2026-10-14.

| Claim in the skill | Source |
|---|---|
| ParticleEmitter properties (TimeScale 0..1, Squash, Flipbook*, Orientation incl. VelocityPerpendicular, ShapeInOut, LightEmission 0 normal / 1 additive, LightInfluence, ZOffset, Emit) | https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter |
| Particle emitters guide (burst vs continuous, shaping over life, flipbooks) | https://create.roblox.com/docs/effects/particle-emitters |
| Beams (attachments, FaceCamera, TextureMode, TextureSpeed, widths, curves) | https://create.roblox.com/docs/effects/beams |
| Trails (two moving attachments, Lifetime, WidthScale) | https://create.roblox.com/docs/effects/trails |
| Highlight (DepthMode AlwaysOnTop / Occluded; Studio shows at most 255 at once, extras ignored) | https://create.roblox.com/docs/reference/engine/classes/Highlight |
| ColorCorrectionEffect (Brightness -1..1, Contrast below 0 reduces contrast, Saturation -1 full desaturation, TintColor multiplies; works only under Lighting or the current camera) | https://create.roblox.com/docs/reference/engine/classes/ColorCorrectionEffect |
| Post-processing effects (Bloom, ColorCorrection, Blur, DepthOfField) | https://create.roblox.com/docs/environment/post-processing-effects |
| TweenService and TweenInfo easing | https://create.roblox.com/docs/reference/engine/classes/TweenService |
| RunService:BindToRenderStep priorities (camera controls at 200; lower runs first), RenderStepped superseded by PreRender | https://create.roblox.com/docs/reference/engine/classes/RunService |
| Debris:AddItem | https://create.roblox.com/docs/reference/engine/classes/Debris |
| WorldRoot:BulkMoveTo | https://create.roblox.com/docs/reference/engine/classes/WorldRoot |
| Remote events and server validation | https://create.roblox.com/docs/scripting/events/remote |
| Open Cloud Assets API (Decal/Image upload, multipart request + fileContent, operations, moderation result) | https://create.roblox.com/docs/cloud/guides/usage-assets |
| Community: meshes plus tweening as the common spell-VFX method | https://devforum.roblox.com/t/how-to-make-spells/411488 |
| Community: VFX tutorial (cylinder mesh shockwave in Blender, particles) | https://devforum.roblox.com/t/vfx-tutorial-roblox/872437 |

Contrast -2 as an inversion: the documentation only says that negative values reduce contrast. That -2 maps a value
c to 1 - c (a full inversion; with Saturation -1 a grey negative) is STAR's own observation from Studio captures
(docs/agents/roblox-vfx-20261013/iter1b, frame 11), not a documented guarantee.

API names verified with the knowledge service /api-lookup on 2026-10-14 (all found, none deprecated):
ParticleEmitter.TimeScale, ParticleEmitter.Squash, ParticleEmitter.FlipbookLayout, ParticleEmitter.ShapeInOut,
ParticleEmitter:Emit, Enum.ParticleOrientation.VelocityPerpendicular, Enum.ParticleFlipbookMode.OneShot,
Enum.ParticleEmitterShapeInOut.Inward, Highlight.DepthMode, ColorCorrectionEffect.Contrast, BloomEffect.Intensity,
Beam.TextureSpeed, Trail.Lifetime, Trail.WidthScale, RunService:BindToRenderStep, Enum.RenderPriority.Camera,
WorldRoot:BulkMoveTo, Enum.BulkMoveMode.FireCFrameChanged, Debris:AddItem, InsertService:LoadAsset,
TweenService:Create, Camera.FieldOfView, Random:NextUnitVector, UserGameSettings.SavedQualityLevel.
