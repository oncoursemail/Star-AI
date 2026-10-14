local ret, env = load_answer()
local Heap = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.Heap) or env.Heap
check("the module returns a Heap class with new()", type(Heap) == "table" and type(Heap.new) == "function")

local h = Heap.new()
check("an empty heap pops nil, peeks nil and has size 0", h:pop() == nil and h:peek() == nil and h:size() == 0)

local rand = lcg(7)
local values = {}
for i = 1, 200 do
	local v = rand(1000)
	values[i] = v
	h:push(v)
end
check("size counts every push", h:size() == 200)
table.sort(values)
check("peek returns the smallest without removing it", h:peek() == values[1] and h:size() == 200)
local sorted, ok = {}, true
for i = 1, 200 do
	sorted[i] = h:pop()
end
check("popping everything returns the values in ascending order, duplicates included", deepEqual(sorted, values))
check("the heap is empty again", h:size() == 0 and h:pop() == nil)

local maxHeap = Heap.new(function(a, b) return a > b end)
for _, v in { 5, 1, 9, 3, 9, 7 } do maxHeap:push(v) end
check("a custom comparator makes a max-heap", maxHeap:pop() == 9 and maxHeap:pop() == 9 and maxHeap:pop() == 7)

local records = Heap.new(function(a, b) return a.cost < b.cost end)
records:push({ cost = 3, id = "c" })
records:push({ cost = 1, id = "a" })
records:push({ cost = 2, id = "b" })
check("the comparator works on tables (an A* open set)", records:pop().id == "a" and records:pop().id == "b")

-- Interleaved pushes and pops against a simple reference.
local mixed, ref, match = Heap.new(), {}, true
local r2 = lcg(99)
for _ = 1, 500 do
	if r2(3) == 1 and #ref > 0 then
		table.sort(ref)
		local expect = table.remove(ref, 1)
		if mixed:pop() ~= expect then match = false end
	else
		local v = r2(50)
		mixed:push(v)
		table.insert(ref, v)
	end
end
check("interleaved pushes and pops always return the current minimum", match and mixed:size() == #ref)

-- Push and pop must be O(log n): count comparator calls for 1024 pushes and 1024 pops.
local calls = 0
local counted = Heap.new(function(a, b)
	calls += 1
	return a < b
end)
local r3 = lcg(3)
for _ = 1, 1024 do counted:push(r3(100000)) end
local last, ordered = -math.huge, true
for _ = 1, 1024 do
	local v = counted:pop()
	if v < last then ordered = false end
	last = v
end
check("1024 pushes and pops stay ordered", ordered)
check("1024 pushes and pops use fewer than 60000 comparisons (O(log n) each)", calls > 0 and calls < 60000)
