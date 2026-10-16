local M = {}
local function copy(value)
	if type(value) ~= "table" then return value end
	local out = {}
	for k, v in value do out[k] = copy(v) end
	return out
end
function M.reconcile(data, template)
	local out = copy(data)
	for key, value in template do
		if out[key] == nil then
			out[key] = copy(value)
		elseif type(out[key]) == "table" and type(value) == "table" then
			out[key] = M.reconcile(out[key], value)
		end
	end
	return out
end
return M
