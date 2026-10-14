--!strict
-- CutsceneUi (client ModuleScript): the screen layer of a cutscene.
--   * letterbox bars (two black frames that slide in/out; IgnoreGuiInset so they cover the top bar area too),
--   * dialogue captions (speaker + text, typed on at a readable pace, kept on screen long enough to read),
--   * a skip button (bottom-right, large touch target, also bound to keyboard/gamepad through ContextActionService),
--   * a fade frame for cuts to/from black.
-- Everything lives under one ScreenGui that destroy() removes.

local ContextActionService = game:GetService("ContextActionService")
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")

export type Ui = {
	gui: ScreenGui,
	letterbox: (self: Ui, show: boolean, duration: number?) -> (),
	caption: (self: Ui, text: string, speaker: string?, duration: number?, speed: number?) -> (),
	clearCaption: (self: Ui) -> (),
	fade: (self: Ui, alpha: number, duration: number?) -> (),
	onSkip: (self: Ui, callback: () -> ()) -> (),
	destroy: (self: Ui) -> (),
}

local CutsceneUi = {}
CutsceneUi.__index = CutsceneUi
CutsceneUi.ACTION = "StarCutsceneSkip"
CutsceneUi.CHARS_PER_SECOND = 40

local function bar(parent: Instance, top: boolean): Frame
	local f = Instance.new("Frame")
	f.Name = if top then "BarTop" else "BarBottom"
	f.BackgroundColor3 = Color3.new(0, 0, 0)
	f.BorderSizePixel = 0
	f.AnchorPoint = Vector2.new(0, if top then 0 else 1)
	f.Position = UDim2.fromScale(0, if top then 0 else 1)
	f.Size = UDim2.fromScale(1, 0)
	f.ZIndex = 5
	f.Parent = parent
	return f
end

export type UiOptions = { barHeight: number?, skippable: boolean?, speed: number? }

function CutsceneUi.new(options: UiOptions?): Ui
	local o: UiOptions = options or { barHeight = nil, skippable = nil, speed = nil }
	local player = Players.LocalPlayer
	local gui = Instance.new("ScreenGui")
	gui.Name = "StarCutsceneUi"
	gui.IgnoreGuiInset = true
	gui.ResetOnSpawn = false
	gui.DisplayOrder = 50
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	local fade = Instance.new("Frame")
	fade.Name = "Fade"
	fade.BackgroundColor3 = Color3.new(0, 0, 0)
	fade.BackgroundTransparency = 1
	fade.BorderSizePixel = 0
	fade.Size = UDim2.fromScale(1, 1)
	fade.ZIndex = 4
	fade.Parent = gui

	local captionFrame = Instance.new("Frame")
	captionFrame.Name = "Caption"
	captionFrame.AnchorPoint = Vector2.new(0.5, 1)
	captionFrame.Position = UDim2.new(0.5, 0, 1, -12)
	captionFrame.Size = UDim2.new(0.7, 0, 0, 64)
	captionFrame.BackgroundTransparency = 1
	captionFrame.Visible = false
	captionFrame.ZIndex = 6
	captionFrame.Parent = gui
	local size = Instance.new("UISizeConstraint")
	size.MaxSize = Vector2.new(820, 120)
	size.Parent = captionFrame

	local speaker = Instance.new("TextLabel")
	speaker.Name = "Speaker"
	speaker.BackgroundTransparency = 1
	speaker.Size = UDim2.new(1, 0, 0, 22)
	speaker.Font = Enum.Font.GothamBold
	speaker.TextSize = 18
	speaker.TextColor3 = Color3.fromRGB(255, 214, 120)
	speaker.TextXAlignment = Enum.TextXAlignment.Center
	speaker.ZIndex = 6
	speaker.Parent = captionFrame

	local line = Instance.new("TextLabel")
	line.Name = "Line"
	line.BackgroundTransparency = 1
	line.Position = UDim2.fromOffset(0, 22)
	line.Size = UDim2.new(1, 0, 1, -22)
	line.Font = Enum.Font.Gotham
	line.TextSize = 20
	line.TextWrapped = true
	line.TextColor3 = Color3.new(1, 1, 1)
	line.TextStrokeTransparency = 0.4
	line.TextXAlignment = Enum.TextXAlignment.Center
	line.TextYAlignment = Enum.TextYAlignment.Top
	line.MaxVisibleGraphemes = 0
	line.ZIndex = 6
	line.Parent = captionFrame

	local self = setmetatable({}, CutsceneUi) :: any
	self.gui = gui
	self._bars = { bar(gui, true), bar(gui, false) }
	self._height = math.clamp(o.barHeight or 0.11, 0, 0.2)
	self._fade = fade
	self._captionFrame = captionFrame
	self._speaker = speaker
	self._line = line
	self._speed = math.clamp(o.speed or 1, 0.05, 1)
	self._captionToken = 0
	self._skipCallbacks = {} :: { () -> () }

	if o.skippable ~= false then
		local skip = Instance.new("TextButton")
		skip.Name = "Skip"
		skip.AnchorPoint = Vector2.new(1, 0)
		skip.Position = UDim2.new(1, -16, 0, 16)
		skip.Size = UDim2.fromOffset(112, 44) -- at least 44 px tall for touch
		skip.BackgroundColor3 = Color3.fromRGB(20, 20, 24)
		skip.BackgroundTransparency = 0.35
		skip.TextColor3 = Color3.new(1, 1, 1)
		skip.Font = Enum.Font.GothamMedium
		skip.TextSize = 16
		skip.Text = "Skip  >>"
		skip.ZIndex = 7
		skip.AutoButtonColor = true
		local corner = Instance.new("UICorner")
		corner.CornerRadius = UDim.new(0, 8)
		corner.Parent = skip
		skip.Parent = gui
		self._skip = skip
		skip.Activated:Connect(function()
			self:_fireSkip()
		end)
		ContextActionService:BindAction(CutsceneUi.ACTION, function(_name, state, _input)
			if state == Enum.UserInputState.Begin then
				self:_fireSkip()
			end
			return Enum.ContextActionResult.Sink
		end, false, Enum.KeyCode.Return, Enum.KeyCode.ButtonB)
	end
	gui.Parent = player:WaitForChild("PlayerGui")
	return self :: Ui
