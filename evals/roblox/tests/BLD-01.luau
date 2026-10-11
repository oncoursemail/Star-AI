local ret, env = load_answer()
local snap = resolve(ret, env, "snap")
local snapPoint = resolve(ret, env, "snapPoint")
local layoutWall = resolve(ret, env, "layoutWall")
check("snap(5, 4) is 4 and snap(6, 4) is 8", snap(5, 4) == 4 and snap(6, 4) == 8)
check("snap handles negative values: snap(-5, 4) is -4 and snap(-7, 4) is -8", snap(-5, 4) == -4 and snap(-7, 4) == -8)
check("snap(0.4, 1) is 0 and snap(0.5, 1) is 1", snap(0.4, 1) == 0 and snap(0.5, 1) == 1)
local p = { x = 5, y = 1, z = -7 }
local q = snapPoint(p, 4)
check("snapPoint snaps every field", q.x == 4 and q.y == 0 and q.z == -8)
check("snapPoint returns a new table and leaves the input alone", q ~= p and p.x == 5 and p.y == 1 and p.z == -7)
local function shape(list)
	local out = {}
	for i, item in list do out[i] = { piece = item.piece, offset = item.offset } end
	return out
end
check("layoutWall(40) is 16, 16, 8", deepEqual(shape(layoutWall(40)), { { piece = 16, offset = 0 }, { piece = 16, offset = 16 }, { piece = 8, offset = 32 } }))
check("layoutWall(28) is 16, 8, 4", deepEqual(shape(layoutWall(28)), { { piece = 16, offset = 0 }, { piece = 8, offset = 16 }, { piece = 4, offset = 24 } }))
check("layoutWall(4) is a single 4", deepEqual(shape(layoutWall(4)), { { piece = 4, offset = 0 } }))
check("layoutWall(12) is 8 then 4", deepEqual(shape(layoutWall(12)), { { piece = 8, offset = 0 }, { piece = 4, offset = 8 } }))
local total = 0
for _, item in layoutWall(100) do total += item.piece end
check("the pieces of layoutWall(100) add up to 100 in 7 pieces", total == 100 and #layoutWall(100) == 7)
check("layoutWall(6) and layoutWall(0) and layoutWall(-8) raise errors", throws(layoutWall, 6) and throws(layoutWall, 0) and throws(layoutWall, -8))
check("layoutWall(64) is four 16 pieces", #layoutWall(64) == 4)
