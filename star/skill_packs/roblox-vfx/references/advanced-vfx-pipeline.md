# STAR Advanced Roblox VFX — editable cinematic effects

Use this deeper reference when the user requests intricate combat effects, magic, anime moves, destruction, camera choreography, or a specific VFX video. This is procedural design advice, not evidence that the current STAR installation can author or export these visuals.

## Frame analysis contract

For each approved video/image reference, write an observation sheet:
- Source and usage rights; timestamps actually inspected; playback speed and frames skipped.
- At each meaningful beat: focal subject, silhouette, foreground/midground/background layers, dominant colors, object movement, motion blur appearance, camera movement, sound/transient cue, and uncertainty.
- Difference between observed on-screen geometry and hypothesized implementation. A bright aura is not evidence of a shader, a mesh or any particular Roblox API.
- Seek one base camera angle and two counterviews before modeling motion; effects with good front views can fail badly side-on.

An attack should have *readability first*. Example 2.4s authored timing (illustrative, not universal):

| Seconds | Character | Effects | Sound and camera |
| --- | --- | --- | --- |
| 0.00–0.35 | Brace, weight transfer | Subtle inward motes | Quiet rise, stable view |
| 0.35–0.85 | Wind-up and hold | Spiral ribbons, contraction | Pitch lift, slight zoom |
| 0.85–1.05 | Snap/extreme | Directional slash and one bright flash | Single transient on contact |
| 1.05–1.40 | Hold-through | Distinct impact ring, fragments, burst | Low hit + restrained shake |
| 1.40–2.40 | Recover | Smoke/embers taper, ring disappears | Tail and camera settle |

Avoid instant simultaneous flash, ring, sparks, fragments and giant trail all at the first frame: that makes every layer compete for attention. Reserve largest contrast for gameplay contact.

## Native building blocks (verified; choose by function)

- **ParticleEmitter**: fire, sparks, smoke, dust, magical motes and spritesheet flips. Rate=0 plus Emit(n) for authored short events; Enabled and Rate for steady emission. Control speed, drag, rotation, size/alpha over life, velocity inheritance and lifetime. See https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter and https://create.roblox.com/docs/effects/particle-emitters .
- **Beam**: textured line or curved ribbon between Attachment0 and Attachment1. Align attachments, inspect FaceCamera requirements and Segments. Curvature responds to attachment orientations. See https://create.roblox.com/docs/effects/beams .
- **Trail**: textured slash/wake between two *moving* attachments. Width derives from their separation; lifetime determines streak length. See https://create.roblox.com/docs/effects/trails .
- **MeshPart + SurfaceAppearance**: bespoke slash silhouettes, crystallized aura geometry, environment-specific bursts; export authored meshes (FBX/glTF) from Blender with UVs, normals, pivots and texture budget. See https://create.roblox.com/docs/parts/meshes .
- **Light sources**: localized flashes (PointLight/SpotLight/SurfaceLight), never permanent extreme brightness as a substitute for effect design. See https://create.roblox.com/docs/effects .
- **Post-processing**: Lighting- or Camera-scoped BloomEffect, ColorCorrectionEffect, BlurEffect, DepthOfFieldEffect and friends. Do not invent arbitrary runtime HLSL/GLSL injection as a Roblox Luau feature. See https://create.roblox.com/docs/environment/post-processing-effects .
- **Sound**: edit and normalize separate buildup, release, impact and dissipate clips with legitimate source rights; trigger exact audio cues using animation markers.

### The actual layering method

1. Define the gameplay semantic signal: charging, firing, hit confirmed, lingering hazard, or purely ambient. VFX must not determine server-authoritative hit validation.
2. Form **large composition** from one or two visually distinctive meshes or beams. Inspect grayscale and silhouette against the environment before adding particles.
3. Add **secondary motion** with low-rate textured emitters, not arbitrary glowing balls. Define what each particle represents physically: sparks fall, embers rise, smoke expands/drifts, impact fragments travel outward and down.
4. Vary scale intentionally: dominant primary effect, supporting directional accents, tiny micro-sparks.
5. Time offsets by layer, not all at 0ms. Build named cue markers such as Windup, Release, Impact and Recover.
6. Animate dissipations. Ending abruptly is a quality defect; a particle whose parent is destroyed before it can expire is also a quality defect.
7. Distinguish independent client-side quality tiers from server game state. Use bounded effect concurrency and cleanup.
8. Capture comparison at the impact frame, at its predecessor and at the tail; verify multiple lighting conditions and graphics quality levels.

## Example Luau *presentation* controller

This assumes an artist-created Model named ShockwaveTemplate in ReplicatedStorage; the model contains a correctly anchored pivot/base part, attachments, and optional ParticleEmitters. It does NOT create meshes, animations, textures or gameplay damage.

~~~luau
--!strict
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")

local template = ReplicatedStorage:WaitForChild("ShockwaveTemplate")
assert(template:IsA("Model"), "Expected an editable Model template")

local function showImpact(worldCFrame: CFrame)
    local effect = template:Clone()
    effect:PivotTo(worldCFrame)
    effect.Parent = workspace

    for _, child in effect:GetDescendants() do
        if child:IsA("ParticleEmitter") then
            child.Enabled = false
            child.Rate = 0
            child:Emit(16)
        end
    end

    -- Set for the longest configured emitter lifetime + safety tail.
    Debris:AddItem(effect, 3)
end

return showImpact
~~~

This is a small code example, not a complete plug-and-play combat ability; the input must come from a trusted visual cue with server-validated gameplay, and three seconds must be adjusted to the selected emitter's actual Lifetime range.

## Performance and cleanup checks

- Profile actual target hardware; a Studio emulator is insufficient to prove phone GPU behavior. Follow https://create.roblox.com/docs/performance-optimization/design .
- Transparency overdraw is usually more important than how many mesh parts the designer can see. Multiple screen-filling soft particles can be visually simple and extremely expensive.
- Avoid high-rate continuous emitters for one-off impacts; inspect maximum concurrently active attacks, camera proximity and transparent overlap.
- Beware texture bloat and many unique materials preventing batching/instancing. Reuse textures and shapes with controlled hue/scale changes.
- Pool only when profiling shows allocation/destruction overhead matters; pooled objects still need canceled animation/tween connections and full state reset.
- Clean event subscriptions, orphaned attachments, lights and sounds when a character respawns, action cancels, target disappears or user leaves.
- Client VFX can be reduced based on device settings without weakening authoritative damage validation.
- Check that the same effect still reads at low graphics quality; beam/trail quality can differ by rendering settings.

## Quality acceptance evidence

Minimum attachment to a review request:
- The approved reference and observed time range.
- Native edited object hierarchy + source texture/mesh filenames, licensing manifest.
- A short actual Studio playback or several labelled frame captures for charge/release/contact/recovery.
- Test with 1, 5 and 10 simultaneous active instances if the gameplay permits them; measured client frame time/memory with exact devices.
- Observed defects and next iteration, especially missing cues, abrupt cuts, excessive bloom, weak silhouette, incorrect hand offsets and performance spikes.
- An explicit statement if no Studio playback/screenshot was actually performed.

Reference learning: Roblox VFX use-case tutorials https://create.roblox.com/docs/tutorials/use-case-tutorials/use-case-tutorial-overview ; free CC0 alpha spritesheet example https://opengameart.org/content/animated-particle-effects-1 ; individual CC0 magical light alpha texture example https://opengameart.org/content/light-magic-effect ; Roblox Creator Store https://create.roblox.com/docs/production/creator-store (model scripts and rights need inspection).
