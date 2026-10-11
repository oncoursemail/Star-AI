-- Holdout test body HO-BLD-01 (frozen 2026-10-11; harness-owned, never shown to the model).
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
local Mod = load_answer({ Vector3 = Vector3, CFrame = CFrame, typeof = typeofGeom, debug = debugStub })
local function V(x, y, z) return Vector3.new(x, y, z) end

local center = CFrame.new(10, 5, -3) * CFrame.Angles(0, math.rad(90), 0)
local radius, count = 8, 6
local ring = Mod.cframes(center, radius, count)
check("6 CFrames are returned", type(ring) == "table" and #ring == 6 and typeofGeom(ring[1]) == "CFrame")

local posOk, lookOk, levelOk = true, true, true
local firstOk = false
for i = 1, count do
	local theta = 2 * math.pi * (i - 1) / count
	local expected = center * V(radius * math.sin(theta), 0, -radius * math.cos(theta))
	local cf = ring[i]
	if cf == nil then
		posOk, lookOk, levelOk = false, false, false
	else
		if not cf.Position:FuzzyEq(expected, 1e-6) then posOk = false end
		local toCenter = (center.Position - cf.Position).Unit
		if not cf.LookVector:FuzzyEq(toCenter, 1e-6) then lookOk = false end
		if math.abs(cf.Position.Y - center.Position.Y) > 1e-9 then levelOk = false end
	end
end
check("each position is the center's local offset (radius * sin, 0, -radius * cos) of the angle 2 * pi * (i - 1) / count", posOk)
check("every CFrame faces the center", lookOk)
check("the ring is horizontal: every element has the center's height", levelOk)
check("element 1 is straight ahead of the center (rotating the center rotates the ring)",
	ring[1] ~= nil and ring[1].Position:FuzzyEq(V(2, 5, -3), 1e-6) and not ring[1].Position:FuzzyEq(V(10, 5, -11), 1e-6))
check("elements are evenly spaced: neighbours are the same distance apart",
	ring[1] ~= nil and ring[2] ~= nil and ring[6] ~= nil and math.abs((ring[1].Position - ring[2].Position).Magnitude - (ring[1].Position - ring[6].Position).Magnitude) < 1e-6
	and math.abs((ring[1].Position - ring[2].Position).Magnitude - radius) < 1e-6)

local flat = Mod.cframes(CFrame.new(0, 0, 0), 4, 4)
local expectedFlat = { V(0, 0, -4), V(4, 0, 0), V(0, 0, 4), V(-4, 0, 0) }
local flatOk = #flat == 4
for i = 1, 4 do
	if flat[i] == nil or not flat[i].Position:FuzzyEq(expectedFlat[i], 1e-6) then flatOk = false end
end
check("an unrotated center: 4 elements at -Z, +X, +Z, -X", flatOk)

local single = Mod.cframes(CFrame.new(1, 2, 3), 5, 1)
check("count 1 gives one element straight ahead, facing the center",
	#single == 1 and single[1].Position:FuzzyEq(V(1, 2, -2), 1e-6) and single[1].LookVector:FuzzyEq(V(0, 0, 1), 1e-6))

local before = center.Position
Mod.cframes(center, 3, 3)
check("the center CFrame is not modified", center.Position:FuzzyEq(before, 1e-12))

local rejected = true
for _, args in {
	{ center, 8, 0 }, { center, 8, -2 }, { center, 8, 2.5 }, { center, 8, "6" }, { center, 8, 0 / 0 }, { center, 8, math.huge },
	{ center, 0, 6 }, { center, -3, 6 }, { center, 0 / 0, 6 }, { center, math.huge, 6 }, { center, "8", 6 },
} do
	if pcall(Mod.cframes, args[1], args[2], args[3]) then rejected = false end
end
check("a count that is not a positive integer, or a radius that is not a positive finite number, raises an error", rejected)
