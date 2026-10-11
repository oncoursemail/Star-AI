--!strict
-- UpdateAsync-based session leases prevent two servers from silently overwriting a profile.
local Service = require(script.Parent:WaitForChild("SimulatorService"))

local ProfileStore = {}
local MAX_ATTEMPTS = 4
local LEASE_SECONDS = 180

local function update(store: any, key: string, transform: (any) -> any, sleep: (number) -> ()): (any, string?)
	for attempt = 1, MAX_ATTEMPTS do
		local ok, value = pcall(function()
			return store:UpdateAsync(key, transform)
		end)
		if ok then
			return value, nil
		end
		if attempt < MAX_ATTEMPTS then
			sleep(0.25 * (2 ^ (attempt - 1)))
		end
	end
	return nil, "data_store_unavailable"
end

function ProfileStore.load(store: any, key: string, sessionId: string,
	sleep: ((number) -> ())?, clock: (() -> number)?)
	local pause = sleep or task.wait
	local now = clock or os.time
	local result, err = update(store, key, function(previous: any)
		local record = if type(previous) == "table" then previous else {}
		local lock = if type(record.lock) == "table" then record.lock else {}
		if type(lock.id) == "string" and lock.id ~= sessionId
			and type(lock.expires) == "number" and lock.expires > now() then
			return nil
		end
		local raw = if record.data ~= nil then record.data else record
		return {
			data = Service.normalize(raw),
			lock = { id = sessionId, expires = now() + LEASE_SECONDS },
		}
	end, pause)
	if err then
		return nil, err
	end
	if result == nil then
		return nil, "profile_in_use"
	end
	return Service.normalize(result.data), nil
end

function ProfileStore.save(store: any, key: string, sessionId: string, profile: any,
	release: boolean, sleep: ((number) -> ())?, clock: (() -> number)?): (boolean, string?)
	local pause = sleep or task.wait
	local now = clock or os.time
	local result, err = update(store, key, function(previous: any)
		if type(previous) ~= "table" or type(previous.lock) ~= "table"
			or previous.lock.id ~= sessionId then
			return nil
		end
		return {
			data = Service.normalize(profile),
			lock = if release then nil else { id = sessionId, expires = now() + LEASE_SECONDS },
		}
	end, pause)
	if err then
		return false, err
	end
	if result == nil then
		return false, "session_lost"
	end
	return true, nil
end

return ProfileStore
