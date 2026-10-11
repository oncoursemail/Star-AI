--!strict
local TouchValidation = require(script.Parent.TouchValidation)

local KillService = {}
local COOLDOWN_SECONDS = 1

function KillService.connect(killParts: { BasePart })
	local lastHit: { [Humanoid]: number } = {}
	for _, part in ipairs(killParts) do
		part.Touched:Connect(function(hit: BasePart)
			local player = TouchValidation.playerNear(hit, part, 7)
			if not player then
				return
			end
			local character = player.Character
			local humanoid = if character then character:FindFirstChildOfClass("Humanoid") else nil
			if not humanoid or humanoid.Health <= 0 then
				return
			end
			local now = os.clock()
			if lastHit[humanoid] and now - lastHit[humanoid] < COOLDOWN_SECONDS then
				return
			end
			lastHit[humanoid] = now
			humanoid.Health = 0
			task.delay(COOLDOWN_SECONDS, function()
				if lastHit[humanoid] == now then
					lastHit[humanoid] = nil
				end
			end)
		end)
	end
end

return KillService
