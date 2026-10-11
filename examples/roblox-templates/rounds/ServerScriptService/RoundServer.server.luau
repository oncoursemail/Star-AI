--!strict
-- The server alone owns round state, participants, winner selection and coins.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local shared = ReplicatedStorage:WaitForChild("Shared")
local RoundState = require(shared:WaitForChild("RoundState"))
local WinnerRules = require(shared:WaitForChild("WinnerRules"))
local ArenaFactory = require(ServerScriptService:WaitForChild("ArenaFactory"))
local RoundResources = require(ServerScriptService:WaitForChild("RoundResources"))
local Config = require(ServerScriptService:WaitForChild("RoundConfig"))

type Entry = {
	player: Player,
	character: Model,
	alive: boolean,
	score: number,
}

local lobbySpawn = ArenaFactory.ensureLobby()
local state = RoundState.Intermission
local deadline: number? = nil
local entrants: { [number]: Entry } = {}
local resources: any = nil
local rewarded: { [number]: boolean } = {}
local characterHooks: { [Player]: RBXScriptConnection } = {}

-- A single replicated attribute is authoritative for the state machine.
-- RoundDeadline is display-only countdown metadata, never client input.
ReplicatedStorage:SetAttribute("RoundState", state)
ReplicatedStorage:SetAttribute("RoundDeadline", nil)

local function setDeadline(value: number?)
	deadline = value
	ReplicatedStorage:SetAttribute("RoundDeadline", value)
end

local function advance(event: string, count: number): boolean
	local nextState, reason = RoundState.next(state, event, count, Config.MinimumPlayers)
	if nextState == nil then
		warn("Round transition rejected:", state, event, reason)
		return false
	end
	state = nextState
	ReplicatedStorage:SetAttribute("RoundState", state)
	return true
end

local function coinsFor(player: Player): IntValue
	local stats = player:FindFirstChild("leaderstats")
	if not stats then
		stats = Instance.new("Folder")
		stats.Name = "leaderstats"
		stats.Parent = player
	end
	local coins = stats:FindFirstChild("Coins")
	if not coins or not coins:IsA("IntValue") then
		coins = Instance.new("IntValue")
		coins.Name = "Coins"
		coins.Parent = stats
	end
	return coins :: IntValue
end

local function moveToLobby(player: Player)
	if player.Parent ~= Players then
		return
	end
	player.RespawnLocation = lobbySpawn
	local character = player.Character
	if character and character.Parent and character:FindFirstChild("HumanoidRootPart") then
		character:PivotTo(lobbySpawn.CFrame * CFrame.new(0, 5, 0))
	end
end

local function watchPlayer(player: Player)
	if characterHooks[player] then
		return
	end
	coinsFor(player)
	player.RespawnLocation = lobbySpawn

	local function onCharacter(character: Model)
		task.defer(function()
			local root = character:WaitForChild("HumanoidRootPart", 5)
			if not root or player.Parent ~= Players or player.Character ~= character then
				return
			end
			local entry = entrants[player.UserId]
			if state == RoundState.Playing and entry and entry.alive and entry.character == character then
				return
			end
			moveToLobby(player)
		end)
	end

	characterHooks[player] = player.CharacterAdded:Connect(onCharacter)
	if player.Character then
		onCharacter(player.Character)
	end
end

Players.PlayerAdded:Connect(watchPlayer)
Players.PlayerRemoving:Connect(function(player: Player)
	local entry = entrants[player.UserId]
	if entry and entry.player == player then
		entry.alive = false
	end
	local hook = characterHooks[player]
	if hook then
		hook:Disconnect()
		characterHooks[player] = nil
	end
end)
for _, player in ipairs(Players:GetPlayers()) do
	watchPlayer(player)
end

local function aliveCount(): number
	local count = 0
	for _, entry in pairs(entrants) do
		if entry.alive and entry.player.Parent == Players then
			count += 1
		end
	end
	return count
end

local function cleanRound()
	for _, entry in pairs(entrants) do
		moveToLobby(entry.player)
	end
	if resources then
		resources:cleanup()
		resources = nil
	end
	table.clear(entrants)
	table.clear(rewarded)
end

