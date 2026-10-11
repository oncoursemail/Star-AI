```luau
--!strict
local function snap(value: number, grid: number): number
	return math.floor(value / grid) * grid
end
local function snapPoint(p, grid)
	p.x = snap(p.x, grid)
	p.y = snap(p.y, grid)
	p.z = snap(p.z, grid)
	return p
end
local function layoutWall(length: number)
	local out = {}
	local offset = 0
	while offset < length do
		table.insert(out, { piece = 4, offset = offset })
		offset += 4
	end
	return out
end
return { snap = snap, snapPoint = snapPoint, layoutWall = layoutWall }
```
