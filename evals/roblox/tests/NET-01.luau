local remote = { OnServerEvent = Signal.new() }
local grants = {}
local observed = false
local function giveItem(player, itemId)
	observed = true
	local k = player.Name .. "|" .. tostring(itemId)
	grants[k] = (grants[k] or 0) + 1
end
local playersSvc = { PlayerRemoving = Signal.new(), PlayerAdded = Signal.new(), GetPlayers = function() return {} end }
local g = mockGame({ Players = playersSvc, ReplicatedStorage = node({ BuyItem = remote }) })
load_answer({ BuyItem = remote, giveItem = giveItem, Catalog = { sword = 100, shield = 250 }, game = g })
local n = 0
local function fresh(coins)
	n += 1
	return mockPlayer("p" .. n, n, coins)
end
local function fire(player, ...)
	local args = table.pack(...)
	return pcall(function() remote.OnServerEvent:Fire(player, table.unpack(args, 1, args.n)) end)
end
-- An answer that defines its own giveItem is not observable through the stub: judge the grant by the charge
-- (the catalog price of a sword is 100), which the task ties to the grant.
local function owned(player, id, start)
	if observed then return grants[player.Name .. "|" .. tostring(id)] or 0 end
	return math.floor(((start or 0) - player.leaderstats.Coins.Value) / 100)
end

local p = fresh(100)
fire(p, "sword", -1e9)
check("a client price of -1e9 is ignored (balance 0, sword granted once)", p.leaderstats.Coins.Value == 0 and owned(p, "sword", 100) == 1)

local priceOk = true
for _, price in { -1e9, 0, 0 / 0, "free" } do
	local q = fresh(1000)
	fire(q, "sword", price)
	local change = 1000 - q.leaderstats.Coins.Value
	if change ~= 0 and change ~= 100 then priceOk = false end
end
local q = fresh(1000)
fire(q, "sword", nil)
local change = 1000 - q.leaderstats.Coins.Value
if change ~= 0 and change ~= 100 then priceOk = false end
check("whatever price the client sends, the charge is 0 or exactly the catalog price", priceOk)

local idOk = true
for _, id in { 5, {}, "gold", string.rep("x", 10000) } do
	local r = fresh(1000)
	local ok = fire(r, id, 100)
	if not ok or r.leaderstats.Coins.Value ~= 1000 or owned(r, id, 1000) ~= 0 then idOk = false end
end
local r = fresh(1000)
local okNil = fire(r, nil, 100)
if not okNil or r.leaderstats.Coins.Value ~= 1000 then idOk = false end
check("invalid or unknown itemId: no charge, no grant, no error", idOk)

local poor, rich = fresh(99), fresh(100)
fire(poor, "sword", 100)
fire(rich, "sword", 100)
check("99 coins cannot buy a sword", poor.leaderstats.Coins.Value == 99 and owned(poor, "sword", 99) == 0)
check("100 coins buys it: balance 0, granted once", rich.leaderstats.Coins.Value == 0 and owned(rich, "sword", 100) == 1)

local spammer = fresh(1000)
for _ = 1, 50 do fire(spammer, "sword", 100) end
check("50 rapid valid calls grant once and charge once", owned(spammer, "sword", 1000) == 1 and spammer.leaderstats.Coins.Value == 900)

local rnd = lcg(1234)
local pool = { "sword", "shield", 5, "gold", {}, false }
local prices = { -1e9, 0, 100, 250, "free", 1e9 }
local players = { fresh(300), fresh(50), fresh(1000), fresh(0), fresh(260) }
local fuzzOk = true
for _ = 1, 500 do
	local pl = players[rnd(#players)]
	local before = pl.leaderstats.Coins.Value
	local ok = fire(pl, pool[rnd(#pool)], prices[rnd(#prices)])
	local after = pl.leaderstats.Coins.Value
	if not ok or after > before or after < 0 then fuzzOk = false end
end
check("fuzz (500 calls): never an error, the balance never rises or goes negative", fuzzOk)
