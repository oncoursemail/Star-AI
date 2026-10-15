--!strict
-- ExpressionPlayer (client ModuleScript): facial expressions for cutscenes and NPCs.
--
-- Backend "facs": a Dynamic Head (a head MeshPart with a FaceControls child). Every expression is a set of FACS
-- values (0..1) on FaceControls properties; the player blends from the current pose to the target with an eased
-- curve, adds overlays (blink closes the eyes, talk moves the jaw in syllables) and writes the union of all
-- properties it uses every frame. FaceControls properties are NOT replicated, so this runs on the client (each
-- client animates the faces it sees; the server only says which expression to show).
-- Backend "gui": a head without FaceControls (classic head + face decal). The same FACS values drive a simple
-- SurfaceGui face (eyes, brows, mouth wings), so expressions still read in a shot. The decal is hidden while the
-- GUI face is on and restored by destroy().

local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

export type Pose = { [string]: number }
export type Player = {
	model: Model,
	backend: string, -- "facs" | "gui"
	current: string,
	set: (self: Player, name: string, duration: number?, weight: number?) -> boolean,
	blink: (self: Player, duration: number?) -> (),
	talk: (self: Player, duration: number, rate: number?) -> (),
	update: (self: Player, dt: number) -> (),
	snapshot: (self: Player) -> Pose,
	start: (self: Player, speed: number?) -> (),
	destroy: (self: Player) -> (),
}

local ExpressionPlayer = {}
ExpressionPlayer.__index = ExpressionPlayer

-- FACS presets. Pairs are symmetric on purpose; asymmetry (a smirk) is a custom pose.
ExpressionPlayer.PRESETS = {
	neutral = {},
	happy = {
		LeftLipCornerPuller = 0.85, RightLipCornerPuller = 0.85, LeftCheekRaiser = 0.6, RightCheekRaiser = 0.6,
		LeftEyeClosed = 0.2, RightEyeClosed = 0.2, LeftInnerBrowRaiser = 0.2, RightInnerBrowRaiser = 0.2,
		LeftDimpler = 0.3, RightDimpler = 0.3, JawDrop = 0.12,
	},
	angry = {
		LeftBrowLowerer = 0.9, RightBrowLowerer = 0.9, Corrugator = 0.7, LeftNoseWrinkler = 0.4,
		RightNoseWrinkler = 0.4, LipPresser = 0.6, LeftUpperLipRaiser = 0.25, RightUpperLipRaiser = 0.25,
		LeftEyeUpperLidRaiser = 0.3, RightEyeUpperLidRaiser = 0.3, ChinRaiser = 0.3,
	},
	surprised = {
		LeftInnerBrowRaiser = 0.9, RightInnerBrowRaiser = 0.9, LeftOuterBrowRaiser = 0.9, RightOuterBrowRaiser = 0.9,
		LeftEyeUpperLidRaiser = 0.85, RightEyeUpperLidRaiser = 0.85, JawDrop = 0.55, Funneler = 0.25,
	},
	sad = {
		LeftInnerBrowRaiser = 0.8, RightInnerBrowRaiser = 0.8, Corrugator = 0.35, LeftLipCornerDown = 0.75,
		RightLipCornerDown = 0.75, ChinRaiser = 0.4, LeftEyeClosed = 0.25, RightEyeClosed = 0.25,
		LeftLowerLipDepressor = 0.2, RightLowerLipDepressor = 0.2, EyesLookDown = 0.3,
	},
} :: { [string]: Pose }

-- Every property any preset or overlay writes (written every frame so nothing is left half-set).
local USED: { string } = { "LeftEyeClosed", "RightEyeClosed", "JawDrop", "Funneler", "Pucker" }
do
	local seen: { [string]: boolean } = {}
	for _, name in USED do
		seen[name] = true
	end
	for _, pose in ExpressionPlayer.PRESETS do
		for name in pose do
			if not seen[name] then
				seen[name] = true
				table.insert(USED, name)
			end
		end
	end
	table.sort(USED)
end
ExpressionPlayer.USED = USED

local function ease(a: number): number
	return TweenService:GetValue(math.clamp(a, 0, 1), Enum.EasingStyle.Cubic, Enum.EasingDirection.Out)
end

local function findFaceControls(model: Model): FaceControls?
	local head = model:FindFirstChild("Head")
	if head then
		local direct = head:FindFirstChildOfClass("FaceControls")
		if direct then
			return direct
		end
	end
	return model:FindFirstChildWhichIsA("FaceControls", true)
end

-- ---------------------------------------------------------------- GUI fallback face

