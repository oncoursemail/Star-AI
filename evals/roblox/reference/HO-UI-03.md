The bar remembers the last fraction it showed and the tween that is running. A new fraction cancels the old tween first, then one tween moves both `Size` and `BackgroundColor3`. Bad numbers become 0 instead of dividing by zero.

```luau
--!strict
local TweenService = game:GetService("TweenService")

local HealthBar = {}
HealthBar.__index = HealthBar

local INFO = TweenInfo.new(0.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local GREEN = Color3.fromRGB(80, 200, 120)
local AMBER = Color3.fromRGB(240, 180, 40)
local RED = Color3.fromRGB(220, 60, 60)

function HealthBar.new(fill: Frame)
	return setmetatable({
		fill = fill,
		tween = nil :: Tween?,
		applied = nil :: number?,
	}, HealthBar)
end

local function fractionOf(current: any, max: any): number
	if type(current) ~= "number" or type(max) ~= "number" or current ~= current or max ~= max or max <= 0 then
		return 0
	end
	return math.clamp(current / max, 0, 1)
end

function HealthBar:set(current: number, max: number)
	local fraction = fractionOf(current, max)
	if fraction == self.applied then
		return
	end
	self.applied = fraction
	if self.tween then
		self.tween:Cancel()
	end
	local color = if fraction > 0.5 then GREEN elseif fraction > 0.25 then AMBER else RED
	local tween = TweenService:Create(self.fill, INFO, {
		Size = UDim2.fromScale(fraction, 1),
		BackgroundColor3 = color,
	})
	self.tween = tween
	tween:Play()
end

return HealthBar
```
