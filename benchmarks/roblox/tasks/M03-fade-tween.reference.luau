local TweenService = game:GetService("TweenService")
local M = {}
function M.fadeOut(part: BasePart, duration: number): Tween
	local tween = TweenService:Create(part, TweenInfo.new(duration, Enum.EasingStyle.Linear), { Transparency = 1 })
	tween.Completed:Connect(function(state)
		if state == Enum.PlaybackState.Completed then
			part.CanCollide = false
		end
	end)
	tween:Play()
	return tween
end
return M
