local ret, env = load_answer()
local AStar = (type(ret) == "table" and ret.findPath ~= nil and ret) or (type(ret) == "table" and ret.AStar) or env.AStar
check("the module returns a table with findPath", type(AStar) == "table" and type(AStar.findPath) == "function")

local function cell(grid, x, y)
	local row = grid[y]
	if not row or x < 1 or x > #row then return "#" end
	return string.sub(row, x, x)
end

-- Reference shortest path length (number of moves) by breadth-first search.
local function bfs(grid, sx, sy, gx, gy)
	if cell(grid, sx, sy) == "#" or cell(grid, gx, gy) == "#" then return nil end
	local dist = { [sy * 1000 + sx] = 0 }
	local queue, head = { { sx, sy } }, 1
	while queue[head] do
		local x, y = queue[head][1], queue[head][2]
		head += 1
		if x == gx and y == gy then return dist[y * 1000 + x] end
		for _, d in { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } } do
			local nx, ny = x + d[1], y + d[2]
			if cell(grid, nx, ny) ~= "#" and dist[ny * 1000 + nx] == nil then
				dist[ny * 1000 + nx] = dist[y * 1000 + x] + 1
				table.insert(queue, { nx, ny })
			end
		end
	end
	return nil
end

-- A path is valid when it starts and ends at the right cells and every step is one orthogonal move onto a free cell.
local function valid(grid, path, sx, sy, gx, gy)
	if type(path) ~= "table" or #path == 0 then return false end
	if path[1].x ~= sx or path[1].y ~= sy or path[#path].x ~= gx or path[#path].y ~= gy then return false end
	for i = 1, #path do
		if cell(grid, path[i].x, path[i].y) == "#" then return false end
		if i > 1 and math.abs(path[i].x - path[i - 1].x) + math.abs(path[i].y - path[i - 1].y) ~= 1 then return false end
	end
	return true
end

local open = { ".....", ".....", "....." }
local p = AStar.findPath(open, { x = 1, y = 2 }, { x = 5, y = 2 })
check("a straight corridor gives a valid 5-cell path", valid(open, p, 1, 2, 5, 2) and #p == 5)

local same = AStar.findPath(open, { x = 3, y = 3 }, { x = 3, y = 3 })
check("start equal to goal returns a one-cell path", valid(open, same, 3, 3, 3, 3) and #same == 1)

local wall = {
	".....",
	".###.",
	".#...",
	".#.#.",
	"...#.",
}
local w = AStar.findPath(wall, { x = 3, y = 3 }, { x = 1, y = 1 })
check("a path around walls is valid and shortest", valid(wall, w, 3, 3, 1, 1) and #w - 1 == bfs(wall, 3, 3, 1, 1))

local closed = { "..#..", "..#..", "..#.." }
check("an unreachable goal returns nil", AStar.findPath(closed, { x = 1, y = 1 }, { x = 5, y = 3 }) == nil)
check("a goal on a wall returns nil", AStar.findPath(wall, { x = 1, y = 1 }, { x = 2, y = 2 }) == nil)

-- Random mazes: every returned path must be valid and as short as breadth-first search says.
local rand = lcg(2026)
local allGood, foundSome, nilWhenNone = true, 0, true
for _ = 1, 25 do
	local rows = {}
	for y = 1, 14 do
		local chars = {}
		for x = 1, 18 do chars[x] = (rand(100) <= 30) and "#" or "." end
		rows[y] = table.concat(chars)
	end
	rows[1] = "." .. string.sub(rows[1], 2)
	rows[14] = string.sub(rows[14], 1, 17) .. "."
	local expect = bfs(rows, 1, 1, 18, 14)
	local got = AStar.findPath(rows, { x = 1, y = 1 }, { x = 18, y = 14 })
	if expect == nil then
		if got ~= nil then nilWhenNone = false end
	else
		foundSome += 1
		if not (valid(rows, got, 1, 1, 18, 14) and #got - 1 == expect) then allGood = false end
	end
end
check("random mazes: some are solvable", foundSome >= 5)
check("random mazes: every path is valid and optimal", allGood)
check("random mazes: unsolvable mazes return nil", nilWhenNone)
