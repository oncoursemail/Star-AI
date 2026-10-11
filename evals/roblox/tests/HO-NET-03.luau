-- Holdout test body HO-NET-03 (frozen 2026-10-11; harness-owned, never shown to the model).
local Mod = load_answer({ debug = debugStub })
local allowed = { jump = true, fire = true, reload = true }

local q = Mod.new(allowed, 4)
check("a valid batch is fully accepted", q:push(1, { { seq = 1, action = "jump" }, { seq = 2, action = "fire" } }) == 2)
check("replayed and older seq values are dropped", q:push(1, { { seq = 2, action = "fire" }, { seq = 1, action = "jump" } }) == 0)
check("gaps in seq are fine", q:push(1, { { seq = 10, action = "reload" } }) == 1)
check("drain returns the accepted actions in order", deepEqual(q:drain(1), { "jump", "fire", "reload" }))
check("drain empties the queue", deepEqual(q:drain(1), {}))
check("the highest seq is kept after a drain: seq 10 again is a replay", q:push(1, { { seq = 10, action = "jump" } }) == 0)
check("drain of a player who never pushed returns an empty list", deepEqual(q:drain(99), {}))

local q2 = Mod.new(allowed, 4)
check("an entry with a forbidden action is dropped, the next valid one kept",
	q2:push(2, { { seq = 1, action = "teleport" }, { seq = 2, action = "jump" } }) == 1)
check("the same seq twice in one batch is accepted once",
	q2:push(2, { { seq = 5, action = "jump" }, { seq = 5, action = "fire" } }) == 1)
check("a falling seq inside one batch drops the later entry",
	q2:push(2, { { seq = 9, action = "jump" }, { seq = 8, action = "fire" } }) == 1)
check("only the accepted actions were queued", deepEqual(q2:drain(2), { "jump", "jump", "jump" }))

local q3 = Mod.new(allowed, 4)
local big = {}
for i = 1, 6 do big[i] = { seq = i, action = "fire" } end
check("only the first maxBatch entries are looked at", q3:push(3, big) == 4)
check("entries beyond maxBatch did not raise the highest seq", q3:push(3, { { seq = 5, action = "fire" } }) == 1)

local q4 = Mod.new(allowed, 10)
local hostile = {
	5, "a", true, false,
	{ seq = "3", action = "jump" },
	{ seq = 1.5, action = "jump" },
	{ seq = 0 / 0, action = "jump" },
	{ seq = math.huge, action = "jump" },
	{ seq = -math.huge, action = "jump" },
	{ seq = 0, action = "jump" },
	{ seq = -4, action = "jump" },
	{ seq = 1, action = 5 },
	{ seq = 1, action = {} },
	{ seq = 1 },
	{ action = "jump" },
	{},
}
local ok, n = pcall(q4.push, q4, 4, hostile)
check("hostile entries never throw and none is accepted", ok == true and n == 0)
local notTables = true
for _, bad in { 5, "batch", true, 0 / 0 } do
	local ok2, n2 = pcall(q4.push, q4, 4, bad)
	if not ok2 or n2 ~= 0 then notTables = false end
end
local ok3, n3 = pcall(q4.push, q4, 4, nil)
check("a batch that is not a table gives 0 and never throws", notTables and ok3 == true and n3 == 0)
check("after hostile input a clean first command with seq 1 is still accepted", q4:push(4, { { seq = 1, action = "jump" } }) == 1)

q4:forget(4)
check("forget clears the highest seq: seq 1 is accepted again", q4:push(4, { { seq = 1, action = "fire" } }) == 1)
check("players are independent", q4:push(5, { { seq = 1, action = "fire" } }) == 1 and deepEqual(q4:drain(5), { "fire" }))
