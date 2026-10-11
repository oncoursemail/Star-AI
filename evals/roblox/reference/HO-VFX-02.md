The emitter is switched to burst-only (`Enabled = false`) and driven from `Humanoid.Running`. The time of the last burst is only updated when a burst really happens, so ignored events never push the next burst back.

```luau
--!strict
local Dust = {}

local MIN_SPEED = 8
local MIN_GAP = 0.25

function Dust.attach(humanoid: Humanoid, emitter: ParticleEmitter, now: () -> number): () -> ()
	emitter.Enabled = false
	local lastBurst: number? = nil
	local connection = humanoid.Running:Connect(function(speed: number)
		if speed <= MIN_SPEED then
			return
		end
		local t = now()
		if lastBurst ~= nil and t - lastBurst < MIN_GAP then
			return
		end
		lastBurst = t
		emitter:Emit(math.clamp(math.floor(speed / 4), 1, 6))
	end)
	return function()
		connection:Disconnect()
	end
end

return Dust
```
