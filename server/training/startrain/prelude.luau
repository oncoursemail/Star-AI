-- STAR training-data harness prelude (owned by the generator; the answer under test never sees or edits it).
-- Adapted from the evaluation harness prelude (evals/roblox/prelude.luau) and extended with small, deterministic
-- Roblox stand-ins (Vector3, Vector2, Color3, UDim, UDim2, NumberRange, Enum, Random, Instance, services) so that
-- engine-flavoured tasks can be checked in the standalone Luau VM. Everything here is a MOCK: a task that passes
-- is "mock-verified", never "run in Roblox".
-- The answer arrives as the string __SRC and is only loaded with loadstring() into a whitelisted environment, so it
-- has no require, no loadstring, no file or network access. Result lines start with "@@".
local __print = print
local __loadstring = loadstring
local __setfenv = setfenv
local __typeof = typeof
local __clock = 0

local function check(name, cond)
	__print("@@T\t" .. (cond and "pass" or "fail") .. "\t" .. tostring(name))
end

local function deepEqual(a, b)
	if a == b then return true end
	if type(a) ~= "table" or type(b) ~= "table" then return false end
	for k, v in a do
		if not deepEqual(v, b[k]) then return false end
	end
	for k in b do
		if a[k] == nil then return false end
	end
	return true
end

local function deepCopy(t)
	if type(t) ~= "table" then return t end
	local out = {}
	for k, v in t do out[k] = deepCopy(v) end
	return out
end

local function countKeys(t)
	local n = 0
	for _ in t do n += 1 end
	return n
end

local function approx(a, b, eps)
	return math.abs(a - b) <= (eps or 1e-6)
end

-- A deterministic generator (the harness never uses math.random, so runs are repeatable).
local function lcg(seed)
	local state = seed
	return function(n)
		state = (state * 1103515245 + 12345) % 2147483648
		return (state % n) + 1
	end
end

-- Run `fn` and report whether it threw (a thrown error is a legitimate, checked outcome).
local function throws(fn, ...)
	local ok = pcall(fn, ...)
	return not ok
end

local Signal = {}
Signal.__index = Signal
function Signal.new()
	return setmetatable({ _fns = {} }, Signal)
end
function Signal:Connect(fn)
	local entry = { fn = fn, connected = true }
	table.insert(self._fns, entry)
	local conn = { Connected = true }
	function conn:Disconnect()
		entry.connected = false
		self.Connected = false
	end
	return conn
end
function Signal:Once(fn)
	local conn
	conn = self:Connect(function(...)
		conn:Disconnect()
		fn(...)
	end)
	return conn
end
function Signal:Fire(...)
	local snapshot = table.clone(self._fns)
	for _, entry in snapshot do
		if entry.connected then entry.fn(...) end
	end
end
function Signal:Count()
	local n = 0
	for _, entry in self._fns do
		if entry.connected then n += 1 end
	end
	return n
end

-- ===== Roblox data types (faithful for the operations listed) =====
local Vector3 = {}
local V3 = { __type = "Vector3" }
local function v3(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V3) end
local V3methods = {}
V3.__index = function(self, k)
	if k == "Magnitude" then return math.sqrt(self.X * self.X + self.Y * self.Y + self.Z * self.Z) end
	if k == "Unit" then
		local m = self.Magnitude
		return v3(self.X / m, self.Y / m, self.Z / m)
	end
	return V3methods[k]
end
function V3methods.Dot(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end
function V3methods.Cross(a, b)
	return v3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X)
end
function V3methods.Lerp(a, b, t) return v3(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t, a.Z + (b.Z - a.Z) * t) end
function V3methods.FuzzyEq(a, b, eps)
	eps = eps or 1e-5
	return math.abs(a.X - b.X) <= eps and math.abs(a.Y - b.Y) <= eps and math.abs(a.Z - b.Z) <= eps
