--!strict
-- Pure inventory used only from the server-owned shop state.
local Inventory = {}

function Inventory.new()
    return {}
end

function Inventory.has(items, itemId)
    return items[itemId] == true
end

function Inventory.grantOnce(items, itemId)
    if type(itemId) ~= "string" or #itemId == 0 or items[itemId] then
        return false
    end
    items[itemId] = true
    return true
end

function Inventory.revoke(items, itemId)
    if not items[itemId] then return false end
    items[itemId] = nil
    return true
end

function Inventory.ids(items)
    local result = {}
    for id, owned in pairs(items) do
        if owned then table.insert(result, id) end
    end
    table.sort(result)
    return result
end

return Inventory
