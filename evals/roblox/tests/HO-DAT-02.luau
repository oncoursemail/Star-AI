-- Holdout test body HO-DAT-02 (frozen 2026-10-11; harness-owned, never shown to the model).
local Mod = load_answer({ debug = debugStub })

local function v1() return { gold = 120, items = { "sword", "potion", "sword" } } end
local input = v1()
local out, steps = Mod.upgrade(input)
check("version 1 data takes two steps", steps == 2)
check("the whole result is exactly version 3 data",
	deepEqual(out, { version = 3, coins = 120, items = { sword = 2, potion = 1 }, settings = { music = true, sfx = true } }))
check("the input table was not modified", deepEqual(input, v1()))

local explicit = { version = 1, gold = 9, items = { "axe" } }
out, steps = Mod.upgrade(explicit)
check("an explicit version = 1 is the same layout", steps == 2 and out.coins == 9 and deepEqual(out.items, { axe = 1 }) and out.gold == nil)

local extra = { gold = 5, items = {}, level = 7, flags = { vip = true } }
out, steps = Mod.upgrade(extra)
check("other fields are kept", out.level == 7 and deepEqual(out.flags, { vip = true }))
out.flags.vip = false
check("the result shares no nested table with the input", extra.flags.vip == true)

out, steps = Mod.upgrade({})
check("an empty save gets defaults: 0 coins, no items", steps == 2 and out.version == 3 and out.coins == 0 and deepEqual(out.items, {}))

local v2 = { version = 2, coins = 50, items = { axe = 3 } }
out, steps = Mod.upgrade(v2)
check("version 2 data takes one step and keeps coins and items",
	steps == 1 and out.version == 3 and out.coins == 50 and deepEqual(out.items, { axe = 3 }) and deepEqual(out.settings, { music = true, sfx = true }))
out.items.axe = 99
check("version 2 result shares no nested table with the input", v2.items.axe == 3 and v2.version == 2)

local v3 = { version = 3, coins = 1, items = {}, settings = { music = false } }
out, steps = Mod.upgrade(v3)
check("version 3 data takes no steps", steps == 0 and out.version == 3 and out.coins == 1)
check("an existing false setting is kept, a missing one gets its default", out.settings.music == false and out.settings.sfx == true)
check("the version 3 input is not modified", deepEqual(v3, { version = 3, coins = 1, items = {}, settings = { music = false } }))

local okFuture, errFuture = pcall(Mod.upgrade, { version = 4, coins = 1 })
check("a newer version raises an error that names the version", okFuture == false and string.find(tostring(errFuture), "4", 1, true) ~= nil)
local allThrow = true
for _, bad in { { version = 0 }, { version = -1 }, { version = 1.5 }, { version = "3" }, { version = true }, { version = 0 / 0 } } do
	if not throws(Mod.upgrade, bad) then allThrow = false end
end
check("a version that is not an integer from 1 to 3 raises an error", allThrow)
local nonTables = true
for _, bad in { 5, "save", true } do
	if not throws(Mod.upgrade, bad) then nonTables = false end
end
if not throws(Mod.upgrade, nil) then nonTables = false end
check("data that is not a table raises an error", nonTables)
