local ret, env = load_answer()
local luminance = resolve(ret, env, "luminance")
local contrast = resolve(ret, env, "contrast")
local pickText = resolve(ret, env, "pickText")
local shade = resolve(ret, env, "shade")
local function near(a, b, eps) return type(a) == "number" and math.abs(a - b) <= (eps or 1e-6) end
local white = { r = 1, g = 1, b = 1 }
local black = { r = 0, g = 0, b = 0 }
local grey = { r = 0.5, g = 0.5, b = 0.5 }
check("luminance of white is 1 and of black is 0", near(luminance(white), 1) and near(luminance(black), 0))
check("luminance of pure red is 0.2126", near(luminance({ r = 1, g = 0, b = 0 }), 0.2126))
check("luminance of mid grey uses the sRGB curve (about 0.2140)", near(luminance(grey), 0.2140, 0.0005))
check("contrast of white on black is 21, in either order", near(contrast(white, black), 21, 0.001) and near(contrast(black, white), 21, 0.001))
check("contrast of a colour with itself is 1", near(contrast(grey, grey), 1))
check("pickText picks light text on a dark background", pickText({ r = 0.1, g = 0.1, b = 0.1 }, white, black) == white)
check("pickText picks dark text on a light background", pickText({ r = 0.9, g = 0.9, b = 0.9 }, white, black) == black)
check("pickText on mid grey picks dark (contrast 5.3 against 4.0)", pickText(grey, white, black) == black)
local lighter = shade(grey, 0.5)
check("shade(grey, 0.5) moves half way to white", near(lighter.r, 0.75) and near(lighter.g, 0.75) and near(lighter.b, 0.75))
local darker = shade(grey, -0.5)
check("shade(grey, -0.5) halves each channel", near(darker.r, 0.25) and near(darker.g, 0.25) and near(darker.b, 0.25))
check("shade returns a new table and leaves the input alone", lighter ~= grey and grey.r == 0.5)
local clamped = shade(grey, 2)
check("shade clamps the amount to [-1, 1]", near(clamped.r, 1) and near(shade(grey, -3).g, 0))
