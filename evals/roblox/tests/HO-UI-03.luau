-- Holdout test body HO-UI-03 (frozen 2026-10-11; harness-owned, never shown to the model).
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
-- UI and effect datatype stand-ins.
local UDim = {}
UDim.__index = UDim
function UDim.new(s, o) return setmetatable({ Scale = s or 0, Offset = o or 0 }, UDim) end
function UDim.__eq(a, b) return a.Scale == b.Scale and a.Offset == b.Offset end
local UDim2 = {}
UDim2.__index = UDim2
function UDim2.new(xs, xo, ys, yo)
	if type(xs) == "table" then return setmetatable({ X = xs, Y = xo }, UDim2) end
	return setmetatable({ X = UDim.new(xs, xo), Y = UDim.new(ys, yo) }, UDim2)
end
function UDim2.fromScale(x, y) return UDim2.new(x, 0, y, 0) end
function UDim2.fromOffset(x, y) return UDim2.new(0, x, 0, y) end
function UDim2.__eq(a, b) return a.X == b.X and a.Y == b.Y end
local Vector2 = {}
Vector2.__index = function(v, k)
	if k == "Magnitude" then return math.sqrt(v.X * v.X + v.Y * v.Y) end
	return Vector2[k]
end
function Vector2.new(x, y) return setmetatable({ X = x or 0, Y = y or 0 }, Vector2) end
function Vector2.__eq(a, b) return a.X == b.X and a.Y == b.Y end
function Vector2.__add(a, b) return Vector2.new(a.X + b.X, a.Y + b.Y) end
function Vector2.__sub(a, b) return Vector2.new(a.X - b.X, a.Y - b.Y) end
local Color3 = {}
Color3.__index = Color3
function Color3.new(r, g, b) return setmetatable({ R = r or 0, G = g or 0, B = b or 0 }, Color3) end
function Color3.fromRGB(r, g, b) return Color3.new((r or 0) / 255, (g or 0) / 255, (b or 0) / 255) end
function Color3.__eq(a, b) return a.R == b.R and a.G == b.G and a.B == b.B end
function Color3:Lerp(o, t) return Color3.new(self.R + (o.R - self.R) * t, self.G + (o.G - self.G) * t, self.B + (o.B - self.B) * t) end
local function sameColor(a, b, eps)
	eps = eps or 1e-6
	return a ~= nil and b ~= nil and math.abs(a.R - b.R) <= eps and math.abs(a.G - b.G) <= eps and math.abs(a.B - b.B) <= eps
end
local TweenInfo = {}
function TweenInfo.new(time, style, dir, repeatCount, reverses, delayTime)
	return {
		Time = time or 1, EasingStyle = style or Enum.EasingStyle.Quad, EasingDirection = dir or Enum.EasingDirection.Out,
		RepeatCount = repeatCount or 0, Reverses = reverses or false, DelayTime = delayTime or 0,
	}
end
local NumberRange = {}
function NumberRange.new(a, b) return { Min = a, Max = b or a } end
local NumberSequenceKeypoint = {}
function NumberSequenceKeypoint.new(t, v, e) return { Time = t, Value = v, Envelope = e or 0 } end
local NumberSequence = {}
function NumberSequence.new(a, b)
	if type(a) == "table" then return { Keypoints = a } end
	if b ~= nil then return { Keypoints = { { Time = 0, Value = a, Envelope = 0 }, { Time = 1, Value = b, Envelope = 0 } } } end
	return { Keypoints = { { Time = 0, Value = a, Envelope = 0 }, { Time = 1, Value = a, Envelope = 0 } } }
end
local ColorSequenceKeypoint = {}
function ColorSequenceKeypoint.new(t, c) return { Time = t, Value = c } end
local ColorSequence = {}
function ColorSequence.new(a, b)
	if getmetatable(a) ~= Color3 then return { Keypoints = a } end
	return { Keypoints = { { Time = 0, Value = a }, { Time = 1, Value = b or a } } }
