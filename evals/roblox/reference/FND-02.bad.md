```luau
--!strict
-- Greedy best-first search: follows the heuristic only, ignores the cost so far. Paths are valid but not always shortest.
type Point = { x: number, y: number }
local AStar = {}

local function blocked(grid: { string }, x: number, y: number): boolean
	local row = grid[y]
	if row == nil or x < 1 or x > #row then return true end
	return string.sub(row, x, x) == "#"
end

function AStar.findPath(grid: { string }, start: Point, goal: Point): { Point }?
	if blocked(grid, start.x, start.y) or blocked(grid, goal.x, goal.y) then return nil end
	local function key(x: number, y: number): string return x .. "," .. y end
	local open: { Point } = { { x = start.x, y = start.y } }
	local seen: { [string]: boolean } = { [key(start.x, start.y)] = true }
	local cameFrom: { [string]: Point } = {}
	while #open > 0 do
		local bestIndex = 1
		for i, p in open do
			local hb = math.abs(open[bestIndex].x - goal.x) + math.abs(open[bestIndex].y - goal.y)
			local hp = math.abs(p.x - goal.x) + math.abs(p.y - goal.y)
			if hp < hb then bestIndex = i end
		end
		local p = table.remove(open, bestIndex) :: Point
		if p.x == goal.x and p.y == goal.y then
			local path: { Point } = { p }
			local c = cameFrom[key(p.x, p.y)]
			while c do
				table.insert(path, 1, c)
				c = cameFrom[key(c.x, c.y)]
			end
			return path
		end
		for _, d in { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } } do
			local nx, ny = p.x + d[1], p.y + d[2]
			if not blocked(grid, nx, ny) and not seen[key(nx, ny)] then
				seen[key(nx, ny)] = true
				cameFrom[key(nx, ny)] = p
				table.insert(open, { x = nx, y = ny })
			end
		end
	end
	return nil
end

return AStar
```
