Tests first (they fail against an empty stub, then pass once `chunk` exists). Paste both into one script and run it; no output means every assert passed.

```luau
local function chunk(list, size)
	if type(size) ~= "number" or size < 1 or size % 1 ~= 0 then
		error("size must be a positive integer")
	end
	local out = {}
	for i = 1, #list do
		local bucket = math.ceil(i / size)
		out[bucket] = out[bucket] or {}
		table.insert(out[bucket], list[i])
	end
	return out
end

local function same(a, b)
	if #a ~= #b then return false end
	for i = 1, #a do
		if #a[i] ~= #b[i] then return false end
		for j = 1, #a[i] do
			if a[i][j] ~= b[i][j] then return false end
		end
	end
	return true
end
assert(same(chunk({ 1, 2, 3, 4, 5 }, 2), { { 1, 2 }, { 3, 4 }, { 5 } }), "uneven")
assert(same(chunk({}, 3), {}), "empty")
assert(same(chunk({ 1, 2 }, 5), { { 1, 2 } }), "size larger than the list")
assert(not pcall(chunk, { 1 }, 0), "size 0")
assert(not pcall(chunk, { 1 }, 2.5), "fractional size")
local input = { 1, 2, 3 }
chunk(input, 2)
assert(#input == 3 and input[1] == 1, "input untouched")
return chunk
```
