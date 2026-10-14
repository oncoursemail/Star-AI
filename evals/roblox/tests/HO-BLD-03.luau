-- Holdout test body HO-BLD-03 (frozen 2026-10-11; harness-owned, never shown to the model).
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
local CS = { _tagged = {}, _added = {}, _removed = {} }
local function sig(map, tag)
	if not map[tag] then map[tag] = Signal.new() end
	return map[tag]
end
function CS:GetTagged(tag)
	local out = {}
	for _, inst in self._tagged[tag] or {} do table.insert(out, inst) end
	return out
end
function CS:GetInstanceAddedSignal(tag) return sig(self._added, tag) end
function CS:GetInstanceRemovedSignal(tag) return sig(self._removed, tag) end
function CS:HasTag(inst, tag)
	for _, i in self._tagged[tag] or {} do if i == inst then return true end end
	return false
end
function CS:AddTag(inst, tag)
	if self:HasTag(inst, tag) then return end
	self._tagged[tag] = self._tagged[tag] or {}
	table.insert(self._tagged[tag], inst)
	sig(self._added, tag):Fire(inst)
end
function CS:RemoveTag(inst, tag)
	local list = self._tagged[tag] or {}
	for i, other in list do
		if other == inst then
			table.remove(list, i)
			sig(self._removed, tag):Fire(inst)
			return
		end
	end
end

local Mod = load_answer({ game = mockGame({ CollectionService = CS }), debug = debugStub })
local function new(name) return { Name = name } end
local a, b, c, d = new("A"), new("B"), new("C"), new("D")
local function names(list)
	local out = table.clone(list)
	table.sort(out)
	return table.concat(out, ",")
end

CS:AddTag(a, "Door")
CS:AddTag(b, "Door")
local handled, cleaned = {}, {}
local function handler(inst)
	table.insert(handled, inst.Name)
	return function() table.insert(cleaned, inst.Name) end
end
local unbind = Mod.bind("Door", handler)
check("bind returns a function", type(unbind) == "function")
check("instances that already have the tag are handled at bind time", names(handled) == "A,B")
CS:AddTag(c, "Door")
check("an instance tagged later is handled", names(handled) == "A,B,C")
CS:AddTag(d, "Other")
check("instances with other tags are not handled", names(handled) == "A,B,C")
sig(CS._added, "Door"):Fire(a)
check("the same instance is not handled twice at the same time", names(handled) == "A,B,C")

CS:RemoveTag(a, "Door")
check("removing the tag runs that instance's cleanup, only", names(cleaned) == "A")
sig(CS._removed, "Door"):Fire(a)
check("a second removal event does not run the cleanup again", names(cleaned) == "A")
CS:AddTag(a, "Door")
check("an instance that gets the tag again is handled again", #handled == 4 and handled[4] == "A")

local second, secondCleaned = {}, 0
local unbind2 = Mod.bind("Door", function(inst)
	table.insert(second, inst.Name)
	return function() secondCleaned += 1 end
end)
check("a second binding on the same tag handles every tagged instance on its own", names(second) == "A,B,C")

unbind()
check("unbinding runs the cleanup of every live instance exactly once", names(cleaned) == "A,A,B,C")
CS:AddTag(d, "Door")
check("after unbinding, new instances are not handled by that binding", #handled == 4 and names(second) == "A,B,C,D")
CS:RemoveTag(b, "Door")
check("after unbinding, a removal does not run that binding's cleanup", names(cleaned) == "A,A,B,C" and secondCleaned == 1)
check("unbinding one binding left the other working", secondCleaned == 1 and #second == 4)
unbind()
check("calling unbind twice is harmless", names(cleaned) == "A,A,B,C")
unbind2()
check("the unbinding of the second binding cleans its live instances", secondCleaned == 1 + 3)
check("no connection is left on the tag's signals", liveCount(CS._added["Door"]) == 0 and liveCount(CS._removed["Door"]) == 0)

local seen = {}
local g1, g2, boom = new("Good1"), new("Good2"), new("Boom")
CS:AddTag(g1, "Mine")
CS:AddTag(boom, "Mine")
CS:AddTag(g2, "Mine")
local okBind = pcall(function()
	Mod.bind("Mine", function(inst)
		if inst.Name == "Boom" then error("handler failed on purpose") end
		table.insert(seen, inst.Name)
	end)
end)
check("a handler that throws for one instance does not stop bind or the other instances", okBind == true and names(seen) == "Good1,Good2")
local later = new("Later")
local okLater = pcall(function() CS:AddTag(later, "Mine") end)
check("a throwing handler does not break later additions either", okLater == true and names(seen) == "Good1,Good2,Later")
local okRemove = pcall(function() CS:RemoveTag(g1, "Mine") end)
check("handlers that return nothing need no cleanup", okRemove == true)
