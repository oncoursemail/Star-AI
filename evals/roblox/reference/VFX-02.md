```luau
--!strict
local function attach(part: BasePart, offset: Vector3): Attachment
	local a = Instance.new("Attachment")
	a.Position = offset
	a.Parent = part
	return a
end

local function makeBeam(a: BasePart, b: BasePart): Beam
	local beam = Instance.new("Beam")
	beam.Attachment0 = attach(a, Vector3.zero)
	beam.Attachment1 = attach(b, Vector3.zero)
	beam.Width0 = 0.15
	beam.Width1 = 0.15
	beam.Segments = 10
	beam.FaceCamera = true
	beam.LightEmission = 1
	beam.Color = ColorSequence.new(Color3.fromRGB(255, 40, 40))
	beam.Parent = a
	return beam
end

local function makeTrail(handle: BasePart): Trail
	local base = attach(handle, Vector3.new(0, 0, -2))
	local tip = attach(handle, Vector3.new(0, 0, 2))
	local trail = Instance.new("Trail")
	trail.Attachment0 = base
	trail.Attachment1 = tip
	trail.Lifetime = 0.25
	trail.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1) })
	trail.Color = ColorSequence.new(Color3.fromRGB(255, 255, 255), Color3.fromRGB(120, 200, 255))
	trail.LightEmission = 0.8
	trail.Enabled = false
	trail.Parent = handle
	return trail
end

local function swing(trail: Trail, duration: number)
	trail.Enabled = true
	task.delay(duration, function()
		trail.Enabled = false
	end)
end

return { makeBeam = makeBeam, makeTrail = makeTrail, swing = swing }
```