end
function V3methods.Min(a, b) return v3(math.min(a.X, b.X), math.min(a.Y, b.Y), math.min(a.Z, b.Z)) end
function V3methods.Max(a, b) return v3(math.max(a.X, b.X), math.max(a.Y, b.Y), math.max(a.Z, b.Z)) end
function V3methods.Abs(a) return v3(math.abs(a.X), math.abs(a.Y), math.abs(a.Z)) end
function V3methods.Floor(a) return v3(math.floor(a.X), math.floor(a.Y), math.floor(a.Z)) end
function V3methods.Ceil(a) return v3(math.ceil(a.X), math.ceil(a.Y), math.ceil(a.Z)) end
V3.__add = function(a, b) return v3(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V3.__sub = function(a, b) return v3(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V3.__mul = function(a, b)
	if type(a) == "number" then return v3(a * b.X, a * b.Y, a * b.Z) end
	if type(b) == "number" then return v3(a.X * b, a.Y * b, a.Z * b) end
	return v3(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
V3.__div = function(a, b)
	if type(b) == "number" then return v3(a.X / b, a.Y / b, a.Z / b) end
	return v3(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
end
V3.__unm = function(a) return v3(-a.X, -a.Y, -a.Z) end
V3.__eq = function(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
V3.__tostring = function(a) return a.X .. ", " .. a.Y .. ", " .. a.Z end
function Vector3.new(x, y, z) return v3(x or 0, y or 0, z or 0) end
Vector3.zero, Vector3.one = v3(0, 0, 0), v3(1, 1, 1)
Vector3.xAxis, Vector3.yAxis, Vector3.zAxis = v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1)

local Vector2 = {}
local V2 = { __type = "Vector2" }
local function v2(x, y) return setmetatable({ X = x, Y = y }, V2) end
local V2methods = {}
V2.__index = function(self, k)
	if k == "Magnitude" then return math.sqrt(self.X * self.X + self.Y * self.Y) end
	if k == "Unit" then
		local m = self.Magnitude
		return v2(self.X / m, self.Y / m)
	end
	return V2methods[k]
end
function V2methods.Dot(a, b) return a.X * b.X + a.Y * b.Y end
function V2methods.Cross(a, b) return a.X * b.Y - a.Y * b.X end
function V2methods.Lerp(a, b, t) return v2(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t) end
V2.__add = function(a, b) return v2(a.X + b.X, a.Y + b.Y) end
V2.__sub = function(a, b) return v2(a.X - b.X, a.Y - b.Y) end
V2.__mul = function(a, b)
	if type(a) == "number" then return v2(a * b.X, a * b.Y) end
	if type(b) == "number" then return v2(a.X * b, a.Y * b) end
	return v2(a.X * b.X, a.Y * b.Y)
end
V2.__div = function(a, b)
	if type(b) == "number" then return v2(a.X / b, a.Y / b) end
	return v2(a.X / b.X, a.Y / b.Y)
end
V2.__unm = function(a) return v2(-a.X, -a.Y) end
V2.__eq = function(a, b) return a.X == b.X and a.Y == b.Y end
V2.__tostring = function(a) return a.X .. ", " .. a.Y end
function Vector2.new(x, y) return v2(x or 0, y or 0) end
Vector2.zero, Vector2.one = v2(0, 0), v2(1, 1)

local Color3 = {}
local C3 = { __type = "Color3" }
local function c3(r, g, b) return setmetatable({ R = r, G = g, B = b }, C3) end
local C3methods = {}
C3.__index = C3methods
function C3methods.Lerp(a, b, t) return c3(a.R + (b.R - a.R) * t, a.G + (b.G - a.G) * t, a.B + (b.B - a.B) * t) end
C3.__eq = function(a, b) return a.R == b.R and a.G == b.G and a.B == b.B end
C3.__tostring = function(a) return a.R .. ", " .. a.G .. ", " .. a.B end
function Color3.new(r, g, b) return c3(r or 0, g or 0, b or 0) end
function Color3.fromRGB(r, g, b) return c3((r or 0) / 255, (g or 0) / 255, (b or 0) / 255) end

local UDim = {}
local UD = { __type = "UDim" }
local function ud(s, o) return setmetatable({ Scale = s, Offset = o }, UD) end
UD.__eq = function(a, b) return a.Scale == b.Scale and a.Offset == b.Offset end
UD.__add = function(a, b) return ud(a.Scale + b.Scale, a.Offset + b.Offset) end
UD.__sub = function(a, b) return ud(a.Scale - b.Scale, a.Offset - b.Offset) end
UD.__tostring = function(a) return "{" .. a.Scale .. ", " .. a.Offset .. "}" end
function UDim.new(s, o) return ud(s or 0, o or 0) end

local UDim2 = {}
local U2 = { __type = "UDim2" }
local function u2(x, y)
	return setmetatable({ X = x, Y = y, Width = x, Height = y }, U2)
end
U2.__eq = function(a, b) return a.X == b.X and a.Y == b.Y end
U2.__add = function(a, b) return u2(a.X + b.X, a.Y + b.Y) end
U2.__sub = function(a, b) return u2(a.X - b.X, a.Y - b.Y) end
U2.__tostring = function(a) return tostring(a.X) .. ", " .. tostring(a.Y) end
function UDim2.new(xs, xo, ys, yo)
	if type(xs) == "table" then return u2(xs, xo) end
	return u2(ud(xs or 0, xo or 0), ud(ys or 0, yo or 0))
end
function UDim2.fromScale(xs, ys) return u2(ud(xs, 0), ud(ys, 0)) end
function UDim2.fromOffset(xo, yo) return u2(ud(0, xo), ud(0, yo)) end

local NumberRange = {}
local NR = { __type = "NumberRange" }
function NumberRange.new(a, b) return setmetatable({ Min = a, Max = b or a }, NR) end
NR.__eq = function(a, b) return a.Min == b.Min and a.Max == b.Max end

local Enum = setmetatable({}, { __index = function(root, enumName)
	local items = setmetatable({}, { __index = function(list, itemName)
		local item = setmetatable({ Name = itemName, EnumType = enumName }, { __type = "EnumItem",
			__tostring = function() return "Enum." .. enumName .. "." .. itemName end })
		rawset(list, itemName, item)
		return item
	end })
	rawset(root, enumName, items)
	return items
end })

local Random = {}
Random.__index = Random
function Random.new(seed)
	return setmetatable({ _next = lcg(seed or 1) }, Random)
end
function Random:NextNumber(lo, hi)
	local u = (self._next(1000000) - 1) / 1000000
	if lo == nil then return u end
	return lo + (hi - lo) * u
end
function Random:NextInteger(lo, hi)
	return lo + self._next(hi - lo + 1) - 1
end

-- ===== Instance mock =====
-- Properties live in _props so that assignments always reach __newindex (and fire Changed signals), whether or not
-- the property has a default. Raw fields starting with an underscore are the mock's own bookkeeping.
local PARENT = {
	Part = "BasePart", WedgePart = "BasePart", MeshPart = "BasePart", TrussPart = "BasePart",
	SpawnLocation = "BasePart", Seat = "BasePart", UnionOperation = "BasePart", BasePart = "PVInstance",
	Model = "PVInstance", PVInstance = "Instance", Folder = "Instance", Workspace = "Instance",
	Frame = "GuiObject", TextLabel = "GuiObject", ImageLabel = "GuiObject", ScrollingFrame = "GuiObject",
	TextButton = "GuiButton", ImageButton = "GuiButton", GuiButton = "GuiObject", GuiObject = "GuiBase2d",
	ScreenGui = "LayerCollector", SurfaceGui = "LayerCollector", BillboardGui = "LayerCollector",
	LayerCollector = "GuiBase2d", GuiBase2d = "Instance",
	UIListLayout = "UIGridStyleLayout", UIGridLayout = "UIGridStyleLayout", UIGridStyleLayout = "UILayout",
	UILayout = "UIComponent", UIPadding = "UIComponent", UICorner = "UIComponent", UIStroke = "UIComponent",
	UIScale = "UIComponent", UIAspectRatioConstraint = "UIConstraint", UISizeConstraint = "UIConstraint",
	UITextSizeConstraint = "UIConstraint", UIConstraint = "UIComponent", UIComponent = "Instance",
	Script = "BaseScript", LocalScript = "BaseScript", BaseScript = "LuaSourceContainer",
	ModuleScript = "LuaSourceContainer", LuaSourceContainer = "Instance",
	RemoteEvent = "BaseRemoteEvent", UnreliableRemoteEvent = "BaseRemoteEvent", BaseRemoteEvent = "Instance",
	StringValue = "ValueBase", IntValue = "ValueBase", NumberValue = "ValueBase", BoolValue = "ValueBase",
	ObjectValue = "ValueBase", ValueBase = "Instance",
	PointLight = "Light", SpotLight = "Light", SurfaceLight = "Light", Light = "Instance",
	Tool = "BackpackItem", HopperBin = "BackpackItem", BackpackItem = "Instance",
}
local EVENTS = {
	Touched = true, TouchEnded = true, Activated = true, Deactivated = true, Equipped = true, Unequipped = true,
	MouseButton1Click = true, MouseButton1Down = true, MouseButton1Up = true, MouseEnter = true, MouseLeave = true,
	InputBegan = true, InputEnded = true, InputChanged = true, ChildAdded = true, ChildRemoved = true,
	DescendantAdded = true, DescendantRemoving = true, Destroying = true, AncestryChanged = true, Changed = true,
	Died = true, HealthChanged = true, OnServerEvent = true, OnClientEvent = true, Completed = true,
	Ended = true, Triggered = true, Heartbeat = true, Stepped = true, RenderStepped = true,
	PlayerAdded = true, PlayerRemoving = true, CharacterAdded = true, CharacterRemoving = true,
}
local DEFAULTS = {
	Humanoid = { Health = 100, MaxHealth = 100, WalkSpeed = 16, JumpPower = 50 },
	BasePart = { Size = Vector3.new(4, 1, 2), Position = Vector3.new(0, 0, 0), Anchored = false, CanCollide = true, Transparency = 0 },
	GuiObject = { Size = UDim2.new(0, 0, 0, 0), Position = UDim2.new(0, 0, 0, 0), Visible = true },
}
local Instance = {}
local IM = { __type = "Instance" }
local methods = {}
local function chainOf(cls)
	local out, c = {}, cls
	while c do
		out[c] = true
		c = PARENT[c]
	end
	out.Instance = true
	return out
end
local function signalOf(self, name)
	local signals = rawget(self, "_signals")
	if not signals[name] then signals[name] = Signal.new() end
	return signals[name]
end
local function nameOf(obj) return rawget(obj, "_props").Name end
IM.__index = function(self, k)
	if k == "Parent" then return rawget(self, "_parent") end
	local v = rawget(self, "_props")[k]
	if v ~= nil then return v end          -- a service's own functions shadow the generic methods
	local m = methods[k]
	if m ~= nil then return m end
	if EVENTS[k] then return signalOf(self, k) end
	for _, child in rawget(self, "_children") do
		if nameOf(child) == k then return child end
	end
	return nil
end
local function detach(self)
	local old = rawget(self, "_parent")
	if old then
		local list = rawget(old, "_children")
		for i, child in list do
			if child == self then table.remove(list, i) break end
		end
		signalOf(old, "ChildRemoved"):Fire(self)
	end
	rawset(self, "_parent", nil)
end
IM.__newindex = function(self, k, v)
	if k == "Parent" then
		if rawget(self, "_destroyed") then error("The Parent property of " .. tostring(nameOf(self)) .. " is locked") end
		if rawget(self, "_parent") == v then return end
		detach(self)
		if v ~= nil then
			rawset(self, "_parent", v)
			table.insert(rawget(v, "_children"), self)
			signalOf(v, "ChildAdded"):Fire(self)
		end
		signalOf(self, "AncestryChanged"):Fire(self, v)
		return
	end
	rawget(self, "_props")[k] = v
	local prop = rawget(self, "_propSignals")[k]
	if prop then prop:Fire() end
	signalOf(self, "Changed"):Fire(k)
end
function Instance.new(className, parent)
	local obj = setmetatable({ ClassName = className, _props = { Name = className }, _children = {}, _attrs = {},
		_signals = {}, _propSignals = {}, _calls = {}, _tags = {} }, IM)
	local chain = chainOf(className)
	for cls, defaults in DEFAULTS do
		if chain[cls] then
			for k, v in defaults do rawget(obj, "_props")[k] = v end
		end
	end
	if parent ~= nil then obj.Parent = parent end
	return obj
end
function methods.IsA(self, name) return chainOf(rawget(self, "ClassName"))[name] == true end
function methods.GetChildren(self) return table.clone(rawget(self, "_children")) end
function methods.GetDescendants(self)
	local out = {}
	local function walk(n)
		for _, child in rawget(n, "_children") do
			table.insert(out, child)
			walk(child)
		end
	end
	walk(self)
	return out
end
function methods.FindFirstChild(self, name, recursive)
	for _, child in rawget(self, "_children") do
		if nameOf(child) == name then return child end
	end
	if recursive then
		for _, child in rawget(self, "_children") do
			local found = child:FindFirstChild(name, true)
			if found then return found end
		end
	end
	return nil
end
function methods.WaitForChild(self, name) return self:FindFirstChild(name) end
function methods.FindFirstChildOfClass(self, className)
	for _, child in rawget(self, "_children") do
		if rawget(child, "ClassName") == className then return child end
	end
	return nil
end
function methods.FindFirstChildWhichIsA(self, className)
	for _, child in rawget(self, "_children") do
		if child:IsA(className) then return child end
	end
	return nil
end
function methods.IsDescendantOf(self, ancestor)
	local p = rawget(self, "_parent")
	while p do
		if p == ancestor then return true end
		p = rawget(p, "_parent")
	end
	return false
end
function methods.GetFullName(self)
	local names, n = {}, self
	while n do
		table.insert(names, 1, nameOf(n))
		n = rawget(n, "_parent")
	end
	return table.concat(names, ".")
end
function methods.SetAttribute(self, k, v) rawget(self, "_attrs")[k] = v end
function methods.GetAttribute(self, k) return rawget(self, "_attrs")[k] end
function methods.GetAttributes(self) return table.clone(rawget(self, "_attrs")) end
function methods.GetPropertyChangedSignal(self, prop)
	local sigs = rawget(self, "_propSignals")
	if not sigs[prop] then sigs[prop] = Signal.new() end
	return sigs[prop]
end
function methods.ClearAllChildren(self)
	for _, child in table.clone(rawget(self, "_children")) do child:Destroy() end
end
function methods.Destroy(self)
	if rawget(self, "_destroyed") then return end
	signalOf(self, "Destroying"):Fire()
	for _, child in table.clone(rawget(self, "_children")) do child:Destroy() end
	detach(self)
	rawset(self, "_destroyed", true)
end
function methods.Clone(self)
	local copy = Instance.new(rawget(self, "ClassName"))
	for k, v in rawget(self, "_props") do rawget(copy, "_props")[k] = v end
	for k, v in rawget(self, "_attrs") do rawget(copy, "_attrs")[k] = v end
	for _, child in rawget(self, "_children") do
		child:Clone().Parent = copy
	end
	return copy
end
-- Tags: one registry shared by Instance:AddTag and CollectionService, as in Roblox.
local TAGGED = {}          -- tag -> array of instances in the order they were tagged
local TAG_ADDED = {}       -- tag -> Signal
local function tagSignal(tag)
	if not TAG_ADDED[tag] then TAG_ADDED[tag] = Signal.new() end
	return TAG_ADDED[tag]
end
function methods.AddTag(self, tag)
	if rawget(self, "_tags")[tag] then return end
	rawget(self, "_tags")[tag] = true
	TAGGED[tag] = TAGGED[tag] or {}
	table.insert(TAGGED[tag], self)
	tagSignal(tag):Fire(self)
end
function methods.HasTag(self, tag) return rawget(self, "_tags")[tag] == true end
function methods.RemoveTag(self, tag)
	if not rawget(self, "_tags")[tag] then return end
	rawget(self, "_tags")[tag] = nil
	for i, inst in TAGGED[tag] or {} do
		if inst == self then table.remove(TAGGED[tag], i) break end
	end
end
-- RemoteEvent / RemoteFunction stand-ins record what was sent in inst._calls.
function methods.FireServer(self, ...) table.insert(rawget(self, "_calls"), { method = "FireServer", args = { ... } }) end
function methods.FireClient(self, player, ...) table.insert(rawget(self, "_calls"), { method = "FireClient", player = player, args = { ... } }) end
function methods.FireAllClients(self, ...) table.insert(rawget(self, "_calls"), { method = "FireAllClients", args = { ... } }) end
-- Humanoid
function methods.TakeDamage(self, n) self.Health = math.max(0, self.Health - n) end
function methods.MoveTo(self, pos) rawset(self, "_movedTo", pos) end

-- ===== services =====
local function mockPlayers()
	local svc = Instance.new("Players")
	rawset(svc, "_list", {})
	function svc:GetPlayers() return table.clone(rawget(self, "_list")) end
	function svc:GetPlayerFromCharacter(model)
		for _, p in rawget(self, "_list") do
			if p.Character == model then return p end
		end
		return nil
	end
	function svc:AddPlayer(p)
		table.insert(rawget(self, "_list"), p)
		self.PlayerAdded:Fire(p)
	end
	function svc:RemovePlayer(p)
		self.PlayerRemoving:Fire(p)
		local list = rawget(self, "_list")
		for i, q in list do
			if q == p then table.remove(list, i) break end
		end
	end
	return svc
end

local function mockRunService()
	local svc = Instance.new("RunService")
	function svc:IsServer() return true end
	function svc:IsClient() return false end
	function svc:IsStudio() return false end
	return svc
end

local function mockDebris()
	local svc = Instance.new("Debris")
	rawset(svc, "_items", {})
	function svc:AddItem(item, lifetime) table.insert(rawget(self, "_items"), { item = item, lifetime = lifetime or 10 }) end
	return svc
end

local function mockCollection()
	local svc = Instance.new("CollectionService")
	function svc:AddTag(inst, tag) inst:AddTag(tag) end
	function svc:HasTag(inst, tag) return inst:HasTag(tag) end
	function svc:RemoveTag(inst, tag) inst:RemoveTag(tag) end
	function svc:GetTagged(tag)
		local out = {}
		for _, inst in TAGGED[tag] or {} do
			if not rawget(inst, "_destroyed") then table.insert(out, inst) end
		end
		return out
	end
	function svc:GetInstanceAddedSignal(tag) return tagSignal(tag) end
	return svc
end

local function mockTween()
	local svc = Instance.new("TweenService")
	rawset(svc, "_created", {})
	function svc:Create(target, info, goal)
		local tween = Instance.new("Tween")
		tween.Instance = target
		tween.TweenInfo = info
		tween.Goal = goal
		function tween:Play()
			rawset(self, "_played", true)
			for k, v in goal do target[k] = v end
			self.Completed:Fire("Completed")
		end
		function tween:Cancel() rawset(self, "_cancelled", true) end
		table.insert(rawget(svc, "_created"), tween)
		return tween
	end
	return svc
end

-- A mock `game`: GetService returns what the test registered; Players, RunService, Debris, CollectionService
-- and TweenService have working defaults; any other service name is an empty Instance of that class.
local function mockGame(services)
	services = services or {}
	local g = { __closers = {} }
	local cache = {}
	local factories = { Players = mockPlayers, RunService = mockRunService, Debris = mockDebris,
		CollectionService = mockCollection, TweenService = mockTween }
	function g:GetService(name)
		if services[name] ~= nil then return services[name] end
		if cache[name] == nil then
			cache[name] = if factories[name] then factories[name]() else Instance.new(name)
		end
		return cache[name]
	end
	function g:BindToClose(fn) table.insert(g.__closers, fn) end
	g.PlaceId = 1
	g.JobId = "test-job"
	for name, service in services do g[name] = service end   -- game.Players as well as game:GetService("Players")
	return g
end

local function mockPlayer(name, userId, coins)
	local p = Instance.new("Player")
	p.Name, p.UserId = name, userId
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = p
	local c = Instance.new("IntValue")
	c.Name, c.Value = "Coins", coins or 0
	c.Parent = stats
	return p
end

local function mockCharacter(health)
	local model = Instance.new("Model")
	model.Name = "Character"
	local hum = Instance.new("Humanoid")
	hum.Health = health or 100
	hum.Parent = model
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Parent = model
	return model, hum
end

-- A folder-like plain table node (kept from the evaluation prelude for tests that prefer plain tables).
local function node(t)
	function t:FindFirstChild(name) return rawget(self, name) end
	function t:WaitForChild(name) return rawget(self, name) end
	function t:FindFirstChildOfClass(className)
		for _, child in self do
			if type(child) == "table" and child.ClassName == className then return child end
		end
		return nil
	end
	t.FindFirstChildWhichIsA = t.FindFirstChildOfClass
	return t
end

local function robloxTypeof(v)
	if type(v) == "table" then
		local mt = getmetatable(v)
		if mt and mt.__type then return mt.__type end
	end
	return __typeof(v)
end
local typeof = robloxTypeof   -- tests see the Roblox behaviour too

local SAFE = {
	assert = assert, error = error, ipairs = ipairs, pairs = pairs, next = next, pcall = pcall, xpcall = xpcall,
	select = select, tonumber = tonumber, tostring = tostring, type = type, typeof = robloxTypeof, unpack = unpack,
	rawequal = rawequal, rawget = rawget, rawset = rawset, rawlen = rawlen, setmetatable = setmetatable,
	getmetatable = getmetatable, math = math, string = string, table = table, utf8 = utf8, bit32 = bit32,
	coroutine = coroutine, buffer = buffer,
	os = { time = os.time, clock = os.clock, date = os.date },
	print = function() end, warn = function() end,
	time = function() return os.clock() end,
	Vector3 = Vector3, Vector2 = Vector2, Color3 = Color3, UDim = UDim, UDim2 = UDim2, NumberRange = NumberRange,
	Enum = Enum, Random = Random, Instance = Instance,
}
SAFE.task = {
	wait = function(t) local d = t or 0.03; __clock += d; return d end,
	spawn = function(f, ...) local co = coroutine.create(f); coroutine.resume(co, ...); return co end,
	defer = function(f, ...) local co = coroutine.create(f); coroutine.resume(co, ...); return co end,
	delay = function() end, cancel = function() end,
}
SAFE.game = mockGame()
SAFE.workspace = SAFE.game:GetService("Workspace")

local function newEnv(extra)
	local env = {}
	for k, v in SAFE do env[k] = v end
	if extra then
		for k, v in extra do env[k] = v end
		if extra.game ~= nil and extra.workspace == nil and extra.game.GetService then
			env.workspace = extra.game:GetService("Workspace")
		end
	end
	return env
end

-- Load the answer; returns what its chunk returns (the ModuleScript's value) and the chunk's globals table.
-- `extra` adds or replaces globals such as game, workspace, task or require.
local function load_answer(extra)
	local f, err = __loadstring(__SRC, "=answer")
	if not f then
		__print("@@LOADERR\t" .. string.sub(tostring(err), 1, 300))
		error("answer did not load")
	end
	local env = newEnv(extra)
	__setfenv(f, env)
	return f(), env
end

-- The thing named `name` that the answer provides: its returned function or table member, else a global.
local function resolve(ret, env, name)
	if type(ret) == "function" then return ret end
	if type(ret) == "table" and ret[name] ~= nil then return ret[name] end
	return env[name]
end
