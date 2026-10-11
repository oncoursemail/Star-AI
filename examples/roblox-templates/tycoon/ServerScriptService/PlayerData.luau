--!strict
-- Player data is exclusively server-owned. The lease prevents stale servers from overwriting newer sessions.
local DataStoreService = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Economy = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Economy"))

export type Session = { key: string, token: string, busy: boolean, closed: boolean }

local PlayerData = {}
local store = DataStoreService:GetDataStore("STAR_TYCOON_TEMPLATE_V1")
local MAX_ATTEMPTS = 3
local LEASE_SECONDS = 180

local function update(key: string, transform: (any) -> any): (boolean, any)
	for attempt = 1, MAX_ATTEMPTS do
		local ok, result = pcall(function()
			return store:UpdateAsync(key, transform)
		end)
		if ok then
			return true, result
		end
		if attempt < MAX_ATTEMPTS then
			task.wait(2 ^ (attempt - 1))
		end
	end
	return false, nil
end

local function record(state: Economy.State, token: string?, expiresAt: number?): { [string]: any }
	local data: { [string]: any } = {
		cash = state.cash,
		rebirths = state.rebirths,
		owned = state.owned,
	}
	if token ~= nil and expiresAt ~= nil then
		data.lease = { token = token, expiresAt = expiresAt }
	end
	return data
end

function PlayerData.open(player: Player): (Session?, Economy.State?, string?)
	local key = "player_" .. tostring(player.UserId)
	local token = HttpService:GenerateGUID(false)
	local ok, saved = update(key, function(previous: any): any
		if type(previous) == "table" and type(previous.lease) == "table" then
			local lease = previous.lease
			if type(lease.token) == "string" and type(lease.expiresAt) == "number"
				and lease.expiresAt > os.time() and lease.token ~= token then
				return nil
			end
		end
		local state = Economy.fromSaved(previous)
		return record(state, token, os.time() + LEASE_SECONDS)
	end)
	if not ok then
		return nil, nil, "unavailable"
	end
	if type(saved) ~= "table" or type(saved.lease) ~= "table" or saved.lease.token ~= token then
		return nil, nil, "active_session"
	end
	return { key = key, token = token, busy = false, closed = false }, Economy.fromSaved(saved), nil
end

function PlayerData.save(session: Session, current: () -> Economy.State, closing: boolean): boolean
	while session.busy and not session.closed do
		task.wait()
	end
	if session.closed then
		return true
	end
	session.busy = true
	-- Read after acquiring the local save lock, not before awaiting another save.
	local snapshot = Economy.serialize(current())
	local ok, saved = update(session.key, function(previous: any): any
		if type(previous) ~= "table" or type(previous.lease) ~= "table"
			or previous.lease.token ~= session.token then
			return nil
		end
		if closing then
			return record(snapshot, nil, nil)
		end
		return record(snapshot, session.token, os.time() + LEASE_SECONDS)
	end)
	session.busy = false
	if not ok or type(saved) ~= "table" then
		return false
	end
	if closing then
		session.closed = true
	end
	return true
end

return PlayerData
