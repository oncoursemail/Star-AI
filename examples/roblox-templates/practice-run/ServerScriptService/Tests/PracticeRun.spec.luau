--!strict
-- Executed in the checksum-pinned official standalone Luau CLI workflow.
-- Reference and plausible wrong solution both use these same six assertion cases.
local function deepEqual(a, b)
    if a == b then return true end
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for key, value in a do
        if not deepEqual(value, b[key]) then return false end
    end
    for key in b do
        if a[key] == nil then return false end
    end
    return true
end
local tests = {}

local function __good_001(userId: number): string?
  if userId <= 0 or userId % 1 ~= 0 then return nil end
  return "user_" .. tostring(userId)
end

local function __bad_001(userId: number): string?
  if userId < 0 or userId % 1 ~= 0 then return nil end
  return "user_" .. tostring(userId)
end
local function __trial_001(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(1), "user_1"))
    check("case 2", deepEqual(fn(42), "user_42"))
    check("case 3", deepEqual(fn(0), nil))
    check("case 4", deepEqual(fn(-2), nil))
    check("case 5", deepEqual(fn(1.5), nil))
    check("case 6", deepEqual(fn(1000), "user_1000"))
    return passed, total
end
tests["practice-run-001"] = function()
    local goodPassed, goodTotal = __trial_001(function() return __good_001 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-001: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_001, function() return __bad_001 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-001: incorrect solution passed")
end

local function __good_002(row)
  local source = type(row) == "table" and row or {}
  local function clean(value)
    if type(value) ~= "number" or value < 0 or value % 1 ~= 0 then return 0 end
    return value
  end
  return { coins = clean(source.coins), xp = clean(source.xp) }
end

local function __bad_002(row)
  local source = type(row) == "table" and row or {}
  local function clean(value)
    if type(value) ~= "number" or value < -100 or value % 1 ~= 0 then return 0 end
    return value
  end
  return { coins = clean(source.coins), xp = clean(source.xp) }
end
local function __trial_002(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(nil), {coins=0,xp=0}))
    check("case 2", deepEqual(fn({coins=4,xp=7}), {coins=4,xp=7}))
    check("case 3", deepEqual(fn({coins=-1,xp=9}), {coins=0,xp=9}))
    check("case 4", deepEqual(fn({coins=8.5,xp=2}), {coins=0,xp=2}))
    check("case 5", deepEqual(fn({coins=4,xp='bad'}), {coins=4,xp=0}))
    check("case 6", deepEqual(fn("invalid"), {coins=0,xp=0}))
    return passed, total
end
tests["practice-run-002"] = function()
    local goodPassed, goodTotal = __trial_002(function() return __good_002 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-002: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_002, function() return __bad_002 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-002: incorrect solution passed")
end

local function __good_003(row)
  local source = type(row) == "table" and row or {}
  local modern = source.version == 2
  local money = modern and source.coins or source.gold
  local level = modern and source.rank or source.level
  local coins = 0
  if type(money) == "number" and money >= 0 then coins = math.floor(money) end
  local rank = 1
  if type(level) == "number" and level >= 1 then rank = math.floor(level) end
  return { version = 2, coins = coins, rank = rank }
end

local function __bad_003(row)
  local source = type(row) == "table" and row or {}
  local modern = source.version == 1
  local money = modern and source.coins or source.gold
  local level = modern and source.rank or source.level
  local coins = 0
  if type(money) == "number" and money >= 0 then coins = math.floor(money) end
  local rank = 1
  if type(level) == "number" and level >= 1 then rank = math.floor(level) end
  return { version = 2, coins = coins, rank = rank }
end
local function __trial_003(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(nil), {version=2,coins=0,rank=1}))
    check("case 2", deepEqual(fn({version=1,gold=9,level=3}), {version=2,coins=9,rank=3}))
    check("case 3", deepEqual(fn({version=2,coins=7,rank=4}), {version=2,coins=7,rank=4}))
    check("case 4", deepEqual(fn({version=1,gold=-4,level=2}), {version=2,coins=0,rank=2}))
    check("case 5", deepEqual(fn({version=2,coins=4.7,rank=2.9}), {version=2,coins=4,rank=2}))
    check("case 6", deepEqual(fn({version=1,gold=5,level=0}), {version=2,coins=5,rank=1}))
    return passed, total
