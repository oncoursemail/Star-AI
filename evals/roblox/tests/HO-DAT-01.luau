-- Holdout test body HO-DAT-01 (frozen 2026-10-11; harness-owned, never shown to the model).
local function newStore()
	local store = { data = {}, updates = 0, gets = 0, sets = 0, failNext = nil }
	function store:UpdateAsync(key, fn)
		self.updates += 1
		if self.failNext then
			local msg = self.failNext
			self.failNext = nil
			error(msg, 0)
		end
		local new = fn(deepCopy(self.data[key]))
		if new == nil then return nil end -- the callback cancelled the update
		self.data[key] = deepCopy(new)
		return deepCopy(new)
	end
	function store:GetAsync(key)
		self.gets += 1
		return deepCopy(self.data[key])
	end
	function store:SetAsync(key, value)
		self.sets += 1
		self.data[key] = deepCopy(value)
	end
	return store
end

local Mod = load_answer({ debug = debugStub })
local store = newStore()

local ok, data = Mod.acquire(store, 1, "A", 100, 300)
check("a new player acquires the lock and gets an empty data table", ok == true and type(data) == "table" and next(data) == nil)
check("the new record holds the lock of job A at time 100", deepEqual(store.data["1"], { lock = { jobId = "A", at = 100 }, data = {} }))
check("acquire used exactly one UpdateAsync and no GetAsync/SetAsync", store.updates == 1 and store.gets == 0 and store.sets == 0)

store.data["1"].data = { coins = 5 }
ok, data = Mod.acquire(store, 1, "A", 150, 300)
check("the same job can acquire again and gets the saved data", ok == true and deepEqual(data, { coins = 5 }))
check("re-acquiring refreshes the lock time", deepEqual(store.data["1"], { lock = { jobId = "A", at = 150 }, data = { coins = 5 } }))

local snapshot = deepCopy(store.data["1"])
local u = store.updates
local reason
ok, reason = Mod.acquire(store, 1, "B", 200, 300)
check("another job with a fresh lock is refused with the reason \"locked\"", ok == false and reason == "locked")
check("a refused acquire writes nothing", deepEqual(store.data["1"], snapshot))
check("a refused acquire still used exactly one UpdateAsync", store.updates == u + 1)

ok, data = Mod.acquire(store, 1, "B", 449, 300)
check("299 seconds after the lock is still fresh", ok == false and data == "locked")
ok, data = Mod.acquire(store, 1, "B", 450, 300)
check("a lock exactly staleAfter old is stale: job B takes it over and gets the data", ok == true and deepEqual(data, { coins = 5 }))
check("the takeover keeps the data and records job B", deepEqual(store.data["1"], { lock = { jobId = "B", at = 450 }, data = { coins = 5 } }))

store.failNext = "429 request was throttled"
local okFail = pcall(Mod.acquire, store, 2, "A", 500, 300)
check("a failing UpdateAsync never throws out of acquire", okFail == true and store.data["2"] == nil)
local failing = newStore()
failing.failNext = "429 request was throttled"
local f1, f2 = Mod.acquire(failing, 2, "A", 500, 300)
check("a failing UpdateAsync gives false and the error message", f1 == false and type(f2) == "string" and string.find(f2, "throttled", 1, true) ~= nil)

check("release by a job that does not hold the lock returns false", Mod.release(store, 1, "A") == false)
check("... and leaves the record unchanged", deepEqual(store.data["1"], { lock = { jobId = "B", at = 450 }, data = { coins = 5 } }))
u = store.updates
check("release by the owner returns true", Mod.release(store, 1, "B") == true)
check("release used exactly one UpdateAsync", store.updates == u + 1)
check("release removes only the lock and keeps the data", deepEqual(store.data["1"], { data = { coins = 5 } }))
check("releasing a record without a lock returns false", Mod.release(store, 1, "B") == false)
check("releasing for a player with no record returns false and creates nothing", Mod.release(store, 99, "B") == false and store.data["99"] == nil)
local failing2 = newStore()
failing2.data["7"] = { lock = { jobId = "A", at = 1 }, data = {} }
failing2.failNext = "503 service unavailable"
local okRel, resRel = pcall(Mod.release, failing2, 7, "A")
check("a failing UpdateAsync makes release return false and not throw", okRel == true and resRel == false)
ok, data = Mod.acquire(store, 1, "C", 600, 300)
check("after a release anyone can acquire", ok == true and deepEqual(store.data["1"], { lock = { jobId = "C", at = 600 }, data = { coins = 5 } }))
