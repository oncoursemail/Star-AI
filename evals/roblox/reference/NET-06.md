```luau
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local hit = ReplicatedStorage:WaitForChild("Hit")
local DAMAGE, RANGE, COOLDOWN = 10, 12, 0.6
local lastSwing: { [Player]: number } = {}

hit.OnServerEvent:Connect(function(player, target)
	local now = os.clock()
	if now - (lastSwing[player] or -math.huge) < COOLDOWN then
		return
	end
	lastSwing[player] = now
	if typeof(target) ~= "Instance" or not target:IsA("Model") then
		return
	end
	local attacker = player.Character
	if attacker == nil or target == attacker then
		return
	end
	local humanoid = target:FindFirstChildOfClass("Humanoid")
	local targetRoot = target:FindFirstChild("HumanoidRootPart")
	local attackerRoot = attacker:FindFirstChild("HumanoidRootPart")
	if humanoid == nil or humanoid.Health <= 0 or targetRoot == nil or attackerRoot == nil then
		return
	end
	if (targetRoot.Position - attackerRoot.Position).Magnitude > RANGE then
		return
	end
	humanoid:TakeDamage(DAMAGE)
end)

Players.PlayerRemoving:Connect(function(player)
	lastSwing[player] = nil
end)
```
