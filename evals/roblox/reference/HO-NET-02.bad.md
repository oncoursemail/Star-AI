A token bucket per player, refilled with os.clock, kicking after enough denied calls.

```luau
local Limiter = {}
Limiter.__index = Limiter

function Limiter.new(capacity: number, refillPerSecond: number, maxStrikes: number, now: () -> number, onAbuse: (number) -> ())
	return setmetatable({
		capacity = capacity,
		refill = refillPerSecond,
		maxStrikes = maxStrikes,
		onAbuse = onAbuse,
		buckets = {},
	}, Limiter)
end

function Limiter:allow(userId: number): boolean
	local t = os.clock()
	local bucket = self.buckets[userId]
	if bucket == nil then
		bucket = { tokens = self.capacity, last = t, strikes = 0 }
		self.buckets[userId] = bucket
	end
	bucket.tokens = bucket.tokens + (t - bucket.last) * self.refill
	bucket.last = t
	if bucket.tokens >= 1 then
		bucket.tokens -= 1
		return true
	end
	bucket.strikes += 1
	if bucket.strikes >= self.maxStrikes then
		self.onAbuse(userId)
	end
	return false
end

function Limiter:forget(userId: number)
	self.buckets[userId] = nil
end

return Limiter
```
