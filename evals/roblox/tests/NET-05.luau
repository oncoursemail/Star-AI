local function setup(mode)
	local S = { stored = {}, writes = {}, ok = {}, setCalls = 0, yielded = false, inCb = false }
	local store = {}
	function store:GetAsync(key) return S.stored[key] end
	function store:UpdateAsync(key, fn)
		S.writes[key] = (S.writes[key] or 0) + 1
		if mode == "down" or (mode == "flaky" and S.writes[key] <= 2) then error("503 simulated outage") end
		S.inCb = true
		local new = fn(S.stored[key])
		S.inCb = false
		if new ~= nil then
			S.stored[key] = new
			S.ok[key] = (S.ok[key] or 0) + 1
		end
		return new
	end
	function store:SetAsync(key, value)
		S.setCalls += 1
		S.writes[key] = (S.writes[key] or 0) + 1
		if mode == "down" or (mode == "flaky" and S.writes[key] <= 2) then error("503 simulated outage") end
		S.stored[key] = value
		S.ok[key] = (S.ok[key] or 0) + 1
	end
	local dss = { GetDataStore = function() return store end }
	local players = { PlayerAdded = Signal.new(), PlayerRemoving = Signal.new(), list = {} }
	function players:GetPlayers() return self.list end
	local g = mockGame({ DataStoreService = dss, Players = players })
	local function wait(t) if S.inCb then S.yielded = true end return t or 0.03 end
	local ret = load_answer({
		game = g, wait = wait,
		task = { wait = wait, spawn = function(f, ...) f(...) end, defer = function(f, ...) f(...) end, delay = function() end },
	})
	if type(ret) == "table" then
		for _, name in { "init", "Init", "start", "Start", "setup", "Setup", "run", "Run" } do
			if type(ret[name]) == "function" then pcall(ret[name]) end
		end
	end
	local function join(id)
		local p = { Name = "P" .. id, UserId = id }
		table.insert(players.list, p)
		players.PlayerAdded:Fire(p)
		return p
	end
	return S, players, g, join
end

local S, players, g, join = setup("flaky")
local p = join(11)
local okLeave = pcall(function() players.PlayerRemoving:Fire(p) end)
check("flaky store (first 2 writes fail): saved under Player_<UserId> within 4 attempts",
	okLeave and S.stored["Player_11"] ~= nil and (S.writes["Player_11"] or 0) <= 4)

local D, dplayers, _, djoin = setup("down")
local dp = djoin(12)
local okDown = pcall(function() dplayers.PlayerRemoving:Fire(dp) end)
check("store always down: the save ends (no endless loop, at most 6 attempts, no error escapes)",
	okDown and (D.writes["Player_12"] or 0) <= 6)

local O, oplayers, _, ojoin = setup("ok")
local op = ojoin(13)
pcall(function() oplayers.PlayerRemoving:Fire(op) end)
check("PlayerRemoving causes exactly one successful save", O.ok["Player_13"] == 1)

local B, _, bg, bjoin = setup("ok")
bjoin(21) bjoin(22) bjoin(23)
for _, fn in bg.__closers do pcall(fn) end
check("BindToClose saves all three loaded players", B.stored["Player_21"] ~= nil and B.stored["Player_22"] ~= nil and B.stored["Player_23"] ~= nil)
check("nothing yields inside the UpdateAsync callback", not (S.yielded or D.yielded or O.yielded or B.yielded))
