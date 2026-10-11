The guard keeps one baseline (position and time) per player. Only an allowed sample moves the baseline, so a flagged player cannot launder a teleport by being sampled again from the new place. Only X and Z count, because falling and jumping are normal.

```luau
--!strict
local SpeedGuard = {}
SpeedGuard.__index = SpeedGuard

type Baseline = { position: Vector3, time: number }

function SpeedGuard.new(maxSpeed: number, tolerance: number)
	return setmetatable({
		maxSpeed = maxSpeed,
		tolerance = tolerance,
		baselines = {} :: { [number]: Baseline },
	}, SpeedGuard)
end

function SpeedGuard:sample(userId: number, position: Vector3, now: number): boolean
	local baseline = self.baselines[userId]
	if baseline == nil then
		self.baselines[userId] = { position = position, time = now }
		return true
	end
	local dt = now - baseline.time
	if dt <= 0 then
		return false
	end
	local dx = position.X - baseline.position.X
	local dz = position.Z - baseline.position.Z
	local distance = math.sqrt(dx * dx + dz * dz)
	if distance <= self.maxSpeed * dt * self.tolerance then
		self.baselines[userId] = { position = position, time = now }
		return true
	end
	return false
end

function SpeedGuard:forget(userId: number)
	self.baselines[userId] = nil
end

return SpeedGuard
```

Call `forget` from `Players.PlayerRemoving`, and set the character back to the last allowed position when `sample` returns false.
