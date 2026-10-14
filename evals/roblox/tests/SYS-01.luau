local Svc = load_answer()
local player = { Name = "p1", UserId = 1 }
local rnd = lcg(1234)
local items = { "sword", "potion", "gem", "arrow" }
for _ = 1, 30 do pcall(Svc.Give, player, items[rnd(4)], rnd(60)) end
local function totals(snap)
	local t = {}
	for _, slot in snap do t[slot.itemId] = (t[slot.itemId] or 0) + slot.count end
	return t
end
local okSnap, snap0 = pcall(Svc.GetSnapshot, player)
local initial = okSnap and totals(snap0) or {}
local seeded = 0
for _, n in initial do seeded += n end
check("seeding through Give put items in the inventory", seeded > 0)

local bad = { "3", 0, 21, 1.5, 0 / 0, {}, -1, math.huge, true }
local function pick()
	local r = rnd(10)
	if r <= 6 then return rnd(20) end
	if r <= 9 then return bad[rnd(#bad)] end
	return nil
end
local function validSlot(x) return type(x) == "number" and x == x and x >= 1 and x <= 20 and x == math.floor(x) end
local threw, lostOrDuped, outOfRange, badInvalid = false, false, false, false
for _ = 1, 2000 do
	local a, b = pick(), pick()
	local before = deepCopy(Svc.GetSnapshot(player))
	local ok, res, reason = pcall(Svc.MoveItem, player, a, b)
	if not ok then
		threw = true
	else
		local snap = Svc.GetSnapshot(player)
		local now = totals(snap)
		for id, n in initial do if now[id] ~= n then lostOrDuped = true end end
		for id in now do if initial[id] == nil then lostOrDuped = true end end
		for _, slot in snap do
			if slot.count > 99 or slot.count <= 0 then outOfRange = true end
		end
		local srcEmpty = validSlot(a) and before[a] == nil
		local shouldFail = not (validSlot(a) and validSlot(b) and a ~= b) or srcEmpty
		if shouldFail and (res ~= false or type(reason) ~= "string" or reason == "" or not deepEqual(before, snap)) then
			badInvalid = true
		end
	end
end
check("no call throws", not threw)
check("totals per item are preserved (no duplication, no loss)", not lostOrDuped)
check("no slot has count > 99 or <= 0", not outOfRange)
check("invalid requests return false plus a reason and change nothing", not badInvalid)
local s1 = Svc.GetSnapshot(player)
for _, slot in s1 do slot.count = 1 end
s1[999] = { itemId = "fake", count = 5 }
check("GetSnapshot returns a copy", deepEqual(totals(Svc.GetSnapshot(player)), initial))