end
tests["practice-run-003"] = function()
    local goodPassed, goodTotal = __trial_003(function() return __good_003 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-003: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_003, function() return __bad_003 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-003: incorrect solution passed")
end

local function __good_004(a, b)
  local x = a or {}
  local y = b or {}
  return {checkpoint = math.max(0, x.checkpoint or 0, y.checkpoint or 0),
          trophies = math.max(0, x.trophies or 0, y.trophies or 0)}
end

local function __bad_004(a, b)
  local x = a or {}
  local y = b or {}
  return {checkpoint = math.min(0, x.checkpoint or 0, y.checkpoint or 0),
          trophies = math.max(0, x.trophies or 0, y.trophies or 0)}
end
local function __trial_004(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(nil,nil), {checkpoint=0,trophies=0}))
    check("case 2", deepEqual(fn({checkpoint=2,trophies=3},{checkpoint=5,trophies=1}), {checkpoint=5,trophies=3}))
    check("case 3", deepEqual(fn({checkpoint=9,trophies=1},{checkpoint=1,trophies=6}), {checkpoint=9,trophies=6}))
    check("case 4", deepEqual(fn({},{}), {checkpoint=0,trophies=0}))
    check("case 5", deepEqual(fn({checkpoint=4},{trophies=7}), {checkpoint=4,trophies=7}))
    check("case 6", deepEqual(fn({checkpoint=0,trophies=2},nil), {checkpoint=0,trophies=2}))
    return passed, total
end
tests["practice-run-004"] = function()
    local goodPassed, goodTotal = __trial_004(function() return __good_004 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-004: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_004, function() return __bad_004 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-004: incorrect solution passed")
end

local function __good_005(balance: number, delta: number): number
  if delta % 1 ~= 0 then return balance end
  return math.clamp(balance + delta, 0, 500)
end

local function __bad_005(balance: number, delta: number): number
  if delta % 1 ~= 0 then return balance end
  return math.clamp(balance + delta, 0, 600)
end
local function __trial_005(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(10,5), 15))
    check("case 2", deepEqual(fn(0,-3), 0))
    check("case 3", deepEqual(fn(499,9), 500))
    check("case 4", deepEqual(fn(500,1), 500))
    check("case 5", deepEqual(fn(20,1.5), 20))
    check("case 6", deepEqual(fn(23,-20), 3))
    return passed, total
end
tests["practice-run-005"] = function()
    local goodPassed, goodTotal = __trial_005(function() return __good_005 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-005: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_005, function() return __bad_005 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-005: incorrect solution passed")
end

local function __good_006(row)
  local data = type(row) == "table" and row or {}
  local coins = type(data.coins) == "number" and math.max(0, math.floor(data.coins)) or 0
  local stage = type(data.stage) == "number" and math.max(1, math.floor(data.stage)) or 1
  local soundEnabled = type(data.soundEnabled) == "boolean" and data.soundEnabled or data.soundEnabled ~= false
  return {coins=coins,stage=stage,soundEnabled=soundEnabled}
end

local function __bad_006(row)
  local data = type(row) == "table" and row or {}
  local coins = type(data.coins) == "number" and math.max(0, math.floor(data.coins)) or 0
  local stage = type(data.stage) == "number" and math.max(1, math.floor(data.stage)) or 1
  local soundEnabled = type(data.soundEnabled) == "boolean" and data.soundEnabled or data.soundEnabled ~= true
  return {coins=coins,stage=stage,soundEnabled=soundEnabled}
end
local function __trial_006(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(nil), {coins=0,stage=1,soundEnabled=true}))
    check("case 2", deepEqual(fn({coins=3,stage=2,soundEnabled=false,runtime='ignore'}), {coins=3,stage=2,soundEnabled=false}))
    check("case 3", deepEqual(fn({coins=-5,stage=0,soundEnabled=true}), {coins=0,stage=1,soundEnabled=true}))
    check("case 4", deepEqual(fn({coins=8.8,stage=5.5}), {coins=8,stage=5,soundEnabled=true}))
    check("case 5", deepEqual(fn({coins='bad',stage='bad',soundEnabled='x'}), {coins=0,stage=1,soundEnabled=true}))
    check("case 6", deepEqual(fn({coins=0,stage=1,soundEnabled=false}), {coins=0,stage=1,soundEnabled=false}))
    return passed, total
