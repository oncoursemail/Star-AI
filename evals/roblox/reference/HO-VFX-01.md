Points are validated first, so a bad list creates nothing. Each point gets an invisible anchored part with an attachment; each gap gets a `Beam` parented to its starting part, so scheduling the parts with `Debris` removes the beams with them.

```luau
--!strict
local Debris = game:GetService("Debris")

local Chain = {}

local LIFETIME = 0.4

function Chain.zap(parent: Instance, points: { Vector3 }): { Beam }
	for _, point in points do
		if typeof(point) ~= "Vector3" then
			error("every point must be a Vector3")
		end
	end

	local beams: { Beam } = {}
	if #points < 2 then
		return beams
	end

	local parts: { Part } = {}
	local attachments: { Attachment } = {}
	for index, point in points do
		local part = Instance.new("Part")
		part.Name = "ZapPoint" .. index
		part.Anchored = true
		part.CanCollide = false
		part.Transparency = 1
		part.Size = Vector3.new(0.2, 0.2, 0.2)
		part.Position = point
		part.Parent = parent

		local attachment = Instance.new("Attachment")
		attachment.Parent = part

		parts[index] = part
		attachments[index] = attachment
	end

	for index = 1, #points - 1 do
		local beam = Instance.new("Beam")
		beam.Attachment0 = attachments[index]
		beam.Attachment1 = attachments[index + 1]
		beam.Color = ColorSequence.new(Color3.fromRGB(120, 200, 255))
		beam.Width0 = 0.6
		beam.Width1 = 0.2
		beam.Segments = 12
		beam.FaceCamera = true
		beam.LightEmission = 1
		beam.Transparency = NumberSequence.new(0.1)
		beam.Parent = parts[index]
		table.insert(beams, beam)
	end

	for _, part in parts do
		Debris:AddItem(part, LIFETIME)
	end
	return beams
end

return Chain
```
