---
name: game-inventory
description: Build Roblox server-owned inventories, tool equip, persistence and validated client requests.
---
# game-inventory
## When to use
Item pickup, item inventory, equipping tools, saving ownership.
## Server/client split
Client may ask to equip a catalog ID; server confirms ownership, clones tools from ServerStorage and prevents duplicates.
## Data model
inventory[UserId]={owned: {[string]:boolean}, equipped:string?}; ServerStorage.Tools holds template Tools; IDs are server allowlisted.
## Ten rules that prevent bugs
1. Server owns progress, rewards, cooldowns, and prices; client displays and requests.
2. Validate type, range, ownership, character state and proximity for every remote.
3. Debounce server-side before a yield; never trust client timestamps.
4. Use bounded pcall retries with backoff for DataStore calls; never save every event.
5. Do not yield in UpdateAsync callbacks; preserve old data and version schema.
6. Avoid unbounded while loops; task.wait and stop loops when player/plot leaves.
7. Disconnect transient event connections and remove per-player tables on leaving.
8. Check nil characters, destroyed parts and respawns before indexing.
9. Keep reward mutations atomic in one server handler; never double-grant on retries.
10. Test two clients and rejoin; never claim Studio validation without running it.

## Strict Luau skeleton
```luau
--!strict
-- ServerScriptService/Inventory.server.luau; ReplicatedStorage.Equip is RemoteEvent
local Players = game:GetService("Players")
local store = game:GetService("DataStoreService"):GetDataStore("Inventory_v1")
local storage = game:GetService("ServerStorage"):WaitForChild("Tools")
local event = game:GetService("ReplicatedStorage"):WaitForChild("Equip") :: RemoteEvent
type State = {owned: {[string]: boolean}, equipped: string?}
local inventory: {[number]: State} = {}
Players.PlayerAdded:Connect(function(player)
    local loaded = nil
    local ok = pcall(function() loaded = store:GetAsync(tostring(player.UserId)) end)
    if not ok then player:Kick("Inventory unavailable; rejoin."); return end
    local owned = {Sword = true}
    if type(loaded) == "table" and type(loaded.owned) == "table" then
        for id, yes in loaded.owned do
            if type(id) == "string" and #id <= 32 and yes == true
                and storage:FindFirstChild(id) then owned[id] = true end
        end
    end
    inventory[player.UserId] = {owned = owned, equipped = nil}
end)
event.OnServerEvent:Connect(function(player, itemId)
    if type(itemId) ~= "string" or #itemId > 32 then return end
    local s = inventory[player.UserId]
    if not s or not s.owned[itemId] then return end
    local template = storage:FindFirstChild(itemId)
    if not template or not template:IsA("Tool") then return end
    local backpack = player:FindFirstChildOfClass("Backpack")
    if not backpack then return end
    for _, container in {backpack, player.Character} do
        if container then
            for _, child in container:GetChildren() do
                if child:IsA("Tool") and child.Name == itemId then child:Destroy() end
            end
        end
    end
    template:Clone().Parent = backpack
    s.equipped = itemId
end)
local function save(player: Player)
    local s = inventory[player.UserId]; if not s then return end
    local snapshot = {owned = s.owned}
    for attempt = 1, 3 do
        local ok = pcall(function()
            store:UpdateAsync(tostring(player.UserId), function(_old) return snapshot end)
        end)
        if ok then return end
        task.wait(attempt * 2)
    end
    warn("Inventory save failed", player.UserId)
end
Players.PlayerRemoving:Connect(function(player)
    save(player); inventory[player.UserId] = nil
end)
game:BindToClose(function()
    for _, p in Players:GetPlayers() do task.spawn(save, p) end
    task.wait(3) -- In production wait for saves with a bounded deadline.
end)
-- Add budgeted autosave and session concurrency protection.
```
## Studio playtest checklist
- Equip unowned ID, huge string, invalid type, forged Tool, duplicate spam, death, reconnect; only one template exists; load failure does not overwrite existing data.
- Confirm Output has no errors; inspect DataStore retry/backoff, save on exit, and client UI separately if these are added to the skeleton.
