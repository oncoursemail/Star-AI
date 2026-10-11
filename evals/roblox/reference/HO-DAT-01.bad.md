Read the record, check the lock, write it back.

```luau
local SessionLock = {}

function SessionLock.acquire(store: DataStore, userId: number, jobId: string, now: number, staleAfter: number): (boolean, any)
	local key = tostring(userId)
	local ok, record = pcall(function()
		return store:GetAsync(key)
	end)
	if not ok then
		return false, tostring(record)
	end
	record = record or { data = {} }
	if record.lock and record.lock.jobId ~= jobId and now - record.lock.at <= staleAfter then
		return false, "locked"
	end
	record.lock = { jobId = jobId, at = now }
	local saved, err = pcall(function()
		store:SetAsync(key, record)
	end)
	if not saved then
		return false, tostring(err)
	end
	return true, record.data
end

function SessionLock.release(store: DataStore, userId: number, jobId: string): boolean
	local key = tostring(userId)
	local ok, record = pcall(function()
		return store:GetAsync(key)
	end)
	if not ok or not record then
		return false
	end
	record.lock = nil
	return pcall(function()
		store:SetAsync(key, record)
	end)
end

return SessionLock
```
