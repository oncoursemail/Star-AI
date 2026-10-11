--!strict
-- The server is the only authority for plot ownership, purchases, collection, rebirth and persistence.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local Economy = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Economy"))
local PlayerData = require(ServerScriptService:WaitForChild("PlayerData"))
local Plots = require(ServerScriptService:WaitForChild("Plots"))

type Runtime = { handle: PlayerData.Session, state: Economy.State, plot: Plots.Plot }
local sessions: { [Player]: Runtime } = {}

Plots.create()

local function publish(player: Player, runtime: Runtime)
	local stats = player:FindFirstChild("leaderstats")
	if stats then
		local cash = stats:FindFirstChild("Cash")
		local rebirths = stats:FindFirstChild("Rebirths")
		if cash and cash:IsA("IntValue") then
			cash.Value = runtime.state.cash
		end
		if rebirths and rebirths:IsA("IntValue") then
			rebirths.Value = runtime.state.rebirths
		end
	end
	local item = Economy.nextUnlock(runtime.state)
	player:SetAttribute("TycoonNextItem", if item then item.id else "")
	player:SetAttribute("TycoonRebirthPrice", Economy.rebirthPrice(runtime.state.rebirths))
	Plots.refresh(runtime.plot, runtime.state)
end

local function notice(player: Player, message: string)
	player:SetAttribute("TycoonNotice", message)
	player:SetAttribute("TycoonNoticeVersion", (player:GetAttribute("TycoonNoticeVersion") or 0) + 1)
end

local function purchase(player: Player, itemId: string)
	local runtime = sessions[player]
	if not runtime then
		return
	end
	local nextState, reason = Economy.buy(runtime.state, itemId)
	if not nextState then
		notice(player, reason)
		return
	end
	runtime.state = nextState
	publish(player, runtime)
	notice(player, "Purchased " .. itemId)
end

local function rebirth(player: Player)
	local runtime = sessions[player]
	if not runtime then
		return
	end
	local nextState, reason = Economy.rebirth(runtime.state)
	if not nextState then
		notice(player, reason)
		return
	end
	runtime.state = nextState
	Plots.reset(runtime.plot)
	publish(player, runtime)
	notice(player, "Rebirth complete")
end

local function collect(player: Player, itemId: string)
	local runtime = sessions[player]
	if not runtime then
		return
	end
	local nextState = Economy.collect(runtime.state, itemId)
	if nextState then
		runtime.state = nextState
		publish(player, runtime)
	end
end

local function createStats(player: Player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = player
	local cash = Instance.new("IntValue")
	cash.Name = "Cash"
	cash.Parent = stats
	local rebirths = Instance.new("IntValue")
	rebirths.Name = "Rebirths"
	rebirths.Parent = stats
end

local function join(player: Player)
	local handle, state, reason = PlayerData.open(player)
	if not handle or not state then
		if player.Parent == Players then
			player:Kick("Tycoon data could not be opened (" .. (reason or "unavailable") .. "). Try again later.")
		end
		return
	end
	if player.Parent ~= Players then
		PlayerData.save(handle, function()
			return state
		end, true)
		return
	end
	local plot = Plots.claim(player, purchase, rebirth, collect)
	if not plot then
		PlayerData.save(handle, function()
			return state
		end, true)
		if player.Parent == Players then
			player:Kick("Every tycoon plot is occupied. Join a server with space.")
		end
		return
	end
	local runtime: Runtime = { handle = handle, state = state, plot = plot }
	sessions[player] = runtime
	createStats(player)
	publish(player, runtime)
	local character = player.Character
	if character then
		character:PivotTo(CFrame.new(plot.spawn.Position + Vector3.new(0, 5, 0)))
	end
end

local function leave(player: Player)
	local runtime = sessions[player]
	if not runtime then
		return
	end
	sessions[player] = nil
	Plots.release(player)
	if not PlayerData.save(runtime.handle, function()
		return runtime.state
	end, true) then
		warn("Tycoon closing save was not confirmed; the session lease will expire.")
	end
end

Players.PlayerAdded:Connect(join)
Players.PlayerRemoving:Connect(leave)
for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(join, player)
end

task.spawn(function()
	while true do
		task.wait(60)
		for player, runtime in pairs(sessions) do
			task.spawn(function()
				if sessions[player] == runtime and not PlayerData.save(runtime.handle, function()
					return runtime.state
				end, false) then
					warn("Tycoon autosave was not confirmed; it will be retried.")
				end
			end)
		end
	end
end)

game:BindToClose(function()
	local remaining = 0
	for player in pairs(sessions) do
		remaining += 1
		task.spawn(function()
			leave(player)
			remaining -= 1
		end)
	end
	local deadline = os.clock() + 25
	while remaining > 0 and os.clock() < deadline do
		task.wait(0.1)
	end
end)
