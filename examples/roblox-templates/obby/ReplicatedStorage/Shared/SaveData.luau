--!strict
-- Pure, defensive migration/merge rules. No engine objects or DataStore calls belong here.
export type Lock = { token: string, expiresAt: number }
export type SaveRecord = { version: number, furthestStage: number, finishes: number, lock: Lock? }

local SaveData = {}
SaveData.VERSION = 2

local MAX_FINISHES = 1000000000

local function whole(value: any, minimum: number, maximum: number, fallback: number): number
	if type(value) ~= "number" or value ~= value then
		return fallback
	end
	return math.clamp(math.floor(value), minimum, maximum)
end

function SaveData.migrate(value: any, lastStage: number): SaveRecord
	local maximum = whole(lastStage, 1, 1000, 1)
	local stage: any = 1
	local finishes: any = 0
	local lock: Lock? = nil

	if type(value) == "number" then
		stage = value
	elseif type(value) == "table" then
		if value.version == SaveData.VERSION then
			stage = value.furthestStage
			finishes = value.finishes
			local candidate = value.lock
			if type(candidate) == "table"
				and type(candidate.token) == "string"
				and #candidate.token > 0
				and type(candidate.expiresAt) == "number"
				and candidate.expiresAt == candidate.expiresAt then
				lock = { token = candidate.token, expiresAt = candidate.expiresAt }
			end
		else
			-- Legacy values: a bare stage, or { stage = n, wins = n }.
			stage = value.stage or value.furthestStage
			finishes = value.wins or value.finishes
		end
	end

	return {
		version = SaveData.VERSION,
		furthestStage = whole(stage, 1, maximum, 1),
		finishes = whole(finishes, 0, MAX_FINISHES, 0),
		lock = lock,
	}
end

function SaveData.isLocked(record: SaveRecord, token: string, now: number): boolean
	local lock = record.lock
	return lock ~= nil and lock.token ~= token and lock.expiresAt > now
end

function SaveData.merge(record: SaveRecord, reachedStage: number, earnedFinishes: number, lastStage: number): SaveRecord
	return {
		version = SaveData.VERSION,
		furthestStage = math.max(record.furthestStage, whole(reachedStage, 1, lastStage, 1)),
		finishes = math.max(record.finishes, whole(earnedFinishes, 0, MAX_FINISHES, 0)),
		lock = record.lock,
	}
end

function SaveData.hold(record: SaveRecord, token: string, now: number, ttlSeconds: number): SaveRecord
	return {
		version = SaveData.VERSION,
		furthestStage = record.furthestStage,
		finishes = record.finishes,
		lock = { token = token, expiresAt = now + ttlSeconds },
	}
end

function SaveData.release(record: SaveRecord): SaveRecord
	return {
		version = SaveData.VERSION,
		furthestStage = record.furthestStage,
		finishes = record.finishes,
		lock = nil,
	}
end

return SaveData
