local M = solution()
local T, F = true, false
local grid = {
	{ T, T, T, T, T },
	{ F, F, F, F, T },
	{ T, T, T, F, T },
	{ T, F, T, T, T },
	{ T, F, F, F, F },
}
local function valid(path, s, g, length)
	expect(path, "no path")
	expect(#path == length, "length " .. #path .. ", shortest is " .. length)
	expect(path[1] == s and path[#path] == g, "wrong ends")
	for i, cell in path do
		expect(grid[cell.Y] and grid[cell.Y][cell.X], "path goes through a wall at " .. tostring(cell))
		if i > 1 then
			local d = cell - path[i - 1]
			expect(math.abs(d.X) + math.abs(d.Y) == 1, "jump between steps")
		end
	end
end
check("maze shortest path", function()
	valid(M.findPath(grid, Vector2.new(1, 1), Vector2.new(1, 5)), Vector2.new(1, 1), Vector2.new(1, 5), 15)
end)
check("unreachable is nil", function()
	local blocked = { { T, F, T } }
	expect(M.findPath(blocked, Vector2.new(1, 1), Vector2.new(3, 1)) == nil, "expected nil")
end)
check("start equals goal", function()
	local path = M.findPath(grid, Vector2.new(3, 3), Vector2.new(3, 3))
	expect(path and #path == 1 and path[1] == Vector2.new(3, 3), "expected {start}")
end)
check("open 30x30 is fast and shortest", function()
	local open = {}
	for y = 1, 30 do
		open[y] = {}
		for x = 1, 30 do open[y][x] = true end
	end
	local t = os.clock()
	local path = M.findPath(open, Vector2.new(1, 1), Vector2.new(30, 30))
	expect(os.clock() - t < 0.5, "too slow")
	expect(path and #path == 59, "length " .. tostring(path and #path))
end)
