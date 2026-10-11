--!strict
local ServerScriptService = game:GetService("ServerScriptService")
local Store = require(ServerScriptService:WaitForChild("ProfileStore"))
local Service = require(ServerScriptService:WaitForChild("SimulatorService"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

local function fakeStore()
	local mock = { value = nil :: any, failures = 0, calls = 0 }
	function mock:UpdateAsync(_key: string, transform: (any) -> any)
		self.calls += 1
		if self.failures > 0 then
			self.failures -= 1
			error("transient simulated store failure")
		end
		local result = transform(self.value)
		if result ~= nil then
			self.value = result
		end
		return result
	end
	return mock
end

local function noSleep(_seconds: number) end
local function timeNow(): number
	return 1000
end

return {
	["load, save and release use UpdateAsync"] = function()
		local store = fakeStore()
		local profile, err = Store.load(store, "u1", "session-a", noSleep, timeNow)
		expect(profile ~= nil and err == nil and profile.coins == 0, "default state loaded")
		profile.coins = 200
		local saved = Store.save(store, "u1", "session-a", profile, false, noSleep, timeNow)
		expect(saved and store.value.data.coins == 200, "server changes persisted")
		expect(store.value.lock.id == "session-a", "lease extended on save")
		local released = Store.save(store, "u1", "session-a", profile, true, noSleep, timeNow)
		expect(released and store.value.lock == nil, "session unlocked")
		expect(store.calls == 3, "all operations used UpdateAsync")
	end,
	["another session cannot overwrite an active player"] = function()
		local store = fakeStore()
		local first = Store.load(store, "u1", "session-a", noSleep, timeNow)
		first.coins = 50
		local second, errorCode = Store.load(store, "u1", "session-b", noSleep, timeNow)
		expect(second == nil and errorCode == "profile_in_use", "second server cannot take lease")
		local saved, saveError = Store.save(store, "u1", "session-b", Service.newProfile(),
			false, noSleep, timeNow)
		expect(not saved and saveError == "session_lost", "foreign save rejected")
		expect(Store.save(store, "u1", "session-a", first, false, noSleep, timeNow),
			"legitimate owner can save")
		expect(store.value.data.coins == 50, "no foreign overwrite")
	end,
	["transient datastore failures are retried with bounded backoff"] = function()
		local store = fakeStore()
		store.failures = 2
		local delays = {}
		local profile = Store.load(store, "u1", "session-a", function(seconds: number)
			table.insert(delays, seconds)
		end, timeNow)
		expect(profile ~= nil and store.calls == 3, "load succeeded on third try")
		expect(#delays == 2 and delays[1] == 0.25 and delays[2] == 0.5, "backoff was bounded")
		store.failures = 4
		local saved, err = Store.save(store, "u1", "session-a", profile, false, noSleep, timeNow)
		expect(not saved and err == "data_store_unavailable", "four failures fail closed")
	end,
	["expired lease can be reclaimed and legacy records are normalized"] = function()
		local store = fakeStore()
		store.value = { coins = 25, pets = { bunny = true }, lock = { id = "old", expires = 100 } }
		local profile = Store.load(store, "u1", "session-b", noSleep, timeNow)
		expect(profile.coins == 25 and profile.pets.bunny, "old record was recovered")
		expect(store.value.lock.id == "session-b", "new lease owned by new session")
	end,
}