end
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
-- Virtual-time scheduler (task.wait/delay/spawn/defer/cancel) and a TweenService that finishes tweens in virtual time.
local sched = { now = 0, seq = 0, q = {}, errors = {} }
local function schedAdd(t, co, args)
	sched.seq += 1
	table.insert(sched.q, { t = t, seq = sched.seq, co = co, args = args })
end
local function runCo(co, ...)
	local ok, err = coroutine.resume(co, ...)
	if not ok then table.insert(sched.errors, tostring(err)) end
end
function sched.advance(dt)
	local target = sched.now + dt
	while true do
		local best, bi = nil, 0
		for i, e in sched.q do
			if e.t <= target and (best == nil or e.t < best.t or (e.t == best.t and e.seq < best.seq)) then
				best, bi = e, i
			end
		end
		if best == nil then break end
		table.remove(sched.q, bi)
		if best.t > sched.now then sched.now = best.t end
		if coroutine.status(best.co) == "suspended" then runCo(best.co, unpack(best.args)) end
	end
	sched.now = target
end
local schedTask = {}
function schedTask.spawn(f, ...)
	local co = type(f) == "thread" and f or coroutine.create(f)
	runCo(co, ...)
	return co
end
function schedTask.defer(f, ...)
	local co = type(f) == "thread" and f or coroutine.create(f)
	schedAdd(sched.now, co, { ... })
	return co
end
function schedTask.delay(t, f, ...)
	local co = type(f) == "thread" and f or coroutine.create(f)
	schedAdd(sched.now + (t or 0), co, { ... })
	return co
end
function schedTask.wait(t)
	t = t or 0.03
	if coroutine.isyieldable() then
		schedAdd(sched.now + t, coroutine.running(), { t })
		return coroutine.yield()
	end
	sched.advance(t)
	return t
end
function schedTask.cancel(co)
	for i = #sched.q, 1, -1 do
		if sched.q[i].co == co then table.remove(sched.q, i) end
	end
	pcall(coroutine.close, co)
end
local schedEnv = {
	task = schedTask, wait = schedTask.wait, spawn = schedTask.spawn,
	delay = function(t, f) schedTask.delay(t, f) end,
	time = function() return sched.now end, tick = function() return 1000000 + sched.now end,
	os = { clock = function() return sched.now end, time = function() return 1000000 + math.floor(sched.now) end, date = os.date },
}
local TweenService = { created = {} }
function TweenService:Create(inst, info, goals)
	local tw = { Instance = inst, TweenInfo = info, Goals = goals, plays = 0, cancels = 0, Completed = Signal.new(),
		PlaybackState = Enum.PlaybackState.Begin }
	function tw:Play()
		if self.PlaybackState == Enum.PlaybackState.Playing then return end
		self.plays += 1
		self.PlaybackState = Enum.PlaybackState.Playing
		schedAdd(sched.now + (info.DelayTime or 0) + (info.Time or 1), coroutine.create(function() self:_finish() end), {})
	end
	function tw:_finish()
		if self.PlaybackState ~= Enum.PlaybackState.Playing then return end
		for k, v in goals do inst[k] = v end
		self.PlaybackState = Enum.PlaybackState.Completed
		self.Completed:Fire(Enum.PlaybackState.Completed)
	end
	function tw:Cancel()
		if self.PlaybackState ~= Enum.PlaybackState.Playing then return end
		self.cancels += 1
		self.PlaybackState = Enum.PlaybackState.Cancelled
		schedAdd(sched.now, coroutine.create(function() self.Completed:Fire(Enum.PlaybackState.Cancelled) end), {})
	end
	function tw:Destroy() end
	function tw:Pause() end
	table.insert(TweenService.created, tw)
	return tw
end
local env = { Instance = Instance, Enum = Enum, UDim2 = UDim2, UDim = UDim, Vector2 = Vector2, Color3 = Color3, TweenInfo = TweenInfo,
	debug = debugStub, game = mockGame({ TweenService = TweenService }) }
