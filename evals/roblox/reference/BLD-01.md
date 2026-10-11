```luau
--!strict
local PIECES = { 16, 8, 4 }

local function snap(value: number, grid: number): number
	return math.floor(value / grid + 0.5) * grid
end

local function snapPoint(p: { x: number, y: number, z: number }, grid: number)
	return { x = snap(p.x, grid), y = snap(p.y, grid), z = snap(p.z, grid) }
end

local function layoutWall(length: number)
	if length <= 0 or length % 4 ~= 0 then
		error("wall length must be a positive multiple of 4")
	end
	local out = {}
	local offset, left = 0, length
	for _, size in PIECES do
		while left >= size do
			table.insert(out, { piece = size, offset = offset })
			offset += size
			left -= size
		end
	end
	return out
end

return { snap = snap, snapPoint = snapPoint, layoutWall = layoutWall }
```
