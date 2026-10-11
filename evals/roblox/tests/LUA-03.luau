local ListUtil = load_answer()
local nums = { 1, 2, 3, 4 }
local doubled = ListUtil.map(nums, function(x) return x * 2 end)
check("map doubles", deepEqual(doubled, { 2, 4, 6, 8 }))
check("filter keeps evens", deepEqual(ListUtil.filter(nums, function(x) return x % 2 == 0 end), { 2, 4 }))
check("find returns the match", ListUtil.find({ "a", "b" }, function(s) return s == "b" end) == "b")
check("find returns nil without a match", ListUtil.find({ "a", "b" }, function(s) return s == "z" end) == nil)
check("the input list is unchanged", deepEqual(nums, { 1, 2, 3, 4 }))
