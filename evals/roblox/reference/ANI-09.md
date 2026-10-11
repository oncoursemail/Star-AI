```luau
local Spring = {}
Spring.__index = Spring

function Spring.new(initial: number, frequency: number, damping: number)
	return setmetatable({ x = initial, v = 0, w = frequency * 2 * math.pi, z = damping }, Spring)
end

function Spring:reset(position: number)
	self.x = position
	self.v = 0
end

function Spring:step(target: number, dt: number): number
	if dt <= 0 then
		return self.x
	end
	local w, z = self.w, self.z
	local offset = self.x - target
	local v = self.v
	local newOffset, newV
	if z == 1 then
		local e = math.exp(-w * dt)
		newOffset = (offset + (v + w * offset) * dt) * e
		newV = (v - (v + w * offset) * w * dt) * e
	elseif z < 1 then
		local wd = w * math.sqrt(1 - z * z)
		local e = math.exp(-z * w * dt)
		local c, s = math.cos(wd * dt), math.sin(wd * dt)
		newOffset = e * (offset * c + ((v + z * w * offset) / wd) * s)
		newV = e * (v * c - ((v * z * w + offset * w * w) / wd) * s)
	else
		local r = math.sqrt(z * z - 1)
		local r1, r2 = -w * (z - r), -w * (z + r)
		local c2 = (v - r1 * offset) / (r2 - r1)
		local c1 = offset - c2
		newOffset = c1 * math.exp(r1 * dt) + c2 * math.exp(r2 * dt)
		newV = c1 * r1 * math.exp(r1 * dt) + c2 * r2 * math.exp(r2 * dt)
	end
	self.x = target + newOffset
	self.v = newV
	return self.x
end

return Spring
```
