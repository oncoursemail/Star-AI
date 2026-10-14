The number is rounded in the unit it will be shown in; if that rounding reaches 1000 the next suffix is tried instead (so 999999 becomes `1M`, not `1000K`). The top suffix has nowhere to carry to. The sign is added after rounding, so a negative that rounds to zero prints `0`.

```luau
--!strict
local SUFFIXES = { "", "K", "M", "B", "T" }

local function abbreviate(n: number): string
	if type(n) ~= "number" or n ~= n or n == math.huge or n == -math.huge then
		error("abbreviate needs a finite number")
	end
	local magnitude = math.abs(n)
	local index = 1
	local rounded = 0
	while true do
		local scaled = magnitude / (1000 ^ (index - 1))
		if index == 1 then
			rounded = math.floor(scaled + 0.5)
		else
			rounded = math.floor(scaled * 10 + 0.5) / 10
		end
		if rounded >= 1000 and index < #SUFFIXES then
			index += 1
		else
			break
		end
	end

	local text: string
	if rounded == math.floor(rounded) then
		text = string.format("%d", rounded)
	else
		text = string.format("%.1f", rounded)
	end
	local sign = if n < 0 and rounded > 0 then "-" else ""
	return sign .. text .. SUFFIXES[index]
end

return abbreviate
```
