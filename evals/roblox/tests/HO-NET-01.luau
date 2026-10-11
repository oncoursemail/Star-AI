-- Holdout test body HO-NET-01 (frozen 2026-10-11; harness-owned, never shown to the model).
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
local Mod = load_answer({ Vector3 = Vector3, typeof = typeofGeom, debug = debugStub })
local function P(x, y, z) return Vector3.new(x, y, z) end

local g = Mod.new(20, 1.5) -- 20 studs/s * 1.5 tolerance = 30 studs per second
check("the first sample of a player is allowed", g:sample(1, P(0, 0, 0), 100) == true)
check("a normal step (7 studs in 0.5 s, limit 15) is allowed", g:sample(1, P(7, 0, 0), 100.5) == true)
check("a step of exactly the limit (15 studs in 0.5 s) is allowed", g:sample(1, P(22, 0, 0), 101) == true)
check("a step just over the limit is rejected", g:sample(1, P(22 + 15.5, 0, 0), 101.5) == false)
check("a rejected sample does not move the baseline: a step from the old place is allowed", g:sample(1, P(10, 0, 0), 102) == true)
check("the teleport destination is still rejected when sampled again", g:sample(1, P(500, 0, 0), 102.5) == false and g:sample(1, P(500, 0, 0), 103) == false)
check("vertical movement is ignored (falling 900 studs while standing still horizontally)", g:sample(1, P(10, 900, 0), 104) == true)
check("only the horizontal distance counts when both are present", g:sample(1, P(30, -900, 40), 104.5) == false)
check("a sample with dt = 0 is rejected", g:sample(1, P(10, 900, 0), 104) == false)
check("a sample from the past (dt < 0) is rejected", g:sample(1, P(10, 900, 0), 103) == false)
check("rejected samples with dt <= 0 left the baseline alone", g:sample(1, P(11, 900, 0), 105) == true)
check("another player is tracked separately (first sample allowed)", g:sample(2, P(1000, 0, 0), 50) == true)
g:forget(1)
check("after forget the player's next sample counts as a first sample", g:sample(1, P(9999, 0, 0), 106) == true)

local h = Mod.new(20, 1.5)
h:sample(3, P(0, 0, 0), 0)
check("a 100 stud jump in 1 s is rejected", h:sample(3, P(100, 0, 0), 1) == false)
check("still rejected at t = 3 (limit 90 from the last allowed sample)", h:sample(3, P(100, 0, 0), 3) == false)
check("the allowance grows with the time since the last allowed sample", h:sample(3, P(80, 0, 0), 3.5) == true)

local k = Mod.new(10, 3)
k:sample(4, P(0, 0, 0), 10)
check("tolerance multiplies the limit: 29 studs in 1 s with 10 * 3 is allowed", k:sample(4, P(29, 0, 5), 11) == true)
check("31 studs in 1 s with 10 * 3 is rejected", k:sample(4, P(29 + 31, 0, 5), 12) == false)
