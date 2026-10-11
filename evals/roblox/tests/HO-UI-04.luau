-- Holdout test body HO-UI-04 (frozen 2026-10-11; harness-owned, never shown to the model).
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
local env = { Instance = Instance, Enum = Enum, UDim2 = UDim2, UDim = UDim, Vector2 = Vector2, Color3 = Color3, debug = debugStub,
	game = mockGame({}) }
local Mod = load_answer(env)
local BLUE, DARK = Color3.fromRGB(70, 130, 255), Color3.fromRGB(45, 45, 55)

local bar = Instance.new("Frame")
local pages = { Stats = Instance.new("Frame"), Items = Instance.new("Frame"), Map = Instance.new("Frame") }
for _, page in pages do page.Visible = true end
local tabs = Mod.new(bar, pages, { "Stats", "Items", "Map" })

local function btn(name) return bar:FindFirstChild("Tab_" .. name) end
local function visibleSet()
	local out = {}
	for name, page in pages do
		if page.Visible == true then table.insert(out, name) end
	end
	table.sort(out)
	return table.concat(out, ",")
end
local function colors(active)
	for _, name in { "Stats", "Items", "Map" } do
		local b = btn(name)
		local want = if name == active then BLUE else DARK
		if b == nil or not sameColor(b.BackgroundColor3, want) then return false end
	end
	return true
end

local buttons = descendantsOfClass(bar, "TextButton")
check("one TextButton per name is created inside the tab bar", #buttons == 3 and btn("Stats") ~= nil and btn("Items") ~= nil and btn("Map") ~= nil)
local texts, orders = true, true
for i, name in { "Stats", "Items", "Map" } do
	local b = btn(name)
	if b == nil or b.Text ~= name then texts = false end
	if b == nil or b.LayoutOrder ~= i then orders = false end
end
check("each button shows its name", texts)
check("LayoutOrder follows the order list", orders)
local layouts = descendantsOfClass(bar, "UIListLayout")
check("a single horizontal UIListLayout sorted by LayoutOrder lines the buttons up",
	#layouts == 1 and layouts[1].FillDirection == Enum.FillDirection.Horizontal and layouts[1].SortOrder == Enum.SortOrder.LayoutOrder)
check("the first name is selected after creation", tabs:selected() == "Stats")
check("only the first page is visible", visibleSet() == "Stats" and pages.Items.Visible == false and pages.Map.Visible == false)
check("the selected button is blue and the others are dark", colors("Stats"))

check("select returns true for a known tab", tabs:select("Items") == true)
check("selecting Items shows only Items", visibleSet() == "Items" and tabs:selected() == "Items")
check("the highlight moved to Items", colors("Items"))
check("an unknown name returns false", tabs:select("Nope") == false)
check("an unknown name changes nothing", visibleSet() == "Items" and tabs:selected() == "Items" and colors("Items"))

btn("Map").Activated:Fire()
check("clicking a button (Activated) selects its tab", tabs:selected() == "Map" and visibleSet() == "Map" and colors("Map"))
check("selecting the same tab twice is fine", tabs:select("Map") == true and visibleSet() == "Map")
for _ = 1, 3 do
	tabs:select("Stats")
	tabs:select("Map")
end
local connections = 0
for _, name in { "Stats", "Items", "Map" } do connections += liveCount(btn(name).Activated) end
check("each button has exactly one click connection however often select ran", connections == 3)

tabs:destroy()
for _, b in buttons do
	pcall(function() b.Activated:Fire() end)
end
check("after destroy the buttons are gone", btn("Stats") == nil and btn("Items") == nil and btn("Map") == nil)
check("after destroy clicks no longer change the selection", tabs:selected() == "Map")
local alive = 0
for _, b in buttons do alive += liveCount(b.Activated) end
check("after destroy no old button keeps a live click connection", alive == 0)
