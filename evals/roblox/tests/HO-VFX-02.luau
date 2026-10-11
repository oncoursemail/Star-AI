-- Holdout test body HO-VFX-02 (frozen 2026-10-11; harness-owned, never shown to the model).
-- Enum stand-in: any Enum.X.Y exists and is the same table every time (so == works).
local Enum = setmetatable({}, { __index = function(t, enumName)
	local enum = setmetatable({}, { __index = function(e, itemName)
		local item = setmetatable({ EnumType = enumName, Name = itemName }, {
			__tostring = function() return "Enum." .. enumName .. "." .. itemName end,
		})
		rawset(e, itemName, item)
		return item
	end })
	rawset(t, enumName, enum)
	return enum
end })
local debugStub = { traceback = function(m) return tostring(m) end }
-- Signal additions (the prelude's Signal has Connect and Fire only).
function Signal:Once(fn)
	local conn
	conn = self:Connect(function(...)
		conn.Disconnect()
		fn(...)
	end)
	return conn
end
function Signal:Wait()
	local co = coroutine.running()
	local conn
	conn = self:Connect(function(...)
		conn.Disconnect()
		coroutine.resume(co, ...)
	end)
	return coroutine.yield()
end
local function liveCount(sig)
	local n = 0
	for _, entry in sig._fns do
		if entry.connected then n += 1 end
	end
	return n
end
local Mod = load_answer({ debug = debugStub })
local t = 1000
local function now() return t end

local humanoid = { Running = Signal.new() }
local emitter = { Enabled = true, emits = {} }
function emitter:Emit(n) table.insert(self.emits, n) end

local stop = Mod.attach(humanoid, emitter, now)
check("attach turns continuous emission off (bursts only)", emitter.Enabled == false)
check("attach connects exactly one handler to Humanoid.Running", liveCount(humanoid.Running) == 1)
check("attach returns a function", type(stop) == "function")
check("nothing is emitted by attaching", #emitter.emits == 0)

humanoid.Running:Fire(16)
check("the first burst is allowed at once: speed 16 emits floor(16 / 4) = 4", deepEqual(emitter.emits, { 4 }))
t = 1000.1
humanoid.Running:Fire(20)
check("a second event 0.1 s later is ignored", deepEqual(emitter.emits, { 4 }))
t = 1000.25
humanoid.Running:Fire(20)
check("exactly 0.25 s after the last burst is allowed: floor(20 / 4) = 5", deepEqual(emitter.emits, { 4, 5 }))
t = 1000.3
humanoid.Running:Fire(40)
check("an ignored event does not restart the 0.25 s timer", deepEqual(emitter.emits, { 4, 5 }))
t = 1000.5
humanoid.Running:Fire(9)
check("0.25 s after the last burst (not after the ignored event) is allowed: floor(9 / 4) = 2", deepEqual(emitter.emits, { 4, 5, 2 }))
t = 1001
humanoid.Running:Fire(100)
check("the burst size is capped at 6", deepEqual(emitter.emits, { 4, 5, 2, 6 }))
t = 1002
humanoid.Running:Fire(8)
humanoid.Running:Fire(0)
humanoid.Running:Fire(3)
humanoid.Running:Fire(-20)
check("speeds of 8 or less (walking, standing, backwards) emit nothing", #emitter.emits == 4)
humanoid.Running:Fire(8.5)
check("a quiet event does not use up the timer: 8.5 emits floor(8.5 / 4) = 2 right away", deepEqual(emitter.emits, { 4, 5, 2, 6, 2 }))
t = 1003
humanoid.Running:Fire(8.9)
check("a fractional speed is floored: 8.9 emits 2", deepEqual(emitter.emits, { 4, 5, 2, 6, 2, 2 }))

stop()
check("the returned function disconnects the handler", liveCount(humanoid.Running) == 0)
t = 1010
humanoid.Running:Fire(30)
check("after stopping nothing is emitted", #emitter.emits == 6)
local okTwice = pcall(stop)
check("calling the returned function twice is harmless", okTwice == true)

t = 3000
local a, b = { Running = Signal.new() }, { Running = Signal.new() }
local ea, eb = { Enabled = true, emits = {} }, { Enabled = true, emits = {} }
function ea:Emit(n) table.insert(self.emits, n) end
function eb:Emit(n) table.insert(self.emits, n) end
Mod.attach(a, ea, now)
Mod.attach(b, eb, now)
a.Running:Fire(100)
b.Running:Fire(100)
a.Running:Fire(100)
check("each attach keeps its own timer", deepEqual(ea.emits, { 6 }) and deepEqual(eb.emits, { 6 }))
