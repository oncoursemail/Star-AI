```luau
--!strict
-- Fixed timestep with an accumulator: the simulation always advances by exactly `step` seconds.
local FixedStep = {}
FixedStep.__index = FixedStep

export type FixedStep = typeof(setmetatable({} :: { step: number, maxFrame: number, accumulator: number }, FixedStep))

function FixedStep.new(step: number, maxFrame: number): FixedStep
	assert(step > 0, "step must be positive")
	return setmetatable({ step = step, maxFrame = maxFrame, accumulator = 0 }, FixedStep)
end

-- Adds one frame's time (clamped to [0, maxFrame] so a hitch cannot start a spiral of death)
-- and returns how many fixed steps to simulate now.
function FixedStep.advance(self: FixedStep, frameDt: number): number
	local dt = math.clamp(frameDt, 0, self.maxFrame)
	self.accumulator += dt
	local steps = 0
	while self.accumulator >= self.step do
		self.accumulator -= self.step
		steps += 1
	end
	return steps
end

-- How far we are between the previous and the current simulation state, for render interpolation.
function FixedStep.alpha(self: FixedStep): number
	return self.accumulator / self.step
end

return FixedStep
```
