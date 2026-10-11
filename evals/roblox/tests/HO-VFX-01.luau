-- Holdout test body HO-VFX-01 (frozen 2026-10-11; harness-owned, never shown to the model).
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
-- Vector3 and CFrame stand-ins (real maths: a position plus a 3x3 rotation, row-major).
local Vector3 = {}
local function V3(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, Vector3) end
Vector3.__index = function(v, k)
	if k == "Magnitude" then return math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z) end
	if k == "Unit" then
		local m = math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
		return V3(v.X / m, v.Y / m, v.Z / m)
	end
	return Vector3[k]
end
function Vector3.new(x, y, z) return V3(x or 0, y or 0, z or 0) end
Vector3.zero = V3(0, 0, 0)
Vector3.one = V3(1, 1, 1)
Vector3.xAxis = V3(1, 0, 0)
Vector3.yAxis = V3(0, 1, 0)
Vector3.zAxis = V3(0, 0, 1)
function Vector3.__add(a, b) return V3(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
function Vector3.__sub(a, b) return V3(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
function Vector3.__mul(a, b)
	if type(a) == "number" then return V3(a * b.X, a * b.Y, a * b.Z) end
	if type(b) == "number" then return V3(a.X * b, a.Y * b, a.Z * b) end
	return V3(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
function Vector3.__div(a, b)
	if type(b) == "number" then return V3(a.X / b, a.Y / b, a.Z / b) end
	return V3(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
end
function Vector3.__unm(a) return V3(-a.X, -a.Y, -a.Z) end
function Vector3.__eq(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
function Vector3.__tostring(v) return string.format("%g, %g, %g", v.X, v.Y, v.Z) end
function Vector3:Dot(o) return self.X * o.X + self.Y * o.Y + self.Z * o.Z end
function Vector3:Cross(o)
	return V3(self.Y * o.Z - self.Z * o.Y, self.Z * o.X - self.X * o.Z, self.X * o.Y - self.Y * o.X)
end
function Vector3:Lerp(o, t) return self + (o - self) * t end
function Vector3:FuzzyEq(o, eps)
	eps = eps or 1e-5
	return math.abs(self.X - o.X) <= eps and math.abs(self.Y - o.Y) <= eps and math.abs(self.Z - o.Z) <= eps
end

local CFrame = {}
local IDENT = { 1, 0, 0, 0, 1, 0, 0, 0, 1 }
local function CF(p, r) return setmetatable({ Position = p, X = p.X, Y = p.Y, Z = p.Z, _r = r }, CFrame) end
CFrame.__index = function(cf, k)
	local r = cf._r
	if k == "RightVector" then return V3(r[1], r[4], r[7]) end
	if k == "UpVector" then return V3(r[2], r[5], r[8]) end
	if k == "LookVector" then return V3(-r[3], -r[6], -r[9]) end
	if k == "Rotation" then return CF(V3(0, 0, 0), r) end
	return CFrame[k]
end
local function mm(a, b)
	local o = {}
	for i = 0, 2 do
		for j = 0, 2 do
			o[i * 3 + j + 1] = a[i * 3 + 1] * b[j + 1] + a[i * 3 + 2] * b[j + 4] + a[i * 3 + 3] * b[j + 7]
		end
	end
	return o
end
local function mv(r, v)
	return V3(r[1] * v.X + r[2] * v.Y + r[3] * v.Z, r[4] * v.X + r[5] * v.Y + r[6] * v.Z, r[7] * v.X + r[8] * v.Y + r[9] * v.Z)
end
local function tr(r) return { r[1], r[4], r[7], r[2], r[5], r[8], r[3], r[6], r[9] } end
function CFrame.lookAt(at, target, up)
	up = up or V3(0, 1, 0)
	local back = at - target
	local m = back.Magnitude
	if m == 0 then return CF(at, IDENT) end
	back = back / m
	local right = up:Cross(back)
	local rm = right.Magnitude
	if rm < 1e-9 then right = V3(1, 0, 0) else right = right / rm end
	local upv = back:Cross(right)
	return CF(at, { right.X, upv.X, back.X, right.Y, upv.Y, back.Y, right.Z, upv.Z, back.Z })
end
function CFrame.new(a, b, c)
	if a == nil then return CF(V3(0, 0, 0), IDENT) end
	if type(a) == "number" then return CF(V3(a, b, c), IDENT) end
	if b ~= nil then return CFrame.lookAt(a, b) end
	return CF(a, IDENT)
end
local function rx(a) local c, s = math.cos(a), math.sin(a) return { 1, 0, 0, 0, c, -s, 0, s, c } end
local function ry(a) local c, s = math.cos(a), math.sin(a) return { c, 0, s, 0, 1, 0, -s, 0, c } end
local function rz(a) local c, s = math.cos(a), math.sin(a) return { c, -s, 0, s, c, 0, 0, 0, 1 } end
function CFrame.Angles(x, y, z) return CF(V3(0, 0, 0), mm(mm(rx(x), ry(y)), rz(z))) end
CFrame.fromEulerAnglesXYZ = CFrame.Angles
function CFrame.fromEulerAnglesYXZ(x, y, z) return CF(V3(0, 0, 0), mm(mm(ry(y), rx(x)), rz(z))) end
CFrame.fromOrientation = CFrame.fromEulerAnglesYXZ
CFrame.identity = CF(V3(0, 0, 0), IDENT)
function CFrame.__mul(a, b)
	if getmetatable(b) == CFrame then return CF(a.Position + mv(a._r, b.Position), mm(a._r, b._r)) end
	return a.Position + mv(a._r, b)
end
function CFrame.__add(a, v) return CF(a.Position + v, a._r) end
function CFrame.__sub(a, v) return CF(a.Position - v, a._r) end
function CFrame:Inverse() local rt = tr(self._r) return CF(-mv(rt, self.Position), rt) end
function CFrame:PointToWorldSpace(v) return self * v end
function CFrame:PointToObjectSpace(v) return self:Inverse() * v end
function CFrame:VectorToWorldSpace(v) return mv(self._r, v) end
function CFrame:VectorToObjectSpace(v) return mv(tr(self._r), v) end
function CFrame:ToWorldSpace(cf) return self * cf end
function CFrame:ToObjectSpace(cf) return self:Inverse() * cf end
function CFrame:FuzzyEq(o, eps)
	eps = eps or 1e-5
	if not self.Position:FuzzyEq(o.Position, eps) then return false end
	for i = 1, 9 do if math.abs(self._r[i] - o._r[i]) > eps then return false end end
	return true
end
local function typeofGeom(x)
	if type(x) == "table" then
		local mt = getmetatable(x)
		if mt == Vector3 then return "Vector3" end
		if mt == CFrame then return "CFrame" end
	end
	return typeof(x)
end
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
local debrisLog = {}
local ws = Instance.new("Folder")
ws.Terrain = Instance.new("Terrain", ws)
local Debris = { AddItem = function(_, item, t) table.insert(debrisLog, { item = item, t = t }) end }
local env = {
	Instance = Instance, Enum = Enum, Vector3 = Vector3, CFrame = CFrame, Color3 = Color3, ColorSequence = ColorSequence,
	ColorSequenceKeypoint = ColorSequenceKeypoint, NumberSequence = NumberSequence, NumberSequenceKeypoint = NumberSequenceKeypoint,
	NumberRange = NumberRange, typeof = function(x) if type(x) == "table" and getmetatable(x) == IMT then return "Instance" end return typeofGeom(x) end,
	debug = debugStub, game = mockGame({ Debris = Debris }), workspace = ws,
}
local Mod = load_answer(env)
local function near(a, b) return a ~= nil and math.abs(a - b) < 1e-6 end
local function posOf(part)
	if part.Position ~= nil then return part.Position end
	if part.CFrame ~= nil then return part.CFrame.Position end
	return nil
end
local function firstValue(seq) return seq and seq.Keypoints and seq.Keypoints[1] and seq.Keypoints[1].Value end
local function allValues(seq)
	local out = {}
	for _, k in (seq and seq.Keypoints) or {} do table.insert(out, k.Value) end
	return out
end

local points = { Vector3.new(0, 5, 0), Vector3.new(10, 6, 2), Vector3.new(20, 4, -3), Vector3.new(30, 5, 0) }
local folder = Instance.new("Folder")
local beams = Mod.zap(folder, points)
check("zap returns one Beam per gap between points (3 for 4 points)", type(beams) == "table" and #beams == 3 and beams[1] ~= nil and beams[1].ClassName == "Beam")

local parts = descendantsOfClass(folder, "Part")
check("one Part per point is created under the given parent", #parts == 4)
local flagsOk, atPoints = true, true
for _, part in parts do
	if part.Anchored ~= true or part.CanCollide ~= false or part.Transparency ~= 1 then flagsOk = false end
	local found = false
	local p = posOf(part)
	for _, point in points do
		if p ~= nil and p:FuzzyEq(point, 1e-6) then found = true end
	end
	if not found then atPoints = false end
	if #descendantsOfClass(part, "Attachment") ~= 1 or part.Parent ~= folder then flagsOk = false end
end
check("the parts are invisible, anchored, non-colliding, directly under the parent and hold one Attachment each", flagsOk)
check("each part sits at one of the points", atPoints)

local function partAt(point)
	for _, part in parts do
		local p = posOf(part)
		if p and p:FuzzyEq(point, 1e-6) then return part end
	end
	return nil
end
local linked, owned = true, true
for i = 1, 3 do
	local b = beams[i]
	local from, to = partAt(points[i]), partAt(points[i + 1])
	if not (b and from and to and b.Attachment0 and b.Attachment1) then
		linked = false
		owned = false
	else
		if b.Attachment0.Parent ~= from or b.Attachment1.Parent ~= to then linked = false end
		if b.Parent ~= from then owned = false end
	end
end
check("beam i runs from the attachment at point i to the one at point i + 1", linked)
check("each beam is parented to the part it starts at", owned)

local b1 = beams[1]
check("beam color is a ColorSequence of (120, 200, 255)", b1 ~= nil and #allValues(b1.Color) >= 1 and (function()
	for _, v in allValues(b1.Color) do if not sameColor(v, Color3.fromRGB(120, 200, 255), 1e-6) then return false end end
	return true
end)())
check("Width0 = 0.6 and Width1 = 0.2", b1 ~= nil and near(b1.Width0, 0.6) and near(b1.Width1, 0.2))
check("Segments = 12, FaceCamera = true, LightEmission = 1", b1 ~= nil and b1.Segments == 12 and b1.FaceCamera == true and b1.LightEmission == 1)
check("Transparency is a NumberSequence of 0.1", b1 ~= nil and near(firstValue(b1.Transparency), 0.1))

local lifetimes = {}
for _, entry in debrisLog do lifetimes[entry.item] = entry.t end
local cleaned = true
for _, part in parts do
	if lifetimes[part] == nil or not near(lifetimes[part], 0.4) then cleaned = false end
end
check("every part is handed to Debris:AddItem with a lifetime of 0.4 s", cleaned)

local before = #debrisLog
local f2 = Instance.new("Folder")
local none1 = Mod.zap(f2, {})
local none2 = Mod.zap(f2, { Vector3.new(1, 1, 1) })
check("fewer than two points: an empty table, nothing created, nothing scheduled",
	type(none1) == "table" and #none1 == 0 and type(none2) == "table" and #none2 == 0 and #f2:GetChildren() == 0 and #debrisLog == before)

local f3 = Instance.new("Folder")
local okBad = pcall(Mod.zap, f3, { Vector3.new(0, 0, 0), "not a point", Vector3.new(1, 1, 1) })
check("a point that is not a Vector3 raises an error before anything is created", okBad == false and #f3:GetChildren() == 0 and #debrisLog == before)
