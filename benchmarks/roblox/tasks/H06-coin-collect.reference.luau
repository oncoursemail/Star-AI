local Players = game:GetService("Players")
local function setup(player)
	if player:FindFirstChild("leaderstats") then return end
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Parent = stats
	stats.Parent = player
end
Players.PlayerAdded:Connect(setup)
for _, player in Players:GetPlayers() do setup(player) end
local folder = Instance.new("Folder")
folder.Name = "Coins"
folder.Parent = script.Parent
for i = 1, 5 do
	local coin = Instance.new("Part")
	coin.Name = "Coin"
	coin.Anchored = true
	coin.CanCollide = false
	coin.Size = Vector3.new(2, 2, 2)
	coin.Position = Vector3.new(400 + 10 * i, 50, 400)
	coin.Parent = folder
	local taken = false
	coin.Touched:Connect(function(hit)
		if taken then return end
		local player = Players:GetPlayerFromCharacter(hit.Parent)
		local stats = player and player:FindFirstChild("leaderstats")
		if not stats then return end
		taken = true
		stats.Coins.Value += 1
		coin:Destroy()
	end)
end
