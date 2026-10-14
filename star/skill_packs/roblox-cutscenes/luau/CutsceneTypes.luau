--!strict
-- CutsceneTypes (shared ModuleScript, e.g. ReplicatedStorage.StarCutscene.CutsceneTypes): the data a cutscene is
-- made of, plus `validate`, used by the client before playing and by tests/generators.
--
-- A timeline is DATA in the cutscene's own local space: every position is relative to the origin CFrame the
-- server passes at play time, so the same timeline can play anywhere in a map.
--   shots: camera shots back to back (start, duration, a path of camera positions, what to look at, FOV, easing)
--   cues:  things that happen at a time (actors spawn/walk/animate, expressions, captions, VFX, letterbox, fades)

export type Ease = { style: string?, direction: string? } -- Enum.EasingStyle / Enum.EasingDirection item names

export type Shot = {
	name: string,
	start: number, -- seconds from the cutscene start
	duration: number,
	curve: string?, -- "catmull" (default, passes through every point), "bezier" (points are control points), "linear"
	points: { Vector3 }, -- camera positions (local space); one point = a locked-off camera
	look: { Vector3 }?, -- look-at targets along the shot (local space); interpolated with the same alpha
	lookActor: string?, -- or: look at this actor's head (overrides `look`)
	lookOffset: Vector3?, -- added to the actor's head position (e.g. lead room)
	fov: { number }?, -- { from, to } in degrees (1..120); default 70
	ease: Ease?, -- how alpha moves along the path; default Sine InOut
	roll: number?, -- degrees of camera roll (dutch angle)
	dof: { focusActor: string?, distance: number?, radius: number?, far: number?, near: number? }?,
}

export type Cue = {
	at: number, -- seconds from the cutscene start
	kind: string, -- see KINDS below
	actor: string?,
	template: string?, -- spawn: the actor template name
	position: Vector3?, -- spawn: where (local space)
	facing: number?, -- spawn: yaw in degrees
	to: Vector3?, -- walk: destination (local space)
	duration: number?, -- walk / expression blend / talk / caption / fade / letterbox time
	name: string?, -- expression: happy, angry, surprised, sad, neutral; anim: a named built-in gesture
	weight: number?, -- expression strength 0..1
	animation: string?, -- anim: rbxassetid://... (uploaded) when not a built-in gesture
	text: string?, -- caption text
	speaker: string?, -- caption speaker
	ability: string?, -- vfx: ability name of the VFX composer
	style: string?, -- vfx: style profile name of the VFX composer
	target: string?, -- vfx: an actor name or "point" (default)
	show: boolean?, -- letterbox: show or hide
	alpha: number?, -- fade: 0 clear .. 1 black
}

export type Timeline = {
	name: string,
	length: number, -- seconds; the cutscene ends (and control returns) here
	skippable: boolean?,
	letterbox: number?, -- bar height as a fraction of the screen height (0..0.2), default 0.11
	shots: { Shot },
	cues: { Cue },
}

local Types = {}

Types.KINDS = {
	spawn = true,
	walk = true,
	anim = true,
	expression = true,
	blink = true,
	talk = true,
	caption = true,
	vfx = true,
	letterbox = true,
	fade = true,
	despawn = true,
}
Types.EXPRESSIONS = { neutral = true, happy = true, angry = true, surprised = true, sad = true }
Types.CURVES = { catmull = true, bezier = true, linear = true }
Types.MAX_SHOTS = 16
Types.MAX_CUES = 64
Types.MAX_POINTS = 12
Types.MAX_LENGTH = 120
Types.MAX_TEXT = 140

local function isVector(value: any): boolean
	return typeof(value) == "Vector3"
end

local function enumItem(enum: any, name: string?): boolean
	if name == nil then
		return true
	end
	local ok = pcall(function()
		return enum[name :: string]
	end)
	return ok
end

