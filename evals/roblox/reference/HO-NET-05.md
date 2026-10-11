Anything can arrive through a RemoteEvent, so the handler proves what it was given before it touches it: a real Instance, a Tool, owned by this player (inside their Backpack or Character), and the player must be alive.

```luau
--!strict
local Workspace = game:GetService("Workspace")

local Dropper = {}

function Dropper.handle(player: Player, tool: any): boolean
	if typeof(tool) ~= "Instance" then
		return false
	end
	if not tool:IsA("Tool") then
		return false
	end
	local character = player.Character
	local backpack = player:FindFirstChildOfClass("Backpack")
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if humanoid == nil or humanoid.Health <= 0 then
		return false
	end
	local ownedByBackpack = backpack ~= nil and tool:IsDescendantOf(backpack)
	local ownedByCharacter = character ~= nil and tool:IsDescendantOf(character)
	if not (ownedByBackpack or ownedByCharacter) then
		return false
	end
	tool.Parent = Workspace
	return true
end

return Dropper
```
