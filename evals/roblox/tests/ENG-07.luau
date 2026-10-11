local ret, env = load_answer()
local median = resolve(ret, env, "median")
check("the median of an odd list", median({ 3, 1, 2 }) == 2)
check("the median of an even list is the mean of the middle two", median({ 4, 1, 3, 2 }) == 2.5)
check("the median of an empty list is nil", median({}) == nil)
local input = { 3, 1, 2 }
median(input)
check("the caller's list keeps its order", deepEqual(input, { 3, 1, 2 }))
check("a single value", median({ 5 }) == 5)
check("duplicates and negatives", median({ 2, 2, 2, 2 }) == 2 and median({ -5, -1, -3 }) == -3)
local big = {}
for i = 1, 101 do big[i] = (i * 37) % 101 end
check("a longer unsorted list", median(big) == 50)
