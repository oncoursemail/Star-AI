--!strict
local TouchValidation = require(script.Parent.TouchValidation)

local CheckpointService = {}

function CheckpointService.connect(checkpoints: { [number]: BasePart }, onCheckpoint: (Player, number) -> ())
	for stage, pad in pairs(checkpoints) do
		pad.Touched:Connect(function(hit: BasePart)
			local player = TouchValidation.playerNear(hit, pad, 7)
			if player then
				onCheckpoint(player, stage)
			end
		end)
	end
end

return CheckpointService
