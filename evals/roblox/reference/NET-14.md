```luau
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")

local store = DataStoreService:GetDataStore("PlayerData")
local AUTOSAVE_INTERVAL = 60
local SHUTDOWN_LIMIT = 25
local cache: { [Player]: { [string]: any } } = {}

local function save(player: Player)
	local data = cache[player]
	if data == nil then
		return
	end
	local ok, err = pcall(function()
		store:UpdateAsync("Player_" .. player.UserId, function()
			return data
		end)
	end)
	if not ok then
		warn("save failed for " .. player.Name .. ": " .. tostring(err))
	end
end

Players.PlayerAdded:Connect(function(player)
	local ok, saved = pcall(function()
		return store:GetAsync("Player_" .. player.UserId)
	end)
	cache[player] = (ok and type(saved) == "table") and saved or { coins = 0 }
	task.spawn(function()
		-- a per-player offset spreads the writes over the minute
		task.wait(math.random() * AUTOSAVE_INTERVAL)
		while player.Parent == Players do
			save(player)
			task.wait(AUTOSAVE_INTERVAL)
		end
	end)
end)

Players.PlayerRemoving:Connect(function(player)
	save(player)
	cache[player] = nil
end)

game:BindToClose(function()
	local pending = 0
	for _, player in Players:GetPlayers() do
		pending += 1
		task.spawn(function()
			save(player)
			pending -= 1
		end)
	end
	local started = os.clock()
	while pending > 0 and os.clock() - started < SHUTDOWN_LIMIT do
		task.wait(0.1)
	end
end)
```
