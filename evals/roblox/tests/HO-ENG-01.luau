-- Holdout test body HO-ENG-01 (frozen 2026-10-11; harness-owned, never shown to the model).
local Heap = load_answer({ debug = debugStub })
local function lessNum(a, b) return a < b end

local h = Heap.new(lessNum)
check("an empty heap: pop and peek give nil and size is 0", h:pop() == nil and h:peek() == nil and h:size() == 0)
for _, v in { 5, 3, 8, 1, 9, 2 } do h:push(v) end
check("size counts the pushed items", h:size() == 6)
check("peek shows the smallest and removes nothing", h:peek() == 1 and h:size() == 6)
local out = {}
while h:size() > 0 do table.insert(out, h:pop()) end
check("pop returns the items in ascending order", deepEqual(out, { 1, 2, 3, 5, 8, 9 }))
check("popping an empty heap again gives nil and size 0", h:pop() == nil and h:size() == 0)

local tasks = Heap.new(function(a, b) return a.priority < b.priority end)
for i = 1, 12 do tasks:push({ priority = i % 3, id = i }) end
local order = {}
while tasks:size() > 0 do
	local t = tasks:pop()
	table.insert(order, t.id)
end
check("items that compare equal come out in the order they were pushed", deepEqual(order, { 3, 6, 9, 12, 1, 4, 7, 10, 2, 5, 8, 11 }))

local rnd = lcg(42)
local items = {}
local big = Heap.new(lessNum)
for i = 1, 500 do
	local v = rnd(1000)
	items[i] = v
	big:push(v)
end
table.sort(items)
local popped = {}
for i = 1, 500 do popped[i] = big:pop() end
check("500 pseudo-random pushes come out sorted", deepEqual(popped, items) and big:size() == 0)

local pairsHeap = Heap.new(function(a, b) return a.key < b.key end)
local expected = {}
local rnd2 = lcg(7)
for i = 1, 200 do
	local entry = { key = rnd2(4), id = i }
	pairsHeap:push(entry)
	expected[i] = entry
end
table.sort(expected, function(a, b)
	if a.key ~= b.key then return a.key < b.key end
	return a.id < b.id
end)
local stable = true
for i = 1, 200 do
	local got = pairsHeap:pop()
	if got == nil or got.id ~= expected[i].id then stable = false end
end
check("200 items with only 4 distinct keys come out sorted by key and then by push order", stable)

local maxHeap = Heap.new(function(a, b) return a > b end)
maxHeap:push(3)
maxHeap:push(10)
maxHeap:push(7)
local first = maxHeap:pop()
maxHeap:push(12)
local second = maxHeap:pop()
local third = maxHeap:pop()
maxHeap:push(1)
local fourth = maxHeap:pop()
local fifth = maxHeap:pop()
check("pushes and pops can be interleaved (max-heap through the less function)",
	first == 10 and second == 12 and third == 7 and fourth == 3 and fifth == 1 and maxHeap:pop() == nil)

local byLength = Heap.new(function(a, b) return #a < #b end)
for _, word in { "pear", "fig", "banana", "kiwi", "plum", "date" } do byLength:push(word) end
local words = {}
while byLength:size() > 0 do table.insert(words, byLength:pop()) end
check("any comparison function works: words by length, ties in push order", deepEqual(words, { "fig", "pear", "kiwi", "plum", "date", "banana" }))

local a, b = Heap.new(lessNum), Heap.new(lessNum)
a:push(1)
b:push(2)
b:push(3)
check("two heaps do not share state", a:size() == 1 and b:size() == 2 and a:pop() == 1 and b:peek() == 2)

local falsy = Heap.new(function(x, y) return (x and 1 or 0) < (y and 1 or 0) end)
falsy:push(true)
falsy:push(false)
check("false is a legal item and sorts first here; size counts it", falsy:size() == 2 and falsy:pop() == false and falsy:pop() == true)
