local ret, env = load_answer()
local Signal = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.Signal) or env.Signal
local calls = {}
local s = Signal.new()
s:Connect(function() table.insert(calls, "a") end)
local b
b = s:Connect(function() table.insert(calls, "b"); b:Disconnect() end)
s:Connect(function() table.insert(calls, "c") end)
s:Fire()
check("a handler that disconnects itself does not make the next one skip", table.concat(calls) == "abc")
calls = {}
s:Fire()
check("the second Fire calls only the remaining handlers", table.concat(calls) == "ac")

local t, log = Signal.new(), {}
local c2
t:Connect(function() table.insert(log, "d1"); c2:Disconnect() end)
c2 = t:Connect(function() table.insert(log, "d2") end)
t:Connect(function() table.insert(log, "d3") end)
t:Fire()
check("a handler disconnected before its turn is not called", table.concat(log, ",") == "d1,d3")

local u, seen = Signal.new(), {}
u:Connect(function()
	table.insert(seen, "first")
	u:Connect(function() table.insert(seen, "late") end)
end)
u:Fire()
check("a handler connected during Fire waits for the next Fire", table.concat(seen, ",") == "first")
seen = {}
u:Fire()
check("and is called by the next Fire", table.find(seen, "late") ~= nil and seen[1] == "first")

local v, got = Signal.new(), nil
local conn = v:Connect(function(...) got = { ... } end)
v:Fire(1, "x", true)
check("arguments are passed through", got ~= nil and got[1] == 1 and got[2] == "x" and got[3] == true)
conn:Disconnect()
conn:Disconnect()
got = nil
v:Fire(2)
check("Disconnect twice is safe and the handler stays disconnected", got == nil)
local w, n = Signal.new(), 0
for _ = 1, 5 do w:Connect(function() n += 1 end) end
w:Fire()
check("five handlers are each called once", n == 5)
