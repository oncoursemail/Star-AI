--!strict
-- CutscenePlayer (client ModuleScript): plays a validated Timeline (CutsceneTypes) on the local client.
--
-- Every frame (BindToRenderStep at Camera + 1, i.e. right after the default camera scripts, so the cutscene camera
-- wins; VFX camera shake bound at Camera + 2 then shakes the cutscene view without accumulating):
--   * advance the cutscene clock by dt * speed (speed < 1 = slow motion for review captures),
--   * fire cues whose time has come, in order (spawn, walk, anim, expression, blink, talk, caption, vfx, ...),
--   * move walking actors (trapezoid speed profile: short acceleration, constant cruise that matches the walk cycle,
--     short deceleration; the walk track's speed follows the actual speed, so feet do not slide),
--   * update facial expressions, then set the camera from the active shot's path (CameraType Scriptable, CFrame,
--     FieldOfView, Focus) and depth of field.
-- At the end, on skip, or on cancel: actors are put in their end state (skip), the camera goes back to Custom on
-- the player's Humanoid with the old FOV, controls and hidden UI come back, and everything made is destroyed.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local StarterGui = game:GetService("StarterGui")

local Types = require(script.Parent:WaitForChild("CutsceneTypes"))
local CameraPath = require(script.Parent:WaitForChild("CameraPath"))
local ExpressionPlayer = require(script.Parent:WaitForChild("ExpressionPlayer"))
local CutsceneUi = require(script.Parent:WaitForChild("CutsceneUi"))
local ActorMotion = require(script.Parent:WaitForChild("ActorMotion"))

export type PlayOptions = {
	origin: CFrame, -- where the timeline's local space sits in the world
	speed: number?, -- 1 = real time
	templates: Instance?, -- folder of actor template Models (looked up by cue.template)
	vfx: ((cue: Types.Cue, at: CFrame, speed: number) -> ())?, -- plays a VFX composer cue (see CutsceneClient)
	onCue: ((cue: Types.Cue, t: number, detail: string?) -> ())?,
	onShot: ((shot: Types.Shot, t: number) -> ())?,
	onFrame: ((t: number, shot: Types.Shot, camera: Camera) -> ())?,
	hideScreenGuis: boolean?, -- default true
	keepActors: boolean?, -- leave the actors in the world after the end (default false)
	faceBackend: string?, -- "auto" (default: FaceControls when the head has them), "facs" or "gui"
}

export type Handle = {
	length: number,
	actors: { [string]: ActorMotion.Actor },
	faces: { [string]: ExpressionPlayer.Player },
	skip: () -> (),
	cancel: () -> (),
	time: () -> number,
	state: () -> string, -- "playing" | "finished" | "skipped" | "cancelled"
	finished: RBXScriptSignal, -- fires (state)
}

type Walk = {
	actor: ActorMotion.Actor,
	from: Vector3,
	to: Vector3,
	start: number,
	duration: number,
	done: boolean,
}

local CutscenePlayer = {}
CutscenePlayer.RENDER_NAME = "StarCutsceneCamera"
CutscenePlayer.ACCEL = 0.15 -- fraction of a walk spent accelerating (and decelerating)
CutscenePlayer.WALK_SPEED = 8 -- studs/s when a walk cue gives no duration
CutscenePlayer.active = nil :: Handle?

-- Fraction of the distance covered at time fraction a, for a trapezoid speed profile; and the speed factor.
function CutscenePlayer.walkProfile(a: number, ramp: number): (number, number)
	local x = math.clamp(a, 0, 1)
	local r = math.clamp(ramp, 0.001, 0.5)
	local vmax = 1 / (1 - r)
	if x < r then
		return 0.5 * vmax * x * x / r, vmax * x / r
	elseif x <= 1 - r then
		return 0.5 * vmax * r + vmax * (x - r), vmax
	end
	local y = 1 - x
	return 1 - 0.5 * vmax * y * y / r, vmax * y / r
end

local function shotAt(shots: { Types.Shot }, t: number): number
	for i, shot in shots do
		if t < shot.start + shot.duration then
			return i
		end
	end
	return #shots
end

local function headPosition(actor: ActorMotion.Actor): Vector3
	local head = actor.model:FindFirstChild("Head")
	if head and head:IsA("BasePart") then
		return head.Position
	end
	return actor.root.Position + Vector3.new(0, 1.5, 0)
end

local GUI_TYPES = { Enum.CoreGuiType.PlayerList, Enum.CoreGuiType.Backpack, Enum.CoreGuiType.Health, Enum.CoreGuiType.EmotesMenu }

