local ret, env = load_answer()
local Quat = (type(ret) == "table" and ret.fromAxisAngle ~= nil and ret) or (type(ret) == "table" and ret.Quat) or env.Quat
check("the module returns a Quat table", type(Quat) == "table" and type(Quat.fromAxisAngle) == "function"
	and type(Quat.mul) == "function" and type(Quat.rotate) == "function" and type(Quat.slerp) == "function")

local function near(a, b, eps)
	return type(a) == "number" and math.abs(a - b) <= (eps or 1e-6)
end
local function vnear(v, x, y, z)
	return type(v) == "table" and near(v.x, x) and near(v.y, y) and near(v.z, z)
end
local function unit(q)
	return near(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z, 1)
end
local X, Z = { x = 1, y = 0, z = 0 }, { x = 0, y = 0, z = 1 }
local half = math.pi / 2

local qz = Quat.fromAxisAngle(Z, half)
local qx = Quat.fromAxisAngle(X, half)
check("fromAxisAngle gives a unit quaternion with w = cos(angle / 2)", unit(qz) and near(qz.w, math.cos(half / 2)))
check("90 degrees about +Z turns (1, 0, 0) into (0, 1, 0)", vnear(Quat.rotate(qz, { x = 1, y = 0, z = 0 }), 0, 1, 0))
check("mul(qx, qz) applies qz first: (1, 0, 0) -> (0, 0, 1)", vnear(Quat.rotate(Quat.mul(qx, qz), { x = 1, y = 0, z = 0 }), 0, 0, 1))
check("mul(qz, qx) applies qx first: (0, 1, 0) -> (0, 0, 1)", vnear(Quat.rotate(Quat.mul(qz, qx), { x = 0, y = 1, z = 0 }), 0, 0, 1))
check("a non-unit axis is normalised", vnear(Quat.rotate(Quat.fromAxisAngle({ x = 0, y = 0, z = 5 }, half), { x = 1, y = 0, z = 0 }), 0, 1, 0))

local id = Quat.fromAxisAngle(Z, 0)
local mid = Quat.slerp(id, qz, 0.5)
check("slerp halfway between identity and 90 degrees about Z is 45 degrees", unit(mid)
	and vnear(Quat.rotate(mid, { x = 1, y = 0, z = 0 }), math.cos(math.pi / 4), math.sin(math.pi / 4), 0))
check("slerp at t = 0 and t = 1 returns the end rotations", vnear(Quat.rotate(Quat.slerp(id, qz, 0), { x = 1, y = 0, z = 0 }), 1, 0, 0)
	and vnear(Quat.rotate(Quat.slerp(id, qz, 1), { x = 1, y = 0, z = 0 }), 0, 1, 0))
local negated = { w = -qz.w, x = -qz.x, y = -qz.y, z = -qz.z }
check("slerp takes the short way when the second quaternion is negated (q and -q are the same rotation)",
	vnear(Quat.rotate(Quat.slerp(id, negated, 0.5), { x = 1, y = 0, z = 0 }), math.cos(math.pi / 4), math.sin(math.pi / 4), 0))
local tiny = Quat.fromAxisAngle(Z, 1e-7)
local s = Quat.slerp(id, tiny, 0.5)
check("slerp between nearly equal rotations is finite and unit length", s.w == s.w and s.x == s.x and unit(s))

local q = Quat.fromAxisAngle({ x = 1, y = 2, z = 3 }, 0.7)
local v = Quat.rotate(q, { x = 2, y = -1, z = 0.5 })
check("rotation keeps vector length", near(v.x * v.x + v.y * v.y + v.z * v.z, 4 + 1 + 0.25))
local back = Quat.rotate(Quat.mul(Quat.fromAxisAngle({ x = 1, y = 2, z = 3 }, -0.7), q), { x = 2, y = -1, z = 0.5 })
check("a rotation followed by its inverse returns the original vector", vnear(back, 2, -1, 0.5))
