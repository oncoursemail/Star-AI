--!strict
-- CutsceneLook (client ModuleScript): the cinematic "look" of a cutscene, applied locally for its length and
-- restored afterwards.
--   * mood presets (golden_hour, dusk, battle, neutral): time of day, ambient colours, exposure, Atmosphere (haze
--     and glare give depth and a sky glow), a ColorCorrection grade, Bloom tuned so only emissive things glow
--     (threshold above 1, so the sky and lit walls do not white out), a touch of SunRays;
--   * a rim light for close-ups: a warm SpotLight kept behind the subject's head, opposite the camera, so the
--     silhouette separates from the background;
--   * accent abilities for the VFX composer: small, short effects that read as an accent in a shot instead of
--     filling the frame (see CutsceneClient.composerVfx: scale and screen multipliers).
-- Lighting changes made by a LocalScript stay on this client. Existing post effects of the same kinds are disabled
-- while the look is on (two Bloom effects add up) and switched back on by restore().

local Lighting = game:GetService("Lighting")

export type Grade = { brightness: number, contrast: number, saturation: number, tint: Color3 }
export type Haze = { density: number, offset: number, color: Color3, decay: Color3, glare: number, haze: number }
export type Look = {
	clock: number?,
	brightness: number,
	exposure: number,
	ambient: Color3,
	outdoorAmbient: Color3,
	colorShiftTop: Color3,
	colorShiftBottom: Color3,
	diffuse: number, -- EnvironmentDiffuseScale
	specular: number, -- EnvironmentSpecularScale
	atmosphere: Haze?,
	grade: Grade?,
	bloom: { intensity: number, size: number, threshold: number }?,
	sunRays: { intensity: number, spread: number }?,
	rim: { color: Color3, brightness: number, range: number, angle: number },
}

local CutsceneLook = {}
CutsceneLook.TAG = "StarCutsceneLook"

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

CutsceneLook.PRESETS = {
	-- Low warm sun, long shadows, golden haze; warm rim, slightly lifted saturation. Teal/green emissives pop
	-- against it (complementary).
	golden_hour = {
		clock = 17.4,
		brightness = 2.2,
		exposure = 0.05,
		ambient = rgb(84, 74, 76),
		outdoorAmbient = rgb(126, 110, 104),
		colorShiftTop = rgb(255, 212, 170),
		colorShiftBottom = rgb(60, 44, 64),
		diffuse = 0.5,
		specular = 0.6,
		atmosphere = { density = 0.3, offset = 0.22, color = rgb(255, 212, 178), decay = rgb(140, 100, 104), glare = 0.55, haze = 1.6 },
		grade = { brightness = 0.01, contrast = 0.12, saturation = 0.04, tint = rgb(255, 243, 232) },
		bloom = { intensity = 0.5, size = 28, threshold = 1.3 },
		sunRays = { intensity = 0.06, spread = 0.55 },
		rim = { color = rgb(255, 196, 140), brightness = 2.5, range = 8, angle = 60 },
	} :: Look,
	-- Sun just under the horizon: cool blue-violet ambient, pink-orange sky glow, deeper contrast, stronger bloom
	-- so practical lights and magic carry the frame.
	dusk = {
		clock = 18.25,
		brightness = 1.3,
		exposure = 0.25,
		ambient = rgb(70, 64, 96),
		outdoorAmbient = rgb(96, 86, 128),
		colorShiftTop = rgb(255, 140, 110),
		colorShiftBottom = rgb(40, 36, 80),
		diffuse = 0.45,
		specular = 0.5,
		atmosphere = { density = 0.4, offset = 0.12, color = rgb(196, 150, 200), decay = rgb(92, 70, 124), glare = 0.35, haze = 2.2 },
		grade = { brightness = 0, contrast = 0.18, saturation = -0.04, tint = rgb(228, 222, 255) },
		bloom = { intensity = 0.8, size = 32, threshold = 1.1 },
		sunRays = { intensity = 0.1, spread = 0.4 },
		rim = { color = rgb(255, 160, 200), brightness = 3, range = 8, angle = 60 },
	} :: Look,
	-- Overcast afternoon through smoke: grey-orange haze, desaturated, hard contrast, little bloom.
	battle = {
		clock = 15.2,
		brightness = 1.8,
		exposure = -0.1,
		ambient = rgb(80, 74, 70),
		outdoorAmbient = rgb(112, 102, 96),
		colorShiftTop = rgb(255, 222, 190),
		colorShiftBottom = rgb(50, 44, 40),
		diffuse = 0.5,
		specular = 0.4,
		atmosphere = { density = 0.5, offset = 0.05, color = rgb(172, 150, 134), decay = rgb(96, 86, 80), glare = 0, haze = 3 },
		grade = { brightness = -0.02, contrast = 0.28, saturation = -0.3, tint = rgb(255, 232, 210) },
		bloom = { intensity = 0.45, size = 24, threshold = 1.35 },
		sunRays = { intensity = 0.03, spread = 0.2 },
		rim = { color = rgb(255, 214, 180), brightness = 2, range = 8, angle = 60 },
	} :: Look,
	-- Leave the game's lighting alone (still gives close-ups a soft neutral rim).
	neutral = {
		brightness = -1, -- -1 = keep
		exposure = 0,
		ambient = rgb(0, 0, 0),
		outdoorAmbient = rgb(0, 0, 0),
		colorShiftTop = rgb(0, 0, 0),
		colorShiftBottom = rgb(0, 0, 0),
		diffuse = -1,
		specular = -1,
		rim = { color = rgb(255, 244, 228), brightness = 1.8, range = 8, angle = 60 },
	} :: Look,
}
CutsceneLook.ORDER = { "golden_hour", "dusk", "battle", "neutral" }

