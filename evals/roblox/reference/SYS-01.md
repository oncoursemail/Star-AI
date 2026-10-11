```luau
--!strict
local SLOTS, MAX_STACK = 20, 99

type Slot = { itemId: string, count: number }
local inventories: { [any]: { [number]: Slot } } = {}

local InventoryService = {}

local function inventoryOf(player: any): { [number]: Slot }
	local inv = inventories[player]
	if not inv then
		inv = {}
		inventories[player] = inv
	end
	return inv
end

local function isSlot(x: any): boolean
	return type(x) == "number" and x == x and x >= 1 and x <= SLOTS and x == math.floor(x)
end

function InventoryService.Give(player: any, itemId: string, count: number): boolean
	if type(itemId) ~= "string" or itemId == "" or type(count) ~= "number" or count < 1 or count ~= math.floor(count) then
		return false
	end
	local inv = inventoryOf(player)
	local remaining = count
	for i = 1, SLOTS do
		local slot = inv[i]
		if slot and slot.itemId == itemId and slot.count < MAX_STACK then
			local add = math.min(MAX_STACK - slot.count, remaining)
			slot.count += add
			remaining -= add
		end
	end
	for i = 1, SLOTS do
		if remaining <= 0 then
			break
		end
		if inv[i] == nil then
			local add = math.min(MAX_STACK, remaining)
			inv[i] = { itemId = itemId, count = add }
			remaining -= add
		end
	end
	return remaining <= 0
end

function InventoryService.MoveItem(player: any, fromSlot: any, toSlot: any): (boolean, string?)
	if not isSlot(fromSlot) or not isSlot(toSlot) then
		return false, "slots must be integers from 1 to 20"
	end
	if fromSlot == toSlot then
		return false, "slots must differ"
	end
	local inv = inventoryOf(player)
	local src, dst = inv[fromSlot], inv[toSlot]
	if src == nil then
		return false, "source slot is empty"
	end
	if dst == nil then
		inv[toSlot], inv[fromSlot] = src, nil
	elseif dst.itemId == src.itemId then
		local moved = math.min(MAX_STACK - dst.count, src.count)
		dst.count += moved
		src.count -= moved
		if src.count <= 0 then
			inv[fromSlot] = nil
		end
	else
		inv[toSlot], inv[fromSlot] = src, dst
	end
	return true, nil
end

function InventoryService.GetSnapshot(player: any): { [number]: Slot }
	local copy = {}
	for i, slot in pairs(inventoryOf(player)) do
		copy[i] = { itemId = slot.itemId, count = slot.count }
	end
	return copy
end

return InventoryService
```
