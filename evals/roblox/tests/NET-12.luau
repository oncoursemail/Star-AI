local Retry = load_answer()
local function recorder()
	local delays = {}
	return delays, function(t) table.insert(delays, t) end
end

local delays, wait = recorder()
local calls = 0
local ok, value = Retry.run(function() calls += 1 return "saved" end, 3, 1, wait)
check("success on the first call: true, the value, one call, no wait", ok == true and value == "saved" and calls == 1 and #delays == 0)

delays, wait = recorder()
calls = 0
ok, value = Retry.run(function()
	calls += 1
	if calls < 3 then error("transient") end
	return "ok" .. calls
end, 5, 1, wait)
check("two failures then success: true after 3 calls, waits 1 then 2", ok == true and value == "ok3" and calls == 3 and deepEqual(delays, { 1, 2 }))

delays, wait = recorder()
calls = 0
ok, value = Retry.run(function() calls += 1 error("boom") end, 3, 0.5, wait)
check("always failing: false plus the error text after exactly 3 calls", ok == false and type(value) == "string" and string.find(value, "boom", 1, true) ~= nil and calls == 3)
check("delays double and there is no wait after the last failure", deepEqual(delays, { 0.5, 1 }))

delays, wait = recorder()
calls = 0
ok = Retry.run(function() calls += 1 error("x") end, 1, 2, wait)
check("a single attempt never waits", ok == false and calls == 1 and #delays == 0)

local bad = true
for _, n in { 0, -1, 1.5 } do
	if not throws(Retry.run, function() end, n, 1, wait) then bad = false end
end
check("attempts must be a positive integer (0, -1 and 1.5 throw)", bad)

delays, wait = recorder()
ok, value = Retry.run(function() return false end, 3, 1, wait)
check("a function that returns false without error counts as success", ok == true and value == false and #delays == 0)