end
tests["practice-run-006"] = function()
    local goodPassed, goodTotal = __trial_006(function() return __good_006 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-006: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_006, function() return __bad_006 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-006: incorrect solution passed")
end

local function __good_007(old, receipt)
  local result = {}
  for _, id in old do table.insert(result, id) end
  if type(receipt) ~= "string" or receipt == "" then return result end
  for _, id in result do if id == receipt then return result end end
  table.insert(result, receipt)
  while #result > 3 do table.remove(result, 1) end
  return result
end

local function __bad_007(old, receipt)
  local result = {}
  for _, id in old do table.insert(result, id) end
  if type(receipt) ~= "string" or receipt == "" then return result end
  for _, id in result do if id == receipt then return result end end
  table.insert(result, receipt)
  while #result > 4 do table.remove(result, 1) end
  return result
end
local function __trial_007(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({},'a'), {'a'}))
    check("case 2", deepEqual(fn({'a'},'a'), {'a'}))
    check("case 3", deepEqual(fn({'a','b'},'c'), {'a','b','c'}))
    check("case 4", deepEqual(fn({'a','b','c'},'d'), {'b','c','d'}))
    check("case 5", deepEqual(fn({'x'},''), {'x'}))
    check("case 6", deepEqual(fn({'a','b','c'},'a'), {'a','b','c'}))
    return passed, total
end
tests["practice-run-007"] = function()
    local goodPassed, goodTotal = __trial_007(function() return __good_007 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-007: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_007, function() return __bad_007 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-007: incorrect solution passed")
end

local function __good_008(scores)
  local best = 0
  for _, score in scores do
    if type(score) == "number" and score > best then best = score end
  end
  return best
end

local function __bad_008(scores)
  local best = 0
  for _, score in scores do
    if type(score) == "number" and score < best then best = score end
  end
  return best
end
local function __trial_008(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({}), 0))
    check("case 2", deepEqual(fn({1,9,4}), 9))
    check("case 3", deepEqual(fn({-3,-1}), 0))
    check("case 4", deepEqual(fn({3,'bad',8}), 8))
    check("case 5", deepEqual(fn({7,7,2}), 7))
    check("case 6", deepEqual(fn({1,20,15}), 20))
    return passed, total
end
tests["practice-run-008"] = function()
    local goodPassed, goodTotal = __trial_008(function() return __good_008 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-008: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_008, function() return __bad_008 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-008: incorrect solution passed")
end

local function __good_009(lastDay: number, today: number, streak: number): number
  if today <= lastDay then return streak end
  if today == lastDay + 1 then return streak + 1 end
  return 1
end

local function __bad_009(lastDay: number, today: number, streak: number): number
  if today <= lastDay then return streak end
  if today >= lastDay + 1 then return streak + 1 end
  return 1
end
local function __trial_009(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(10,10,5), 5))
    check("case 2", deepEqual(fn(10,11,5), 6))
    check("case 3", deepEqual(fn(10,12,5), 1))
    check("case 4", deepEqual(fn(20,21,0), 1))
    check("case 5", deepEqual(fn(30,29,7), 7))
    check("case 6", deepEqual(fn(1,9,3), 1))
    return passed, total
end
tests["practice-run-009"] = function()
    local goodPassed, goodTotal = __trial_009(function() return __good_009 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-009: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_009, function() return __bad_009 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-009: incorrect solution passed")
end

local function __good_010(current, incoming)
  if current == nil then return incoming end
  if incoming == nil then return current end
  if incoming.version > current.version then return incoming end
  return current
end

local function __bad_010(current, incoming)
  if current == nil then return incoming end
  if incoming == nil then return current end
  if incoming.version >= current.version then return incoming end
  return current
end
local function __trial_010(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(nil,{version=1,coins=3}), {version=1,coins=3}))
    check("case 2", deepEqual(fn({version=2,coins=10},nil), {version=2,coins=10}))
    check("case 3", deepEqual(fn({version=2,coins=10},{version=3,coins=2}), {version=3,coins=2}))
    check("case 4", deepEqual(fn({version=4,coins=10},{version=1,coins=2}), {version=4,coins=10}))
    check("case 5", deepEqual(fn({version=2,coins=10},{version=2,coins=2}), {version=2,coins=10}))
    check("case 6", deepEqual(fn({version=8,coins=0},{version=9,coins=40}), {version=9,coins=40}))
    return passed, total
