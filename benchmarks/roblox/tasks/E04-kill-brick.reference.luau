local brick = Instance.new("Part")
brick.Name = "KillBrick"
brick.Size = Vector3.new(8, 1, 8)
brick.Position = Vector3.new(0, 40, 300)
brick.Anchored = true
brick.Color = Color3.fromRGB(255, 0, 0)
brick.Touched:Connect(function(hit)
	local humanoid = hit.Parent and hit.Parent:FindFirstChildOfClass("Humanoid")
	if humanoid then
		humanoid.Health = 0
	end
end)
brick.Parent = script.Parent
