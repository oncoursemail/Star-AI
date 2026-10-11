Each sample is compared with the previous one and the guard stores the newest position every time.

```luau
local SpeedGuard = {}
SpeedGuard.__index = SpeedGuard

function SpeedGuard.new(maxSpeed: number, tolerance: number)
	return setmetatable({ maxSpeed = maxSpeed, tolerance = tolerance, last = {} }, SpeedGuard)
end

function SpeedGuard:sample(userId: number, position: Vector3, now: number): boolean
	local last = self.last[userId]
	self.last[userId] = { position = position, time = now }
	if not last then
		return true
	end
	local dt = now - last.time
	if dt <= 0 then
		return false
	end
	return (position - last.position).Magnitude <= self.maxSpeed * dt * self.tolerance
end

function SpeedGuard:forget(userId: number)
	self.last[userId] = nil
end

return SpeedGuard
```
