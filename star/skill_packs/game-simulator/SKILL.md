---
name: game-simulator
description: Build Roblox clicker and tool simulators with currency, upgrades, rebirth and leaderstats.
---
# game-simulator
## When to use
Click-to-earn, tool-act-to-earn, rebirth and upgrade loops.
## Server/client split
Client sends only action IDs; server gates action rates, computes earnings and costs; leaderstats are replicated display.
## Data model
state[UserId]={coins,power,rebirths,lastAction}; leaderstats mirrors server values, never a source of truth.
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
-- ServerScriptService/Simulator.server.luau; ReplicatedStorage.Action is RemoteEvent
local Players = game:GetService("Players")
local event = game:GetService("ReplicatedStorage"):WaitForChild("Action") :: RemoteEvent
type State = {coins: number, power: number, rebirths: number, last: number}
local data: {[number]: State} = {}
Players.PlayerAdded:Connect(function(player)
    local stats = Instance.new("Folder"); stats.Name = "leaderstats"; stats.Parent = player
    local coins = Instance.new("IntValue"); coins.Name = "Coins"; coins.Parent = stats
    data[player.UserId] = {coins = 0, power = 1, rebirths = 0, last = 0}
end)
event.OnServerEvent:Connect(function(player, action)
    if type(action) ~= "string" then return end
    local s = data[player.UserId]; if not s then return end
    if action == "click" then
        if os.clock() - s.last < 0.15 then return end
        s.last = os.clock(); s.coins += s.power * (s.rebirths + 1)
    elseif action == "upgrade" then
        local cost = s.power * 10
        if s.coins < cost then return end
        s.coins -= cost; s.power += 1
    elseif action == "rebirth" then
        if s.coins < 1000 then return end
        s.coins = 0; s.power = 1; s.rebirths += 1
    else return end
    local stats = player:FindFirstChild("leaderstats")
    local v = stats and stats:FindFirstChild("Coins")
    if v and v:IsA("IntValue") then v.Value = s.coins end
end)
Players.PlayerRemoving:Connect(function(player) data[player.UserId] = nil end)
```
## Studio playtest checklist
- Spam 100 clicks cannot exceed server rate; fake currencies ignored; upgrades deduct exactly once; rebirth resets correctly; two leaderboards isolated.
- Confirm Output has no errors; inspect DataStore retry/backoff, save on exit, and client UI separately if these are added to the skeleton.
