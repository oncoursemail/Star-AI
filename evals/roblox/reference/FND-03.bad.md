```luau
--!strict
-- No clamp: a long hitch is simulated in full, which is how the spiral of death starts.
local FixedStep = {}
FixedStep.__index = FixedStep

function FixedStep.new(step: number, maxFrame: number)
	return setmetatable({ step = step, maxFrame = maxFrame, accumulator = 0 }, FixedStep)
end

function FixedStep:advance(frameDt: number): number
	self.accumulator += frameDt
	local steps = 0
	while self.accumulator >= self.step do
		self.accumulator -= self.step
		steps += 1
	end
	return steps
end

function FixedStep:alpha(): number
	return self.accumulator / self.step
end

return FixedStep
```
