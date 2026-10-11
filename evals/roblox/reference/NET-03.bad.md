```luau
--!strict
local Players = game:GetService("Players")
local AbilityGate = {}
local seen: { [Player]: boolean } = {}
function AbilityGate.tryUse(player: Player): boolean
	seen[player] = true
	return true
end
function AbilityGate.forget(player: Player)
	seen[player] = nil
end
function AbilityGate.trackedCount(): number
	local n = 0
	for _ in seen do n += 1 end
	return n
end
Players.PlayerRemoving:Connect(AbilityGate.forget)
return AbilityGate
```