end
tests["practice-run-010"] = function()
    local goodPassed, goodTotal = __trial_010(function() return __good_010 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-010: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_010, function() return __bad_010 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-010: incorrect solution passed")
end

local function __good_011(phase: string, event: string): string
  if phase == "Lobby" and event == "start" then return "Playing" end
  if phase == "Playing" and event == "finish" then return "Results" end
  if phase == "Results" and event == "reset" then return "Lobby" end
  return phase
end

local function __bad_011(phase: string, event: string): string
  if phase == "Lobby" and event == "start" then return "Playing" end
  if phase == "Playing" and event == "stop" then return "Results" end
  if phase == "Results" and event == "reset" then return "Lobby" end
  return phase
end
local function __trial_011(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn("Lobby","start"), "Playing"))
    check("case 2", deepEqual(fn("Playing","finish"), "Results"))
    check("case 3", deepEqual(fn("Results","reset"), "Lobby"))
    check("case 4", deepEqual(fn("Lobby","finish"), "Lobby"))
    check("case 5", deepEqual(fn("Playing","start"), "Playing"))
    check("case 6", deepEqual(fn("Results","start"), "Results"))
    return passed, total
end
tests["practice-run-011"] = function()
    local goodPassed, goodTotal = __trial_011(function() return __good_011 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-011: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_011, function() return __bad_011 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-011: incorrect solution passed")
end

local function __good_012(remaining: number, dt: number): number
  if dt < 0 then return remaining end
  return math.max(0, remaining - dt)
end

local function __bad_012(remaining: number, dt: number): number
  if dt < 0 then return remaining end
  return math.max(0, remaining + dt)
end
local function __trial_012(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(10,2), 8))
    check("case 2", deepEqual(fn(5,5), 0))
    check("case 3", deepEqual(fn(3,8), 0))
    check("case 4", deepEqual(fn(0,2), 0))
    check("case 5", deepEqual(fn(12,0), 12))
    check("case 6", deepEqual(fn(8,-1), 8))
    return passed, total
end
tests["practice-run-012"] = function()
    local goodPassed, goodTotal = __trial_012(function() return __good_012 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-012: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_012, function() return __bad_012 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-012: incorrect solution passed")
end

local function __good_013(scores)
  local winner = nil
  local high = -math.huge
  for player, score in scores do
    if score > high or (score == high and (winner == nil or player < winner)) then
      winner = player
      high = score
    end
  end
  return winner
end

local function __bad_013(scores)
  local winner = nil
  local high = -math.huge
  for player, score in scores do
    if score > high or (score == high and (winner == nil or player > winner)) then
      winner = player
      high = score
    end
  end
  return winner
end
local function __trial_013(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({}), nil))
    check("case 2", deepEqual(fn({A=1}), "A"))
    check("case 3", deepEqual(fn({A=2,B=5}), "B"))
    check("case 4", deepEqual(fn({Z=6,A=6}), "A"))
    check("case 5", deepEqual(fn({A=0,B=0}), "A"))
    check("case 6", deepEqual(fn({C=-3,B=-1}), "B"))
    return passed, total
end
tests["practice-run-013"] = function()
    local goodPassed, goodTotal = __trial_013(function() return __good_013 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-013: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_013, function() return __bad_013 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-013: incorrect solution passed")
end

local function __good_014(count: number): boolean
  return count % 1 == 0 and count >= 2 and count <= 12
end

local function __bad_014(count: number): boolean
  return count % 1 == 0 and count >= 3 and count <= 12
end
local function __trial_014(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(2), true))
    check("case 2", deepEqual(fn(12), true))
    check("case 3", deepEqual(fn(1), false))
    check("case 4", deepEqual(fn(13), false))
    check("case 5", deepEqual(fn(4.5), false))
    check("case 6", deepEqual(fn(8), true))
    return passed, total
end
tests["practice-run-014"] = function()
    local goodPassed, goodTotal = __trial_014(function() return __good_014 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-014: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_014, function() return __bad_014 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-014: incorrect solution passed")
end

local function __good_015(base: number, combo: number): number
  if base < 0 or base % 1 ~= 0 then return 0 end
  return base * math.clamp(combo, 1, 5)
end

local function __bad_015(base: number, combo: number): number
  if base < 0 or base % 1 ~= 0 then return 0 end
  return base * math.clamp(combo, 1, 6)
end
local function __trial_015(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(10,1), 10))
    check("case 2", deepEqual(fn(10,3), 30))
    check("case 3", deepEqual(fn(10,9), 50))
    check("case 4", deepEqual(fn(10,0), 10))
    check("case 5", deepEqual(fn(-1,4), 0))
    check("case 6", deepEqual(fn(1.5,2), 0))
    return passed, total
