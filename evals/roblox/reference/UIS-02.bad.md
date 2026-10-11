```luau
--!strict
local function luminance(c)
	return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
end
local function contrast(a, b)
	local la, lb = luminance(a), luminance(b)
	return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05)
end
local function pickText(bg, light, dark)
	if luminance(bg) > 0.5 then return dark end
	return light
end
local function shade(c, amount)
	c.r = math.clamp(c.r + amount, 0, 1)
	c.g = math.clamp(c.g + amount, 0, 1)
	c.b = math.clamp(c.b + amount, 0, 1)
	return c
end
return { luminance = luminance, contrast = contrast, pickText = pickText, shade = shade }
```
