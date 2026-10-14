--!strict
-- Authoritative demo shop. Put this Script and pure modules in ServerScriptService.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")

local Catalog = require(ReplicatedStorage:WaitForChild("ShopCatalog"))
local Shop = require(script.Parent:WaitForChild("ShopCore"))
local state = assert(Shop.new(Catalog))
local stock = ServerStorage:WaitForChild("ShopTools")
local remote = ReplicatedStorage:FindFirstChild("PurchaseItem")
if not remote then
    remote = Instance.new("RemoteFunction")
    remote.Name = "PurchaseItem"
    remote.Parent = ReplicatedStorage
end
assert(remote:IsA("RemoteFunction"), "PurchaseItem must be a RemoteFunction")

local initialized = {}

local function sendOwnedTools(player)
    local backpack = player:WaitForChild("Backpack", 5)
    if not backpack then return end
    for _, itemId in Shop.ownedIds(state, player.UserId) do
        local template = stock:FindFirstChild(itemId)
        if template and template:IsA("Tool") and not backpack:FindFirstChild(itemId) then
            local cloned = template:Clone()
            cloned.Parent = backpack
        end
    end
end

local function setup(player)
    if initialized[player] then return end
    initialized[player] = true
    assert(Shop.seed(state, player.UserId, 250))
    local stats = Instance.new("Folder")
    stats.Name = "leaderstats"
    stats.Parent = player
    local coins = Instance.new("IntValue")
    coins.Name = "Coins"
    coins.Value = 250
    coins.Parent = stats
    player.CharacterAdded:Connect(function()
        task.defer(sendOwnedTools, player) -- Backpack may be replaced on respawn.
    end)
    if player.Character then task.defer(sendOwnedTools, player) end
end

remote.OnServerInvoke = function(player, itemId, quantity, clientPrice)
    -- No trusting a user-supplied price, quantity or arbitrary item ID.
    if clientPrice ~= nil then return {ok = false, reason = "client price refused"} end
    if type(itemId) ~= "string" or type(quantity) ~= "number" then
        return {ok = false, reason = "invalid input"}
    end
    local template = stock:FindFirstChild(itemId)
    local backpack = player:FindFirstChildOfClass("Backpack")
    if not template or not template:IsA("Tool") or not backpack then
        return {ok = false, reason = "item unavailable"}
    end
    local okClone, cloned = pcall(function() return template:Clone() end)
    if not okClone then return {ok = false, reason = "item unavailable"} end
    local accepted, result = Shop.purchase(state, player.UserId, itemId, quantity, clientPrice)
    if not accepted then
        cloned:Destroy()
        return {ok = false, reason = result}
    end
    local granted = pcall(function() cloned.Parent = backpack end)
    if not granted then
        cloned:Destroy()
        Shop.rollback(state, player.UserId, itemId)
        return {ok = false, reason = "grant failed"}
    end
    Shop.confirm(state, player.UserId, itemId)
    local stats = player:FindFirstChild("leaderstats")
    local coins = stats and stats:FindFirstChild("Coins")
    if coins then coins.Value = Shop.balance(state, player.UserId) end
    return {ok = true, item = itemId, remaining = Shop.balance(state, player.UserId)}
end

Players.PlayerAdded:Connect(setup)
for _, player in Players:GetPlayers() do setup(player) end
Players.PlayerRemoving:Connect(function(player)
    initialized[player] = nil
    Shop.removePlayer(state, player.UserId)
end)
