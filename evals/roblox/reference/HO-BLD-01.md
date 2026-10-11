The offsets are built in the center's local space and then multiplied by the center CFrame, so rotating or moving the center moves the whole ring. `CFrame.lookAt` turns each element to face the center.

```luau
--!strict
local Ring = {}

function Ring.cframes(center: CFrame, radius: number, count: number): { CFrame }
	if type(count) ~= "number" or count ~= math.floor(count) or count < 1 or count == math.huge then
		error("count must be a positive whole number")
	end
	if type(radius) ~= "number" or radius ~= radius or radius <= 0 or radius == math.huge then
		error("radius must be a positive finite number")
	end

	local result: { CFrame } = {}
	for i = 1, count do
		local theta = 2 * math.pi * (i - 1) / count
		local localOffset = Vector3.new(radius * math.sin(theta), 0, -radius * math.cos(theta))
		local position = center * localOffset
		result[i] = CFrame.lookAt(position, center.Position)
	end
	return result
end

return Ring
```
