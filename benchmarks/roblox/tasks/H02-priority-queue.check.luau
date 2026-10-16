local PQ = solution()
check("pops in sorted order", function()
	local q = PQ.new()
	local rng = Random.new(3)
	local values = {}
	for i = 1, 2000 do
		values[i] = rng:NextInteger(1, 100000)
		q:push(values[i])
	end
	table.sort(values)
	expect(q:size() == 2000, "size " .. q:size())
	expect(q:peek() == values[1], "peek")
	for i = 1, 2000 do
		local v = q:pop()
		expect(v == values[i], "pop " .. i .. " gave " .. tostring(v))
	end
	expect(q:pop() == nil and q:size() == 0, "not empty at the end")
end)
check("custom order", function()
	local q = PQ.new(function(a, b) return a.p > b.p end)
	q:push({ p = 1 }); q:push({ p = 9 }); q:push({ p = 5 })
	expect(q:pop().p == 9 and q:pop().p == 5 and q:pop().p == 1, "max-first order")
end)
check("fast enough for 30000 items", function()
	local q = PQ.new()
	local t = os.clock()
	for i = 1, 30000 do q:push((i * 7919) % 30011) end
	for _ = 1, 30000 do q:pop() end
	expect(os.clock() - t < 1.0, string.format("%.2f s", os.clock() - t))
end)
