-- Holdout test body HO-ANI-01 (frozen 2026-10-11; harness-owned, never shown to the model).
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
-- Instance stand-in: Instance.new(class, parent?) with Parent/children bookkeeping, IsA, lookups, attributes, events and
-- property-changed signals. Properties live in a private table so that every assignment is seen.
local ISA = {
	GuiObject = { Frame = 1, TextLabel = 1, TextButton = 1, ImageLabel = 1, ImageButton = 1, ScrollingFrame = 1, TextBox = 1, CanvasGroup = 1, ViewportFrame = 1 },
	GuiButton = { TextButton = 1, ImageButton = 1 },
	LayerCollector = { ScreenGui = 1, SurfaceGui = 1, BillboardGui = 1 },
	BasePart = { Part = 1, MeshPart = 1, WedgePart = 1, SpawnLocation = 1, TrussPart = 1 },
	PVInstance = { Part = 1, MeshPart = 1, Model = 1, WedgePart = 1, SpawnLocation = 1, TrussPart = 1 },
	UIGridStyleLayout = { UIListLayout = 1, UIGridLayout = 1 },
	UILayout = { UIListLayout = 1, UIGridLayout = 1, UIPageLayout = 1, UITableLayout = 1 },
	GuiBase2d = { Frame = 1, TextLabel = 1, TextButton = 1, ImageLabel = 1, ImageButton = 1, ScrollingFrame = 1, TextBox = 1, ScreenGui = 1 },
}
local EVENTS = {
	Activated = 1, MouseButton1Click = 1, MouseButton1Down = 1, MouseButton1Up = 1, MouseEnter = 1, MouseLeave = 1,
	ChildAdded = 1, ChildRemoved = 1, Destroying = 1, Changed = 1, AncestryChanged = 1, Touched = 1, InputBegan = 1, InputEnded = 1,
}
local imethods = {}
local IMT = {}
local Instance = {}
local function isMock(x) return type(x) == "table" and rawget(x, "_children") ~= nil end
IMT.__index = function(self, k)
	if k == "Parent" then return rawget(self, "_parent") end
	local props = rawget(self, "_props")
	local v = props[k]
	if v ~= nil then return v end
	local m = imethods[k]
	if m then return m end
	if EVENTS[k] then
		local s = Signal.new()
		props[k] = s
		return s
	end
	return nil
end
local function setParent(self, p)
	local old = rawget(self, "_parent")
	if old == p then return end
	if old and isMock(old) then
		for i, c in old._children do
			if c == self then table.remove(old._children, i) break end
		end
		local sig = rawget(old, "_props").ChildRemoved
		if sig then sig:Fire(self) end
	end
	rawset(self, "_parent", p)
	if p and isMock(p) then
		table.insert(p._children, self)
		local sig = rawget(p, "_props").ChildAdded
		if sig then sig:Fire(self) end
	end
end
IMT.__newindex = function(self, k, v)
	if k == "Parent" then setParent(self, v) return end
	local props = rawget(self, "_props")
	props[k] = v
	local sigs = rawget(self, "_propSignals")
	if sigs and sigs[k] then sigs[k]:Fire() end
	if rawget(props, "Changed") then props.Changed:Fire(k) end
end
function imethods:IsA(c)
	return self.ClassName == c or c == "Instance" or (ISA[c] ~= nil and ISA[c][self.ClassName] ~= nil)
end
function imethods:GetChildren() return table.clone(self._children) end
function imethods:GetDescendants()
	local out = {}
	local function walk(n)
		for _, c in n._children do
			table.insert(out, c)
			walk(c)
		end
	end
	walk(self)
	return out
end
function imethods:FindFirstChild(name, recursive)
	for _, c in self._children do
		if c.Name == name then return c end
	end
	if recursive then
		for _, c in self._children do
			local f = c:FindFirstChild(name, true)
			if f then return f end
		end
	end
	return nil
end
imethods.WaitForChild = imethods.FindFirstChild
function imethods:FindFirstChildOfClass(cls)
	for _, c in self._children do
		if c.ClassName == cls then return c end
	end
	return nil
end
function imethods:FindFirstChildWhichIsA(cls)
	for _, c in self._children do
		if c:IsA(cls) then return c end
	end
	return nil
end
function imethods:IsDescendantOf(a)
	local p = rawget(self, "_parent")
	while p do
		if p == a then return true end
		p = isMock(p) and rawget(p, "_parent") or nil
	end
	return false
end
function imethods:IsAncestorOf(d) return d:IsDescendantOf(self) end
function imethods:ClearAllChildren()
	for _, c in table.clone(self._children) do c:Destroy() end
end
function imethods:Clone()
	local copy = Instance.new(self.ClassName)
	for k, v in rawget(self, "_props") do
		if k ~= "Destroyed" and not (type(v) == "table" and getmetatable(v) == Signal) then rawget(copy, "_props")[k] = v end
	end
	for _, c in self._children do c:Clone().Parent = copy end
	return copy
end
function imethods:Destroy()
	local props = rawget(self, "_props")
	if props.Destroyed then return end
	props.Destroyed = true
	if props.Destroying then props.Destroying:Fire() end
	for _, c in table.clone(self._children) do c:Destroy() end
	setParent(self, nil)
	for _, v in props do -- Destroy disconnects every connection made to the instance's events
		if type(v) == "table" and getmetatable(v) == Signal then
			for _, entry in v._fns do entry.connected = false end
		end
	end
