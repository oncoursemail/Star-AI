```luau
--!strict
-- Unit quaternions as plain tables {w, x, y, z}. v' = q v q^-1; mul(a, b) applies b first, then a.
export type Quat = { w: number, x: number, y: number, z: number }
export type Vec = { x: number, y: number, z: number }

local Quat = {}

function Quat.normalize(q: Quat): Quat
	local len = math.sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z)
	if len < 1e-12 then
		return { w = 1, x = 0, y = 0, z = 0 }
	end
	return { w = q.w / len, x = q.x / len, y = q.y / len, z = q.z / len }
end

function Quat.fromAxisAngle(axis: Vec, angle: number): Quat
	local len = math.sqrt(axis.x * axis.x + axis.y * axis.y + axis.z * axis.z)
	if len < 1e-12 then
		return { w = 1, x = 0, y = 0, z = 0 }
	end
	local s = math.sin(angle / 2) / len
	return { w = math.cos(angle / 2), x = axis.x * s, y = axis.y * s, z = axis.z * s }
end

-- Hamilton product.
function Quat.mul(a: Quat, b: Quat): Quat
	return {
		w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
		x = a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
		y = a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
		z = a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
	}
end

function Quat.rotate(q: Quat, v: Vec): Vec
	local conj = { w = q.w, x = -q.x, y = -q.y, z = -q.z }
	local r = Quat.mul(Quat.mul(q, { w = 0, x = v.x, y = v.y, z = v.z }), conj)
	return { x = r.x, y = r.y, z = r.z }
end

function Quat.slerp(a: Quat, b: Quat, t: number): Quat
	local d = a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z
	local bw, bx, by, bz = b.w, b.x, b.y, b.z
	if d < 0 then
		-- q and -q are the same rotation: flip to take the short way round.
		d, bw, bx, by, bz = -d, -bw, -bx, -by, -bz
	end
	local s0, s1
	if d > 0.9995 then
		-- Nearly parallel: sin(theta) is close to 0, so use normalised lerp.
		s0, s1 = 1 - t, t
	else
		local theta = math.acos(d)
		local sinTheta = math.sin(theta)
		s0 = math.sin((1 - t) * theta) / sinTheta
		s1 = math.sin(t * theta) / sinTheta
	end
	return Quat.normalize({
		w = s0 * a.w + s1 * bw,
		x = s0 * a.x + s1 * bx,
		y = s0 * a.y + s1 * by,
		z = s0 * a.z + s1 * bz,
	})
end

return Quat
```
