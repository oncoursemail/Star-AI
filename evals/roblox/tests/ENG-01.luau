local ret, env = load_answer()
local addItem = resolve(ret, env, "addItem")
local function counts(stacks)
	local out = {}
	for i, s in stacks do out[i] = s.count end
	return out
end
local s1 = addItem({}, "potion", 70, 20)
check("70 potions with a limit of 20 make stacks of 20, 20, 20, 10", deepEqual(counts(s1), { 20, 20, 20, 10 }))
local own = { { name = "potion", count = 15 } }
check("an existing stack is topped up first and the rest goes to a new stack", deepEqual(counts(addItem(own, "potion", 10, 20)), { 20, 5 }))
check("the same table is returned", addItem(own, "potion", 1, 20) == own)
local mixed = { { name = "sword", count = 1 }, { name = "potion", count = 19 } }
addItem(mixed, "potion", 3, 20)
check("other items are left alone and only potions are added", mixed[1].count == 1 and mixed[2].count == 20 and mixed[3].name == "potion" and mixed[3].count == 2)
check("adding 0 changes nothing", deepEqual(counts(addItem({ { name = "a", count = 5 } }, "a", 0, 10)), { 5 }))
local big = addItem({}, "arrow", 1000, 64)
local total, over = 0, false
for _, s in big do total += s.count; if s.count > 64 then over = true end end
check("1000 arrows in stacks of 64: 16 stacks, none over the limit, total kept", #big == 16 and not over and total == 1000)
check("a stack that is already full is not topped up", deepEqual(counts(addItem({ { name = "a", count = 20 } }, "a", 5, 20)), { 20, 5 }))
