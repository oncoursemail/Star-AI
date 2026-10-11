```luau
--!strict
local Players = game:GetService("Players")

local COOLDOWN = 2
local lastUse: { [Player]: number } = {}
local count = 0

local AbilityGate = {}

function AbilityGate.tryUse(player: Player): boolean
	local now = os.clock()
	local last = lastUse[player]
	if last ~= nil and now - last < COOLDOWN then
		return false
	end
	if last == nil then
		count += 1
	end
	lastUse[player] = now
	return true
end

function AbilityGate.forget(player: Player)
	if lastUse[player] ~= nil then
		lastUse[player] = nil
		count -= 1
	end
end

function AbilityGate.trackedCount(): number
	return count
end

Players.PlayerRemoving:Connect(AbilityGate.forget)

return AbilityGate
```
