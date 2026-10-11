---
name: game-tycoon
description: Build Roblox tycoon games with per-player plots, droppers, collectors, upgrades and saving.
---
# game-tycoon
## When to use
Incremental factory plots with buy buttons and production.
## Server/client split
Server assigns plots, accrues resources, charges prices, spawns owned upgrades; client shows money and available buttons.
## Data model
playerState[UserId]={cash,owned}; plotOwner[plot]=UserId; catalog is immutable server price/production data.
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
-- ServerScriptService/Tycoon.server.luau; configure Workspace.Plots/<Plot>/BuyPrompt
local Players = game:GetService("Players")
local plots = workspace:WaitForChild("Plots")
local state: {[number]: {cash: number, owned: boolean}} = {}
local owners: {[Instance]: number} = {}
local PRICE = 25
for _, plot in plots:GetChildren() do
    local prompt = plot:FindFirstChild("BuyPrompt", true)
    if prompt and prompt:IsA("ProximityPrompt") then
        prompt.Triggered:Connect(function(player)
            local s = state[player.UserId]
            if not s or owners[plot] ~= player.UserId or s.owned or s.cash < PRICE then return end
            s.cash -= PRICE
            s.owned = true
        end)
    end
end
Players.PlayerAdded:Connect(function(player)
    state[player.UserId] = {cash = 50, owned = false}
    for _, plot in plots:GetChildren() do
        if owners[plot] == nil then owners[plot] = player.UserId; break end
    end
end)
task.spawn(function()
    while true do
        task.wait(2)
        for userId, s in state do
            if s.owned and Players:GetPlayerByUserId(userId) then s.cash += 5 end
        end
    end
end)
Players.PlayerRemoving:Connect(function(player)
    state[player.UserId] = nil
    for plot, owner in owners do if owner == player.UserId then owners[plot] = nil end end
end)
-- Add DataStore GetAsync/UpdateAsync around this state with pcall,
-- save on PlayerRemoving/BindToClose and autosave with a budget.
```
## Studio playtest checklist
- Two players receive distinct plots; other plot purchase denied; no duplicate buying; collector credits once; leave/rejoin restores cash and ownership after implementing persistence.
- Confirm Output has no errors; inspect DataStore retry/backoff, save on exit, and client UI separately if these are added to the skeleton.
