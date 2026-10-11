A heap over `any` items, sorted with `table.sort` after every push.

```luau
--!strict
export type Heap = {
	push: (self: Heap, item: any) -> (),
	pop: (self: Heap) -> any?,
	peek: (self: Heap) -> any?,
	size: (self: Heap) -> number,
}

local Heap = {}

function Heap.new(less: (any, any) -> boolean): Heap
	local items: { any } = {}
	local self: Heap = {
		push = function(_: Heap, item: any)
			table.insert(items, item)
			table.sort(items, less)
		end,
		pop = function(_: Heap): any?
			return table.remove(items, 1)
		end,
		peek = function(_: Heap): any?
			return items[1]
		end,
		size = function(_: Heap): number
			return #items
		end,
	}
	return self
end

return Heap
```
