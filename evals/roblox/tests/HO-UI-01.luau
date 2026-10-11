-- Holdout test body HO-UI-01 (frozen 2026-10-11; harness-owned, never shown to the model).
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
local env = { Instance = Instance, Enum = Enum, UDim = UDim, UDim2 = UDim2, Vector2 = Vector2, Color3 = Color3, debug = debugStub,
	game = mockGame({}) }
local Mod = load_answer(env)
local function near(a, b) return a ~= nil and math.abs(a - b) < 1e-6 end

local playerGui = Instance.new("Folder")
local bar = Mod.build(playerGui, 5)
local gui = playerGui:FindFirstChild("Hotbar")
check("a ScreenGui named Hotbar with ResetOnSpawn = false is parented to the PlayerGui",
	gui ~= nil and gui.ClassName == "ScreenGui" and gui.ResetOnSpawn == false and gui.Parent == playerGui)
check("build returns the Frame named Bar inside that ScreenGui", bar ~= nil and bar.ClassName == "Frame" and bar.Name == "Bar" and bar.Parent == gui)
check("Bar is anchored bottom-center", bar.AnchorPoint == Vector2.new(0.5, 1) and near(bar.Position.X.Scale, 0.5) and near(bar.Position.Y.Scale, 0.98)
	and bar.Position.X.Offset == 0 and bar.Position.Y.Offset == 0)
check("Bar is 60% of the screen width with no pixel offset", near(bar.Size.X.Scale, 0.6) and bar.Size.X.Offset == 0 and bar.Size.Y.Offset == 0)
check("Bar has a transparent background", bar.BackgroundTransparency == 1)
local ratio = bar:FindFirstChildOfClass("UIAspectRatioConstraint")
check("a UIAspectRatioConstraint with AspectRatio = slotCount keeps the bar's shape", ratio ~= nil and ratio.AspectRatio == 5)
local layouts = descendantsOfClass(bar, "UIListLayout")
local layout = layouts[1]
check("exactly one UIListLayout arranges the slots", #layouts == 1 and layout.Parent == bar)
check("the layout is horizontal, sorted by LayoutOrder and centered",
	layout.FillDirection == Enum.FillDirection.Horizontal and layout.SortOrder == Enum.SortOrder.LayoutOrder
	and layout.HorizontalAlignment == Enum.HorizontalAlignment.Center)
check("the padding is 0.01 in scale with no pixels", near(layout.Padding.Scale, 0.01) and layout.Padding.Offset == 0)

local slots = descendantsOfClass(bar, "TextButton")
check("there are 5 TextButton slots", #slots == 5)
local named, ordered, labelled, tall = true, true, true, true
for i = 1, 5 do
	local slot = bar:FindFirstChild("Slot" .. i)
	if slot == nil or slot.ClassName ~= "TextButton" then
		named = false
	else
		if slot.LayoutOrder ~= i then ordered = false end
		if slot.Text ~= tostring(i) then labelled = false end
		if not (near(slot.Size.Y.Scale, 1) and slot.Size.Y.Offset == 0) then tall = false end
	end
end
check("slots are named Slot1..Slot5 with LayoutOrder = their number", named and ordered)
check("slot text is the number as a string", labelled)
check("every slot has full height in scale", tall)
local first = bar:FindFirstChild("Slot1")
local width = first and first.Size.X.Scale or 0
local total = 5 * width + 4 * layout.Padding.Scale
check("the slots and the gaps between them fill the bar without overflowing (95% to 100%)", total <= 1 + 1e-6 and total >= 0.95)
local same = true
for i = 2, 5 do
	local s = bar:FindFirstChild("Slot" .. i)
	if s == nil or not near(s.Size.X.Scale, width) then same = false end
end
check("all slots have the same width", same)

local noPixels = true
for _, d in gui:GetDescendants() do
	for _, prop in { "Size", "Position" } do
		local v = d[prop]
		if v ~= nil and (v.X.Offset ~= 0 or v.Y.Offset ~= 0) then noPixels = false end
	end
end
check("no Size or Position anywhere uses a pixel Offset", noPixels)

local other = Instance.new("Folder")
local bar3 = Mod.build(other, 3)
local aspect3 = bar3:FindFirstChildOfClass("UIAspectRatioConstraint")
local slot3 = bar3:FindFirstChild("Slot1")
local pad3 = bar3:FindFirstChildOfClass("UIListLayout").Padding.Scale
check("slotCount 3 gives 3 slots, aspect ratio 3 and a fitting width",
	#descendantsOfClass(bar3, "TextButton") == 3 and aspect3 ~= nil and aspect3.AspectRatio == 3
	and slot3 ~= nil and 3 * slot3.Size.X.Scale + 2 * pad3 <= 1 + 1e-6 and 3 * slot3.Size.X.Scale + 2 * pad3 >= 0.95)

local refusedAll, cleanAll = true, true
for _, bad in { 0, 11, 2.5, -1, "5", true, 0 / 0, math.huge } do
	local pg = Instance.new("Folder")
	local ok = pcall(Mod.build, pg, bad)
	if ok then refusedAll = false end
	if #pg:GetChildren() > 0 then cleanAll = false end
end
local pgNil = Instance.new("Folder")
if pcall(Mod.build, pgNil, nil) then refusedAll = false end
check("a slotCount that is not a whole number from 1 to 10 raises an error", refusedAll)
check("a refused call creates nothing in the PlayerGui", cleanAll and #pgNil:GetChildren() == 0)