end
tests["practice-run-015"] = function()
    local goodPassed, goodTotal = __trial_015(function() return __good_015 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-015: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_015, function() return __bad_015 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-015: incorrect solution passed")
end

local function __good_016(phase: string, participants, playerId: number)
  local result = {}
  for _, id in participants do table.insert(result, id) end
  if phase ~= "Lobby" then return result end
  for _, id in result do if id == playerId then return result end end
  table.insert(result, playerId)
  return result
end

local function __bad_016(phase: string, participants, playerId: number)
  local result = {}
  for _, id in participants do table.insert(result, id) end
  if phase ~= "Playing" then return result end
  for _, id in result do if id == playerId then return result end end
  table.insert(result, playerId)
  return result
end
local function __trial_016(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn("Lobby",{},1), {1}))
    check("case 2", deepEqual(fn("Lobby",{1,2},3), {1,2,3}))
    check("case 3", deepEqual(fn("Lobby",{1,2},1), {1,2}))
    check("case 4", deepEqual(fn("Playing",{1},2), {1}))
    check("case 5", deepEqual(fn("Results",{1},2), {1}))
    check("case 6", deepEqual(fn("Lobby",{4},5), {4,5}))
    return passed, total
end
tests["practice-run-016"] = function()
    local goodPassed, goodTotal = __trial_016(function() return __good_016 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-016: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_016, function() return __bad_016 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-016: incorrect solution passed")
end

local function __good_017(attacker: string, victim: string, active: boolean): boolean
  return active and attacker ~= "" and victim ~= "" and attacker ~= victim
end

local function __bad_017(attacker: string, victim: string, active: boolean): boolean
  return active and attacker ~= "" and victim ~= "" and attacker == victim
end
local function __trial_017(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn("red","blue",true), true))
    check("case 2", deepEqual(fn("red","red",true), false))
    check("case 3", deepEqual(fn("red","blue",false), false))
    check("case 4", deepEqual(fn("","blue",true), false))
    check("case 5", deepEqual(fn("red","",true), false))
    check("case 6", deepEqual(fn("blue","red",true), true))
    return passed, total
end
tests["practice-run-017"] = function()
    local goodPassed, goodTotal = __trial_017(function() return __good_017 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-017: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_017, function() return __bad_017 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-017: incorrect solution passed")
end

local function __good_018(coins: number, claimed, roundId: string)
  local flags = {}
  for id, yes in claimed do flags[id] = yes end
  if not flags[roundId] then
    flags[roundId] = true
    coins += 25
  end
  return {coins=coins,claimed=flags}
end

local function __bad_018(coins: number, claimed, roundId: string)
  local flags = {}
  for id, yes in claimed do flags[id] = yes end
  if flags[roundId] then
    flags[roundId] = true
    coins += 25
  end
  return {coins=coins,claimed=flags}
end
local function __trial_018(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(0,{},'r1'), {coins=25,claimed={r1=true}}))
    check("case 2", deepEqual(fn(50,{r1=true},'r1'), {coins=50,claimed={r1=true}}))
    check("case 3", deepEqual(fn(75,{r1=true},'r2'), {coins=100,claimed={r1=true,r2=true}}))
    check("case 4", deepEqual(fn(0,{r2=true},'r3'), {coins=25,claimed={r2=true,r3=true}}))
    check("case 5", deepEqual(fn(10,{},'x'), {coins=35,claimed={x=true}}))
    check("case 6", deepEqual(fn(100,{a=true,b=true},'b'), {coins=100,claimed={a=true,b=true}}))
    return passed, total
end
tests["practice-run-018"] = function()
    local goodPassed, goodTotal = __trial_018(function() return __good_018 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-018: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_018, function() return __bad_018 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-018: incorrect solution passed")
end

local function __good_019(cursor: number, count: number): number?
  if count <= 0 or count % 1 ~= 0 then return nil end
  return (cursor % count) + 1
end

local function __bad_019(cursor: number, count: number): number?
  if count <= 0 or count % 1 ~= 0 then return nil end
  return ((cursor + 1) % count) + 1
end
local function __trial_019(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(0,3), 1))
    check("case 2", deepEqual(fn(1,3), 2))
    check("case 3", deepEqual(fn(2,3), 3))
    check("case 4", deepEqual(fn(3,3), 1))
    check("case 5", deepEqual(fn(10,2), 1))
    check("case 6", deepEqual(fn(0,0), nil))
    return passed, total
