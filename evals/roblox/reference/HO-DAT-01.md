The lock lives inside the saved record, and both acquiring and releasing it are a single `UpdateAsync`, so two servers cannot both read "free" and then both write. The callback returns nil to cancel the write when someone else holds a fresh lock, and it never yields.

```luau
--!strict
local SessionLock = {}

type Record = { lock: { jobId: string, at: number }?, data: any }

function SessionLock.acquire(store: DataStore, userId: number, jobId: string, now: number, staleAfter: number): (boolean, any)
	local key = tostring(userId)
	local granted = false
	local savedData: any = nil
	local ok, err = pcall(function()
		store:UpdateAsync(key, function(record: any)
			granted = false
			local current: Record = if type(record) == "table" then record else { data = {} }
			local lock = current.lock
			if lock ~= nil and lock.jobId ~= jobId and now - lock.at < staleAfter then
				return nil
			end
			local data = current.data
			if data == nil then
				data = {}
			end
			granted = true
			savedData = data
			return { lock = { jobId = jobId, at = now }, data = data }
		end)
	end)
	if not ok then
		return false, tostring(err)
	end
	if not granted then
		return false, "locked"
	end
	return true, savedData
end

function SessionLock.release(store: DataStore, userId: number, jobId: string): boolean
	local released = false
	local ok = pcall(function()
		store:UpdateAsync(tostring(userId), function(record: any)
			released = false
			if type(record) ~= "table" or record.lock == nil or record.lock.jobId ~= jobId then
				return nil
			end
			record.lock = nil
			released = true
			return record
		end)
	end)
	return ok and released
end

return SessionLock
```
