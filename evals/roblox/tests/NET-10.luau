local remote = { OnServerEvent = Signal.new() }
local now = 0
local clock = function() return now end
local playersSvc = { PlayerRemoving = Signal.new(), PlayerAdded = Signal.new(), GetPlayers = function() return {} end }
local g = mockGame({ Players = playersSvc, ReplicatedStorage = node({ SpeedMode = remote }) })
load_answer({
	SpeedMode = remote, game = g, workspace = { GetServerTimeNow = clock },
	os = { clock = clock, time = clock, date = os.date }, time = clock, tick = clock,
})
local n = 0
local function newPlayer(stamina, health)
	n += 1
	local p = mockPlayer("p" .. n, n, 0)
	local char, hum = mockCharacter(health)
	p.Character = char
	p:SetAttribute("Stamina", stamina)
	return p, hum
end
local function fire(player, ...)
	local args = table.pack(...)
	return pcall(function() remote.OnServerEvent:Fire(player, table.unpack(args, 1, args.n)) end)
end

local p1, h1 = newPlayer(50)
fire(p1, "sprint")
check("sprint with stamina sets WalkSpeed 24", h1.WalkSpeed == 24)
now += 1
fire(p1, "walk")
check("walk sets WalkSpeed 16", h1.WalkSpeed == 16)

now += 1
local p2, h2 = newPlayer(0)
fire(p2, "sprint")
check("sprint without stamina stays at 16", h2.WalkSpeed == 16)

now += 1
local p3, h3 = newPlayer(50)
local ok1 = fire(p3, 100)
local ok2 = fire(p3, "fast")
local ok3 = fire(p3, nil)
local ok4 = fire(p3, {})
check("a number, an unknown string, nil or a table changes nothing and never throws",
	h3.WalkSpeed == 16 and ok1 and ok2 and ok3 and ok4)

now += 1
local p4 = newPlayer(50)
p4.Character = nil
local okNoChar = fire(p4, "sprint")
local p5, h5 = newPlayer(50, 0)
local okDead = fire(p5, "sprint")
check("no character or a dead humanoid: nothing changes and nothing throws", okNoChar and okDead and h5.WalkSpeed == 16)

now += 1
local p6, h6 = newPlayer(50)
local modes = { "sprint", "sprint", "sprint", "sprint", "sprint", "walk" }
for _, m in modes do fire(p6, m) end
check("at most 5 requests per second per player: the sixth (walk) is ignored", h6.WalkSpeed == 24)
now += 1.1
fire(p6, "walk")
check("requests are accepted again after the window", h6.WalkSpeed == 16)
