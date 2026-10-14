```luau
--!strict
-- Binary min-heap (priority queue). push and pop are O(log n), peek and size are O(1).
local Heap = {}
Heap.__index = Heap

export type Heap<T> = typeof(setmetatable({} :: { _items: { T }, _less: (T, T) -> boolean }, Heap))

local function defaultLess(a: any, b: any): boolean
	return a < b
end

function Heap.new<T>(less: ((T, T) -> boolean)?): Heap<T>
	return setmetatable({ _items = {} :: { T }, _less = (less or defaultLess) :: (T, T) -> boolean }, Heap)
end

function Heap.size<T>(self: Heap<T>): number
	return #self._items
end

function Heap.peek<T>(self: Heap<T>): T?
	return self._items[1]
end

function Heap.push<T>(self: Heap<T>, value: T)
	local items, less = self._items, self._less
	table.insert(items, value)
	local i = #items
	while i > 1 do
		local parent = i // 2
		if not less(items[i], items[parent]) then
			break
		end
		items[i], items[parent] = items[parent], items[i]
		i = parent
	end
end

function Heap.pop<T>(self: Heap<T>): T?
	local items, less = self._items, self._less
	local n = #items
	if n == 0 then
		return nil
	end
	local top = items[1]
	items[1] = items[n]
	items[n] = nil
	n -= 1
	local i = 1
	while true do
		local left, right, smallest = 2 * i, 2 * i + 1, i
		if left <= n and less(items[left], items[smallest]) then
			smallest = left
		end
		if right <= n and less(items[right], items[smallest]) then
			smallest = right
		end
		if smallest == i then
			break
		end
		items[i], items[smallest] = items[smallest], items[i]
		i = smallest
	end
	return top
end

return Heap
```
