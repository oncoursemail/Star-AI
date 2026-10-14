Here is the Inventory module.

```luau
--!strict
export type Inventory = { [string]: number }

local Inventory = {}

function Inventory.new(): Inventory
	return {}
end

function Inventory.add(inv: Inventory, itemId: string, count: number): ()
	if count ~= math.floor(count) or count <= 0 or count == math.huge then
		error("count must be a positive integer")
	end
	inv[itemId] = (inv[itemId] or 0) + count
end

function Inventory.remove(inv: Inventory, itemId: string, count: number): boolean
	local held = inv[itemId] or 0
	if held < count then
		return false
	end
	if held == count then
		inv[itemId] = nil
	else
		inv[itemId] = held - count
	end
	return true
end

function Inventory.count(inv: Inventory, itemId: string): number
	return inv[itemId] or 0
end

return Inventory
```
