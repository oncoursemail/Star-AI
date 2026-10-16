local M = {}
function M.encode(value)
	local kind = typeof(value)
	-- Tagged values keep their numbers in a separate array: a table with both string keys and array items
	-- does not survive JSONEncode (the array items come back under string keys).
	if kind == "Vector3" then
		return { __t = "V3", v = { value.X, value.Y, value.Z } }
	elseif kind == "CFrame" then
		return { __t = "CF", v = { value:GetComponents() } }
	elseif kind == "Color3" then
		return { __t = "C3", v = { value.R, value.G, value.B } }
	elseif kind == "table" then
		local out = {}
		for k, v in value do out[k] = M.encode(v) end
		return out
	end
	return value
end
function M.decode(value)
	if type(value) ~= "table" then return value end
	local v = value.v
	if value.__t == "V3" then return Vector3.new(v[1], v[2], v[3]) end
	if value.__t == "CF" then return CFrame.new(table.unpack(v, 1, 12)) end
	if value.__t == "C3" then return Color3.new(v[1], v[2], v[3]) end
	local out = {}
	for k, v in value do out[k] = M.decode(v) end
	return out
end
return M
