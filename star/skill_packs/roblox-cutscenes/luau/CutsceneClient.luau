--!strict
-- CutsceneClient (client ModuleScript): plays cutscenes the server asks for.
-- The server sends only ("play", name, origin CFrame, token). The client plays only timelines it registered itself
-- (shipped in the game, never sent over the network), checks every received value, and reports back
-- ("finished", token, state) so the server can give gameplay back. The client is trusted with nothing else.
-- VFX cues are played locally through the VFX composer (roblox-vfx-composer pack) when it is installed, scaled
-- for a shot: cue.scale multiplies the style's size, cue.screen (default 0.35) its screen effects (flash, tint,
-- bloom kick, shake), so a burst reads as an accent instead of filling the frame. CutsceneLook.ACCENTS adds small
-- abilities made for cutscene beats (accent_pulse, accent_hit).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Types = require(script.Parent:WaitForChild("CutsceneTypes"))
local CutscenePlayer = require(script.Parent:WaitForChild("CutscenePlayer"))
local CutsceneLook = require(script.Parent:WaitForChild("CutsceneLook"))

local CutsceneClient = {}
CutsceneClient.REMOTE_NAME = "StarCutsceneEvent"
CutsceneClient.ACTORS_FOLDER = "StarCutsceneActors"
CutsceneClient.SCREEN_DEFAULT = 0.35 -- share of a style's screen effects a cutscene VFX cue gets by default

local timelines: { [string]: Types.Timeline } = {}
local remote: RemoteEvent? = nil

CutsceneClient.speed = 1
CutsceneClient.options = {} :: { [string]: any } -- extra PlayOptions (onCue, onShot, onFrame, ...)
CutsceneClient.onPlay = nil :: ((name: string, handle: CutscenePlayer.Handle) -> ())?

function CutsceneClient.register(timeline: Types.Timeline): (boolean, string?)
	local ok, problem = Types.validate(timeline)
	if not ok then
		warn("[StarCutscene] timeline not registered: " .. tostring(problem))
		return false, problem
	end
	timelines[timeline.name] = timeline
	return true, nil
end

-- A style scaled for a shot: sizes times `scale`, screen effects times `screen` (no inverted frame below 0.5).
function CutsceneClient.scaledStyle(style: { [string]: any }, scale: number, screen: number): { [string]: any }
	local copy = table.clone(style)
	copy.sizeScale = (style.sizeScale or 1) * scale
	local fx = table.clone(style.screen or {})
	for _, key in { "flash", "tint", "bloom", "shake", "fovPunch" } do
		if type(fx[key]) == "number" then
			fx[key] *= screen
		end
	end
	fx.invert = fx.invert == true and screen >= 0.5
	copy.screen = fx
	return copy
end

-- A VFX hook backed by the VFX composer modules (ReplicatedStorage.<folder>: VfxComposer, VfxStyles), or nil.
function CutsceneClient.composerVfx(folderName: string?): ((cue: Types.Cue, at: CFrame, speed: number) -> ())?
	local folder = ReplicatedStorage:FindFirstChild(folderName or "StarVfx")
	local composerModule = folder and folder:FindFirstChild("VfxComposer")
	local stylesModule = folder and folder:FindFirstChild("VfxStyles")
	if not (composerModule and composerModule:IsA("ModuleScript") and stylesModule and stylesModule:IsA("ModuleScript")) then
		return nil
	end
	local Composer = require(composerModule) :: any
	local Styles = require(stylesModule) :: any
	return function(cue: Types.Cue, at: CFrame, speed: number)
		local ability = (CutsceneLook.ACCENTS :: any)[cue.ability] or Composer.ABILITIES[cue.ability]
		local style = Styles.get(cue.style :: string)
		if not ability or not style then
			error("unknown ability or style", 0)
		end
		local scaled = CutsceneClient.scaledStyle(style, cue.scale or 1, cue.screen or CutsceneClient.SCREEN_DEFAULT)
		if not Composer.play(ability, scaled, at, { speed = speed }) then
			error("the composer refused the effect", 0)
		end
	end
end

function CutsceneClient.play(name: string, origin: CFrame, token: string?): (CutscenePlayer.Handle?, string?)
	local timeline = timelines[name]
	if not timeline then
		return nil, "unknown cutscene " .. name
	end
	local options: CutscenePlayer.PlayOptions = {
		origin = origin,
		speed = CutsceneClient.speed,
		templates = ReplicatedStorage:FindFirstChild(CutsceneClient.ACTORS_FOLDER),
		vfx = CutsceneClient.options.vfx or CutsceneClient.composerVfx(),
		onCue = CutsceneClient.options.onCue,
		onShot = CutsceneClient.options.onShot,
		onFrame = CutsceneClient.options.onFrame,
		hideScreenGuis = CutsceneClient.options.hideScreenGuis,
		faceBackend = CutsceneClient.options.faceBackend,
	}
	local handle, problem = CutscenePlayer.play(timeline, options)
	if not handle then
		return nil, problem
	end
	handle.finished:Once(function(state: string)
		local r = remote
		if r and token then
			r:FireServer("finished", token, state)
		end
	end)
	local hook = CutsceneClient.onPlay
	if hook then
		hook(name, handle)
	end
	return handle, nil
end

local function onEvent(action: unknown, name: unknown, origin: unknown, token: unknown)
	if action ~= "play" or type(name) ~= "string" or #name > 40 or typeof(origin) ~= "CFrame" then
		return
	end
	if type(token) ~= "string" or #token > 32 then
		return
	end
	local _handle, problem = CutsceneClient.play(name :: string, origin :: CFrame, token :: string)
	if problem then
		warn("[StarCutscene] " .. problem)
	end
end

function CutsceneClient.start(): RemoteEvent
	local r = ReplicatedStorage:WaitForChild(CutsceneClient.REMOTE_NAME) :: RemoteEvent
	remote = r
	r.OnClientEvent:Connect(onEvent)
	return r
end

return CutsceneClient
