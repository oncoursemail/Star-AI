local player = testPlayer()
local stats = waitFor(function() return player:FindFirstChild("leaderstats") end, 10)
check("leaderstats folder", function() expect(stats and stats:IsA("Folder"), "no leaderstats Folder") end)
check("Coins IntValue at 0", function()
	local coins = stats and stats:FindFirstChild("Coins")
	expect(coins and coins:IsA("IntValue") and coins.Value == 0, "Coins")
end)
check("Wins IntValue at 0", function()
	local wins = stats and stats:FindFirstChild("Wins")
	expect(wins and wins:IsA("IntValue") and wins.Value == 0, "Wins")
end)
check("only one leaderstats", function()
	task.wait(1)
	local n = 0
	for _, child in player:GetChildren() do
		if child.Name == "leaderstats" then n += 1 end
	end
	expect(n == 1, "found " .. n)
end)
