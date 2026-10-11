---
name: game-obby
description: Build Roblox obby games with ordered stages, checkpoints, kill bricks and respawning.
---
# game-obby
## When to use
Obstacle courses, stage progression, checkpoint spawn and hazards.
## Server/client split
Server owns stage and kills; client owns stage HUD and cosmetic feedback.
## Data model
Workspace.Checkpoints has numbered BaseParts; Workspace.KillBricks contains hazards; stageByUserId[UserId] is the last valid stage. Persist stage only if required.
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
-- ServerScriptService/Obby.server.luau
local Players = game:GetService("Players")
local checkpoints = workspace:WaitForChild("Checkpoints")
local hazards = workspace:WaitForChild("KillBricks")
local stages: {[number]: number} = {}
local parts: {[number]: BasePart} = {}
for _, child in checkpoints:GetChildren() do
    local n = tonumber(child.Name)
    if n and n >= 1 and n % 1 == 0 and child:IsA("BasePart") then
        parts[n] = child
        child.Touched:Connect(function(hit)
            local character = hit:FindFirstAncestorOfClass("Model")
            local player = character and Players:GetPlayerFromCharacter(character)
            if player and n == (stages[player.UserId] or 0) + 1 then
                stages[player.UserId] = n
            end
        end)
    end
end
for _, hazard in hazards:GetChildren() do
    if hazard:IsA("BasePart") then
        hazard.Touched:Connect(function(hit)
            local character = hit:FindFirstAncestorOfClass("Model")
            local humanoid = character and character:FindFirstChildOfClass("Humanoid")
            if humanoid then humanoid.Health = 0 end
        end)
    end
end
Players.PlayerAdded:Connect(function(player)
    stages[player.UserId] = 0
    player.CharacterAdded:Connect(function(character)
        local root = character:WaitForChild("HumanoidRootPart", 10)
        local part = parts[stages[player.UserId] or 0]
        if root and part then character:PivotTo(part.CFrame * CFrame.new(0, 4, 0)) end
    end)
end)
Players.PlayerRemoving:Connect(function(player) stages[player.UserId] = nil end)
```
## Studio playtest checklist
- Touch an out-of-order checkpoint, die twice, respawn at last valid checkpoint; hazard kills only humanoids; verify two players advance independently.
- Confirm Output has no errors; inspect DataStore retry/backoff, save on exit, and client UI separately if these are added to the skeleton.
