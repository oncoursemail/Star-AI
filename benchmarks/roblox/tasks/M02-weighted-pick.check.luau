local M = solution()
check("proportional and never zero weight", function()
	local rng = Random.new(12345)
	local counts = { a = 0, b = 0, c = 0 }
	for _ = 1, 20000 do
		local key = M.pick({ a = 1, b = 3, c = 0 }, rng)
		expect(counts[key] ~= nil, "unknown key " .. tostring(key))
		counts[key] += 1
	end
	expect(counts.c == 0, "zero-weight key chosen " .. counts.c .. " times")
	local share = counts.b / 20000
	expect(share > 0.72 and share < 0.78, string.format("b share %.3f, expected 0.75", share))
end)
check("single key", function()
	expect(M.pick({ only = 5 }, Random.new(1)) == "only", "single key")
end)
check("uses the given rng (same seed, same picks)", function()
	local a, b = Random.new(7), Random.new(7)
	for _ = 1, 50 do
		local w = { x = 1, y = 1, z = 1 }
		expect(M.pick(w, a) == M.pick(w, b), "differs with the same seed")
	end
end)
check("errors on total 0", function()
	expect(not pcall(M.pick, { a = 0 }, Random.new(1)), "no error for total 0")
end)
