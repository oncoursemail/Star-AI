--!strict
-- All values and ownership are authoritative server state, not RemoteFunction input.
local Inventory = require("./Inventory")
local Shop = {}

local function whole(value)
    return type(value) == "number" and value == value
        and value < math.huge and value % 1 == 0
end

local function validId(id)
    return whole(id) and id >= 1
end

function Shop.new(catalog)
    if type(catalog) ~= "table" or next(catalog) == nil then
        return nil, "empty catalog"
    end
    local prices = {}
    for item, price in pairs(catalog) do
        if type(item) ~= "string" or #item == 0 or #item > 60
            or not whole(price) or price <= 0 or price > 100000 then
            return nil, "invalid catalog entry"
        end
        prices[item] = price
    end
    return {prices = prices, wallets = {}, owned = {}, pending = {}}
end

function Shop.seed(state, userId, coins)
    if not validId(userId) or not whole(coins) or coins < 0 or coins > 1000000 then
        return false
    end
    if state.wallets[userId] ~= nil then return false end
    state.wallets[userId] = coins
    state.owned[userId] = Inventory.new()
    state.pending[userId] = {}
    return true
end

function Shop.balance(state, userId)
    return state.wallets[userId]
end

function Shop.has(state, userId, itemId)
    local items = state.owned[userId]
    return items ~= nil and Inventory.has(items, itemId)
end

function Shop.ownedIds(state, userId)
    return Inventory.ids(state.owned[userId] or {})
end

function Shop.purchase(state, userId, itemId, quantity, clientPrice)
    -- Even an accurate client-provided price is a protocol violation.
    if clientPrice ~= nil then return false, "client price refused" end
    if not validId(userId) then return false, "invalid player" end
    if not whole(quantity) or quantity ~= 1 then return false, "invalid quantity" end
    if type(itemId) ~= "string" or not state.prices[itemId] then
        return false, "unknown item"
    end
    local wallet = state.wallets[userId]
    if wallet == nil then return false, "wallet not initialized" end
    local items = state.owned[userId]
    if Inventory.has(items, itemId) then return false, "already owned" end
    local price = state.prices[itemId]
    if wallet < price then return false, "insufficient coins" end
    state.wallets[userId] = wallet - price
    assert(Inventory.grantOnce(items, itemId))
    state.pending[userId][itemId] = price
    return true, {item = itemId, price = price, remaining = state.wallets[userId]}
end

function Shop.confirm(state, userId, itemId)
    local pending = state.pending[userId]
    if not pending or pending[itemId] == nil then return false end
    pending[itemId] = nil
    return true
end

function Shop.rollback(state, userId, itemId)
    local pending = state.pending[userId]
    if not pending or pending[itemId] == nil then return false end
    local price = pending[itemId]
    pending[itemId] = nil
    state.wallets[userId] += price
    return Inventory.revoke(state.owned[userId], itemId)
end

function Shop.removePlayer(state, userId)
    if not validId(userId) or state.wallets[userId] == nil then return false end
    state.wallets[userId] = nil
    state.owned[userId] = nil
    state.pending[userId] = nil
    return true
end

return Shop
