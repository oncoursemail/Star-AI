local ret, env = load_answer()
local simulate = resolve(ret, env, "simulate")
local cfg = { baseIncome = 1, incomePerLevel = 1, baseCost = 10, growth = 1.5, upgrades = 10 }
local first = simulate(cfg)
check("simulate returns the reference purchase seconds", deepEqual(first, { 10, 18, 26, 34, 45, 57, 74, 95, 124, 162 }))
check("a second call returns an equal table", deepEqual(simulate(cfg), first))
local before = {}
for k, v in env do before[k] = v end
simulate(cfg)
local same = true
for k, v in env do if before[k] ~= v then same = false end end
for k in before do if env[k] == nil then same = false end end
check("simulate writes no globals", same)
local t0 = os.clock()
local big = simulate({ baseIncome = 1, incomePerLevel = 1, baseCost = 10, growth = 1.05, upgrades = 200 })
check("200 upgrades finish in under 1 second", os.clock() - t0 < 1 and #big == 200)
