```luau
local Lighting = game:GetService("Lighting")

local function getOrCreate(className)
	local existing = Lighting:FindFirstChildOfClass(className)
	if existing then
		return existing
	end
	local created = Instance.new(className)
	created.Parent = Lighting
	return created
end

Lighting.ClockTime = 17.5
Lighting.Brightness = 2
Lighting.OutdoorAmbient = Color3.fromRGB(120, 95, 90)
Lighting.Ambient = Color3.fromRGB(60, 50, 55)

local atmosphere = getOrCreate("Atmosphere")
atmosphere.Density = 0.35
atmosphere.Offset = 0.1
atmosphere.Haze = 1.2
atmosphere.Glare = 0.4
atmosphere.Color = Color3.fromRGB(235, 190, 160)
atmosphere.Decay = Color3.fromRGB(120, 80, 70)

local bloom = getOrCreate("BloomEffect")
bloom.Intensity = 0.3
bloom.Size = 24
bloom.Threshold = 1.8

local grade = getOrCreate("ColorCorrectionEffect")
grade.Contrast = 0.1
grade.Saturation = 0.05
grade.TintColor = Color3.fromRGB(255, 240, 225)
```