-- Returns (true, nil) or (false, reason). Checks shapes, ranges, ordering and that shots tile the timeline.
function Types.validate(timeline: any): (boolean, string?)
	if type(timeline) ~= "table" then
		return false, "timeline is not a table"
	end
	if type(timeline.name) ~= "string" or #timeline.name == 0 or #timeline.name > 40 then
		return false, "name must be a 1..40 character string"
	end
	if type(timeline.length) ~= "number" or timeline.length <= 0 or timeline.length > Types.MAX_LENGTH then
		return false, "length must be 0..120 seconds"
	end
	if type(timeline.shots) ~= "table" or #timeline.shots == 0 or #timeline.shots > Types.MAX_SHOTS then
		return false, "1..16 shots required"
	end
	if type(timeline.cues) ~= "table" or #timeline.cues > Types.MAX_CUES then
		return false, "cues must be a list of at most 64"
	end
	local cursor = 0
	for index, shot in timeline.shots do
		local where = "shot " .. index
		if type(shot) ~= "table" or type(shot.name) ~= "string" then
			return false, where .. ": needs a name"
		end
		if type(shot.start) ~= "number" or type(shot.duration) ~= "number" or shot.duration <= 0 then
			return false, where .. ": start and a positive duration are required"
		end
		if math.abs(shot.start - cursor) > 1e-3 then
			return false, where .. ": starts at " .. shot.start .. " but the previous shot ends at " .. cursor
		end
		cursor = shot.start + shot.duration
		if type(shot.points) ~= "table" or #shot.points == 0 or #shot.points > Types.MAX_POINTS then
			return false, where .. ": 1..12 camera points required"
		end
		for _, p in shot.points do
			if not isVector(p) then
				return false, where .. ": camera points must be Vector3"
			end
		end
		if shot.look ~= nil then
			if type(shot.look) ~= "table" or #shot.look == 0 then
				return false, where .. ": look must be a non-empty list"
			end
			for _, p in shot.look do
				if not isVector(p) then
					return false, where .. ": look targets must be Vector3"
				end
			end
		elseif shot.lookActor == nil then
			return false, where .. ": needs look or lookActor"
		end
		if shot.curve ~= nil and not Types.CURVES[shot.curve] then
			return false, where .. ": unknown curve " .. tostring(shot.curve)
		end
		if shot.fov ~= nil then
			for _, f in shot.fov do
				if type(f) ~= "number" or f < 1 or f > 120 then
					return false, where .. ": FOV must be 1..120"
				end
			end
		end
		if shot.ease ~= nil then
			if not enumItem(Enum.EasingStyle, shot.ease.style) or not enumItem(Enum.EasingDirection, shot.ease.direction) then
				return false, where .. ": unknown easing"
			end
		end
	end
	if math.abs(cursor - timeline.length) > 1e-3 then
		return false, "shots end at " .. cursor .. " but the timeline length is " .. timeline.length
	end
	local last = 0
	for index, cue in timeline.cues do
		local where = "cue " .. index
		if type(cue) ~= "table" or type(cue.at) ~= "number" or type(cue.kind) ~= "string" then
			return false, where .. ": needs at and kind"
		end
		if not Types.KINDS[cue.kind] then
			return false, where .. ": unknown kind " .. cue.kind
		end
		if cue.at < last - 1e-6 then
			return false, where .. ": cues must be sorted by time"
		end
		if cue.at < 0 or cue.at > timeline.length then
			return false, where .. ": time outside the timeline"
		end
		last = cue.at
		if cue.kind == "expression" and not Types.EXPRESSIONS[cue.name or ""] then
			return false, where .. ": unknown expression " .. tostring(cue.name)
		end
		if cue.kind == "caption" and (type(cue.text) ~= "string" or #cue.text > Types.MAX_TEXT) then
			return false, where .. ": caption text must be a string of at most 140 characters"
		end
		if cue.kind == "walk" and not isVector(cue.to) then
			return false, where .. ": walk needs a Vector3 `to`"
		end
		if cue.kind == "spawn" and (type(cue.template) ~= "string" or not isVector(cue.position)) then
			return false, where .. ": spawn needs a template and a Vector3 position"
		end
		if cue.kind == "vfx" and (type(cue.ability) ~= "string" or type(cue.style) ~= "string") then
			return false, where .. ": vfx needs an ability and a style"
		end
	end
	return true, nil
end

return Types
