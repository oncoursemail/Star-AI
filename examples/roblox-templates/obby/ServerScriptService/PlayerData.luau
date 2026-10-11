--!strict
-- Server-owned per-player stages and monotonic DataStore saves with short-lived session locks.
local DataStoreService = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Shared")
local StageProgression = require(Shared:WaitForChild("StageProgression"))
local SaveData = require(Shared:WaitForChild("SaveData"))

type Session = {
	key: string,
	token: string,
	stage: number,
	furthestStage: number,
	finishes: number,
	finishedThisSession: boolean,
	stat: IntValue,
	saving: boolean,
	closing: boolean,
}

local PlayerData = {}
local store = DataStoreService:GetDataStore("STAR_ObbyProgress_v2")
local sessions: { [Player]: Session } = {}
local MAX_ATTEMPTS = 4
local LOCK_SECONDS = 120
local LOAD_LOCK_ATTEMPTS = 3

local function updateWithRetry(key: string, transform: (any) -> any): (boolean, any)
	for attempt = 1, MAX_ATTEMPTS do
		local ok, result = pcall(function()
			return store:UpdateAsync(key, transform)
		end)
		if ok then
			return true, result
		end
		warn(string.format("Obby DataStore attempt %d failed", attempt))
		if attempt < MAX_ATTEMPTS then
			task.wait(2 ^ (attempt - 1))
		end
	end
	return false, nil
end

local function flush(player: Player, releaseLock: boolean): boolean
	local session = sessions[player]
	if not session then
		return false
	end
	while session.saving do
		task.wait(0.05)
	end
	if sessions[player] ~= session or (session.closing and not releaseLock) then
		return false
	end
	session.saving = true
	local stage = session.furthestStage
	local finishes = session.finishes
	local token = session.token
	local ok, updated = updateWithRetry(session.key, function(old: any): any
		local record = SaveData.migrate(old, StageProgression.LAST_STAGE)
		if record.lock == nil or record.lock.token ~= token then
			-- Another server owns this save. Never overwrite or release its data.
			return nil
		end
		local merged = SaveData.merge(record, stage, finishes, StageProgression.LAST_STAGE)
		if releaseLock then
			return SaveData.release(merged)
		end
		return SaveData.hold(merged, token, os.time(), LOCK_SECONDS)
	end)
	session.saving = false
	if not ok then
		warn("Obby progress could not be saved; another attempt will be made if the session is active")
		return false
	end
	if updated == nil then
		warn("Obby session lock was lost; refusing to overwrite another server's progress")
		if not session.closing and player.Parent == Players then
			player:Kick("Your progress session changed. Please rejoin safely.")
		end
		return false
	end
	return true
end

function PlayerData.load(player: Player): boolean
	if player.Parent ~= Players then
		return false
	end
	if sessions[player] ~= nil then
		return true
	end
	local key = "player-" .. tostring(player.UserId)
	local token = HttpService:GenerateGUID(false)
	local value: any = nil

	for attempt = 1, LOAD_LOCK_ATTEMPTS do
		local ok, result = updateWithRetry(key, function(old: any): any
			local record = SaveData.migrate(old, StageProgression.LAST_STAGE)
			local now = os.time()
			if SaveData.isLocked(record, token, now) then
				return nil
			end
			return SaveData.hold(record, token, now, LOCK_SECONDS)
		end)
		if not ok then
			return false
		end
		if result ~= nil then
			value = result
			break
		end
		if attempt < LOAD_LOCK_ATTEMPTS then
			task.wait(2 ^ attempt)
		end
	end
	if value == nil then
		return false
	end
	local record = SaveData.migrate(value, StageProgression.LAST_STAGE)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	local finishes = Instance.new("IntValue")
	finishes.Name = "Finishes"
	finishes.Value = record.finishes
	finishes.Parent = leaderstats
	leaderstats.Parent = player

	sessions[player] = {
		key = key,
		token = token,
		stage = record.furthestStage,
		furthestStage = record.furthestStage,
		finishes = record.finishes,
		finishedThisSession = false,
		stat = finishes,
		saving = false,
		closing = false,
	}
	player:SetAttribute("Stage", record.furthestStage)
	if player.Parent ~= Players then
		PlayerData.close(player)
		return false
	end
	return true
end

function PlayerData.getStage(player: Player): number?
	local session = sessions[player]
	if not session or session.closing then
		return nil
	end
	return session.stage
end

function PlayerData.save(player: Player): boolean
	return flush(player, false)
end

function PlayerData.advance(player: Player, touchedStage: number)
	local session = sessions[player]
	if not session or session.closing then
		return
	end
	local nextStage = StageProgression.advance(session.stage, touchedStage)
	if nextStage == session.stage then
		return
	end
	session.stage = nextStage
	session.furthestStage = StageProgression.furthest(session.furthestStage, nextStage)
	player:SetAttribute("Stage", nextStage)
	task.spawn(function()
		PlayerData.save(player)
	end)
end

function PlayerData.finish(player: Player)
	local session = sessions[player]
	if not session or session.closing or session.finishedThisSession then
		return
	end
	if not StageProgression.canFinish(session.stage) then
		return
	end
	session.finishedThisSession = true
	session.finishes += 1
	session.stat.Value = session.finishes
	task.spawn(function()
		PlayerData.save(player)
	end)
end

function PlayerData.autosave()
	for player, session in pairs(sessions) do
		if not session.closing then
			task.spawn(function()
				PlayerData.save(player)
			end)
		end
	end
end

function PlayerData.close(player: Player)
	local session = sessions[player]
	if not session then
		return
	end
	if session.closing then
		while sessions[player] == session do
			task.wait(0.05)
		end
		return
	end
	session.closing = true
	flush(player, true)
	sessions[player] = nil
end

return PlayerData
