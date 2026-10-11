--!strict
-- Validate server-observed character contacts, not names/IDs reported by the client.
local Players = game:GetService("Players")

local TouchValidation = {}

function TouchValidation.playerNear(hit: BasePart, target: BasePart, margin: number): Player?
	local character = hit:FindFirstAncestorOfClass("Model")
	if not character then
		return nil
	end
	local player = Players:GetPlayerFromCharacter(character)
	if not player or player.Character ~= character then
		return nil
	end
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	local root = character:FindFirstChild("HumanoidRootPart")
	if not humanoid or humanoid.Health <= 0 or not root or not root:IsA("BasePart") then
		return nil
	end

	-- A distance to the target's bounds also works for the large lava floor.
	local offset = root.Position - target.Position
	local outside = Vector3.new(
		math.max(math.abs(offset.X) - target.Size.X / 2, 0),
		math.max(math.abs(offset.Y) - target.Size.Y / 2, 0),
		math.max(math.abs(offset.Z) - target.Size.Z / 2, 0)
	)
	if outside.Magnitude > margin then
		return nil
	end
	return player
end

return TouchValidation
