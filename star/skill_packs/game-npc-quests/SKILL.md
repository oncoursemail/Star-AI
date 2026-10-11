---
name: game-npc-quests
description: Build Roblox NPC dialogue and server-tracked quests using ProximityPrompt, progress and rewards.
---
# game-npc-quests
## When to use
NPC conversation, quest acceptance, objectives, reward claiming.
## Server/client split
Client displays dialogue; server validates prompt proximity, quest steps, completion and one-time reward.
## Data model
quests[UserId]={status: new|active|ready|claimed,progress:number}; objective events must originate on server.
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
-- ServerScriptService/Quests.server.luau; workspace.QuestNPC.Prompt is ProximityPrompt
local Players = game:GetService("Players")
local npc = workspace:WaitForChild("QuestNPC")
local prompt = npc:WaitForChild("Prompt") :: ProximityPrompt
type Quest = {status: string, progress: number, coins: number}
local quests: {[number]: Quest} = {}
Players.PlayerAdded:Connect(function(player)
    quests[player.UserId] = {status = "new", progress = 0, coins = 0}
end)
prompt.Triggered:Connect(function(player)
    local s = quests[player.UserId]
    if not s then return end
    local character = player.Character
    local root = character and character:FindFirstChild("HumanoidRootPart")
    local anchor = prompt.Parent
    if not root or not root:IsA("BasePart") or not anchor:IsA("BasePart") then return end
    if (root.Position - anchor.Position).Magnitude > prompt.MaxActivationDistance + 3 then return end
    if s.status == "new" then
        s.status = "active"
    elseif s.status == "ready" then
        s.status = "claimed"; s.coins += 100
    end
end)
-- Call only from a server-authenticated objective completion handler:
local function progressQuest(player: Player)
    local s = quests[player.UserId]
    if not s or s.status ~= "active" then return end
    s.progress = math.min(3, s.progress + 1)
    if s.progress == 3 then s.status = "ready" end
end
Players.PlayerRemoving:Connect(function(player) quests[player.UserId] = nil end)
```
## Studio playtest checklist
- NPC starts quest; objective progress only from server; claim only after 3 completions; double-claim gives no extra reward; prompt spoofing and two-player isolation.
- Confirm Output has no errors; inspect DataStore retry/backoff, save on exit, and client UI separately if these are added to the skeleton.