for k, v in schedEnv do env[k] = v end
local Mod = load_answer(env)
local function near(a, b) return a ~= nil and math.abs(a - b) < 1e-6 end
local GREEN, AMBER, RED = Color3.fromRGB(80, 200, 120), Color3.fromRGB(240, 180, 40), Color3.fromRGB(220, 60, 60)
local function count() return #TweenService.created end
local function last() return TweenService.created[#TweenService.created] end
local function sizeOf(tw) return tw.Goals.Size end
local function isSize(tw, fraction)
	local s = tw and tw.Goals.Size
	return s ~= nil and near(s.X.Scale, fraction) and near(s.Y.Scale, 1) and s.X.Offset == 0 and s.Y.Offset == 0
end

local fill = Instance.new("Frame")
local bar = Mod.new(fill)
check("creating the bar starts no tween", count() == 0)

bar:set(50, 100)
local t1 = last()
check("set creates one tween on the fill and plays it", count() == 1 and t1.Instance == fill and t1.plays == 1)
check("one tween carries both the Size and the BackgroundColor3 goals", t1.Goals.Size ~= nil and t1.Goals.BackgroundColor3 ~= nil)
check("the tween takes 0.2 s with Quad / Out easing",
	near(t1.TweenInfo.Time, 0.2) and t1.TweenInfo.EasingStyle == Enum.EasingStyle.Quad and t1.TweenInfo.EasingDirection == Enum.EasingDirection.Out)
check("50 of 100 is half the width, full height, in scale", isSize(t1, 0.5))
check("exactly 0.5 is amber (green needs more than 0.5)", sameColor(t1.Goals.BackgroundColor3, AMBER))

bar:set(51, 100)
local t2 = last()
check("0.51 is green", count() == 2 and isSize(t2, 0.51) and sameColor(t2.Goals.BackgroundColor3, GREEN))
check("a new set cancels the tween that is still playing", t1.cancels == 1)

bar:set(102, 200)
check("the same fraction again (0.51) creates no new tween", count() == 2 and t2.cancels == 0)

bar:set(25, 100)
check("exactly 0.25 is red (amber needs more than 0.25)", count() == 3 and sameColor(last().Goals.BackgroundColor3, RED) and isSize(last(), 0.25))
check("the previous tween was cancelled again", t2.cancels == 1)
bar:set(26, 100)
check("0.26 is amber", count() == 4 and sameColor(last().Goals.BackgroundColor3, AMBER))

bar:set(150, 100)
check("a value above max is clamped to a full green bar", count() == 5 and isSize(last(), 1) and sameColor(last().Goals.BackgroundColor3, GREEN))
bar:set(100, 100)
check("100 of 100 is the same fraction as the clamped one: no new tween", count() == 5)
bar:set(-5, 100)
check("a negative value is clamped to an empty red bar", count() == 6 and isSize(last(), 0) and sameColor(last().Goals.BackgroundColor3, RED))

local weird = { { 10, 0 }, { 10, -5 }, { 0 / 0, 100 }, { "x", 100 }, { 5, "y" }, { 7, 0 / 0 } }
local safe, empty = true, true
for _, pair in weird do
	bar:set(100, 100)
	local n = count()
	local ok = pcall(bar.set, bar, pair[1], pair[2])
	if not ok then safe = false end
	if ok and not (count() == n + 1 and isSize(last(), 0)) then empty = false end
end
check("a zero or negative max, NaN or a non-number never throws", safe)
check("... and each of them shows an empty bar (fraction 0)", empty)

sched.advance(1)
local before = count()
bar:set(75, 100)
check("after the tween finished a normal update still works", count() == before + 1 and isSize(last(), 0.75))
sched.advance(1)
check("the fill really ends at the last goal", near(fill.Size.X.Scale, 0.75) and sameColor(fill.BackgroundColor3, GREEN))