end
tests["practice-run-019"] = function()
    local goodPassed, goodTotal = __trial_019(function() return __good_019 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-019: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_019, function() return __bad_019 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-019: incorrect solution passed")
end

local function __good_020(redScore: number, blueScore: number, remaining: number): string?
  if remaining > 0 then return nil end
  if redScore > blueScore then return "red" end
  if blueScore > redScore then return "blue" end
  return "draw"
end

local function __bad_020(redScore: number, blueScore: number, remaining: number): string?
  if remaining >= 0 then return nil end
  if redScore > blueScore then return "red" end
  if blueScore > redScore then return "blue" end
  return "draw"
end
local function __trial_020(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(3,2,10), nil))
    check("case 2", deepEqual(fn(3,2,0), "red"))
    check("case 3", deepEqual(fn(2,3,0), "blue"))
    check("case 4", deepEqual(fn(4,4,0), "draw"))
    check("case 5", deepEqual(fn(0,0,0), "draw"))
    check("case 6", deepEqual(fn(2,3,1), nil))
    return passed, total
end
tests["practice-run-020"] = function()
    local goodPassed, goodTotal = __trial_020(function() return __good_020 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-020: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_020, function() return __bad_020 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-020: incorrect solution passed")
end

local function __good_021(base: number, tier: number): number?
  if base <= 0 or base % 1 ~= 0 or tier < 0 or tier % 1 ~= 0 then return nil end
  return math.floor(base * (1.25 ^ tier))
end

local function __bad_021(base: number, tier: number): number?
  if base <= 0 or base % 1 ~= 0 or tier < 0 or tier % 1 ~= 0 then return nil end
  return math.floor(base * (1 + 0.25 * tier))
end
local function __trial_021(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(100,0), 100))
    check("case 2", deepEqual(fn(100,1), 125))
    check("case 3", deepEqual(fn(100,2), 156))
    check("case 4", deepEqual(fn(80,3), 156))
    check("case 5", deepEqual(fn(5,1), 6))
    check("case 6", deepEqual(fn(40,-1), nil))
    return passed, total
end
tests["practice-run-021"] = function()
    local goodPassed, goodTotal = __trial_021(function() return __good_021 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-021: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_021, function() return __bad_021 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-021: incorrect solution passed")
end

local function __good_022(balance: number, price: number): boolean
  if balance < 0 or price <= 0 or balance % 1 ~= 0 or price % 1 ~= 0 then return false end
  return balance >= price
end

local function __bad_022(balance: number, price: number): boolean
  if balance < 0 or price <= 0 or balance % 1 ~= 0 or price % 1 ~= 0 then return false end
  return balance > price
end
local function __trial_022(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(10,10), true))
    check("case 2", deepEqual(fn(20,10), true))
    check("case 3", deepEqual(fn(9,10), false))
    check("case 4", deepEqual(fn(0,0), false))
    check("case 5", deepEqual(fn(15.5,10), false))
    check("case 6", deepEqual(fn(10,4.5), false))
    return passed, total
end
tests["practice-run-022"] = function()
    local goodPassed, goodTotal = __trial_022(function() return __good_022 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-022: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_022, function() return __bad_022 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-022: incorrect solution passed")
end

local function __good_023(balance: number, grant: number, cap: number): number
  if grant < 0 then return balance end
  return math.min(cap, balance + grant)
end

local function __bad_023(balance: number, grant: number, cap: number): number
  if grant < -100 then return balance end
  return math.min(cap, balance + grant)
end
local function __trial_023(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(20,5,100), 25))
    check("case 2", deepEqual(fn(95,10,100), 100))
    check("case 3", deepEqual(fn(100,1,100), 100))
    check("case 4", deepEqual(fn(10,-5,100), 10))
    check("case 5", deepEqual(fn(0,0,50), 0))
    check("case 6", deepEqual(fn(70,20,90), 90))
    return passed, total
