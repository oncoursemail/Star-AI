-- Generated pure-Luau validators. No Roblox objects or yield points.
local Validators = {}
function Validators.Buy(...)
    if select("#", ...) ~= 2 then return false end
    local arg1 = select(1, ...)
    if typeof(arg1) ~= "number" then return false end
    if arg1 ~= arg1 or arg1 == math.huge or arg1 == -math.huge then return false end
    if arg1 < 1 then return false end
    if arg1 > 5 then return false end
    local arg2 = select(2, ...)
    if typeof(arg2) ~= "string" then return false end
    if #arg2 < 1 then return false end
    if #arg2 > 4 then return false end
    if not (arg2 == "A" or arg2 == "B") then return false end
    return true
end
function Validators.Look(...)
    if select("#", ...) ~= 1 then return false end
    local arg1 = select(1, ...)
    if typeof(arg1) ~= "number" then return false end
    if arg1 ~= arg1 or arg1 == math.huge or arg1 == -math.huge then return false end
    if arg1 < -180 then return false end
    if arg1 > 180 then return false end
    return true
end
function Validators.Updated(...)
    if select("#", ...) ~= 1 then return false end
    local arg1 = select(1, ...)
    if typeof(arg1) ~= "boolean" then return false end
    return true
end
function Validators.Pulse(...)
    if select("#", ...) ~= 1 then return false end
    local arg1 = select(1, ...)
    if typeof(arg1) ~= "number" then return false end
    if arg1 ~= arg1 or arg1 == math.huge or arg1 == -math.huge then return false end
    if arg1 < 0 then return false end
    if arg1 > 1 then return false end
    return true
end
function Validators.Ping(...)
    if select("#", ...) ~= 0 then return false end
    return true
end
return Validators
