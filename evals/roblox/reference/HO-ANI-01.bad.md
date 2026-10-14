The controller creates and loads the animation again every time it is played, after stopping the previous track.

```luau
local AnimController = {}
AnimController.__index = AnimController

function AnimController.new(animator: Animator, ids: { [string]: string })
	return setmetatable({ animator = animator, ids = ids, current = nil, speed = 1 }, AnimController)
end

function AnimController:play(name: string, fadeTime: number?)
	local id = self.ids[name]
	if not id then
		return nil
	end
	if self.current then
		self.current:Stop(fadeTime or 0.1)
	end
	local animation = Instance.new("Animation")
	animation.AnimationId = id
	local track = self.animator:LoadAnimation(animation)
	track:Play(fadeTime or 0.1)
	track:AdjustSpeed(self.speed)
	self.current = track
	return track
end

function AnimController:stop(fadeTime: number?)
	if self.current then
		self.current:Stop(fadeTime or 0.1)
	end
end

function AnimController:setSpeed(multiplier: number)
	self.speed = multiplier
end

return AnimController
```
