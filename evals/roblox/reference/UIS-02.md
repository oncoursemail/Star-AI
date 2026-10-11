```luau
--!strict
export type Color = { r: number, g: number, b: number }

local function lin(v: number): number
	if v <= 0.03928 then
		return v / 12.92
	end
	return ((v + 0.055) / 1.055) ^ 2.4
end

local function luminance(c: Color): number
	return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
end

local function contrast(a: Color, b: Color): number
	local la, lb = luminance(a), luminance(b)
	return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05)
end

local function pickText(bg: Color, light: Color, dark: Color): Color
	if contrast(bg, light) >= contrast(bg, dark) then
		return light
	end
	return dark
end

local function shade(c: Color, amount: number): Color
	local a = math.clamp(amount, -1, 1)
	local function f(v: number): number
		if a >= 0 then
			return v + (1 - v) * a
		end
		return v * (1 + a)
	end
	return { r = f(c.r), g = f(c.g), b = f(c.b) }
end

return { luminance = luminance, contrast = contrast, pickText = pickText, shade = shade }
```
