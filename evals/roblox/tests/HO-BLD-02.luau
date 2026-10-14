-- Holdout test body HO-BLD-02 (frozen 2026-10-11; harness-owned, never shown to the model).
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
local obstacles = {}
local rays = {}
local ws = Instance.new("Folder")
local RaycastParams = {}
function RaycastParams.new()
	return { FilterType = Enum.RaycastFilterType.Exclude, FilterDescendantsInstances = {}, IgnoreWater = false }
end
local function skipped(part, params)
	local listed = false
	for _, inst in params.FilterDescendantsInstances do
		if part == inst or part:IsDescendantOf(inst) then listed = true break end
	end
	if params.FilterType == Enum.RaycastFilterType.Include then return not listed end
	return listed
end
-- the first sphere the segment origin -> origin + direction enters (the length of direction is the length of the ray)
ws.Raycast = function(_, origin, direction, params)
	params = params or RaycastParams.new()
	table.insert(rays, { origin = origin, direction = direction, params = params })
	local a = direction:Dot(direction)
	if a == 0 then return nil end
	local best, bestT
	for _, o in obstacles do
		if not skipped(o.part, params) then
			local oc = origin - o.center
			local b = 2 * direction:Dot(oc)
			local c = oc:Dot(oc) - o.radius * o.radius
			local disc = b * b - 4 * a * c
			if disc >= 0 then
				local t = (-b - math.sqrt(disc)) / (2 * a)
				if t >= 0 and t <= 1 and (bestT == nil or t < bestT) then best, bestT = o, t end
			end
		end
	end
	if best == nil then return nil end
	return { Instance = best.part, Position = origin + direction * bestT, Distance = bestT * math.sqrt(a) }
end

local function part(name, parent, position)
	local p = Instance.new("Part", parent)
	p.Name = name
	p.Position = position
	return p
end
local function V(x, y, z) return Vector3.new(x, y, z) end

local env = { Instance = Instance, Enum = Enum, Vector3 = Vector3, CFrame = CFrame, RaycastParams = RaycastParams, workspace = ws,
	typeof = typeofGeom, debug = debugStub, game = mockGame({ Workspace = ws }) }
local Mod = load_answer(env)

local map = Instance.new("Folder", ws)
local me = Instance.new("Model", ws)
local body = part("Torso", me, V(1.5, 5, 0))
local target = part("Target", map, V(30, 5, 0))
local wall = part("Wall", map, V(15, 5, 0))
local eye = V(0, 5, 0)

obstacles = { { part = body, center = body.Position, radius = 1 }, { part = target, center = target.Position, radius = 2 },
	{ part = wall, center = wall.Position, radius = 3 } }
local ignore = { me }
check("a wall between the eye and the target blocks the view", Mod.canSee(eye, target, ignore) == false)
check("the ray is as long as the distance to the target (not a unit vector): the last ray reaches the target",
	#rays >= 1 and rays[#rays].origin == eye and rays[#rays].direction:FuzzyEq(target.Position - eye, 1e-6))

obstacles = { { part = body, center = body.Position, radius = 1 }, { part = target, center = target.Position, radius = 2 } }
check("with a clear line the target is seen, and the viewer's own body (in the ignore list) does not block", Mod.canSee(eye, target, ignore) == true)
check("without an ignore list the viewer's own body blocks", Mod.canSee(eye, target, nil) == false)
check("an empty ignore list works the same", Mod.canSee(eye, target, {}) == false)
check("the caller's ignore list is not modified", #ignore == 1 and ignore[1] == me)

local side = part("Side", map, V(15, 5, 20))
obstacles = { { part = body, center = body.Position, radius = 1 }, { part = target, center = target.Position, radius = 2 },
	{ part = side, center = side.Position, radius = 3 } }
check("an obstacle beside the line does not block", Mod.canSee(eye, target, { me }) == true)

local behind = part("Behind", map, V(45, 5, 0))
obstacles = { { part = target, center = target.Position, radius = 2 }, { part = behind, center = behind.Position, radius = 3 } }
check("something behind the target does not matter", Mod.canSee(eye, target, { me }) == true)

local far = part("Far", map, V(400, 5, 0))
local wall2 = part("Wall2", map, V(250, 5, 0))
obstacles = { { part = far, center = far.Position, radius = 2 }, { part = wall2, center = wall2.Position, radius = 3 } }
check("a far target is still reached by the ray (400 studs, blocked by a wall at 250)", Mod.canSee(eye, far, {}) == false)
obstacles = { { part = far, center = far.Position, radius = 2 } }
check("a far target with a clear line is seen", Mod.canSee(eye, far, {}) == true)

local nearTarget = part("Near", map, V(1.5, 5, 0))
local ghost = part("Ghost", me, V(0.8, 5, 0.1))
obstacles = { { part = ghost, center = ghost.Position, radius = 0.5 }, { part = nearTarget, center = nearTarget.Position, radius = 0.5 } }
check("a part of the ignored model between the eye and a near target does not block", Mod.canSee(eye, nearTarget, { me }) == true)

local result = Mod.canSee(eye, target, { me })
check("canSee returns a real boolean", type(result) == "boolean")
