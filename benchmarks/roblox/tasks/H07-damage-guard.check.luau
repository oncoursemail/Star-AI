local DamageGuard = solution()
local player, character, root = testPlayer()
root.Anchored = true
local function dummy(offset)
	local model = Instance.new("Model")
	local hrp = Instance.new("Part")
	hrp.Name = "HumanoidRootPart"
	hrp.Anchored = true
	hrp.Position = root.Position + offset
	hrp.Parent = model
	model.PrimaryPart = hrp
	Instance.new("Humanoid").Parent = model
	model.Parent = ROOT
	return model
end
local nearby = dummy(Vector3.new(6, 0, 0))
local faraway = dummy(Vector3.new(40, 0, 0))
local guard = DamageGuard.new()
check("allows a valid hit", function() expect(guard:allow(player, nearby, 10, 100) == true, "refused a valid hit") end)
check("rate limit per player", function()
	expect(guard:allow(player, nearby, 10, 100.2) == false, "allowed 0.2 s later")
	expect(guard:allow(player, nearby, 10, 100.6) == true, "refused 0.6 s later")
end)
check("bad amounts", function()
	for _, amount in { 0, -5, 26, 1 / 0, 0 / 0, "10", nil } do
		local ok, result = pcall(function() return guard:allow(player, nearby, amount, 200) end)
		expect(ok and result == false, "amount " .. tostring(amount))
	end
end)
check("bad targets", function()
	for _, target in { faraway, character, workspace, "x", nil, Instance.new("Model") } do
		local ok, result = pcall(function() return guard:allow(player, target, 5, 300) end)
		expect(ok and result == false, "target " .. tostring(target))
	end
end)
check("refusals do not use up the rate limit", function()
	expect(guard:allow(player, nearby, 5, 300.1) == true, "valid hit after refusals was refused")
end)
check("dead target", function()
	nearby:FindFirstChildOfClass("Humanoid").Health = 0
	expect(guard:allow(player, nearby, 5, 400) == false, "allowed on a dead target")
end)
root.Anchored = false
