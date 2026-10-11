```luau
--!strict
export type Inventory = { [string]: number }
local Inventory = {}
function Inventory.new(): Inventory return {} end
function Inventory.add(inv: Inventory, itemId: string, count: number): ()
	inv[itemId] = (inv[itemId] or 0) + count
end
function Inventory.remove(inv: Inventory, itemId: string, count: number): boolean
	inv[itemId] = (inv[itemId] or 0) - count
	return true
end
function Inventory.count(inv: Inventory, itemId: string): number
	return inv[itemId] or 0
end
return Inventory
```
