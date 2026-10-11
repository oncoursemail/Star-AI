An event-driven ProximityPrompt-free approach: query the area around the door on a short interval instead of every frame.

```luau
local Players = game:GetService("Players")
local params = OverlapParams.new()
params.FilterType = Enum.RaycastFilterType.Include

while true do
	local characters = {}
	for _, plr in Players:GetPlayers() do
		if plr.Character then
			table.insert(characters, plr.Character)
		end
	end
	params.FilterDescendantsInstances = characters
	local near = #workspace:GetPartBoundsInRadius(door.Position, 10, params) > 0
	door.Transparency = near and 0.5 or 0
	task.wait(0.25)
end
```
