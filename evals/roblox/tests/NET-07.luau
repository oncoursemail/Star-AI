local V = load_answer()
check("integer accepts an in-range integer", V.integer(5, 1, 10) == 5 and V.integer(10, 1, 10) == 10 and V.integer(1, 1, 10) == 1)
check("integer rejects fractions, NaN, infinity, strings and out-of-range values",
	V.integer(5.5, 1, 10) == nil and V.integer(0 / 0, 1, 10) == nil and V.integer(math.huge, 1, math.huge) == nil
	and V.integer("5", 1, 10) == nil and V.integer(11, 1, 10) == nil and V.integer(-1, 0, 10) == nil)
check("number accepts finite numbers in range and rejects NaN, infinity and non-numbers",
	V.number(0.5, 0, 1) == 0.5 and V.number(0 / 0, 0, 1) == nil and V.number(math.huge, 0, math.huge) == nil
	and V.number({}, 0, 1) == nil and V.number(2, 0, 1) == nil)
check("string accepts 1..maxLength printable bytes", V.string("abc", 5) == "abc" and V.string("abcde", 5) == "abcde")
check("string rejects empty, too long, control characters and non-strings",
	V.string("", 5) == nil and V.string("abcdef", 5) == nil and V.string("a\nb", 5) == nil
	and V.string("a\127b", 5) == nil and V.string(5, 5) == nil and V.string(nil, 5) == nil)
check("oneOf accepts only keys that are true", V.oneOf("sword", { sword = true }) == "sword"
	and V.oneOf("sword", { sword = false }) == nil and V.oneOf("gold", { sword = true }) == nil)
check("oneOf rejects non-strings", V.oneOf(5, { ["5"] = true }) == nil and V.oneOf({}, { sword = true }) == nil)
local weird = { nil, true, false, 0, -1, 1e308, 0 / 0, math.huge, "", "x", {}, function() end, coroutine.create(function() end) }
local threw = false
for i = 1, 13 do
	local x = weird[i]
	for _, fn in { function() return V.integer(x, 0, 10) end, function() return V.number(x, 0, 10) end,
		function() return V.string(x, 10) end, function() return V.oneOf(x, { a = true }) end } do
		if not pcall(fn) then threw = true end
	end
end
check("no function throws for any input", not threw)