end
function imethods:SetAttribute(k, v)
	local a = rawget(self, "_attrs")
	if not a then a = {} rawset(self, "_attrs", a) end
	a[k] = v
end
function imethods:GetAttribute(k)
	local a = rawget(self, "_attrs")
	return a and a[k]
end
function imethods:GetPropertyChangedSignal(prop)
	local sigs = rawget(self, "_propSignals")
	if not sigs then sigs = {} rawset(self, "_propSignals", sigs) end
	if not sigs[prop] then sigs[prop] = Signal.new() end
	return sigs[prop]
end
function Instance.new(className, parent)
	local o = setmetatable({ _props = { ClassName = className, Name = className }, _children = {} }, IMT)
	if parent ~= nil then o.Parent = parent end
	return o
end
local function typeofInstance(x)
	if type(x) == "table" and getmetatable(x) == IMT then return "Instance" end
	return typeof(x)
end
local function descendantsOfClass(root, className)
	local out = {}
	for _, d in root:GetDescendants() do
		if d.ClassName == className then table.insert(out, d) end
	end
	return out
end
local loads = {}
local tracks = {}
local animator = {}
function animator:LoadAnimation(anim)
	table.insert(loads, anim.AnimationId)
	local track = { id = anim.AnimationId, IsPlaying = false, log = {} }
	function track:Play(fade, weight, speed)
		self.IsPlaying = true
		table.insert(self.log, { "Play", fade, weight, speed })
	end
	function track:Stop(fade)
		self.IsPlaying = false
		table.insert(self.log, { "Stop", fade })
	end
	function track:AdjustSpeed(s) table.insert(self.log, { "Speed", s }) end
	tracks[anim.AnimationId] = track
	return track
end

local function count(track, what)
	local n = 0
	for _, e in track.log do if e[1] == what then n += 1 end end
	return n
end
local function lastOf(track, what)
	for i = #track.log, 1, -1 do
		if track.log[i][1] == what then return track.log[i] end
	end
	return nil
end
local function fade(entry) return entry and (entry[2] or 0.1) end -- no argument means the engine default of 0.1
local function speedOf(track) -- the effective speed: the last of Play's speed argument and AdjustSpeed calls
	local s = 1
	for _, e in track.log do
		if e[1] == "Play" and e[4] ~= nil then s = e[4] end
		if e[1] == "Speed" then s = e[2] end
	end
	return s
end
local function near(a, b) return a ~= nil and math.abs(a - b) < 1e-6 end

local env = { Instance = Instance, Enum = Enum, debug = debugStub, game = mockGame({}) }
local Mod = load_answer(env)
local ids = { Idle = "rbxassetid://111", Slash = "rbxassetid://222", Roll = "rbxassetid://333" }
local ctl = Mod.new(animator, ids)
check("creating the controller loads nothing", #loads == 0)

local idle = ctl:play("Idle")
check("play loads the animation lazily, once, with its asset id, and returns the track",
	idle == tracks["rbxassetid://111"] and #loads == 1 and loads[1] == "rbxassetid://111")
check("the track is played with the default fade time of 0.1", count(idle, "Play") == 1 and near(fade(lastOf(idle, "Play")), 0.1))
check("playing the same animation again while it plays does nothing", ctl:play("Idle") == idle and #loads == 1 and count(idle, "Play") == 1)

local slash = ctl:play("Slash", 0.3)
check("another animation is loaded once and played with the given fade time",
	slash == tracks["rbxassetid://222"] and #loads == 2 and near(fade(lastOf(slash, "Play")), 0.3))
check("the animation that was playing is stopped with the same fade time",
	idle.IsPlaying == false and count(idle, "Stop") == 1 and near(fade(lastOf(idle, "Stop")), 0.3))

local idle2 = ctl:play("Idle")
check("going back to Idle reuses the loaded track: no second load", idle2 == idle and #loads == 2 and idle.IsPlaying == true)
check("... and stops the Slash that was playing", slash.IsPlaying == false and count(slash, "Stop") == 1)

local okUnknown, unknown = pcall(ctl.play, ctl, "Nope")
check("an unknown name returns nil without an error and loads nothing", okUnknown == true and unknown == nil and #loads == 2)
check("the track that was playing keeps playing after an unknown name", idle.IsPlaying == true)

ctl:setSpeed(2)
check("setSpeed changes the speed of the track that is playing", speedOf(idle) == 2)
local roll = ctl:play("Roll", 0.2)
check("a track started after setSpeed gets that speed", roll == tracks["rbxassetid://333"] and speedOf(roll) == 2 and roll.IsPlaying == true)
check("starting Roll stopped Idle", idle.IsPlaying == false)

ctl:stop(0.4)
check("stop stops the current track with the given fade time", roll.IsPlaying == false and near(fade(lastOf(roll, "Stop")), 0.4))
local okStop = pcall(ctl.stop, ctl)
check("stop with nothing playing is harmless", okStop == true)

local again = ctl:play("Roll")
check("a track that is not playing any more starts again, still without a second load",
	again == roll and roll.IsPlaying == true and #loads == 3)
local distinct = {}
for _, id in loads do distinct[id] = true end
check("no animation id was ever loaded twice", countKeys(distinct) == #loads)
