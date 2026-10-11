local state = { yielded = false, inCb = false, calls = 0, fail = false }
local stored = {}
local store = {}
function store:UpdateAsync(key, fn)
	state.calls += 1
	if state.fail then error("503 simulated outage") end
	state.inCb = true
	local new = fn(stored[key])
	state.inCb = false
	if new ~= nil then stored[key] = new end
	return new
end
local function wait(t) if state.inCb then state.yielded = true end return t or 0.03 end
local Wallet = load_answer({ wait = wait, task = { wait = wait, spawn = function(f, ...) f(...) end } })

local ok, balance = Wallet.add(store, "k", 50)
check("adding 50 to a new key gives (true, 50)", ok == true and balance == 50 and stored.k == 50)
ok, balance = Wallet.add(store, "k", -20)
check("subtracting 20 gives (true, 30)", ok == true and balance == 30 and stored.k == 30)
ok, balance = Wallet.add(store, "k", -40)
check("a debit that would go negative is cancelled: (false, nil) and the stored value is unchanged", ok == false and balance == nil and stored.k == 30)
local calls = state.calls
ok = Wallet.add(store, "k", 1.5)
local ok2 = Wallet.add(store, "k", 0 / 0)
local ok3 = Wallet.add(store, "k", math.huge)
check("fractions, NaN and infinity are refused and the stored value is unchanged", ok == false and ok2 == false and ok3 == false and stored.k == 30)
state.calls = 0
Wallet.add(store, "k", 1)
check("exactly one UpdateAsync call per add", state.calls == 1 and stored.k == 31)
state.fail = true
local okDown, balDown = pcall(Wallet.add, store, "k", 5)
check("when UpdateAsync throws, add returns false without raising", okDown and balDown == false)
check("nothing yields inside the UpdateAsync callback", not state.yielded)
