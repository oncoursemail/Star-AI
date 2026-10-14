local ret, env = load_answer()
local Combo = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.Combo) or env.Combo
local moves = {
	{ startup = 2, active = 1, recovery = 3, cancelWindow = 2 },
	{ startup = 3, active = 2, recovery = 4, cancelWindow = 2 },
}
local function is(c, move, phase, frame, hit)
	local s = c:state()
	return s.move == move and s.phase == phase and s.frame == frame and s.hitActive == hit
end
local function stepN(c, n)
	for _ = 1, n do c:step() end
end

local c = Combo.new(moves)
check("a new combo is idle", is(c, 0, "idle", 0, false))
c:step()
check("stepping while idle changes nothing", is(c, 0, "idle", 0, false))
c:press()
check("press while idle starts move 1 at startup frame 1", is(c, 1, "startup", 1, false))
c:step()
check("startup frame 2", is(c, 1, "startup", 2, false))
c:press()
c:step()
check("the next frame is the first active frame and the hit is live", is(c, 1, "active", 1, true))
c:step()
check("recovery frame 1 follows the single active frame", is(c, 1, "recovery", 1, false))
c:press()
stepN(c, 3)
check("a press before the cancel window is dropped: the combo ends idle", is(c, 0, "idle", 0, false))

local d = Combo.new(moves)
d:press()
stepN(d, 4)
check("recovery frame 2 is inside the cancel window", is(d, 1, "recovery", 2, false))
d:press()
d:step()
check("a buffered press does not start the next move early", is(d, 1, "recovery", 3, false))
d:step()
check("the buffered press starts move 2 right after recovery ends", is(d, 2, "startup", 1, false))

local e = Combo.new(moves)
e:press()
stepN(e, 6)
check("an uninterrupted move 1 takes startup + active + recovery = 6 steps", is(e, 0, "idle", 0, false))

local f = Combo.new(moves)
f:press()
stepN(f, 4)
f:press()
f:step()
local hits, reached = 0, false
for _ = 1, 20 do
	local s = f:state()
	if s.hitActive and s.move == 2 then hits += 1 end
	if s.move == 2 and s.phase == "recovery" then reached = true end
	f:step()
end
check("move 2 has exactly 2 hit frames", hits == 2 and reached)
check("the combo returns to idle after the last move", is(f, 0, "idle", 0, false))

local g = Combo.new({ moves[1] })
g:press()
stepN(g, 4)
g:press()
stepN(g, 2)
check("with no next move a buffered press is ignored and the combo ends idle", is(g, 0, "idle", 0, false))
