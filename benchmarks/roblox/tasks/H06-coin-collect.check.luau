local player, character, root = testPlayer()
local folder = waitFor(function() return ROOT:FindFirstChild("Coins", true) end, 10)
local stats = waitFor(function() return player:FindFirstChild("leaderstats") end, 10)
check("5 coins", function()
	expect(folder, "no Coins folder")
	local n = 0
	for _, coin in folder:GetChildren() do
		if coin.Name == "Coin" and coin:IsA("BasePart") and coin.Anchored and not coin.CanCollide then n += 1 end
	end
	expect(n == 5, "found " .. n .. " anchored non-colliding Coin parts")
end)
check("leaderstats Coins at 0", function()
	local coins = stats and stats:FindFirstChild("Coins")
	expect(coins and coins:IsA("IntValue") and coins.Value == 0, "Coins")
end)
check("touching collects each coin once", function()
	local coins = folder:GetChildren()
	for _, coin in coins do
		root.AssemblyLinearVelocity = Vector3.zero
		root.CFrame = CFrame.new(coin.Position)
		local gone = waitFor(function() return coin.Parent == nil end, 3)
		expect(gone, "a coin was not collected")
	end
	task.wait(0.5)
	local value = stats.Coins.Value
	expect(value == 5, "Coins = " .. value .. " after 5 coins")
end)
