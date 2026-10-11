local ret, env = load_answer()
local Spring = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.Spring) or env.Spring
local function run(z, seconds, dt, f)
	local s = Spring.new(0, f or 3, z)
	local peak, last, monotone, prev = -math.huge, 0, true, 0
	for _ = 1, math.floor(seconds / dt + 0.5) do
		last = s:step(1, dt)
		if last > peak then peak = last end
		if last < prev - 1e-9 then monotone = false end
		prev = last
	end
	return last, peak, monotone
end
local last, peak, mono = run(1, 1.5, 1 / 60)
check("critically damped: settles on the target within 0.001 after 1.5 s", math.abs(last - 1) < 0.001)
check("critically damped: never overshoots and never goes backwards", peak <= 1 + 1e-6 and mono)
local last2, peak2 = run(0.3, 3, 1 / 60)
check("underdamped (0.3): overshoots the target by 20 to 60 percent", peak2 > 1.2 and peak2 < 1.6)
check("underdamped: settles within 0.01 after 3 s", math.abs(last2 - 1) < 0.01)
local a = Spring.new(0, 3, 0.3)
local x6
for _ = 1, 6 do x6 = a:step(1, 0.1 / 6) end
local b = Spring.new(0, 3, 0.3)
local x1 = b:step(1, 0.1)
check("0.1 s as 6 steps equals 0.1 s as 1 step (within 0.02)", math.abs(x6 - x1) < 0.02)
local c = Spring.new(0, 3, 1)
local huge = c:step(1, 10)
check("a 10 s step is finite and near the target", huge == huge and math.abs(huge) < math.huge and math.abs(huge - 1) < 0.01)
local d = Spring.new(5, 3, 0.5)
check("dt = 0 leaves the position unchanged", d:step(9, 0) == 5)
d:step(9, 0.05)
d:reset(2)
check("reset puts the spring at rest at the new position", math.abs(d:step(2, 0.5) - 2) < 1e-9)
local e = Spring.new(0, 2, 2)
local e1 = e:step(1, 0.2)
check("overdamped (2) moves toward the target without overshoot", e1 > 0 and e1 < 1)
local ga = Spring.new(0, 3, 0.7)
local p = ga:step(1, 0.05)
local gb = Spring.new(p, 3, 0.7)
local a2, b2 = ga:step(-1, 0.02), gb:step(-1, 0.02)
check("a retarget keeps the velocity (the moving spring stays ahead of one started at rest)", a2 > b2)
