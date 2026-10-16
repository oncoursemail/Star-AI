local M = {}
function M.groundBelow(position: Vector3, ignore: { Instance }): (BasePart?, number?)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore
	local result = workspace:Raycast(position, Vector3.new(0, -500, 0), params)
	if not result then return nil, nil end
	return result.Instance :: BasePart, (position - result.Position).Magnitude
end
return M
