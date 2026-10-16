local Players = game:GetService("Players")
local function setup(player: Player)
	if player:FindFirstChild("leaderstats") then return end
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	for _, name in { "Coins", "Wins" } do
		local value = Instance.new("IntValue")
		value.Name = name
		value.Value = 0
		value.Parent = stats
	end
	stats.Parent = player
end
Players.PlayerAdded:Connect(setup)
for _, player in Players:GetPlayers() do
	setup(player)
end
