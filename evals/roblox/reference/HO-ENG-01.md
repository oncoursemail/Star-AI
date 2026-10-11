A binary min-heap in a plain array. To make equal items leave in push order, every entry carries an increasing sequence number and the ordering is `(item, sequence)`: `less` is asked in both directions, and only a real tie falls back to the sequence number. The object is a table of typed closures, so `Heap<number>` and `Heap<string>` are different types and a string cannot be pushed on a numeric heap.

```luau
--!strict
export type Heap<T> = {
	push: (self: Heap<T>, item: T) -> (),
	pop: (self: Heap<T>) -> T?,
	peek: (self: Heap<T>) -> T?,
	size: (self: Heap<T>) -> number,
}

type Entry<T> = { item: T, seq: number }

local Heap = {}

function Heap.new<T>(less: (T, T) -> boolean): Heap<T>
	local entries: { Entry<T> } = {}
	local counter = 0

	local function before(a: Entry<T>, b: Entry<T>): boolean
		if less(a.item, b.item) then
			return true
		end
		if less(b.item, a.item) then
			return false
		end
		return a.seq < b.seq
	end

	local function swap(i: number, j: number)
		entries[i], entries[j] = entries[j], entries[i]
	end

	local function siftUp(start: number)
		local i = start
		while i > 1 do
			local parent = i // 2
			if before(entries[i], entries[parent]) then
				swap(i, parent)
				i = parent
			else
				break
			end
		end
	end

	local function siftDown(start: number)
		local i = start
		local n = #entries
		while true do
			local left, right = i * 2, i * 2 + 1
			local best = i
			if left <= n and before(entries[left], entries[best]) then
				best = left
			end
			if right <= n and before(entries[right], entries[best]) then
				best = right
			end
			if best == i then
				break
			end
			swap(i, best)
			i = best
		end
	end

	local self: Heap<T> = {
		push = function(_: Heap<T>, item: T)
			counter += 1
			table.insert(entries, { item = item, seq = counter })
			siftUp(#entries)
		end,
		pop = function(_: Heap<T>): T?
			local n = #entries
			if n == 0 then
				return nil
			end
			local top = entries[1]
			entries[1] = entries[n]
			entries[n] = nil
			if n > 1 then
				siftDown(1)
			end
			return top.item
		end,
		peek = function(_: Heap<T>): T?
			local top = entries[1]
			if top == nil then
				return nil
			end
			return top.item
		end,
		size = function(_: Heap<T>): number
			return #entries
		end,
	}
	return self
end

return Heap
```
