The direction of a raycast is a displacement, not a heading: its length is how far the ray reaches. So the full vector from the eye to the target is passed, the viewer's own parts are excluded through the filter (on a copy, so the caller's list is not touched), and the target counts as seen when it is the first thing the ray hits.

```luau
--!strict
local Workspace = game:GetService("Workspace")

local Sight = {}

function Sight.canSee(eye: Vector3, target: BasePart, ignore: { Instance }?): boolean
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = if ignore ~= nil then table.clone(ignore) else {}

	local result = Workspace:Raycast(eye, target.Position - eye, params)
	return result == nil or result.Instance == target
end

return Sight
```
