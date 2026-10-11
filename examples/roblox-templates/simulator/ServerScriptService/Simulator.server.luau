--!strict
-- The only authority for currency, inventory, upgrades and rebirths.
local DataStoreService = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("SimulatorConfig"))
local RateLimiter = require(Shared:WaitForChild("RateLimiter"))
local Service = require(ServerScriptService:WaitForChild("SimulatorService"))
local ProfileStore = require(ServerScriptService:WaitForChild("ProfileStore"))

local store = DataStoreService:GetDataStore("STARSimulator_v1")
local sessionId = HttpService:GenerateGUID(false)
local profiles: { [Player]: Service.Profile } = {}
local saving: { [Player]: boolean } = {}
local leaving: { [Player]: boolean } = {}

local requestLimit = RateLimiter.new(Config.REQUEST_COOLDOWN)
local clickLimit = RateLimiter.new(Config.CLICK_COOLDOWN)
local snapshotLimit = RateLimiter.new(Config.SNAPSHOT_COOLDOWN)

local remotes = Instance.new("Folder")
remotes.Name = "SimulatorRemotes"
remotes.Parent = ReplicatedStorage

local actionEvent = Instance.new("RemoteEvent")
actionEvent.Name = "Action"
actionEvent.Parent = remotes

local stateEvent = Instance.new("RemoteEvent")
stateEvent.Name = "State"
stateEvent.Parent = remotes

local getSnapshot = Instance.new("RemoteFunction")
getSnapshot.Name = "GetSnapshot"
getSnapshot.Parent = remotes

local function keyFor(player: Player): string
	return "user_" .. tostring(player.UserId)
end

local function sync(player: Player, reason: string?)
	local profile = profiles[player]
	if not profile or leaving[player] then
		return
	end
	local leaderstats = player:FindFirstChild("leaderstats")
	if leaderstats then
		local coins = leaderstats:FindFirstChild("Coins")
		local rebirths = leaderstats:FindFirstChild("Rebirths")
		if coins and coins:IsA("IntValue") then
			coins.Value = profile.coins
		end
		if rebirths and rebirths:IsA("IntValue") then
			rebirths.Value = profile.rebirths
		end
	end
	stateEvent:FireClient(player, Service.snapshot(profile), reason)
end

local function persist(player: Player, release: boolean): boolean
	while saving[player] do
		task.wait(0.05)
	end
	local profile = profiles[player]
	if not profile then
		return true
	end
	saving[player] = true
	local called, succeeded, reason = pcall(ProfileStore.save, store, keyFor(player),
		sessionId, profile, release)
	saving[player] = nil
	if not called or not succeeded then
		warn("Simulator save failed: " .. tostring(if called then reason else "internal_error"))
		return false
	end
	return true
end

local function playerAdded(player: Player)
	local loaded, reason = ProfileStore.load(store, keyFor(player), sessionId)
	if not loaded then
		warn("Simulator load failed: " .. tostring(reason))
		player:Kick("Your simulator data could not be loaded safely. Please rejoin.")
		return
	end
	if not player.Parent then
		ProfileStore.save(store, keyFor(player), sessionId, loaded, true)
		return
	end
	profiles[player] = loaded
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = player
	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Parent = stats
	local rebirths = Instance.new("IntValue")
	rebirths.Name = "Rebirths"
	rebirths.Parent = stats
	sync(player)
end

actionEvent.OnServerEvent:Connect(function(player: Player, action: any, arg: any)
	if leaving[player] or not profiles[player] then
		return
	end
	local now = os.clock()
	if not RateLimiter.allow(requestLimit, player.UserId, now) then
		return
	end
	if type(action) ~= "string" or #action > 24
		or (arg ~= nil and (type(arg) ~= "string" or #arg > 32)) then
		return
	end
	local ok, reason = Service.apply(profiles[player], clickLimit, player.UserId, action, arg, now)
	if reason ~= "cooldown" then
		sync(player, if ok then nil else reason)
	end
end)

getSnapshot.OnServerInvoke = function(player: Player)
	if leaving[player] or not profiles[player] then
		return nil
	end
	if not RateLimiter.allow(snapshotLimit, player.UserId, os.clock()) then
		return nil
	end
	return Service.snapshot(profiles[player])
end

Players.PlayerAdded:Connect(playerAdded)
for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(playerAdded, player)
end

Players.PlayerRemoving:Connect(function(player: Player)
	leaving[player] = true
	persist(player, true)
	profiles[player] = nil
	saving[player] = nil
	RateLimiter.forget(requestLimit, player.UserId)
	RateLimiter.forget(clickLimit, player.UserId)
	RateLimiter.forget(snapshotLimit, player.UserId)
end)

task.spawn(function()
	while true do
		task.wait(60)
		for player in pairs(profiles) do
			if not leaving[player] then
				persist(player, false)
			end
		end
	end
end)

game:BindToClose(function()
	local players = Players:GetPlayers()
	local finished = 0
	for _, player in ipairs(players) do
		task.spawn(function()
			leaving[player] = true
			persist(player, true)
			finished += 1
		end)
	end
	local deadline = os.clock() + 25
	while finished < #players and os.clock() < deadline do
		task.wait(0.1)
	end
end)
