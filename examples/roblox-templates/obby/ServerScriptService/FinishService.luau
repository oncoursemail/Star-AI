--!strict
local TouchValidation = require(script.Parent.TouchValidation)

local FinishService = {}

function FinishService.connect(finish: BasePart, onFinish: (Player) -> ())
	finish.Touched:Connect(function(hit: BasePart)
		local player = TouchValidation.playerNear(hit, finish, 7)
		if player then
			onFinish(player)
		end
	end)
end

return FinishService
