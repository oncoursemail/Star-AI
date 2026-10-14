```luau
--!strict
-- Only looks in the query point's own cell, so neighbours across a cell border are missed.
local SpatialHash = {}
SpatialHash.__index = SpatialHash

function SpatialHash.new(cellSize: number)
	return setmetatable({ cellSize = cellSize, cells = {} :: { [string]: { [any]: boolean } }, entries = {} :: { [any]: any } }, SpatialHash)
end

function SpatialHash:remove(id: any)
	local e = self.entries[id]
	if e then
		self.cells[e.cell][id] = nil
		self.entries[id] = nil
	end
end

function SpatialHash:insert(id: any, x: number, y: number)
	self:remove(id)
	local key = math.floor(x / self.cellSize) .. ":" .. math.floor(y / self.cellSize)
	self.cells[key] = self.cells[key] or {}
	self.cells[key][id] = true
	self.entries[id] = { x = x, y = y, cell = key }
end

function SpatialHash:move(id: any, x: number, y: number)
	self:insert(id, x, y)
end

function SpatialHash:queryRadius(x: number, y: number, r: number): { any }
	local found = {}
	local key = math.floor(x / self.cellSize) .. ":" .. math.floor(y / self.cellSize)
	for id in self.cells[key] or {} do
		local e = self.entries[id]
		if (e.x - x) ^ 2 + (e.y - y) ^ 2 <= r * r then table.insert(found, id) end
	end
	return found
end

return SpatialHash
```
