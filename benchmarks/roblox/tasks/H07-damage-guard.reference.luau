local DamageGuard = {}
DamageGuard.__index = DamageGuard
function DamageGuard.new()
	return setmetatable({ last = {} }, DamageGuard)
end
function DamageGuard:allow(player: Player, target: any, amount: any, now: number): boolean
	if type(amount) ~= "number" or amount ~= amount or amount <= 0 or amount > 25 then return false end
	if typeof(target) ~= "Instance" or not target:IsA("Model") or target == player.Character then return false end
	local humanoid = target:FindFirstChildOfClass("Humanoid")
	if not humanoid or humanoid.Health <= 0 then return false end
	local part = target.PrimaryPart or target:FindFirstChild("HumanoidRootPart")
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if not part or not root or (part.Position - root.Position).Magnitude > 15 then return false end
	local last = self.last[player]
	if last and now - last < 0.5 then return false end
	self.last[player] = now
	return true
end
return DamageGuard
