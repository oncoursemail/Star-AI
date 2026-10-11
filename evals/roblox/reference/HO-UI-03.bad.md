Every call tweens to the new fraction.

```luau
local TweenService = game:GetService("TweenService")

local HealthBar = {}
HealthBar.__index = HealthBar

function HealthBar.new(fill: Frame)
	return setmetatable({ fill = fill }, HealthBar)
end

function HealthBar:set(current: number, max: number)
	local fraction = current / max
	local color = Color3.fromRGB(80, 200, 120)
	if fraction < 0.5 then
		color = Color3.fromRGB(240, 180, 40)
	end
	if fraction < 0.25 then
		color = Color3.fromRGB(220, 60, 60)
	end
	TweenService:Create(self.fill, TweenInfo.new(0.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		Size = UDim2.fromScale(fraction, 1),
	}):Play()
	TweenService:Create(self.fill, TweenInfo.new(0.2), { BackgroundColor3 = color }):Play()
end

return HealthBar
```
