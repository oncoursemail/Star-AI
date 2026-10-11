Luau has no `goto` and no integer bitwise operators; use `continue` and the `bit32` library, and `//` still exists for floor division.

```luau
local function pack(flags)
	local out = 0
	for i = 1, #flags do
		if not flags[i] then
			continue
		end
		out = bit32.bor(out, bit32.lshift(1, i - 1))
	end
	return out, out // 4, bit32.rshift(out, 1)
end
return pack
```
