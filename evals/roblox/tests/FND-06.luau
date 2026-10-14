local ret, env = load_answer()
local BT = (type(ret) == "table" and ret.Sequence ~= nil and ret) or (type(ret) == "table" and ret.BT) or env.BT
check("the module returns a BT table with Sequence, Selector, Action, Condition and Inverter", type(BT) == "table"
	and type(BT.Sequence) == "function" and type(BT.Selector) == "function" and type(BT.Action) == "function"
	and type(BT.Condition) == "function" and type(BT.Inverter) == "function")

local log = {}
local function action(name, results)
	local i = 0
	return BT.Action(function(bb)
		i += 1
		table.insert(log, name)
		return results[math.min(i, #results)]
	end)
end
local function cond(value)
	return BT.Condition(function(bb) return value end)
end

-- The example from the fundamentals notes: Selector [Sequence [EnemyVisible, Attack], Sequence [LowHealth, FindCover, Heal], Patrol].
local root = BT.Selector({
	BT.Sequence({ cond(false), action("Attack", { "Success" }) }),
	BT.Sequence({ cond(true), action("FindCover", { "Failure" }), action("Heal", { "Success" }) }),
	action("Patrol", { "Success" }),
})
local status = root:tick({})
check("selector falls through failed sequences: status Success", status == "Success")
check("only FindCover and Patrol ran, in that order", deepEqual(log, { "FindCover", "Patrol" }))

-- A running child is resumed on the next tick without re-running the children before it.
log = {}
local seq = BT.Sequence({ action("A", { "Success" }), action("B", { "Running", "Success" }), action("C", { "Success" }) })
check("a sequence returns Running while a child runs", seq:tick({}) == "Running" and deepEqual(log, { "A", "B" }))
check("the next tick resumes at the running child and completes", seq:tick({}) == "Success" and deepEqual(log, { "A", "B", "B", "C" }))
log = {}
check("after completing, the sequence starts again from its first child", seq:tick({}) == "Success" and log[1] == "A")

log = {}
local sel = BT.Selector({ action("F", { "Failure" }), action("R", { "Running", "Running", "Failure" }), action("S", { "Success" }) })
check("a selector returns Running while a child runs", sel:tick({}) == "Running" and deepEqual(log, { "F", "R" }))
check("the selector resumes at the running child", sel:tick({}) == "Running" and deepEqual(log, { "F", "R", "R" }))
check("when the running child fails the selector moves on", sel:tick({}) == "Success" and deepEqual(log, { "F", "R", "R", "R", "S" }))

check("Inverter swaps Success and Failure", BT.Inverter(cond(true)):tick({}) == "Failure" and BT.Inverter(cond(false)):tick({}) == "Success")
check("Inverter keeps Running", BT.Inverter(action("X", { "Running" })):tick({}) == "Running")

local bb = { ammo = 0 }
local reload = BT.Sequence({
	BT.Condition(function(b) return b.ammo == 0 end),
	BT.Action(function(b) b.ammo = 6; return "Success" end),
})
check("nodes receive the blackboard", reload:tick(bb) == "Success" and bb.ammo == 6 and reload:tick(bb) == "Failure")
check("an empty sequence succeeds and an empty selector fails", BT.Sequence({}):tick({}) == "Success" and BT.Selector({}):tick({}) == "Failure")
