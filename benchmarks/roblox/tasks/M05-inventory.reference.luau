local Inventory = {}
Inventory.__index = Inventory
function Inventory.new(maxStack: number, slots: number)
	local self = setmetatable({ maxStack = maxStack, slots = {} }, Inventory)
	for i = 1, slots do self.slots[i] = { item = nil, n = 0 } end
	return self
end
function Inventory:add(item: string, n: number): number
	local left = n
	for _, slot in self.slots do
		if slot.item == item and left > 0 then
			local put = math.min(left, self.maxStack - slot.n)
			slot.n += put
			left -= put
		end
	end
	for _, slot in self.slots do
		if slot.item == nil and left > 0 then
			local put = math.min(left, self.maxStack)
			slot.item, slot.n = item, put
			left -= put
		end
	end
	return n - left
end
function Inventory:count(item: string): number
	local total = 0
	for _, slot in self.slots do
		if slot.item == item then total += slot.n end
	end
	return total
end
function Inventory:remove(item: string, n: number): boolean
	if self:count(item) < n then return false end
	local left = n
	for i = #self.slots, 1, -1 do
		local slot = self.slots[i]
		if slot.item == item and left > 0 then
			local take = math.min(left, slot.n)
			slot.n -= take
			left -= take
			if slot.n == 0 then slot.item = nil end
		end
	end
	return true
end
return Inventory
