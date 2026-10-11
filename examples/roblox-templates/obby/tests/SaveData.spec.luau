--!strict
local SaveData = require("../ReplicatedStorage/Shared/SaveData")

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

return {
	["migrates old numeric and table records"] = function()
		local numberRecord = SaveData.migrate(3, 4)
		expect(numberRecord.version == 2 and numberRecord.furthestStage == 3, "numeric saves migrate")
		local tableRecord = SaveData.migrate({ stage = 9, wins = 2 }, 4)
		expect(tableRecord.furthestStage == 4 and tableRecord.finishes == 2, "legacy values clamp and migrate")
		expect(tableRecord.lock == nil, "legacy values have no lock")
	end,
	["rejects corrupted values rather than trusting them"] = function()
		local record = SaveData.migrate({ version = 2, furthestStage = "999", finishes = -5 }, 4)
		expect(record.furthestStage == 1 and record.finishes == 0, "invalid fields use safe defaults")
		expect(SaveData.migrate(nil, 4).furthestStage == 1, "new players start at one")
	end,
	["preserves live foreign locks and expires stale locks"] = function()
		local record = SaveData.hold(SaveData.migrate(nil, 4), "first", 100, 120)
		expect(SaveData.isLocked(record, "second", 150), "foreign live lock blocks loading")
		expect(not SaveData.isLocked(record, "first", 150), "owner may refresh")
		expect(not SaveData.isLocked(record, "second", 220), "expired lock may be taken")
		local migrated = SaveData.migrate(record, 4)
		expect(migrated.lock ~= nil and migrated.lock.token == "first", "v2 lock survives migration")
	end,
	["merges monotonic progress and releases ownership"] = function()
		local saved = SaveData.hold(SaveData.migrate({ stage = 4, wins = 3 }, 4), "owner", 100, 120)
		local merged = SaveData.merge(saved, 2, 1, 4)
		expect(merged.furthestStage == 4 and merged.finishes == 3, "merges never decrease values")
		expect(merged.lock ~= nil and merged.lock.token == "owner", "merge retains lock")
		expect(SaveData.release(merged).lock == nil, "close releases lock")
	end,
}
