local M = {}
function M.findPath(grid, start: Vector2, goal: Vector2)
	local function key(v) return v.X .. "," .. v.Y end
	local function open(v) return grid[v.Y] ~= nil and grid[v.Y][v.X] == true end
	if not open(start) or not open(goal) then return nil end
	local queue, head = { start }, 1
	local from = { [key(start)] = start }
	while head <= #queue do
		local cell = queue[head]
		head += 1
		if cell == goal then
			local path = { cell }
			while cell ~= start do
				cell = from[key(cell)]
				table.insert(path, 1, cell)
			end
			return path
		end
		for _, d in { Vector2.new(1, 0), Vector2.new(-1, 0), Vector2.new(0, 1), Vector2.new(0, -1) } do
			local nxt = cell + d
			if open(nxt) and from[key(nxt)] == nil then
				from[key(nxt)] = cell
				table.insert(queue, nxt)
			end
		end
	end
	return nil
end
return M
