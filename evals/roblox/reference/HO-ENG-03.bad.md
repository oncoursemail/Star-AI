Divide by the unit and print one decimal.

```luau
--!strict
local function abbreviate(n: number): string
	local sign = if n < 0 then "-" else ""
	local value = math.abs(n)
	if value >= 1e12 then
		return sign .. string.format("%.1fT", value / 1e12)
	elseif value >= 1e9 then
		return sign .. string.format("%.1fB", value / 1e9)
	elseif value >= 1e6 then
		return sign .. string.format("%.1fM", value / 1e6)
	elseif value >= 1e3 then
		return sign .. string.format("%.1fK", value / 1e3)
	end
	return sign .. tostring(math.floor(value))
end

return abbreviate
```
