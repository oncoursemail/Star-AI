-- Holdout test body HO-NET-04 (frozen 2026-10-11; harness-owned, never shown to the model).
local Mod = load_answer({ debug = debugStub })

local inv = { wood = 10, plank = 1, sword = 1 }
local ok, reason = Mod.craft(inv, "plank", 3)
check("plank x3 succeeds", ok == true)
check("plank x3 takes 6 wood and gives 12 planks", deepEqual(inv, { wood = 4, plank = 13, sword = 1 }))

inv = { wood = 6 }
ok = Mod.craft(inv, "plank", 3)
check("an ingredient that reaches 0 is removed from the table", ok == true and deepEqual(inv, { plank = 12 }))

inv = { plank = 5, coal = 2 }
ok = Mod.craft(inv, "torch", 2)
check("torch x2 uses 2 plank and 2 coal and gives 4 torches", ok == true and deepEqual(inv, { plank = 3, torch = 4 }))

inv = { plank = 6, rope = 1 }
local before = deepCopy(inv)
ok, reason = Mod.craft(inv, "bridge", 1)
check("a missing ingredient fails with a reason", ok == false and type(reason) == "string" and reason ~= "")
local inv2 = { plank = 2, rope = 2 }
local before2 = deepCopy(inv2)
local ok2 = Mod.craft(inv2, "bridge", 1)
check("a failed craft does not take the ingredients that were available (no partial deduction)",
	ok2 == false and deepEqual(inv, before) and deepEqual(inv2, before2))

inv = { wood = 5 }
before = deepCopy(inv)
ok = Mod.craft(inv, "plank", 3)
check("not enough for all the crafts fails and leaves the inventory alone", ok == false and deepEqual(inv, before))

inv = { plank = 3, coal = 0 }
before = deepCopy(inv)
ok = Mod.craft(inv, "torch", 1)
check("an ingredient with count 0 counts as missing", ok == false and deepEqual(inv, before))

inv = { wood = 40 }
ok = Mod.craft(inv, "plank", 20)
check("20 crafts is allowed", ok == true and deepEqual(inv, { plank = 80 }))

local badTimes = { 0, -1, 21, 1.5, 0 / 0, math.huge, -math.huge, 1e300, "3", true, false, {}, function() end }
local allSafe, allUnchanged, allFalse = true, true, true
for _, times in badTimes do
	local i2 = { wood = 1000, plank = 1000, coal = 1000, rope = 1000 }
	local copy = deepCopy(i2)
	local okCall, r1, r2 = pcall(Mod.craft, i2, "plank", times)
	if not okCall then allSafe = false end
	if okCall and r1 ~= false then allFalse = false end
	if okCall and r1 == false and (type(r2) ~= "string" or r2 == "") then allFalse = false end
	if not deepEqual(i2, copy) then allUnchanged = false end
end
local okNil, r1 = pcall(Mod.craft, { wood = 10 }, "plank", nil)
if not okNil then allSafe = false end
if okNil and r1 ~= false then allFalse = false end
check("invalid times values never throw", allSafe)
check("invalid times values return false and a reason", allFalse)
check("invalid times values leave the inventory unchanged", allUnchanged)

local badRecipes = { 5, "wood", "coal", "", "Plank", "plank ", "__index", {}, true, false }
allSafe, allUnchanged, allFalse = true, true, true
for _, id in badRecipes do
	local i2 = { wood = 1000, plank = 1000, coal = 1000, rope = 1000 }
	local copy = deepCopy(i2)
	local okCall, r1 = pcall(Mod.craft, i2, id, 1)
	if not okCall then allSafe = false end
	if okCall and r1 ~= false then allFalse = false end
	if not deepEqual(i2, copy) then allUnchanged = false end
end
local okNil2, r2 = pcall(Mod.craft, { wood = 10 }, nil, 1)
if not okNil2 then allSafe = false end
if okNil2 and r2 ~= false then allFalse = false end
check("recipe ids that are not recipes never throw", allSafe)
check("recipe ids that are not recipes return false and change nothing", allFalse and allUnchanged)
