```luau
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local speedMode = ReplicatedStorage:WaitForChild("SpeedMode")
local SPEEDS = { walk = 16, sprint = 24 }
local MAX_PER_SECOND = 5
local history: { [Player]: { number } } = {}

local function allowed(player: Player): boolean
	local now = os.clock()
	local list = history[player] or {}
	local fresh = {}
	for _, t in list do
		if now - t < 1 then
			table.insert(fresh, t)
		end
	end
	history[player] = fresh
	if #fresh >= MAX_PER_SECOND then
		return false
	end
	table.insert(fresh, now)
	return true
end

speedMode.OnServerEvent:Connect(function(player, mode)
	if not allowed(player) then
		return
	end
	if mode ~= "walk" and mode ~= "sprint" then
		return
	end
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if humanoid == nil or humanoid.Health <= 0 then
		return
	end
	local speed = SPEEDS[mode]
	if mode == "sprint" and (tonumber(player:GetAttribute("Stamina")) or 0) <= 0 then
		speed = SPEEDS.walk
	end
	humanoid.WalkSpeed = speed
end)

Players.PlayerRemoving:Connect(function(player)
	history[player] = nil
end)
```
