The root cause: the while loop stored `count = amount` (everything left) instead of `count = put` (what fits in one stack).

```luau
local function addItem(stacks, name, amount, maxStack)
	for i = 1, #stacks do
		local s = stacks[i]
		if s.name == name and s.count < maxStack then
			local room = maxStack - s.count
			local put = math.min(room, amount)
			s.count += put
			amount -= put
		end
	end
	while amount > 0 do
		local put = math.min(maxStack, amount)
		table.insert(stacks, { name = name, count = put })
		amount -= put
	end
	return stacks
end
return addItem
```
