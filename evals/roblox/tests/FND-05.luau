local ret, env = load_answer()
local Predictor = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.Predictor) or env.Predictor
check("the module returns a Predictor class with new()", type(Predictor) == "table" and type(Predictor.new) == "function")

local function add(state, input)
	return state + input
end

local p = Predictor.new(0, add)
local seqs = {}
for i, dx in { 1, 1, 2, 2, -1, 3, 3, 1 } do
	seqs[i] = p:applyInput(dx)
end
check("applyInput numbers inputs 1, 2, 3, ...", seqs[1] == 1 and seqs[8] == 8)
check("inputs are applied locally at once (predicted x = 12)", p:state() == 12 and p:pendingCount() == 8)
p:onServerState(5, 4)
check("reconciliation: server x = 4 after input 5, replay 6..8 gives 11", p:state() == 11)
check("acknowledged inputs are dropped (3 pending)", p:pendingCount() == 3)
p:onServerState(3, 100)
check("an older server update (ack 3 after ack 5) is ignored", p:state() == 11 and p:pendingCount() == 3)
p:applyInput(2)
check("new inputs keep numbering after reconciliation (state 13, 4 pending)", p:state() == 13 and p:pendingCount() == 4)
p:onServerState(9, 20)
check("an ack of every input leaves nothing to replay", p:state() == 20 and p:pendingCount() == 0)

-- Replay must run the apply function, not add up differences: here a wall clamps x at 10.
local function clamped(state, input)
	return math.min(10, state + input)
end
local c = Predictor.new(0, clamped)
for _, dx in { 4, 4, 4, 4 } do c:applyInput(dx) end
check("predicted state uses the apply function (clamped at 10)", c:state() == 10)
c:onServerState(1, 0)
check("replaying inputs 2..4 from the server state uses the apply function again (0 + 4 + 4 + 4 clamped = 10)", c:state() == 10)
c:onServerState(2, -5)
check("replay from -5 with inputs 3 and 4 gives 3", c:state() == 3 and c:pendingCount() == 2)

-- Tables as state: the server state must not be mutated by the replay.
local function move(state, input)
	return { x = state.x + input }
end
local t = Predictor.new({ x = 0 }, move)
t:applyInput(1)
t:applyInput(1)
local serverState = { x = 5 }
t:onServerState(1, serverState)
check("table states work and the server's table is left unchanged", t:state().x == 6 and serverState.x == 5)