end
tests["practice-run-023"] = function()
    local goodPassed, goodTotal = __trial_023(function() return __good_023 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-023: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_023, function() return __bad_023 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-023: incorrect solution passed")
end

local function __good_024(price: number, count: number): number?
  if price < 0 or count <= 0 or count % 1 ~= 0 then return nil end
  return math.floor(price * count * 0.6)
end

local function __bad_024(price: number, count: number): number?
  if price < 0 or count <= 0 or count % 1 ~= 0 then return nil end
  return math.floor(price * count * 0.7)
end
local function __trial_024(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(10,1), 6))
    check("case 2", deepEqual(fn(9,1), 5))
    check("case 3", deepEqual(fn(9,2), 10))
    check("case 4", deepEqual(fn(100,3), 180))
    check("case 5", deepEqual(fn(4,3), 7))
    check("case 6", deepEqual(fn(10,0), nil))
    return passed, total
end
tests["practice-run-024"] = function()
    local goodPassed, goodTotal = __trial_024(function() return __good_024 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-024: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_024, function() return __bad_024 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-024: incorrect solution passed")
end

local function __good_025(prices, discount: number): number?
  if discount < 0 or discount > 50 or discount % 1 ~= 0 then return nil end
  local total = 0
  for _, cost in prices do
    if cost < 0 or cost % 1 ~= 0 then return nil end
    total += cost
  end
  return math.floor(total * (100 - discount) / 100)
end

local function __bad_025(prices, discount: number): number?
  if discount < 0 or discount > 50 or discount % 1 ~= 0 then return nil end
  local total = 0
  for _, cost in prices do
    if cost < 0 or cost % 1 ~= 0 then return nil end
    total += cost
  end
  return math.ceil(total * (100 - discount) / 100)
end
local function __trial_025(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({10,20},0), 30))
    check("case 2", deepEqual(fn({10,20},10), 27))
    check("case 3", deepEqual(fn({1,2},25), 2))
    check("case 4", deepEqual(fn({11,11},50), 11))
    check("case 5", deepEqual(fn({},50), 0))
    check("case 6", deepEqual(fn({10},51), nil))
    return passed, total
end
tests["practice-run-025"] = function()
    local goodPassed, goodTotal = __trial_025(function() return __good_025 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-025: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_025, function() return __bad_025 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-025: incorrect solution passed")
end

local function __good_026(weights, roll: number): number?
  if roll < 1 or roll % 1 ~= 0 then return nil end
  local total = 0
  for _, weight in weights do
    total += weight
    if roll <= total then return _ end
  end
  return nil
end

local function __bad_026(weights, roll: number): number?
  if roll < 1 or roll % 1 ~= 0 then return nil end
  local total = 0
  for _, weight in weights do
    total += weight
    if roll < total then return _ end
  end
  return nil
end
local function __trial_026(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({2,3,1},1), 1))
    check("case 2", deepEqual(fn({2,3,1},2), 1))
    check("case 3", deepEqual(fn({2,3,1},3), 2))
    check("case 4", deepEqual(fn({2,3,1},5), 2))
    check("case 5", deepEqual(fn({2,3,1},6), 3))
    check("case 6", deepEqual(fn({2,3,1},7), nil))
    return passed, total
end
tests["practice-run-026"] = function()
    local goodPassed, goodTotal = __trial_026(function() return __good_026 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-026: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_026, function() return __bad_026 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-026: incorrect solution passed")
end

local function __good_027(inventory, recipe)
  for item, amount in recipe do
    if amount <= 0 or (inventory[item] or 0) < amount then return nil end
  end
  local result = {}
  for item, count in inventory do result[item] = count end
  for item, amount in recipe do result[item] -= amount end
  return result
end

local function __bad_027(inventory, recipe)
  for item, amount in recipe do
    if amount <= 0 or (inventory[item] or 0) <= amount then return nil end
  end
  local result = {}
  for item, count in inventory do result[item] = count end
  for item, amount in recipe do result[item] -= amount end
  return result
end
local function __trial_027(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({wood=2,iron=1},{wood=2,iron=1}), {wood=0,iron=0}))
    check("case 2", deepEqual(fn({wood=5,iron=1},{wood=2,iron=1}), {wood=3,iron=0}))
    check("case 3", deepEqual(fn({wood=1},{wood=2}), nil))
    check("case 4", deepEqual(fn({wood=3},{iron=1}), nil))
    check("case 5", deepEqual(fn({wood=3},{wood=1}), {wood=2}))
    check("case 6", deepEqual(fn({wood=4,stone=2},{wood=2}), {wood=2,stone=2}))
    return passed, total
