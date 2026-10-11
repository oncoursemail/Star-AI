```luau
--!strict
local Easing = {}

local function clamp01(t: number): number
	if t < 0 then
		return 0
	elseif t > 1 then
		return 1
	end
	return t
end

function Easing.linear(t: number): number
	return clamp01(t)
end

function Easing.inQuad(t: number): number
	local x = clamp01(t)
	return x * x
end

function Easing.outQuad(t: number): number
	local x = clamp01(t)
	return 1 - (1 - x) * (1 - x)
end

function Easing.inOutQuad(t: number): number
	local x = clamp01(t)
	if x < 0.5 then
		return 2 * x * x
	end
	return 1 - ((-2 * x + 2) ^ 2) / 2
end

function Easing.outCubic(t: number): number
	local x = clamp01(t)
	return 1 - (1 - x) ^ 3
end

function Easing.outBack(t: number): number
	local x = clamp01(t)
	local c1 = 1.70158
	local c3 = c1 + 1
	return 1 + c3 * (x - 1) ^ 3 + c1 * (x - 1) ^ 2
end

function Easing.outElastic(t: number): number
	local x = clamp01(t)
	if x == 0 then
		return 0
	elseif x == 1 then
		return 1
	end
	local c4 = (2 * math.pi) / 3
	return 2 ^ (-10 * x) * math.sin((x * 10 - 0.75) * c4) + 1
end

function Easing.lerp(a: number, b: number, t: number, name: string?): number
	local fn = (Easing :: any)[name or "linear"]
	return a + (b - a) * fn(t)
end

return Easing
```
