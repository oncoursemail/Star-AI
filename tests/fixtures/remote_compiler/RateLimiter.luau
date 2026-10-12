-- Generated pure-Luau per-player, per-message one-second fixed windows.
local RateLimiter = {}
RateLimiter.__index = RateLimiter
function RateLimiter.new()
    return setmetatable({ buckets = {} }, RateLimiter)
end
function RateLimiter:allow(player, name, limit, now)
    if player == nil or typeof(name) ~= "string" then return false end
    if typeof(limit) ~= "number" or limit ~= limit or limit < 1 or limit > 10000 or limit % 1 ~= 0 then return false end
    if typeof(now) ~= "number" or now ~= now or now == math.huge or now == -math.huge then return false end
    local bucket = self.buckets[player]
    if not bucket then
        bucket = {}
        self.buckets[player] = bucket
    end
    local state = bucket[name]
    if state and now < state.started then return false end
    if not state or now - state.started >= 1 then
        bucket[name] = { started = now, count = 1 }
        return true
    end
    if state.count >= limit then return false end
    state.count = state.count + 1
    return true
end
function RateLimiter:remove(player)
    self.buckets[player] = nil
end
return RateLimiter
