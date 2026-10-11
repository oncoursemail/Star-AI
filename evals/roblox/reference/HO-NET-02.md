Each player gets a token bucket that is topped up from the injected clock on every call. A denied call adds a strike; an allowed call clears the strikes. `onAbuse` fires when the streak reaches `maxStrikes` and not again until an allowed call has ended the streak.

```luau
--!strict
local Limiter = {}
Limiter.__index = Limiter

type Bucket = { tokens: number, last: number, strikes: number }

function Limiter.new(capacity: number, refillPerSecond: number, maxStrikes: number, now: () -> number, onAbuse: (number) -> ())
	return setmetatable({
		capacity = capacity,
		refill = refillPerSecond,
		maxStrikes = maxStrikes,
		now = now,
		onAbuse = onAbuse,
		buckets = {} :: { [number]: Bucket },
	}, Limiter)
end

function Limiter:allow(userId: number): boolean
	local t = self.now()
	local bucket = self.buckets[userId]
	if bucket == nil then
		bucket = { tokens = self.capacity, last = t, strikes = 0 }
		self.buckets[userId] = bucket
	else
		bucket.tokens = math.min(self.capacity, bucket.tokens + (t - bucket.last) * self.refill)
		bucket.last = t
	end
	if bucket.tokens >= 1 then
		bucket.tokens -= 1
		bucket.strikes = 0
		return true
	end
	bucket.strikes += 1
	if bucket.strikes == self.maxStrikes then
		self.onAbuse(userId)
	end
	return false
end

function Limiter:forget(userId: number)
	self.buckets[userId] = nil
end

return Limiter
```

Comparing with `==` (not `>=`) is what makes the callback fire once per streak.
