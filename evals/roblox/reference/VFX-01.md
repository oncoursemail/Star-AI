```luau
--!strict
local Debris = game:GetService("Debris")

local HitEffect = {}
local MAX_LIFE = 0.45

function HitEffect.play(position: Vector3)
	local part = Instance.new("Part")
	part.Name = "HitSpark"
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.Transparency = 1
	part.Size = Vector3.new(0.2, 0.2, 0.2)
	part.Position = position

	local attachment = Instance.new("Attachment")
	attachment.Parent = part

	local emitter = Instance.new("ParticleEmitter")
	emitter.Rate = 0 -- never emits on its own; we call :Emit once
	emitter.Lifetime = NumberRange.new(0.2, MAX_LIFE) -- short lived sparks
	emitter.Speed = NumberRange.new(20, 40) -- studs per second
	emitter.SpreadAngle = Vector2.new(180, 180) -- all directions
	emitter.Drag = 4 -- sparks slow down
	emitter.LightEmission = 1 -- additive glow
	emitter.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.5), NumberSequenceKeypoint.new(1, 0) }) -- shrink
	emitter.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0),
		NumberSequenceKeypoint.new(0.7, 0.2),
		NumberSequenceKeypoint.new(1, 1),
	}) -- fade out
	emitter.Color = ColorSequence.new(Color3.fromRGB(255, 244, 200), Color3.fromRGB(255, 120, 20)) -- white-yellow to orange
	emitter.Parent = attachment

	part.Parent = workspace
	emitter:Emit(20)
	Debris:AddItem(part, MAX_LIFE + 0.1)
end

return HitEffect
```
