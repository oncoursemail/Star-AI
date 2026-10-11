---
name: roblox-vfx
description: Roblox visual effects: ParticleEmitter, Beam, Trail and Attachments, burst versus continuous emission, shaping over life, layering effects in time, limits and cleanup.
---
# Visual effects (ParticleEmitter, Beam, Trail)
- Beams and trails need Attachments. Beam: Attachment0, Attachment1, Width0, Width1, Segments, FaceCamera = true (a flat strip), LightEmission for glow. Trail: Attachment0 and Attachment1 on the moving part, Lifetime, MinLength, Transparency and Color sequences; enabled only while moving. A ParticleEmitter sits in a Part or an Attachment.
- One-shot burst: Rate = 0 and emitter:Emit(count). Continuous: Rate with Enabled. Docs limits: at most 400 particles per second per emitter (100 on mobile), Lifetime capped at 20 s; keep Rate, Lifetime and Size low and avoid stacked large transparent layers (overdraw costs the GPU).
- Shape a particle's life with NumberSequence (Size, Transparency) and ColorSequence; LightEmission = 1 for fire and sparks; Speed, SpreadAngle, Drag, Acceleration for motion. Layer an effect in time: anticipation flash, impact, debris and smoke, ember tail.
- Clean up with Debris:AddItem(part, seconds) or task.delay then :Destroy(); cap concurrent effects and reuse emitters. There is no ParticleEmitter.Burst property.