-- Small, short abilities for cutscene beats (VFX composer format; the style still decides colours/textures).
-- Sizes are before the cue's scale. No tint, no sky pillar, a flash of a tenth of a second.
CutsceneLook.ACCENTS = {
	accent_pulse = {
		name = "accent_pulse",
		cues = {
			{ stage = "charge", at = 0, fx = "light", params = { dur = 1.2, range = 16, brightness = 2 } },
			{ stage = "charge", at = 0.15, fx = "burst", params = { count = 24, speed = 5, life = 1, size = 0.35,
				texture = "spark", color = "accent", gravity = -8, y = 2.5, spread = 60, drag = 1 } },
			{ stage = "impact", at = 0, fx = "flash", params = { strength = 0.2, dur = 0.1, invert = false } },
			{ stage = "impact", at = 0, fx = "ring", params = { radius = 6, dur = 0.5, y = 0.2 } },
			{ stage = "impact", at = 0, fx = "sparks", params = { count = 28, speed = 26, life = 0.4, size = 0.35, y = 4 } },
			{ stage = "impact", at = 0, fx = "dome", params = { radius = 3, dur = 0.35, y = 4 } },
			{ stage = "impact", at = 0.1, fx = "shake", params = { amplitude = 0.12, dur = 0.25 } },
			{ stage = "shockwave", at = 0, fx = "ring", params = { radius = 9, dur = 0.6, color = "accent" } },
			{ stage = "linger", at = 0, fx = "burst", params = { count = 22, speed = 3, life = 1.6, size = 0.3,
				texture = "spark", color = "accent", gravity = -4, y = 3, spread = 180, drag = 1 } },
			{ stage = "dissipate", at = 0.1, fx = "smoke", params = { count = 4, size = 2, life = 1 } },
		},
	},
	accent_hit = {
		name = "accent_hit",
		cues = {
			{ stage = "impact", at = 0, fx = "flash", params = { strength = 0.15, dur = 0.08, invert = false } },
			{ stage = "impact", at = 0, fx = "sparks", params = { count = 18, speed = 30, life = 0.3, size = 0.3 } },
			{ stage = "impact", at = 0, fx = "light", params = { dur = 0.25, range = 12 } },
			{ stage = "shockwave", at = 0, fx = "ring", params = { radius = 4, dur = 0.4, y = 1 } },
			{ stage = "shockwave", at = 0.2, fx = "smoke", params = { count = 3, size = 1.5, life = 0.7 } },
		},
	},
}

local LIGHTING_PROPS = { "ClockTime", "Brightness", "ExposureCompensation", "Ambient", "OutdoorAmbient", "ColorShift_Top",
	"ColorShift_Bottom", "EnvironmentDiffuseScale", "EnvironmentSpecularScale" }
local ATMOSPHERE_PROPS = { "Density", "Offset", "Color", "Decay", "Glare", "Haze" }
local EFFECT_CLASSES = { "BloomEffect", "ColorCorrectionEffect", "SunRaysEffect", "DepthOfFieldEffect" }

function CutsceneLook.get(name: string?): Look?
	if name == nil then
		return nil
	end
	return (CutsceneLook.PRESETS :: any)[name :: string]
end