type GuiFace = {
	gui: SurfaceGui,
	eyes: { Frame },
	brows: { Frame },
	mouth: Frame,
	wings: { Frame },
	decal: Decal?,
	decalTransparency: number,
}

local function frame(parent: Instance, size: UDim2, position: UDim2, round: boolean): Frame
	local f = Instance.new("Frame")
	f.AnchorPoint = Vector2.new(0.5, 0.5)
	f.BackgroundColor3 = Color3.fromRGB(25, 20, 20)
	f.BorderSizePixel = 0
	f.Size = size
	f.Position = position
	if round then
		local corner = Instance.new("UICorner")
		corner.CornerRadius = UDim.new(0.5, 0)
		corner.Parent = f
	end
	f.Parent = parent
	return f
end

local function makeGuiFace(head: BasePart): GuiFace
	local gui = Instance.new("SurfaceGui")
	gui.Name = "StarExpressionFace"
	gui.Face = Enum.NormalId.Front
	gui.CanvasSize = Vector2.new(200, 200)
	gui.LightInfluence = 0.6
	gui.Adornee = head
	local decal = head:FindFirstChildOfClass("Decal")
	local face: GuiFace = {
		gui = gui,
		eyes = {
			frame(gui, UDim2.fromScale(0.11, 0.15), UDim2.fromScale(0.36, 0.42), true),
			frame(gui, UDim2.fromScale(0.11, 0.15), UDim2.fromScale(0.64, 0.42), true),
		},
		brows = {
			frame(gui, UDim2.fromScale(0.2, 0.045), UDim2.fromScale(0.35, 0.27), false),
			frame(gui, UDim2.fromScale(0.2, 0.045), UDim2.fromScale(0.65, 0.27), false),
		},
		mouth = frame(gui, UDim2.fromScale(0.2, 0.05), UDim2.fromScale(0.5, 0.7), true),
		wings = {
			frame(gui, UDim2.fromScale(0.1, 0.045), UDim2.fromScale(0.37, 0.7), true),
			frame(gui, UDim2.fromScale(0.1, 0.045), UDim2.fromScale(0.63, 0.7), true),
		},
		decal = decal,
		decalTransparency = if decal then decal.Transparency else 0,
	}
	if decal then
		decal.Transparency = 1
	end
	gui.Parent = head
	return face
end

