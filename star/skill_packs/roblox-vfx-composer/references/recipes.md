# VFX technique recipes (Luau, client side)

Each recipe is what a primitive in luau/VfxPrimitives.luau does, reduced to its core. `speed` is the playback speed
(1 = real time); every duration is divided by it and emitters get `TimeScale = speed`, so the same code runs in slow
motion for frame review.

## Particle burst (one-shot)
```luau
local e = Instance.new("ParticleEmitter")
e.Enabled = false; e.Rate = 0
e.Texture = style.textures.spark; e.Color = ColorSequence.new(style.palette.accent)
e.LightEmission = 1; e.LightInfluence = 0 -- additive glow, ignores world light
e.Speed = NumberRange.new(30, 60); e.Lifetime = NumberRange.new(0.3, 0.5); e.Drag = 4
e.Orientation = Enum.ParticleOrientation.VelocityParallel -- streaks
e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 0) })
e.Squash = NumberSequence.new(-1.5) -- stretch along the velocity
e.TimeScale = speed
e.Parent = attachment
e:Emit(count)
Debris:AddItem(attachment, 0.5 / speed + 0.25)
```

## Flat ground ring / crack decal
One particle, `Orientation = VelocityPerpendicular`, `EmissionDirection = Top`, `Speed = 0.01`: it lies flat.
Grow `Size` from ~1 to 2x the radius over its life, fade `Transparency` 0 -> 1. A crack decal is the same with
`LightEmission = 0` and the palette's dark colour (a dark particle renders dark).

## Shockwave of segments (mesh-like, no asset)
N thin blocks on a circle; tween each CFrame outward and its Size from a short to a long arc; tween Transparency to 1
with the style's ease-in. Jagged styles tilt each segment randomly (shards); pixel styles use fewer, stepped moves.

## Shell / dome
Ball part, CanCollide/CanQuery/CanTouch false, `Material = ForceField` for energy (rim glow, see-through) or
SmoothPlastic at 0.35 transparency for soft styles; tween Size up and Transparency to 1.

## Pillar (scrolling beams)
Attachments at the ground and `height` above; two Beams (core: streak texture, TextureSpeed 2.5; glow: soft texture,
TextureSpeed -1.2, wider), `TextureMode = Wrap`, `TextureLength = height / 3`, FaceCamera. Tween Width0/Width1 from
0.2 to full in 0.15 s, hold, tween to 0. Add a vertical Neon cylinder core and a translucent sleeve for readability.

## Vortex
A held ForceField shell plus an invisible spinner part; pairs of attachments at the radius on random tilted planes,
a Trail between each pair; every Heartbeat set the spinner CFrame (yaw and some pitch) and pull the attachments
inward (spiral). Trail Lifetime ~0.3 / speed.

## Ground crack and debris (raycast + own physics)
Raycast down from the impact (exclude the effect folder and the caster). Glowing crack: a few jagged polylines of thin
Neon blocks growing outward. Debris: blocks that copy the hit part's Color and the hit Material, thrown outward and
up; each Heartbeat: `v -= gravity * dt`, raycast the step, bounce with damping on a hit, then
`workspace:BulkMoveTo(parts, cframes, Enum.BulkMoveMode.FireCFrameChanged)`. Fade and shrink at the end.

## Aura
`Highlight` (FillColor glow, OutlineColor core, DepthMode Occluded, Adornee = character) tweened in and out, a short
continuous emitter rising from the feet, and an inward burst from a sphere shell (`Shape = Sphere`,
`ShapeStyle = Surface`, `ShapeInOut = Inward`).

## Screen flash and inverted frame
Inverted frame: `ColorCorrectionEffect` under Lighting with Saturation -1 and Contrast -2 for ~0.07 s (observed in
Studio to give a grey negative). Then a full-screen Frame in the palette's flash colour fading from 1 - strength to
1. Bloom kick: a BloomEffect whose Intensity tweens to 0. Tint: ColorCorrection TintColor lerped toward the glow for
the length of the effect, then back to white.

## Camera shake and FOV punch
```luau
RunService:BindToRenderStep(name, Enum.RenderPriority.Camera.Value + 2, function()
	local t = (os.clock() - started) * speed
	if t > life then RunService:UnbindFromRenderStep(name) return end
	local decay = (1 - t / life) ^ 2
	local x = math.noise(seed, t * freq) * amp * decay
	local y = math.noise(seed + 10, t * freq) * amp * decay
	camera.CFrame *= CFrame.new(x, y, 0)
end)
```
Default camera scripts reset the camera every frame (priority 200), so the offset never accumulates; a game with a
Scriptable camera must set its CFrame each frame before Camera + 2.

## Timing
Anticipation (charge) 0.5-0.9 s, impact 0.1-0.25 s, shockwave 0.45-0.7 s, linger 0.5-1.1 s, dissipate 0.5-1.6 s.
Never start every layer on the impact frame: stagger by 0.03-0.2 s. Reserve the biggest contrast for the hit.

## Server path
Client: `remote:FireServer("energy_burst", "anime_energy")`. Server: type/length checks, allow lists, cooldown,
token bucket, origin from the server's own HumanoidRootPart, `FireClient` to nearby players with
`(ability, style, originCFrame, casterUserId, seed, speed)`. Client: check types and known names, then
`Composer.play`.
