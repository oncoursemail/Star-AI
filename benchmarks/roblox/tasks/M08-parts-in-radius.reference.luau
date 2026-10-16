local M = {}
function M.partsInRadius(center: Vector3, radius: number, exclude: { Instance }?): { BasePart }
	local params = OverlapParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = exclude or {}
	local parts = workspace:GetPartBoundsInRadius(center, radius, params)
	table.sort(parts, function(x, y)
		return (x.Position - center).Magnitude < (y.Position - center).Magnitude
	end)
	return parts
end
return M