-- Applies a preset and returns restore(), which puts every changed property back and removes what was made.
function CutsceneLook.apply(name: string?): () -> ()
	local look = CutsceneLook.get(name)
	if not look or name == "neutral" then
		return function() end
	end
	local saved: { [string]: any } = {}
	for _, prop in LIGHTING_PROPS do
		saved[prop] = (Lighting :: any)[prop]
	end
	local made: { Instance } = {}
	local disabled: { PostEffect } = {}
	for _, child in Lighting:GetChildren() do
		if child:IsA("PostEffect") and child.Enabled and table.find(EFFECT_CLASSES, child.ClassName) then
			child.Enabled = false
			table.insert(disabled, child)
		end
	end
	local L = Lighting :: any
	if look.clock then
		L.ClockTime = look.clock
	end
	L.Brightness = look.brightness
	L.ExposureCompensation = look.exposure
	L.Ambient = look.ambient
	L.OutdoorAmbient = look.outdoorAmbient
	L.ColorShift_Top = look.colorShiftTop
	L.ColorShift_Bottom = look.colorShiftBottom
	L.EnvironmentDiffuseScale = look.diffuse
	L.EnvironmentSpecularScale = look.specular

	local atmosphere = Lighting:FindFirstChildOfClass("Atmosphere")
	local savedAtmosphere: { [string]: any }? = nil
	local haze = look.atmosphere
	if haze then
		if atmosphere then
			local keep: { [string]: any } = {}
			for _, prop in ATMOSPHERE_PROPS do
				keep[prop] = (atmosphere :: any)[prop]
			end
			savedAtmosphere = keep
		else
			local a = Instance.new("Atmosphere")
			a.Name = CutsceneLook.TAG
			a.Parent = Lighting
			atmosphere = a
			table.insert(made, a)
		end
		local a = atmosphere :: Atmosphere
		a.Density = haze.density
		a.Offset = haze.offset
		a.Color = haze.color
		a.Decay = haze.decay
		a.Glare = haze.glare
		a.Haze = haze.haze
	end
	local grade = look.grade
	if grade then
		local cc = Instance.new("ColorCorrectionEffect")
		cc.Name = CutsceneLook.TAG
		cc.Brightness = grade.brightness
		cc.Contrast = grade.contrast
		cc.Saturation = grade.saturation
		cc.TintColor = grade.tint
		cc.Parent = Lighting
		table.insert(made, cc)
	end
	local bloom = look.bloom
	if bloom then
		local b = Instance.new("BloomEffect")
		b.Name = CutsceneLook.TAG
		b.Intensity = bloom.intensity
		b.Size = bloom.size
		b.Threshold = bloom.threshold
		b.Parent = Lighting
		table.insert(made, b)
	end
	local rays = look.sunRays
	if rays then
		local s = Instance.new("SunRaysEffect")
		s.Name = CutsceneLook.TAG
		s.Intensity = rays.intensity
		s.Spread = rays.spread
		s.Parent = Lighting
		table.insert(made, s)
	end

	local restored = false
	return function()
		if restored then
			return
		end
		restored = true
		for prop, value in saved do
			pcall(function()
				(Lighting :: any)[prop] = value
			end)
		end
		local keep = savedAtmosphere
		if keep and atmosphere and atmosphere.Parent then
			for prop, value in keep do
				(atmosphere :: any)[prop] = value
			end
		end
		for _, instance in made do
			instance:Destroy()
		end
		for _, effect in disabled do
			if effect.Parent then
				effect.Enabled = true
			end
		end
	end
end

-- A rim light rig: call place(head, cameraPosition) every frame while a close-up uses it; destroy() at the end.
export type Rim = {
	part: BasePart,
	light: SpotLight,
	place: (self: Rim, head: Vector3, eye: Vector3) -> (),
	enable: (self: Rim, on: boolean) -> (),
	destroy: (self: Rim) -> (),
}

function CutsceneLook.rim(lookName: string?, parent: Instance): Rim
	local look = CutsceneLook.get(lookName) or CutsceneLook.PRESETS.neutral
	local p = Instance.new("Part")
	p.Name = "StarCutsceneRim"
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Transparency = 1
	p.Size = Vector3.one * 0.2
	p.Parent = parent
	local light = Instance.new("SpotLight")
	light.Color = look.rim.color
	light.Brightness = look.rim.brightness
	light.Range = look.rim.range
	light.Angle = look.rim.angle
	light.Face = Enum.NormalId.Front
	light.Shadows = false
	light.Enabled = false
	light.Parent = p
	local rim = { part = p, light = light } :: any
	function rim.place(self: Rim, head: Vector3, eye: Vector3)
		local away = head - eye
		away = Vector3.new(away.X, 0, away.Z)
		if away.Magnitude < 1e-3 then
			return
		end
		-- behind the head (from the camera's point of view), a little above and to one side
		local side = away.Unit:Cross(Vector3.yAxis)
		-- a kicker: behind and well to one side, so the lit edge of the cheek and shoulder faces the camera
		local at = head + away.Unit * 1.8 + side * 1.7 + Vector3.new(0, 0.9, 0)
		self.part.CFrame = CFrame.lookAt(at, head)
	end
	function rim.enable(self: Rim, on: boolean)
		self.light.Enabled = on
	end
	function rim.destroy(self: Rim)
		self.part:Destroy()
	end
	return rim :: Rim
end

return CutsceneLook
