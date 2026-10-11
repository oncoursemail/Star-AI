Pillars on a circle around the center, using world axes.

```luau
local Ring = {}

function Ring.cframes(center: CFrame, radius: number, count: number): { CFrame }
	local result = {}
	for i = 1, count do
		local angle = (i - 1) * 360 / count
		local x = radius * math.cos(angle)
		local z = radius * math.sin(angle)
		local position = center.Position + Vector3.new(x, 0, z)
		result[i] = CFrame.new(position, position + (position - center.Position))
	end
	return result
end

return Ring
```
