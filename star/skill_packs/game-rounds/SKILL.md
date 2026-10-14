---
name: game-rounds
description: Build Roblox multiplayer round games with lobby, intermission, round phases, teleporting and winners.
---
# game-rounds
## When to use
Round-based survival, arena, minigames and lobby flow.
## Server/client split
Server controls round phases, eligibility, teleport and winners; client renders phase countdown.
## Data model
phase is Lobby|Intermission|Playing|Results; active[UserId] tracks participants; lobby and arena SpawnLocations configured.
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
-- ServerScriptService/Rounds.server.luau; workspace.LobbySpawn/ArenaSpawn are BaseParts
local Players = game:GetService("Players")
local lobby = workspace:WaitForChild("LobbySpawn") :: BasePart
local arena = workspace:WaitForChild("ArenaSpawn") :: BasePart
local phase = "Lobby"
local active: {[number]: boolean} = {}
local function teleport(player: Player, target: BasePart)
    local character = player.Character
    if character then character:PivotTo(target.CFrame * CFrame.new(0, 4, 0)) end
end
while true do
    phase = "Lobby"
    repeat task.wait(1) until #Players:GetPlayers() >= 2
    phase = "Intermission"; task.wait(10)
    active = {}
    for _, player in Players:GetPlayers() do
        if player.Character then
            active[player.UserId] = true
            teleport(player, arena)
        end
    end
    phase = "Playing"
    for _ = 1, 60 do
        task.wait(1)
        local alive = 0
        for userId in active do
            local p = Players:GetPlayerByUserId(userId)
            local h = p and p.Character and p.Character:FindFirstChildOfClass("Humanoid")
            if h and h.Health > 0 then alive += 1 else active[userId] = nil end
        end
        if alive <= 1 then break end
    end
    phase = "Results"
    local winnerId: number? = nil
    local survivors = 0
    for userId in active do
        survivors += 1
        winnerId = userId
    end
    if survivors == 1 and winnerId then
        local winner = Players:GetPlayerByUserId(winnerId)
        if winner then
            local wins = winner:FindFirstChild("leaderstats")
            local value = wins and wins:FindFirstChild("Wins")
            if value and value:IsA("IntValue") then value.Value += 1 end
        end
    end
    -- Create leaderstats/Wins on PlayerAdded; broadcast phase with RemoteEvent.
    task.wait(5)
    for _, player in Players:GetPlayers() do teleport(player, lobby) end
end
```
## Studio playtest checklist
- Test empty server, exactly two players, death, disconnect, late join, simultaneous eliminations; round never hangs; winner is unique or no winner.
- Confirm Output has no errors; inspect DataStore retry/backoff, save on exit, and client UI separately if these are added to the skeleton.
