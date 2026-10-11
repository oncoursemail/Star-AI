local ret, env = load_answer()
local E = (type(ret) == "table" and ret.linear ~= nil and ret) or (type(ret) == "table" and ret.Easing) or env.Easing
check("the module returns a table of easing functions", type(E) == "table" and type(E.linear) == "function")
local function near(a, b, eps)
	return type(a) == "number" and math.abs(a - b) <= (eps or 1e-6)
end
check("linear(0.25) is 0.25", near(E.linear(0.25), 0.25))
check("inQuad(0.5) is 0.25", near(E.inQuad(0.5), 0.25))
check("outQuad(0.5) is 0.75", near(E.outQuad(0.5), 0.75))
check("inOutQuad(0.25) is 0.125 and inOutQuad(0.75) is 0.875", near(E.inOutQuad(0.25), 0.125) and near(E.inOutQuad(0.75), 0.875))
check("outCubic(0.5) is 0.875", near(E.outCubic(0.5), 0.875))
local names = { "linear", "inQuad", "outQuad", "inOutQuad", "outCubic", "outBack", "outElastic" }
local ends, clamped = true, true
for _, n in names do
	if not (near(E[n](0), 0) and near(E[n](1), 1)) then ends = false end
	if not (near(E[n](-3), 0) and near(E[n](7), 1)) then clamped = false end
end
check("every easing maps 0 to 0 and 1 to 1", ends)
check("t outside [0, 1] is clamped", clamped)
local peak, epeak = 0, 0
for i = 1, 99 do
	peak = math.max(peak, E.outBack(i / 100))
	epeak = math.max(epeak, E.outElastic(i / 100))
end
check("outBack overshoots 1 but by less than 15 percent", peak > 1.0 and peak < 1.15)
check("outElastic overshoots 1 by more than 10 percent", epeak > 1.1)
check("lerp(0, 100, 0.5, 'outQuad') is 75", near(E.lerp(0, 100, 0.5, "outQuad"), 75))
check("lerp defaults to linear and handles a falling range", near(E.lerp(10, 20, 0.5), 15) and near(E.lerp(5, -5, 0.25), 2.5))
check("lerp clamps t through the easing", near(E.lerp(0, 10, 2, "linear"), 10))
