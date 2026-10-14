```luau
--!strict
local function trim(s: string): string
	return (string.gsub(s, "^%s*(.-)%s*$", "%1"))
end

local function parseKV(s: string): { [string]: string }
	local out: { [string]: string } = {}
	for segment in string.gmatch(s, "[^;]+") do
		local eq = string.find(segment, "=", 1, true)
		if eq then
			local key = trim(string.sub(segment, 1, eq - 1))
			if key ~= "" then
				out[key] = trim(string.sub(segment, eq + 1))
			end
		end
	end
	return out
end

return parseKV
```