local function drawGuiFace(face: GuiFace, v: Pose)
	local function g(name: string): number
		return v[name] or 0
	end
	for side, prefix in { "Left", "Right" } do
		local closed = g(prefix .. "EyeClosed")
		local wide = g(prefix .. "EyeUpperLidRaiser")
		local eye = face.eyes[side]
		eye.Size = UDim2.fromScale(0.11, math.max(0.012, 0.15 * (1 - closed) * (1 + 0.45 * wide)))
		local inner = g(prefix .. "InnerBrowRaiser")
		local outer = g(prefix .. "OuterBrowRaiser")
		local lower = math.max(g(prefix .. "BrowLowerer"), g("Corrugator") * 0.6)
		local brow = face.brows[side]
		local lift = 0.09 * math.max(inner, outer) - 0.05 * lower
		brow.Position = UDim2.fromScale(if side == 1 then 0.35 else 0.65, 0.27 - lift)
		-- inner end down for anger, up for worry/sadness (left brow's inner end is its right end)
		local tilt = 24 * lower - 20 * inner + 8 * outer
		brow.Rotation = if side == 1 then tilt else -tilt
	end
	local smile = (g("LeftLipCornerPuller") + g("RightLipCornerPuller")) / 2
	local frown = (g("LeftLipCornerDown") + g("RightLipCornerDown")) / 2
	local curve = smile - frown
	local jaw = g("JawDrop")
	local funnel = math.max(g("Funneler"), g("Pucker"))
	local press = g("LipPresser")
	local width = 0.2 * (1 - 0.45 * funnel) * (1 - 0.25 * press)
	face.mouth.Size = UDim2.fromScale(width, 0.035 + 0.22 * jaw + 0.04 * funnel)
	for side, wing in face.wings do
		local x = 0.5 + (if side == 1 then -1 else 1) * (width / 2 + 0.035)
		wing.Position = UDim2.fromScale(x, 0.7 - 0.035 * curve)
		wing.Rotation = (if side == 1 then 1 else -1) * 32 * curve
		wing.Visible = math.abs(curve) > 0.05 or jaw < 0.2
	end
end

-- ---------------------------------------------------------------- player

function ExpressionPlayer.new(model: Model, options: { backend: string? }?): Player
	local self = setmetatable({}, ExpressionPlayer) :: any
	self.model = model
	self.current = "neutral"
	self._from = {} :: Pose
	self._to = {} :: Pose
	self._values = {} :: Pose
	self._alpha = 1
	self._blend = 0.25
	self._blinkT = -1
	self._blinkLen = 0.22
	self._talkLeft = 0
	self._talkT = 0
	self._rate = 9
	local wanted = options and options.backend or "auto"
	local controls = findFaceControls(model)
	if controls and wanted ~= "gui" then
		self.backend = "facs"
		self._controls = controls
	else
		self.backend = "gui"
		local head = model:FindFirstChild("Head")
		if head and head:IsA("BasePart") then
			self._face = makeGuiFace(head)
		end
	end
	return self :: Player
end

function ExpressionPlayer.set(self: any, name: string, duration: number?, weight: number?): boolean
	local preset = ExpressionPlayer.PRESETS[name]
	if not preset then
		return false
	end
	local w = math.clamp(weight or 1, 0, 1)
	local target: Pose = {}
	for key, value in preset do
		target[key] = value * w
	end
	self._from = table.clone(self._values)
	self._to = target
	self._alpha = 0
	self._blend = math.max(duration or 0.25, 0.01)
	self.current = name
	return true
end

function ExpressionPlayer.blink(self: any, duration: number?)
	self._blinkLen = math.clamp(duration or 0.22, 0.08, 1)
	self._blinkT = 0
end

function ExpressionPlayer.talk(self: any, duration: number, rate: number?)
	self._talkLeft = math.max(duration, 0)
	self._talkT = 0
	self._rate = math.clamp(rate or 9, 2, 16)
end

-- Advance by dt seconds (already scaled for slow motion by the caller) and write the face.
function ExpressionPlayer.update(self: any, dt: number)
	self._alpha = math.min(1, self._alpha + dt / self._blend)
	local a = ease(self._alpha)
	local values: Pose = {}
	for _, name in USED do
		local from = self._from[name] or 0
		local to = self._to[name] or 0
		values[name] = from + (to - from) * a
	end
	if self._talkLeft > 0 then
		self._talkLeft -= dt
		self._talkT += dt
		-- syllables: an open-close cycle per syllable with a varying peak, rounder lips on some syllables
		local phase = self._talkT * self._rate
		local syllable = math.floor(phase)
		local peak = 0.25 + 0.35 * math.abs(math.noise(syllable * 0.37, 1.7))
		local open = peak * math.sin((phase - syllable) * math.pi)
		values.JawDrop = math.clamp(values.JawDrop + open, 0, 1)
		if syllable % 3 == 1 then
			values.Funneler = math.clamp(values.Funneler + open * 0.6, 0, 1)
		end
	end
	if self._blinkT >= 0 then
		self._blinkT += dt
		local x = self._blinkT / self._blinkLen
		local closed = if x < 0.35 then x / 0.35 elseif x < 0.5 then 1 else math.max(0, 1 - (x - 0.5) / 0.5)
		values.LeftEyeClosed = math.max(values.LeftEyeClosed, closed)
		values.RightEyeClosed = math.max(values.RightEyeClosed, closed)
		if x >= 1 then
			self._blinkT = -1
		end
	end
	self._values = values
	local controls = self._controls
	if controls then
		for name, value in values do
			(controls :: any)[name] = math.clamp(value, 0, 1)
		end
	elseif self._face then
		drawGuiFace(self._face, values)
	end
end

function ExpressionPlayer.snapshot(self: any): Pose
	local out: Pose = {}
	local controls = self._controls
	for _, name in USED do
		out[name] = if controls then (controls :: any)[name] else (self._values[name] or 0)
	end
	return out
end

-- Drive the face from RunService on its own (NPCs outside a cutscene). speed scales time (slow motion).
function ExpressionPlayer.start(self: any, speed: number?)
	if self._conn then
		return
	end
	local s = speed or 1
	self._conn = RunService.Heartbeat:Connect(function(dt: number)
		self:update(dt * s)
	end)
end

function ExpressionPlayer.destroy(self: any)
	if self._conn then
		self._conn:Disconnect()
		self._conn = nil
	end
	local face: GuiFace? = self._face
	if face then
		if face.decal then
			face.decal.Transparency = face.decalTransparency
		end
		face.gui:Destroy()
		self._face = nil
	end
	local controls = self._controls
	if controls then
		for _, name in USED do
			(controls :: any)[name] = 0
		end
	end
end

return ExpressionPlayer
