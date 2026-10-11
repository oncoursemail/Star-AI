--!strict
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local RateLimiter = require(Shared:WaitForChild("RateLimiter"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

return {
	["first action passes but same-tick replay is blocked"] = function()
		local state = RateLimiter.new(0.25)
		expect(RateLimiter.allow(state, 12, 0), "first click")
		for _ = 1, 1000 do
			expect(not RateLimiter.allow(state, 12, 0), "a replay must not pass")
		end
		expect(RateLimiter.allow(state, 12, 0.25), "cooldown expires")
	end,
	["one thousand requests per second cannot beat four normal clicks"] = function()
		local spam = RateLimiter.new(0.25)
		local burstCount = 0
		for index = 0, 999 do
			if RateLimiter.allow(spam, 12, index / 1000) then
				burstCount += 1
			end
		end
		local ordinary = RateLimiter.new(0.25)
		local normalCount = 0
		for index = 0, 3 do
			if RateLimiter.allow(ordinary, 12, index * 0.25) then
				normalCount += 1
			end
		end
		expect(burstCount == 4 and burstCount == normalCount, "flooding buys no extra rewards")
	end,
	["identities are isolated and resets clear their history"] = function()
		local state = RateLimiter.new(0.25)
		expect(RateLimiter.allow(state, 1, 5), "first player")
		expect(RateLimiter.allow(state, 2, 5), "second player")
		expect(not RateLimiter.allow(state, 1, 4), "backwards clocks cannot bypass")
		expect(not RateLimiter.allow(state, 1, 0 / 0), "NaN time cannot bypass")
		RateLimiter.forget(state, 1)
		expect(RateLimiter.allow(state, 1, 5), "leave cleanup")
	end,
}
