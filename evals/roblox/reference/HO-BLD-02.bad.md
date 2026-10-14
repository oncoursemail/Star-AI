Cast a ray from the eye toward the target and see what it hits.

```luau
local Sight = {}

function Sight.canSee(eye: Vector3, target: BasePart, ignore: { Instance }?): boolean
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	local list = ignore or {}
	table.insert(list, target.Parent)
	params.FilterDescendantsInstances = list

	local direction = (target.Position - eye).Unit
	local result = workspace:Raycast(eye, direction, params)
	return result == nil or result.Instance == target
end

return Sight
```