end
tests["practice-run-027"] = function()
    local goodPassed, goodTotal = __trial_027(function() return __good_027 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-027: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_027, function() return __bad_027 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-027: incorrect solution passed")
end

local function __good_028(current: number, amount: number, limit: number): number
  if amount < 0 then return current end
  return math.min(limit, current + amount)
end

local function __bad_028(current: number, amount: number, limit: number): number
  if amount < 0 then return current end
  return math.min(limit - 1, current + amount)
end
local function __trial_028(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(0,1,5), 1))
    check("case 2", deepEqual(fn(4,1,5), 5))
    check("case 3", deepEqual(fn(4,5,5), 5))
    check("case 4", deepEqual(fn(5,1,5), 5))
    check("case 5", deepEqual(fn(3,-2,5), 3))
    check("case 6", deepEqual(fn(1,0,2), 1))
    return passed, total
end
tests["practice-run-028"] = function()
    local goodPassed, goodTotal = __trial_028(function() return __good_028 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-028: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_028, function() return __bad_028 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-028: incorrect solution passed")
end

local function __good_029(source, dest, item: string)
  if (source[item] or 0) < 1 then return nil end
  local from = {}
  local to = {}
  for name, amount in source do from[name] = amount end
  for name, amount in dest do to[name] = amount end
  from[item] = from[item] - 1
  to[item] = (to[item] or 0) + 1
  return {from=from,to=to}
end

local function __bad_029(source, dest, item: string)
  if (source[item] or 0) < 1 then return nil end
  local from = {}
  local to = {}
  for name, amount in source do from[name] = amount end
  for name, amount in dest do to[name] = amount end
  from[item] = from[item] - 0
  to[item] = (to[item] or 0) + 1
  return {from=from,to=to}
end
local function __trial_029(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn({wood=1},{},'wood'), {from={wood=0},to={wood=1}}))
    check("case 2", deepEqual(fn({wood=4},{wood=2},'wood'), {from={wood=3},to={wood=3}}))
    check("case 3", deepEqual(fn({}, {}, 'wood'), nil))
    check("case 4", deepEqual(fn({wood=2,iron=1},{gold=5},'wood'), {from={wood=1,iron=1},to={gold=5,wood=1}}))
    check("case 5", deepEqual(fn({iron=1},{wood=1},'wood'), nil))
    check("case 6", deepEqual(fn({wood=2},{wood=3},'wood'), {from={wood=1},to={wood=4}}))
    return passed, total
end
tests["practice-run-029"] = function()
    local goodPassed, goodTotal = __trial_029(function() return __good_029 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-029: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_029, function() return __bad_029 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-029: incorrect solution passed")
end

local function __good_030(total: number, buyerPortion: number)
  if total < 0 or buyerPortion < 0 or buyerPortion > total then return nil end
  if total % 1 ~= 0 or buyerPortion % 1 ~= 0 then return nil end
  return {buyer=buyerPortion,seller=total-buyerPortion}
end

local function __bad_030(total: number, buyerPortion: number)
  if total < 0 or buyerPortion < 0 or buyerPortion >= total then return nil end
  if total % 1 ~= 0 or buyerPortion % 1 ~= 0 then return nil end
  return {buyer=buyerPortion,seller=total-buyerPortion}
end
local function __trial_030(load_answer)
    local passed, total = 0, 0
    local function check(_name, condition)
        total += 1
        if condition then passed += 1 end
    end
    local fn = load_answer()
    check("case 1", deepEqual(fn(100,20), {buyer=20,seller=80}))
    check("case 2", deepEqual(fn(100,100), {buyer=100,seller=0}))
    check("case 3", deepEqual(fn(0,0), {buyer=0,seller=0}))
    check("case 4", deepEqual(fn(1,0), {buyer=0,seller=1}))
    check("case 5", deepEqual(fn(50,51), nil))
    check("case 6", deepEqual(fn(100,-1), nil))
    return passed, total
end
tests["practice-run-030"] = function()
    local goodPassed, goodTotal = __trial_030(function() return __good_030 end)
    assert(goodTotal == 6 and goodPassed == 6, "practice-run-030: reference failed")
    local ok, badPassed, badTotal = pcall(__trial_030, function() return __bad_030 end)
    assert(not ok or (badTotal == 6 and badPassed < 6), "practice-run-030: incorrect solution passed")
end

return tests