local function awardWinner(userId: number)
	local entry = entrants[userId]
	if not entry or not entry.alive or rewarded[userId] then
		return
	end
	local player = Players:GetPlayerByUserId(userId)
	if not player or player ~= entry.player or player.Parent ~= Players then
		return
	end
	rewarded[userId] = true
	local coins = coinsFor(player)
	coins.Value += Config.WinnerCoins
end

local function finishRound(reason: string)
	if state ~= RoundState.Playing or not advance(reason, aliveCount()) then
		return
	end
	local candidates = {}
	for userId, entry in pairs(entrants) do
		table.insert(candidates, { userId = userId, alive = entry.alive and entry.player.Parent == Players,
			score = entry.score })
	end
	local winner = WinnerRules.resolve(candidates, reason)
	if winner then
		awardWinner(winner)
	end
	cleanRound()
	setDeadline(workspace:GetServerTimeNow() + Config.ResultsSeconds)
end

local function beginRound()
	local eligible: { Entry } = {}
	for _, player in ipairs(Players:GetPlayers()) do
		if #eligible >= Config.MaximumPlayers then
			break
		end
		local character = player.Character
		local humanoid = if character then character:FindFirstChildOfClass("Humanoid") else nil
		local root = if character then character:FindFirstChild("HumanoidRootPart") else nil
		if player.Parent == Players and character and humanoid and humanoid.Health > 0 and root then
			table.insert(eligible, { player = player, character = character, alive = true, score = 0 })
		end
	end

	if #eligible < Config.MinimumPlayers then
		advance("map_ready", #eligible)
		setDeadline(nil)
		return
	end

	local ok, arena, spawns = pcall(ArenaFactory.createArena)
	if not ok or not arena or not spawns or #spawns == 0 then
		warn("Round map could not load:", arena)
		if ok and arena then
			arena:Destroy()
		end
		advance("load_failed", 0)
		setDeadline(nil)
		return
	end

	resources = RoundResources.new()
	resources:add(function()
		arena:Destroy()
	end)
	for _, entry in ipairs(eligible) do
		entrants[entry.player.UserId] = entry
	end
	if not advance("map_ready", #eligible) then
		cleanRound()
		setDeadline(nil)
		return
	end

	for index, entry in ipairs(eligible) do
		local player = entry.player
		local character = entry.character
		local humanoid = character:FindFirstChildOfClass("Humanoid")
		if player.Parent ~= Players or player.Character ~= character
			or not humanoid or humanoid.Health <= 0 then
			entry.alive = false
			continue
		end

		local died = humanoid.Died:Connect(function()
			entry.alive = false
		end)
		resources:add(function()
			died:Disconnect()
		end)
		local removed = player.CharacterRemoving:Connect(function(previous: Model)
			if previous == character then
				entry.alive = false
			end
		end)
		resources:add(function()
			removed:Disconnect()
		end)

		local spawnPad = spawns[(index - 1) % #spawns + 1]
		local placed, message = pcall(function()
			character:PivotTo(spawnPad.CFrame * CFrame.new(0, 5, 0))
		end)
		if not placed then
			warn("Player arena teleport failed:", message)
			entry.alive = false
			moveToLobby(player)
		end
	end
	setDeadline(workspace:GetServerTimeNow() + Config.PlayingSeconds)
end

-- One scheduler coroutine; no per-round heartbeat connections or task.spawn loops.
while true do
	local now = workspace:GetServerTimeNow()
	if state == RoundState.Intermission then
		local count = #Players:GetPlayers()
		if count < Config.MinimumPlayers then
			if deadline then
				setDeadline(nil)
			end
		elseif not deadline then
			setDeadline(now + Config.IntermissionSeconds)
		elseif now >= deadline then
			setDeadline(nil)
			if advance("countdown_elapsed", count) then
				beginRound()
			end
		end
	elseif state == RoundState.Playing then
		local count = aliveCount()
		if count == 0 then
			finishRound("empty")
		elseif count == 1 then
			finishRound("winner")
		elseif deadline and now >= deadline then
			finishRound("timeout")
		end
	elseif state == RoundState.Ended and deadline and now >= deadline then
		cleanRound()
		if advance("results_elapsed", #Players:GetPlayers()) then
			setDeadline(nil)
		end
	end
	task.wait(0.2)
end
