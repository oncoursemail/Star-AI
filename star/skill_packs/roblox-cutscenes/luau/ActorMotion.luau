--!strict
-- ActorMotion (client ModuleScript): cutscene actors.
-- A cutscene actor is a CLIENT-LOCAL clone of a rig template (the server builds the template once, e.g. with
-- Players:CreateHumanoidModelFromDescriptionAsync, and parents it to ReplicatedStorage). Local clones need no network
-- ownership, never fight physics and are identical on every client. The root is anchored and moved by CFrame;
-- the Animator plays walk/idle/gesture tracks locally.
--
-- Gestures in code: `gestureSequence` builds a KeyframeSequence (Keyframe -> nested Pose per R15 joint) and
-- `playGesture` registers it with KeyframeSequenceProvider:RegisterKeyframeSequence. That temporary id works ONLY
-- in Studio (playtests, previews); a live game must play an uploaded animation id instead (cue.animation), so
-- `playGesture` falls back to the built-in emote ids when registration fails.

local KeyframeSequenceProvider = game:GetService("KeyframeSequenceProvider")

export type Actor = {
	name: string,
	model: Model,
	root: BasePart,
	humanoid: Humanoid?,
	animator: Animator?,
	tracks: { [string]: AnimationTrack },
	ground: number, -- root height above the ground point
}

local ActorMotion = {}

-- Animation ids from Roblox's default R15 Animate script (owned by Roblox, load in any experience).
ActorMotion.DEFAULT_ANIMATIONS = {
	-- 507766388 is the default Animate script's main idle (weight 9); 507766666 is its rare look-around variant
	-- (weight 1), which turned the actor's head away from the camera in every close-up up to v4c.
	idle = "rbxassetid://507766388",
	walk = "rbxassetid://913402848", -- the walk the current default Animate script plays (Players:CreateHumanoidModelFromDescriptionAsync rigs)
	run = "rbxassetid://507767714",
	wave = "rbxassetid://507770239",
	point = "rbxassetid://507770453",
	cheer = "rbxassetid://507770677",
}
ActorMotion.WALK_ANIMATION_SPEED = 16 -- studs/s the default walk cycle is authored for (Animate script scale)

-- R15 joint chain: pose name -> parent pose name (KeyframeSequence poses must nest like the rig).
local PARENT: { [string]: string } = {
	LowerTorso = "HumanoidRootPart",
	UpperTorso = "LowerTorso",
	Head = "UpperTorso",
	LeftUpperArm = "UpperTorso",
	LeftLowerArm = "LeftUpperArm",
	LeftHand = "LeftLowerArm",
	RightUpperArm = "UpperTorso",
	RightLowerArm = "RightUpperArm",
	RightHand = "RightLowerArm",
	LeftUpperLeg = "LowerTorso",
	LeftLowerLeg = "LeftUpperLeg",
	RightUpperLeg = "LowerTorso",
	RightLowerLeg = "RightUpperLeg",
}

local function deg(x: number, y: number, z: number): CFrame
	return CFrame.Angles(math.rad(x), math.rad(y), math.rad(z))
end

-- Built-in gestures as keyframes: { time, { joint = CFrame } }. Angles are joint-space rotations.
ActorMotion.GESTURES = {
	recoil = { -- surprised step back: lean back, hands come up to the chest (elbows out, not arms at the lens)
		{ 0, {} },
		{ 0.25, { UpperTorso = deg(-14, 0, 0), Head = deg(-8, 0, 0), RightUpperArm = deg(38, 0, 22),
			LeftUpperArm = deg(38, 0, -22), RightLowerArm = deg(62, 0, 0), LeftLowerArm = deg(62, 0, 0) } },
		{ 0.9, { UpperTorso = deg(-10, 0, 0), Head = deg(-4, 0, 0), RightUpperArm = deg(30, 0, 16),
			LeftUpperArm = deg(30, 0, -16), RightLowerArm = deg(50, 0, 0), LeftLowerArm = deg(50, 0, 0) } },
		{ 1.4, {} },
	},
	nod = {
		{ 0, {} },
		{ 0.2, { Head = deg(-18, 0, 0) } },
		{ 0.4, { Head = deg(4, 0, 0) } },
		{ 0.6, { Head = deg(-12, 0, 0) } },
		{ 0.85, {} },
	},
	reach = { -- reach toward something in front at chest height
		{ 0, {} },
		{ 0.4, { RightUpperArm = deg(85, 0, 5), RightLowerArm = deg(10, 0, 0), UpperTorso = deg(6, 0, 0) } },
		{ 1.2, { RightUpperArm = deg(80, 0, 5), RightLowerArm = deg(14, 0, 0), UpperTorso = deg(5, 0, 0) } },
		{ 1.6, {} },
	},
} :: { [string]: { { any } } }

