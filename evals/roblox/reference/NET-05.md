```luau
--!strict
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")

local store = DataStoreService:GetDataStore("PlayerData")
local DEFAULTS = { coins = 0 }
local MAX_ATTEMPTS = 3

local data: { [Player]: { [string]: any } } = {}
local PlayerData = {}

local function keyFor(player: Player): string
	return "Player_" .. player.UserId
end

local function save(player: Player): boolean
	local snapshot = data[player]
	if snapshot == nil then
		return true
	end
	for attempt = 1, MAX_ATTEMPTS do
		local ok = pcall(function()
			store:UpdateAsync(keyFor(player), function(_old)
				return snapshot
			end)
		end)
		if ok then
			return true
		end
		if attempt < MAX_ATTEMPTS then
			task.wait(2 ^ attempt)
		end
	end
	return false
end

local function load(player: Player)
	local ok, saved = pcall(function()
		return store:GetAsync(keyFor(player))
	end)
	local loaded = {}
	for k, v in pairs(DEFAULTS) do
		loaded[k] = v
	end
	if ok and type(saved) == "table" then
		for k, v in pairs(saved) do
			loaded[k] = v
		end
	end
	data[player] = loaded
end

function PlayerData.get(player: Player): { [string]: any }?
	return data[player]
end

Players.PlayerAdded:Connect(load)
for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(load, player)
end

Players.PlayerRemoving:Connect(function(player)
	save(player)
	data[player] = nil
end)

game:BindToClose(function()
	for _, player in ipairs(Players:GetPlayers()) do
		save(player)
	end
end)

return PlayerData
```
