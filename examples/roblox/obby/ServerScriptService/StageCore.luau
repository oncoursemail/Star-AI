--!strict
-- Pure progression rules. No Roblox objects, global state, or services.
local Obby = {}

local function integer(value)
    return type(value) == "number" and value == value and value < math.huge
        and value % 1 == 0
end

local function playerId(value)
    return integer(value) and value >= 1
end

function Obby.new(maxStage)
    if not integer(maxStage) or maxStage < 1 or maxStage > 64 then
        return nil, "invalid stage count"
    end
    return {maxStage = maxStage, stages = {}, finished = {}, lastKill = {}}
end

function Obby.stage(state, id)
    if not playerId(id) then return nil end
    return state.stages[id] or 0
end

function Obby.advance(state, id, stage)
    if not playerId(id) or not integer(stage) or stage < 1 or stage > state.maxStage then
        return false, "invalid checkpoint"
    end
    local previous = state.stages[id] or 0
    if stage == previous then return false, "already reached" end
    if stage ~= previous + 1 then return false, "out of order" end
    state.stages[id] = stage
    return true, stage
end

function Obby.claimFinish(state, id)
    if not playerId(id) then return false, "invalid player" end
    if (state.stages[id] or 0) < state.maxStage then return false, "incomplete" end
    if state.finished[id] then return false, "already awarded" end
    state.finished[id] = true
    return true, "awarded"
end

function Obby.shouldKill(state, id, now, cooldown)
    if not playerId(id) or type(now) ~= "number" or now ~= now
        or now < 0 or now == math.huge or type(cooldown) ~= "number"
        or cooldown ~= cooldown or cooldown < 0 or cooldown == math.huge then
        return false
    end
    local previous = state.lastKill[id]
    if previous ~= nil and now >= previous and now - previous < cooldown then
        return false
    end
    if previous ~= nil and now < previous then return false end
    state.lastKill[id] = now
    return true
end

function Obby.removePlayer(state, id)
    if not playerId(id) then return false end
    state.stages[id] = nil
    state.finished[id] = nil
    state.lastKill[id] = nil
    return true
end

return Obby
