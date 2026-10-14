local ret, env = load_answer()
local FixedStep = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.FixedStep) or env.FixedStep
check("the module returns a FixedStep class with new()", type(FixedStep) == "table" and type(FixedStep.new) == "function")

local function near(a, b)
	return type(a) == "number" and math.abs(a - b) <= 1e-9
end

local s = FixedStep.new(0.25, 1)
check("a new clock has alpha 0", near(s:alpha(), 0))
check("0.625 s gives 2 steps and alpha 0.5", s:advance(0.625) == 2 and near(s:alpha(), 0.5))
check("the remainder carries over: 0.125 s more gives 1 step and alpha 0", s:advance(0.125) == 1 and near(s:alpha(), 0))
check("a frame shorter than a step gives 0 steps", s:advance(0.125) == 0 and near(s:alpha(), 0.5))
check("a 5 s hitch is clamped to 1 s: 4 steps, remainder kept", s:advance(5) == 4 and near(s:alpha(), 0.5))
check("a negative frame time runs nothing", s:advance(-1) == 0 and near(s:alpha(), 0.5))

local t = FixedStep.new(1 / 60, 0.25)
local total = 0
for _ = 1, 600 do
	total += t:advance(1 / 144)
end
check("600 frames at 144 fps advance about 250 steps of 1/60 s", total >= 249 and total <= 251)
local a = t:alpha()
check("alpha stays in [0, 1)", a >= 0 and a < 1)

local u = FixedStep.new(0.1, 0.25)
local steps = 0
for _ = 1, 20 do steps += u:advance(0.05) end
check("20 frames of 0.05 s with a 0.1 s step give 10 steps (allow float rounding: 9 or 10)", steps == 10 or steps == 9)

local slow = FixedStep.new(0.125, 0.5)
local counts = {}
for i = 1, 5 do counts[i] = slow:advance(3) end
check("repeated long frames run exactly maxFrame / step steps each (no spiral of death)", counts[1] == 4 and counts[5] == 4)
