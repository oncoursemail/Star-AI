The emitter keeps running while the character moves and a rate limit stops it from spamming.

```luau
local Dust = {}

function Dust.attach(humanoid: Humanoid, emitter: ParticleEmitter, now: () -> number): () -> ()
	local last = 0
	local connection = humanoid.Running:Connect(function(speed: number)
		local t = now()
		if t - last < 0.25 then
			return
		end
		last = t
		if speed > 8 then
			emitter.Enabled = true
			emitter:Emit(math.floor(speed / 4))
		else
			emitter.Enabled = false
		end
	end)
	return function()
		connection:Disconnect()
	end
end

return Dust
```
