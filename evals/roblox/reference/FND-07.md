```luau
--!strict
-- Uniform-grid spatial hash for 2D radius queries. Cells are keyed by floor(coordinate / cellSize).
local SpatialHash = {}
SpatialHash.__index = SpatialHash

type Entry = { x: number, y: number, cell: string }
export type SpatialHash = typeof(setmetatable({} :: {
	cellSize: number,
	cells: { [string]: { [any]: boolean } },
	entries: { [any]: Entry },
}, SpatialHash))

function SpatialHash.new(cellSize: number): SpatialHash
	assert(cellSize > 0, "cellSize must be positive")
	return setmetatable({ cellSize = cellSize, cells = {}, entries = {} }, SpatialHash)
end

local function cellKey(cx: number, cy: number): string
	return cx .. ":" .. cy
end

function SpatialHash.remove(self: SpatialHash, id: any)
	local entry = self.entries[id]
	if entry == nil then
		return
	end
	local bucket = self.cells[entry.cell]
	if bucket then
		bucket[id] = nil
		if next(bucket) == nil then
			self.cells[entry.cell] = nil
		end
	end
	self.entries[id] = nil
end

function SpatialHash.insert(self: SpatialHash, id: any, x: number, y: number)
	self:remove(id)
	local key = cellKey(math.floor(x / self.cellSize), math.floor(y / self.cellSize))
	local bucket = self.cells[key]
	if bucket == nil then
		bucket = {}
		self.cells[key] = bucket
	end
	bucket[id] = true
	self.entries[id] = { x = x, y = y, cell = key }
end

function SpatialHash.move(self: SpatialHash, id: any, x: number, y: number)
	self:insert(id, x, y)
end

function SpatialHash.queryRadius(self: SpatialHash, x: number, y: number, r: number): { any }
	local found = {}
	local size = self.cellSize
	local r2 = r * r
	for cx = math.floor((x - r) / size), math.floor((x + r) / size) do
		for cy = math.floor((y - r) / size), math.floor((y + r) / size) do
			local bucket = self.cells[cellKey(cx, cy)]
			if bucket then
				for id in bucket do
					local e = self.entries[id]
					local dx, dy = e.x - x, e.y - y
					if dx * dx + dy * dy <= r2 then
						table.insert(found, id)
					end
				end
			end
		end
	end
	return found
end

return SpatialHash
```
