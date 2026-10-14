local ret, env = load_answer()
local SpatialHash = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.SpatialHash) or env.SpatialHash
check("the module returns a SpatialHash class with new()", type(SpatialHash) == "table" and type(SpatialHash.new) == "function")

local function sortedIds(list)
	local out = {}
	for i, v in list or {} do out[i] = v end
	table.sort(out, function(a, b) return tostring(a) < tostring(b) end)
	return out
end

local h = SpatialHash.new(10)
h:insert("a", 1, 1)
h:insert("b", 9, 9)
h:insert("c", 15, 1)
h:insert("d", -3, -4)
check("query returns points within the radius", deepEqual(sortedIds(h:queryRadius(0, 0, 5)), { "a", "d" }))
check("points exactly on the radius are included", deepEqual(sortedIds(h:queryRadius(-3, 0, 4)), { "d" }))
check("points in neighbouring cells are found", deepEqual(sortedIds(h:queryRadius(12, 2, 4)), { "c" }))
check("points at negative coordinates are found", deepEqual(sortedIds(h:queryRadius(-1, -1, 3.7)), { "a", "d" }))
h:remove("a")
check("removed points are not returned", deepEqual(sortedIds(h:queryRadius(0, 0, 5)), { "d" }))
h:move("d", 40, 40)
check("moved points are found at the new place only", deepEqual(sortedIds(h:queryRadius(0, 0, 5)), {}) and deepEqual(sortedIds(h:queryRadius(41, 41, 2)), { "d" }))
h:insert("b", 100, 100)
check("inserting an existing id moves it", deepEqual(sortedIds(h:queryRadius(9, 9, 1)), {}) and deepEqual(sortedIds(h:queryRadius(100, 100, 0)), { "b" }))

-- Brute-force comparison with random points, radii bigger and smaller than a cell.
local rand = lcg(42)
local g = SpatialHash.new(8)
local pts = {}
for i = 1, 300 do
	local x, y = rand(200) - 100 + rand(10) / 10, rand(200) - 100 + rand(10) / 10
	pts[i] = { x = x, y = y }
	g:insert(i, x, y)
end
for i = 1, 300, 7 do
	pts[i] = nil
	g:remove(i)
end
local allMatch = true
for _ = 1, 30 do
	local qx, qy, r = rand(200) - 100, rand(200) - 100, rand(25)
	local expect = {}
	for id, p in pts do
		local dx, dy = p.x - qx, p.y - qy
		if dx * dx + dy * dy <= r * r then table.insert(expect, id) end
	end
	table.sort(expect)
	local got = g:queryRadius(qx, qy, r) or {}
	local copy = {}
	for k, v in got do copy[k] = v end
	table.sort(copy)
	if not deepEqual(copy, expect) then allMatch = false end
end
check("30 random queries match a brute-force search", allMatch)
