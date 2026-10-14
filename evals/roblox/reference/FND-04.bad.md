```luau
--!strict
-- Two classic bugs: the product is multiplied in the wrong order and slerp never flips to the short path.
type Quat = { w: number, x: number, y: number, z: number }
type Vec = { x: number, y: number, z: number }
local Quat = {}

function Quat.fromAxisAngle(axis: Vec, angle: number): Quat
	local len = math.sqrt(axis.x * axis.x + axis.y * axis.y + axis.z * axis.z)
	local s = math.sin(angle / 2) / len
	return { w = math.cos(angle / 2), x = axis.x * s, y = axis.y * s, z = axis.z * s }
end

local function hamilton(a: Quat, b: Quat): Quat
	return {
		w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
		x = a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
		y = a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
		z = a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
	}
end

function Quat.mul(a: Quat, b: Quat): Quat
	return hamilton(b, a)
end

function Quat.rotate(q: Quat, v: Vec): Vec
	local r = hamilton(hamilton(q, { w = 0, x = v.x, y = v.y, z = v.z }), { w = q.w, x = -q.x, y = -q.y, z = -q.z })
	return { x = r.x, y = r.y, z = r.z }
end

function Quat.slerp(a: Quat, b: Quat, t: number): Quat
	local r = { w = a.w + (b.w - a.w) * t, x = a.x + (b.x - a.x) * t, y = a.y + (b.y - a.y) * t, z = a.z + (b.z - a.z) * t }
	local len = math.sqrt(r.w * r.w + r.x * r.x + r.y * r.y + r.z * r.z)
	return { w = r.w / len, x = r.x / len, y = r.y / len, z = r.z / len }
end

return Quat
```
