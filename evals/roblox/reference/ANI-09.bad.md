```luau
local Spring = {}
Spring.__index = Spring
function Spring.new(initial: number, frequency: number, damping: number)
	return setmetatable({ x = initial, v = 0, k = (frequency * 2 * math.pi) ^ 2, c = 2 * damping * frequency * 2 * math.pi }, Spring)
end
function Spring:reset(position: number) self.x = position; self.v = 0 end
function Spring:step(target: number, dt: number): number
	local a = self.k * (target - self.x) - self.c * self.v
	self.v += a * dt
	self.x += self.v * dt
	return self.x
end
return Spring
```
