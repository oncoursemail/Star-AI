```luau
--!strict
-- Looks like a priority queue but pop scans the whole list: O(n) per pop.
local Heap = {}
Heap.__index = Heap

function Heap.new(less: ((any, any) -> boolean)?)
	return setmetatable({ _items = {} :: { any }, _less = less or function(a: any, b: any): boolean return a < b end }, Heap)
end

function Heap:size(): number
	return #self._items
end

function Heap:peek(): any
	local best = nil
	for _, v in self._items do
		if best == nil or self._less(v, best) then best = v end
	end
	return best
end

function Heap:push(value: any)
	table.insert(self._items, value)
end

function Heap:pop(): any
	local bestIndex = nil
	for i, v in self._items do
		if bestIndex == nil or self._less(v, self._items[bestIndex]) then bestIndex = i end
	end
	if bestIndex == nil then return nil end
	return table.remove(self._items, bestIndex)
end

return Heap
```
