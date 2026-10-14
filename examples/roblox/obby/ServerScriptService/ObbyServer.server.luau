--!strict
-- Place this Server Script and StageCore ModuleScript in ServerScriptService.
local Players = game:GetService("Players")
local StageCore = require(script.Parent:WaitForChild("StageCore"))

local checkpoints = workspace:WaitForChild("Checkpoints")
local killBricks = workspace:WaitForChild("KillBricks")
local finishPad = workspace:WaitForChild("Finish")
local parts = {}
local maximum = 0
for _, item in checkpoints:GetChildren() do
    if item:IsA("BasePart") then
        local stage = tonumber(item.Name)
        if stage and stage % 1 == 0 and stage >= 1 and stage <= 64 then
            assert(not parts[stage], "Duplicate checkpoint index")
            parts[stage] = item
            maximum = math.max(maximum, stage)
        end
    end
end
assert(maximum > 0, "Create at least one numbered checkpoint")
for index = 1, maximum do
    assert(parts[index], "Number checkpoints consecutively from 1")
end

local state = assert(StageCore.new(maximum))
local connected = {}

local function fromTouched(part)
    if not part or not part.Parent then return nil end
    local character = part:FindFirstAncestorOfClass("Model")
    if not character then return nil end
    return Players:GetPlayerFromCharacter(character), character
end

local function setupPlayer(player)
    if connected[player] then return end
    connected[player] = true

    local stats = Instance.new("Folder")
    stats.Name = "leaderstats"
    stats.Parent = player
    local stageValue = Instance.new("IntValue")
    stageValue.Name = "Stage"
    stageValue.Value = 0
    stageValue.Parent = stats
    local wins = Instance.new("IntValue")
    wins.Name = "Wins"
    wins.Parent = stats

    local function placeCharacter(character)
        local root = character:WaitForChild("HumanoidRootPart", 5)
        if player.Character ~= character or not root then return end
        local stage = StageCore.stage(state, player.UserId)
        local checkpoint = stage and parts[stage]
        if checkpoint then
            character:PivotTo(checkpoint.CFrame + Vector3.new(0, 5, 0))
        end
    end
    player.CharacterAdded:Connect(placeCharacter)
    if player.Character then placeCharacter(player.Character) end
end

for index, part in pairs(parts) do
    part.Touched:Connect(function(hit)
        local player = fromTouched(hit)
        if not player then return end
        local ok = StageCore.advance(state, player.UserId, index)
        if ok then
            local stats = player:FindFirstChild("leaderstats")
            local value = stats and stats:FindFirstChild("Stage")
            if value then value.Value = index end
        end
    end)
end

finishPad.Touched:Connect(function(hit)
    local player = fromTouched(hit)
    if not player then return end
    if StageCore.claimFinish(state, player.UserId) then
        local stats = player:FindFirstChild("leaderstats")
        local wins = stats and stats:FindFirstChild("Wins")
        if wins then wins.Value += 1 end
    end
end)

for _, brick in killBricks:GetChildren() do
    if brick:IsA("BasePart") then
        brick.Touched:Connect(function(hit)
            local player, character = fromTouched(hit)
            if not player or not character then return end
            local humanoid = character:FindFirstChildOfClass("Humanoid")
            if humanoid and StageCore.shouldKill(state, player.UserId, os.clock(), 0.75) then
                humanoid.Health = 0
            end
        end)
    end
end

Players.PlayerAdded:Connect(setupPlayer)
for _, player in Players:GetPlayers() do setupPlayer(player) end
Players.PlayerRemoving:Connect(function(player)
    connected[player] = nil
    StageCore.removePlayer(state, player.UserId)
end)
