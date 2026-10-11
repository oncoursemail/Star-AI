The controller creates each `Animation` once and loads it once through the Animator (`Humanoid:LoadAnimation` is deprecated), keeps the tracks in a table, and keeps at most one of its own tracks playing.

```luau
--!strict
local AnimController = {}
AnimController.__index = AnimController

local DEFAULT_FADE = 0.1

function AnimController.new(animator: Animator, ids: { [string]: string })
	return setmetatable({
		animator = animator,
		ids = ids,
		tracks = {} :: { [string]: AnimationTrack },
		current = nil :: AnimationTrack?,
		speed = 1,
	}, AnimController)
end

function AnimController:play(name: string, fadeTime: number?): AnimationTrack?
	local id = self.ids[name]
	if id == nil then
		return nil
	end
	local fade = fadeTime or DEFAULT_FADE

	local track = self.tracks[name]
	if track == nil then
		local animation = Instance.new("Animation")
		animation.AnimationId = id
		track = self.animator:LoadAnimation(animation)
		self.tracks[name] = track
	end
	if track.IsPlaying then
		return track
	end

	local previous = self.current
	if previous ~= nil and previous ~= track and previous.IsPlaying then
		previous:Stop(fade)
	end
	track:Play(fade)
	track:AdjustSpeed(self.speed)
	self.current = track
	return track
end

function AnimController:stop(fadeTime: number?)
	local current = self.current
	if current ~= nil and current.IsPlaying then
		current:Stop(fadeTime or DEFAULT_FADE)
	end
end

function AnimController:setSpeed(multiplier: number)
	self.speed = multiplier
	local current = self.current
	if current ~= nil and current.IsPlaying then
		current:AdjustSpeed(multiplier)
	end
end

return AnimController
```
