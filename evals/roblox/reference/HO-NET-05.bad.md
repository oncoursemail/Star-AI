The handler checks where the tool sits and drops it.

```luau
local Dropper = {}

function Dropper.handle(player: Player, tool: any): boolean
	if tool.Parent == player.Backpack or tool.Parent == player.Character then
		tool.Parent = workspace
		return true
	end
	return false
end

return Dropper
```