end

function CutsceneUi._fireSkip(self: any)
	for _, callback in self._skipCallbacks do
		task.spawn(callback)
	end
end

function CutsceneUi.onSkip(self: any, callback: () -> ())
	table.insert(self._skipCallbacks, callback)
end

local function tween(instance: Instance, seconds: number, goal: { [string]: any })
	TweenService:Create(instance, TweenInfo.new(seconds, Enum.EasingStyle.Quad, Enum.EasingDirection.InOut), goal):Play()
end

function CutsceneUi.letterbox(self: any, show: boolean, duration: number?)
	local seconds = (duration or 0.6) / self._speed
	for _, f in self._bars do
		tween(f, seconds, { Size = UDim2.fromScale(1, if show then self._height else 0) })
	end
end

function CutsceneUi.fade(self: any, alpha: number, duration: number?)
	tween(self._fade, (duration or 0.4) / self._speed, { BackgroundTransparency = 1 - math.clamp(alpha, 0, 1) })
end

-- Types the line on (CHARS_PER_SECOND), then holds it; `duration` is the whole time on screen (cutscene seconds).
function CutsceneUi.caption(self: any, text: string, speaker: string?, duration: number?, _speed: number?)
	self._captionToken += 1
	local token = self._captionToken
	local line: TextLabel = self._line
	self._speaker.Text = speaker or ""
	self._speaker.Visible = speaker ~= nil and speaker ~= ""
	line.Text = text
	line.MaxVisibleGraphemes = 0
	self._captionFrame.Visible = true
	local total = utf8.len(text) or #text
	local hold = duration or math.max(2, total / 15 + 1)
	task.spawn(function()
		local shown = 0
		while shown < total and token == self._captionToken do
			shown = math.min(total, shown + 1)
			line.MaxVisibleGraphemes = shown
			task.wait(1 / (CutsceneUi.CHARS_PER_SECOND * self._speed))
		end
		line.MaxVisibleGraphemes = -1
	end)
	task.delay(hold / self._speed, function()
		if token == self._captionToken then
			self:clearCaption()
		end
	end)
end

function CutsceneUi.clearCaption(self: any)
	self._captionToken += 1
	self._captionFrame.Visible = false
end

function CutsceneUi.destroy(self: any)
	self._captionToken += 1
	if self._skip then
		ContextActionService:UnbindAction(CutsceneUi.ACTION)
	end
	self.gui:Destroy()
end

return CutsceneUi
