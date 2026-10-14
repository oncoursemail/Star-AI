The profile and its level are optional, so refine both before using them.

```luau
--!strict
type Profile = { name: string, level: number? }
local function describe(p: Profile?): string
	if p == nil then
		return "unknown"
	end
	local level = p.level or 0
	return p.name .. " (level " .. (level + 1) .. ")"
end
return describe
```
