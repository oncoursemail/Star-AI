```luau
local map = workspace:WaitForChild("Map", 10)
if map then
	local building = map:WaitForChild("Building", 10)
	local door = building and building:WaitForChild("Door", 10)
	if door then
		door.Touched:Connect(function()
			print("touched")
		end)
	end
	map.ChildAdded:Connect(function(child)
		print("streamed in", child.Name)
	end)
	map.ChildRemoved:Connect(function(child)
		print("streamed out", child.Name)
	end)
end
```

Server side, make the boss model always present so the client can rely on it:

```luau
local boss = workspace.Map.Boss
boss.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
```
