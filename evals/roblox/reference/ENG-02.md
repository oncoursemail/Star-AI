Tests first (they fail against an empty stub, then pass once the function below exists). Paste both blocks into one script in the Studio command bar or a Script and run it; no output means every assert passed.

```luau
local function parseDuration(text)
	if type(text) ~= "string" then
		return nil
	end
	local s = text:gsub("^%s+", ""):gsub("%s+$", "")
	if s == "" then
		return nil
	end
	if s:match("^%d+$") then
		return tonumber(s)
	end
	local total, pos = 0, 1
	local multipliers = { h = 3600, m = 60, s = 1 }
	while pos <= #s do
		local n, unit, nextPos = s:match("^(%d+)([hms])%s*()", pos)
		if not n then
			return nil
		end
		total += tonumber(n) * multipliers[unit]
		pos = nextPos
	end
	return total
end

assert(parseDuration("1h30m") == 5400, "1h30m")
assert(parseDuration("45s") == 45, "45s")
assert(parseDuration("2m 10s") == 130, "2m 10s")
assert(parseDuration("90") == 90, "bare seconds")
assert(parseDuration("") == nil, "empty")
assert(parseDuration("abc") == nil, "letters")
assert(parseDuration("5x") == nil, "unknown unit")
return parseDuration
```
