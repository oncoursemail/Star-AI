--!strict
-- Pure cooldown bookkeeping: callers supply the user id and server clock.
local RateLimiter = {}

export type State = {
	cooldown: number,
	lastAccepted: { [number]: number },
}

function RateLimiter.new(cooldown: number): State
	assert(type(cooldown) == "number" and cooldown > 0 and cooldown < math.huge, "invalid cooldown")
	return { cooldown = cooldown, lastAccepted = {} }
end

function RateLimiter.allow(state: State, userId: number, now: number): boolean
	if type(userId) ~= "number" or userId % 1 ~= 0 then
		return false
	end
	if type(now) ~= "number" or now ~= now or now < 0 or now == math.huge then
		return false
	end
	local previous = state.lastAccepted[userId]
	if previous ~= nil and now - previous < state.cooldown then
		return false
	end
	state.lastAccepted[userId] = now
	return true
end

function RateLimiter.forget(state: State, userId: number)
	state.lastAccepted[userId] = nil
end

return RateLimiter