function ActorMotion.gestureSequence(name: string): KeyframeSequence?
	local frames = ActorMotion.GESTURES[name]
	if not frames then
		return nil
	end
	local kfs = Instance.new("KeyframeSequence")
	kfs.Name = "StarGesture_" .. name
	kfs.Loop = false
	kfs.Priority = Enum.AnimationPriority.Action
	for _, entry in frames do
		local keyframe = Instance.new("Keyframe")
		keyframe.Time = entry[1]
		local joints: { [string]: CFrame } = entry[2]
		local poses: { [string]: Pose } = {}
		local function pose(jointName: string): Pose
			local existing = poses[jointName]
			if existing then
				return existing
			end
			local p = Instance.new("Pose")
			p.Name = jointName
			p.CFrame = joints[jointName] or CFrame.identity
			p.EasingStyle = Enum.PoseEasingStyle.Cubic
			p.EasingDirection = Enum.PoseEasingDirection.InOut
			poses[jointName] = p
			local parentName = PARENT[jointName]
			p.Parent = if parentName then pose(parentName) else keyframe
			return p
		end
		pose("HumanoidRootPart")
		for jointName in PARENT do
			pose(jointName) -- every joint keyed in every keyframe, so unkeyed joints return to rest
		end
		keyframe.Parent = kfs
	end
	return kfs
end

function ActorMotion.spawn(name: string, template: Model, ground: CFrame, parent: Instance): Actor?
	local model = template:Clone()
	model.Name = name
	local root = model:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") then
		model:Destroy()
		return nil
	end
	local humanoid = model:FindFirstChildOfClass("Humanoid")
	local animator = humanoid and humanoid:FindFirstChildOfClass("Animator")
	if humanoid and not animator then
		local made = Instance.new("Animator")
		made.Parent = humanoid
		animator = made
	end
	for _, d in model:GetDescendants() do
		if d:IsA("Script") or d:IsA("LocalScript") then
			d:Destroy() -- a template must not run its own Animate/health scripts
		elseif d:IsA("BasePart") then
			d.CanCollide = false
			d.CanTouch = false
			d.CanQuery = false
		end
	end
	root.Anchored = true
	if humanoid then
		humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
		humanoid:SetStateEnabled(Enum.HumanoidStateType.Dead, false)
	end
	local height = (if humanoid then humanoid.HipHeight else 2) + root.Size.Y / 2
	local actor: Actor = {
		name = name,
		model = model,
		root = root,
		humanoid = humanoid,
		animator = animator,
		tracks = {},
		ground = height,
	}
	ActorMotion.place(actor, ground)
	model.Parent = parent
	return actor
end

-- Put the actor's feet on `ground` (a CFrame on the floor, facing where the actor should face).
function ActorMotion.place(actor: Actor, ground: CFrame)
	actor.root.CFrame = ground * CFrame.new(0, actor.ground, 0)
end

function ActorMotion.groundOf(actor: Actor): Vector3
	return actor.root.Position - Vector3.new(0, actor.ground, 0)
end

function ActorMotion.track(actor: Actor, key: string, id: string, looped: boolean?, priority: Enum.AnimationPriority?): AnimationTrack?
	local existing = actor.tracks[key]
	if existing then
		return existing
	end
	local animator = actor.animator
	if not animator then
		return nil
	end
	local animation = Instance.new("Animation")
	animation.AnimationId = id
	animation.Name = key
	local ok, track = pcall(function()
		return animator:LoadAnimation(animation)
	end)
	if not ok or not track then
		return nil
	end
	track.Looped = looped == true
	if priority then
		track.Priority = priority
	end
	actor.tracks[key] = track
	return track
end

-- Plays a built-in gesture (KeyframeSequence registered in Studio) or an animation id; returns the track.
function ActorMotion.playGesture(actor: Actor, name: string?, animationId: string?, speed: number): (AnimationTrack?, string)
	local id = animationId
	local source = "animation id"
	if not id and name then
		local kfs = ActorMotion.gestureSequence(name)
		if kfs then
			local ok, registered = pcall(function()
				return KeyframeSequenceProvider:RegisterKeyframeSequence(kfs)
			end)
			if ok and type(registered) == "string" then
				id = registered
				source = "keyframes (Studio-only id)"
			end
		end
		if not id then
			id = ActorMotion.DEFAULT_ANIMATIONS[name]
			source = "built-in emote"
		end
	end
	if not id then
		return nil, "no animation for " .. tostring(name)
	end
	local track = ActorMotion.track(actor, "gesture:" .. (name or id), id, false, Enum.AnimationPriority.Action)
	if not track then
		return nil, "could not load " .. source
	end
	track:Play(0.15)
	track:AdjustSpeed(speed)
	return track, source
end

return ActorMotion