function CutscenePlayer.play(timeline: Types.Timeline, options: PlayOptions): (Handle?, string?)
	local valid, problem = Types.validate(timeline)
	if not valid then
		return nil, problem
	end
	local previous = CutscenePlayer.active
	if previous and previous.state() == "playing" then
		previous.cancel()
	end
	local player = Players.LocalPlayer
	local camera = workspace.CurrentCamera
	local speed = math.clamp(options.speed or 1, 0.05, 1)
	local origin = options.origin
	local done = Instance.new("BindableEvent")
	local folder = Instance.new("Folder")
	folder.Name = "StarCutsceneActors"
	folder.Parent = workspace

	-- remember what we change
	local saved = {
		cameraType = camera.CameraType,
		subject = camera.CameraSubject,
		fov = camera.FieldOfView,
		gui = {} :: { [Enum.CoreGuiType]: boolean },
		screens = {} :: { ScreenGui },
	}
	for _, kind in GUI_TYPES do
		local ok, enabled = pcall(function()
			return StarterGui:GetCoreGuiEnabled(kind)
		end)
		if ok then
			saved.gui[kind] = enabled
			pcall(function()
				StarterGui:SetCoreGuiEnabled(kind, false)
			end)
		end
	end
	local playerGui = player:FindFirstChildOfClass("PlayerGui")
	if options.hideScreenGuis ~= false and playerGui then
		for _, gui in playerGui:GetChildren() do
			if gui:IsA("ScreenGui") and gui.Enabled then
				gui.Enabled = false
				table.insert(saved.screens, gui)
			end
		end
	end
	local controls: any = nil
	pcall(function()
		local scripts = player:FindFirstChild("PlayerScripts")
		local module = scripts and scripts:FindFirstChild("PlayerModule")
		if module and module:IsA("ModuleScript") then
			controls = (require(module) :: any):GetControls()
			controls:Disable()
		end
	end)

	local ui = CutsceneUi.new({ barHeight = timeline.letterbox, skippable = timeline.skippable ~= false, speed = speed })
	local dof = Instance.new("DepthOfFieldEffect")
	dof.Enabled = false
	dof.Parent = camera

	local paths = {}
	for i, shot in timeline.shots do
		paths[i] = CameraPath.new(shot)
	end
	local actors: { [string]: ActorMotion.Actor } = {}
	local faces: { [string]: ExpressionPlayer.Player } = {}
	local walks: { Walk } = {}
	local t = 0
	local cueIndex = 1
	local shotIndex = 0
	local state = "playing"

	local function actorHead(name: string): Vector3?
		local actor = actors[name]
		return if actor then headPosition(actor) else nil
	end

	local function report(cue: Types.Cue, detail: string?)
		local hook = options.onCue
		if hook then
			hook(cue, t, detail)
		end
	end

	local function fire(cue: Types.Cue)
		local kind = cue.kind
		local actor = if cue.actor then actors[cue.actor] else nil
		if kind == "spawn" then
			local templates = options.templates
			local template = templates and templates:FindFirstChild(cue.template :: string)
			if not template or not template:IsA("Model") then
				report(cue, "missing template")
				return
			end
			local name = cue.actor or (cue.template :: string)
			local ground = origin * CFrame.new(cue.position :: Vector3) * CFrame.Angles(0, math.rad(cue.facing or 0), 0)
			local made = ActorMotion.spawn(name, template, ground, folder)
			if not made then
				report(cue, "template has no HumanoidRootPart")
				return
			end
			actors[name] = made
			local idle = ActorMotion.track(made, "idle", ActorMotion.DEFAULT_ANIMATIONS.idle, true, Enum.AnimationPriority.Idle)
			if idle then
				idle:Play(0)
				idle:AdjustSpeed(speed)
			end
			local face = ExpressionPlayer.new(made.model, { backend = options.faceBackend })
			faces[name] = face
			report(cue, "face backend " .. face.backend)
		elseif kind == "despawn" and actor then
			actor.model:Destroy()
			actors[actor.name] = nil
		elseif kind == "walk" and actor then
			local from = ActorMotion.groundOf(actor)
			local to = origin:PointToWorldSpace(cue.to :: Vector3)
			to = Vector3.new(to.X, from.Y, to.Z)
			local distance = (to - from).Magnitude
			local duration = cue.duration or math.max(0.5, distance / CutscenePlayer.WALK_SPEED)
			table.insert(walks, { actor = actor, from = from, to = to, start = cue.at, duration = duration, done = false })
			local walk = ActorMotion.track(actor, "walk", ActorMotion.DEFAULT_ANIMATIONS.walk, true, Enum.AnimationPriority.Movement)
			if walk then
				walk:Play(0.2)
			end
			report(cue, string.format("%.1f studs in %.2fs", distance, duration))
		elseif kind == "anim" and actor then
			local _track, source = ActorMotion.playGesture(actor, cue.name, cue.animation, speed)
			report(cue, source)
		elseif kind == "expression" and cue.actor then
			local face = faces[cue.actor]
			if face then
				face:set(cue.name :: string, cue.duration, cue.weight)
			end
		elseif kind == "blink" and cue.actor then
			local face = faces[cue.actor]
			if face then
				face:blink(cue.duration)
			end
		elseif kind == "talk" and cue.actor then
			local face = faces[cue.actor]
			if face then
				face:talk(cue.duration or 1)
			end
		elseif kind == "caption" then
			ui:caption(cue.text :: string, cue.speaker, cue.duration)
		elseif kind == "letterbox" then
			ui:letterbox(cue.show ~= false, cue.duration)
		elseif kind == "fade" then
			ui:fade(cue.alpha or 1, cue.duration)
		elseif kind == "vfx" then
			local at = origin * CFrame.new(cue.position or Vector3.zero)
			if cue.target and actors[cue.target] then
				at = CFrame.new(ActorMotion.groundOf(actors[cue.target]))
			end
			local hook = options.vfx
			if hook then
				local ok, why = pcall(hook, cue, at, speed)
				report(cue, if ok then "played" else ("failed: " .. tostring(why)))
			else
				report(cue, "no vfx player")
			end
			return
		end
		if kind ~= "spawn" and kind ~= "walk" and kind ~= "anim" then
			report(cue, nil)
		end
	end

	local function stepWalks()
		for _, w in walks do
			if not w.done then
				local a = (t - w.start) / w.duration
				local s, factor = CutscenePlayer.walkProfile(a, CutscenePlayer.ACCEL)
				local p = w.from:Lerp(w.to, s)
				local dir = w.to - w.from
				local facing = if dir.Magnitude > 1e-3 then CFrame.lookAt(p, p + Vector3.new(dir.X, 0, dir.Z)) else CFrame.new(p)
				ActorMotion.place(w.actor, facing)
				local walk = w.actor.tracks.walk
				if walk then
					local studsPerSecond = (w.to - w.from).Magnitude / w.duration * factor
					walk:AdjustSpeed(math.max(0.05, studsPerSecond / ActorMotion.WALK_ANIMATION_SPEED) * speed)
				end
				if a >= 1 then
					w.done = true
					if walk then
						walk:Stop(0.25)
					end
				end
			end
		end
	end

	local handle: Handle
	local function finish(final: string)
		if state ~= "playing" then
			return
		end
		state = final
		RunService:UnbindFromRenderStep(CutscenePlayer.RENDER_NAME)
		if final == "skipped" then
			-- end state: walkers at their destination; later spawns/despawns are not replayed
			for _, w in walks do
				if not w.done then
					local dir = w.to - w.from
					ActorMotion.place(w.actor, CFrame.lookAt(w.to, w.to + Vector3.new(dir.X, 0, dir.Z)))
					w.done = true
				end
			end
		end
		for _, face in faces do
			face:destroy()
		end
		if not options.keepActors then
			folder:Destroy()
		end
		dof:Destroy()
		ui:destroy()
		camera.CameraType = Enum.CameraType.Custom
		local character = player.Character
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		camera.CameraSubject = humanoid or saved.subject
		camera.FieldOfView = saved.fov
		for kind, enabled in saved.gui do
			pcall(function()
				StarterGui:SetCoreGuiEnabled(kind, enabled)
			end)
		end
		for _, gui in saved.screens do
			if gui.Parent then
				gui.Enabled = true
			end
		end
		if controls then
			pcall(function()
				controls:Enable()
			end)
		end
		if CutscenePlayer.active == handle then
			CutscenePlayer.active = nil
		end
		done:Fire(final)
	end

	local function step(dt: number)
		t = math.min(t + dt * speed, timeline.length)
		while cueIndex <= #timeline.cues and timeline.cues[cueIndex].at <= t do
			fire(timeline.cues[cueIndex])
			cueIndex += 1
		end
		stepWalks()
		for _, face in faces do
			face:update(dt * speed)
		end
		local index = shotAt(timeline.shots, t)
		local shot = timeline.shots[index]
		if index ~= shotIndex then
			shotIndex = index
			local d = shot.dof
			dof.Enabled = d ~= nil
			if d then
				dof.InFocusRadius = d.radius or 6
				dof.FarIntensity = d.far or 0.5
				dof.NearIntensity = d.near or 0.3
				dof.FocusDistance = d.distance or 20
			end
			local hook = options.onShot
			if hook then
				hook(shot, t)
			end
		end
		local cf, fov = paths[index]:sample(t, origin, actorHead)
		camera.CameraType = Enum.CameraType.Scriptable
		camera.CFrame = cf
		camera.FieldOfView = fov
		local focusActor = shot.dof and shot.dof.focusActor
		local focusPoint = if focusActor then actorHead(focusActor) else nil
		if focusPoint then
			dof.FocusDistance = (focusPoint - cf.Position).Magnitude
			camera.Focus = CFrame.new(focusPoint)
		else
			camera.Focus = cf * CFrame.new(0, 0, -20)
		end
		local hook = options.onFrame
		if hook then
			hook(t, shot, camera)
		end
		if t >= timeline.length then
			finish("finished")
		end
	end

	handle = {
		length = timeline.length,
		actors = actors,
		faces = faces,
		skip = function()
			finish("skipped")
		end,
		cancel = function()
			finish("cancelled")
		end,
		time = function()
			return t
		end,
		state = function()
			return state
		end,
		finished = done.Event,
	}
	ui:onSkip(function()
		finish("skipped")
	end)
	CutscenePlayer.active = handle
	RunService:BindToRenderStep(CutscenePlayer.RENDER_NAME, Enum.RenderPriority.Camera.Value + 1, step)
	return handle, nil
end

return CutscenePlayer
