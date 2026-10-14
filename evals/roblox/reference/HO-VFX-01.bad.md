One part and attachment per segment, beams under the parent, cleanup with a delayed Destroy.

```luau
local Chain = {}

function Chain.zap(parent: Instance, points: { Vector3 }): { Beam }
	local beams = {}
	for i = 1, #points - 1 do
		local a = Instance.new("Attachment")
		a.WorldPosition = points[i]
		a.Parent = workspace.Terrain
		local b = Instance.new("Attachment")
		b.WorldPosition = points[i + 1]
		b.Parent = workspace.Terrain

		local beam = Instance.new("Beam")
		beam.Attachment0 = a
		beam.Attachment1 = b
		beam.Color = ColorSequence.new(Color3.fromRGB(120, 200, 255))
		beam.Width0 = 0.6
		beam.Width1 = 0.2
		beam.Parent = parent
		table.insert(beams, beam)

		task.delay(0.4, function()
			beam:Destroy()
		end)
	end
	return beams
end

return Chain
```
