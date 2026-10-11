-- Holdout test body HO-NET-02 (frozen 2026-10-11; harness-owned, never shown to the model).
local Mod = load_answer({ debug = debugStub })
local t = 0
local function now() return t end
local abuse = {}
local function onAbuse(id) table.insert(abuse, id) end

local lim = Mod.new(3, 1, 3, now, onAbuse)
local first = { lim:allow(7), lim:allow(7), lim:allow(7) }
check("a new player starts with a full bucket of 3 tokens", first[1] == true and first[2] == true and first[3] == true)
check("the 4th call at the same instant is denied", lim:allow(7) == false)
check("one strike does not call onAbuse", #abuse == 0)
lim:allow(7)
check("two strikes do not call onAbuse", #abuse == 0)
lim:allow(7)
check("the third consecutive strike calls onAbuse once with the user id", #abuse == 1 and abuse[1] == 7)
lim:allow(7)
lim:allow(7)
check("more denied calls in the same streak do not call onAbuse again", #abuse == 1)
t = 0.5
check("half a token is not enough: denied", lim:allow(7) == false)
check("still the same streak: no second callback", #abuse == 1)
t = 1.0
check("after one second one token is back: allowed", lim:allow(7) == true)
lim:allow(7)
lim:allow(7)
check("an allowed call reset the strikes: two new strikes do not call onAbuse", #abuse == 1)
lim:allow(7)
check("a new streak of three strikes calls onAbuse again", #abuse == 2 and abuse[2] == 7)

t = 1000
local allowed = 0
for _ = 1, 10 do
	if lim:allow(7) then allowed += 1 end
end
check("tokens never exceed the capacity: 3 of 10 calls allowed after a long wait", allowed == 3)

local a, b, c, d = lim:allow(8), lim:allow(8), lim:allow(8), lim:allow(8)
check("another player has a bucket of their own", a == true and b == true and c == true and d == false)

lim:forget(7)
local again = 0
for _ = 1, 4 do
	if lim:allow(7) then again += 1 end
end
check("forget gives the player a fresh full bucket", again == 3)

t = 2000
local fast = Mod.new(4, 2, 100, now, onAbuse)
for _ = 1, 4 do fast:allow(1) end
t = 2000.25
check("refill is rate * elapsed: 0.25 s at 2 tokens per second is half a token", fast:allow(1) == false)
t = 2000.5
check("0.5 s at 2 per second is one whole token", fast:allow(1) == true)
check("that token is spent", fast:allow(1) == false)
t = 2001.5
local x, y, z = fast:allow(1), fast:allow(1), fast:allow(1)
check("one more second gives two tokens", x == true and y == true and z == false)

local before = #abuse
local one = Mod.new(1, 1, 1, now, onAbuse)
one:allow(5)
one:allow(5)
one:allow(5)
check("with maxStrikes = 1 the first denial calls onAbuse, and only once per streak", #abuse == before + 1 and abuse[#abuse] == 5)
