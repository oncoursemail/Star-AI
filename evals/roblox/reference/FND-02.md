```luau
--!strict
-- A* on a 4-connected grid. Rows are strings, "#" is a wall; x is the column, y the row (both 1-based).
-- Manhattan distance is admissible for 4-way moves of cost 1, so the path is optimal.
type Point = { x: number, y: number }
type Node = { f: number, g: number, key: number }

local AStar = {}

local function blocked(grid: { string }, x: number, y: number): boolean
	local row = grid[y]
	if row == nil or x < 1 or x > #row then
		return true
	end
	return string.sub(row, x, x) == "#"
end

-- Binary heap ordered by f, then by larger g (prefers nodes closer to the goal on ties).
local function before(a: Node, b: Node): boolean
	if a.f ~= b.f then
		return a.f < b.f
	end
	return a.g > b.g
end

local function push(heap: { Node }, node: Node)
	table.insert(heap, node)
	local i = #heap
	while i > 1 do
		local p = i // 2
		if not before(heap[i], heap[p]) then break end
		heap[i], heap[p] = heap[p], heap[i]
		i = p
	end
end

local function pop(heap: { Node }): Node?
	local n = #heap
	if n == 0 then return nil end
	local top = heap[1]
	heap[1] = heap[n]
	heap[n] = nil
	n -= 1
	local i = 1
	while true do
		local l, r, s = 2 * i, 2 * i + 1, i
		if l <= n and before(heap[l], heap[s]) then s = l end
		if r <= n and before(heap[r], heap[s]) then s = r end
		if s == i then break end
		heap[i], heap[s] = heap[s], heap[i]
		i = s
	end
	return top
end

function AStar.findPath(grid: { string }, start: Point, goal: Point): { Point }?
	if blocked(grid, start.x, start.y) or blocked(grid, goal.x, goal.y) then
		return nil
	end
	local width = 0
	for _, row in grid do
		width = math.max(width, #row)
	end
	local stride = width + 2
	local function key(x: number, y: number): number
		return y * stride + x
	end
	local function h(x: number, y: number): number
		return math.abs(x - goal.x) + math.abs(y - goal.y)
	end

	local startKey = key(start.x, start.y)
	local g: { [number]: number } = { [startKey] = 0 }
	local cameFrom: { [number]: number } = {}
	local pos: { [number]: Point } = { [startKey] = { x = start.x, y = start.y } }
	local closed: { [number]: boolean } = {}
	local open: { Node } = {}
	push(open, { f = h(start.x, start.y), g = 0, key = startKey })

	while true do
		local current = pop(open)
		if current == nil then
			return nil
		end
		if not closed[current.key] and current.g == g[current.key] then
			closed[current.key] = true
			local p = pos[current.key]
			if p.x == goal.x and p.y == goal.y then
				local path: { Point } = {}
				local k: number? = current.key
				while k ~= nil do
					table.insert(path, 1, { x = pos[k].x, y = pos[k].y })
					k = cameFrom[k]
				end
				return path
			end
			for _, d in { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } } do
				local nx, ny = p.x + d[1], p.y + d[2]
				if not blocked(grid, nx, ny) then
					local nk = key(nx, ny)
					local tentative = current.g + 1
					local known = g[nk]
					if not closed[nk] and (known == nil or tentative < known) then
						g[nk] = tentative
						cameFrom[nk] = current.key
						pos[nk] = { x = nx, y = ny }
						push(open, { f = tentative + h(nx, ny), g = tentative, key = nk })
					end
				end
			end
		end
	end
end

return AStar
```
