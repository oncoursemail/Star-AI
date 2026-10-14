---
name: roblox-teleport-matchmaking
description: Opt-in Roblox recipes for lobby-to-match flows - TeleportAsync with retries, reserved servers for groups, TeleportInitFailed, memory store queues and safe use of teleport data in typed Luau.
---
# roblox-teleport-matchmaking
## When to use
Use for Roblox lobbies, match queues, parties sent to a private match, moving players between places, reserved servers and reading teleport data on arrival. Teleports do not work in Studio playtests; test in a live game.

## Ten concrete rules
1. Teleport from the server with TeleportService:TeleportAsync(placeId, players, options); the client Teleport method is deprecated. [S1][S2]
2. Send a group in one call so it lands together; without options the first player's data drives server choice. [S1]
3. For a private match, set TeleportOptions.ShouldReserveServer = true; ReserveServerAsync replaces the deprecated ReserveServer. [S1][S2][S3]
4. Teleports can throw: pcall and retry a few times with a short wait. [S1]
5. A call can succeed and still fail later: handle TeleportInitFailed, wait longer on Flooded, retry on Failure, report other results. [S1][S4]
6. SetTeleportData is visible to the client and unencrypted; never send currency or inventory, keep those in data stores or memory stores. [S1][S5]
7. On arrival, read Player:GetJoinData() on the server, check SourcePlaceId against your own places and validate TeleportData types. [S5]
8. For queues across lobby servers use MemoryStoreService:GetQueue with pcall, short expirations and RemoveAsync after each read; read items become invisible for the timeout. [S6][S7]
9. Set Access Control for Places to Secure when non-start places must only be reached by server teleports. [S1]
10. Reserved servers have PrivateServerId set and PrivateServerOwnerId 0; use that to run match-only logic. [S8]

## Three correct Luau examples
All three are server Scripts. Replace place IDs with your own.

### Example 1: teleport with retries and failure handling
~~~luau
--!strict
local TeleportService = game:GetService("TeleportService")
local ATTEMPTS, RETRY, FLOOD = 4, 1, 15

local function safeTeleport(placeId: number, players: { Player }, options: TeleportOptions?): boolean
	for attempt = 1, ATTEMPTS do
		local ok, err = pcall(TeleportService.TeleportAsync, TeleportService, placeId, players, options)
		if ok then
			return true
		end
		warn(`Teleport attempt {attempt} failed: {err}`)
		task.wait(RETRY)
	end
	return false
end

TeleportService.TeleportInitFailed:Connect(function(player: Player, result: Enum.TeleportResult,
	message: string, placeId: number, options: TeleportOptions)
	if result == Enum.TeleportResult.Flooded then
		task.wait(FLOOD)
	elseif result == Enum.TeleportResult.Failure then
		task.wait(RETRY)
	else
		warn(`Teleport not retried ({result.Name}): {message}`)
		return
	end
	safeTeleport(placeId, { player }, options)
end)

return safeTeleport
~~~
Invalid results such as Unauthorized are reported, not retried. [S1][S4]

### Example 2: lobby pad sends groups of four to a reserved match
~~~luau
--!strict
local Players = game:GetService("Players")
local TeleportService = game:GetService("TeleportService")
local MATCH_PLACE, SIZE = 1234567890, 4
local pad = workspace:WaitForChild("QueuePad") :: BasePart
local waiting: { Player } = {}
local busy = false

local function launch()
	local group = table.move(waiting, 1, SIZE, 1, {})
	for _ = 1, SIZE do
		table.remove(waiting, 1)
	end
	local options = Instance.new("TeleportOptions")
	options.ShouldReserveServer = true
	options:SetTeleportData({ mode = "duel" }) -- not secret, not trusted
	local ok, err = pcall(TeleportService.TeleportAsync, TeleportService, MATCH_PLACE, group, options)
	if not ok then
		warn("Match teleport failed", err)
		for _, player in group do
			if player.Parent then
				table.insert(waiting, player) -- back in line
			end
		end
	end
end

pad.Touched:Connect(function(hit: BasePart)
	local model = hit:FindFirstAncestorOfClass("Model")
	local player = if model then Players:GetPlayerFromCharacter(model) else nil
	if player and not table.find(waiting, player) then
		table.insert(waiting, player)
		if #waiting >= SIZE and not busy then
			busy = true
			launch()
			busy = false
		end
	end
end)

Players.PlayerRemoving:Connect(function(player: Player)
	local index = table.find(waiting, player)
	if index then
		table.remove(waiting, index)
	end
end)
~~~
table.find keeps each player in line once; busy stops overlapping launches while a teleport yields. [S1][S9]

### Example 3: match place checks where players came from
~~~luau
--!strict
local Players = game:GetService("Players")
local LOBBY_PLACE = 1111111111
local isReserved = game.PrivateServerId ~= "" and game.PrivateServerOwnerId == 0

local function onJoin(player: Player)
	local join = player:GetJoinData()
	local data = join.TeleportData
	local mode = "duel"
	if isReserved and join.SourcePlaceId == LOBBY_PLACE and typeof(data) == "table"
		and (data.mode == "duel" or data.mode == "teams") then
		mode = data.mode -- a known value from our own lobby
	end
	player:SetAttribute("Mode", mode)
end

Players.PlayerAdded:Connect(onJoin)
for _, player in Players:GetPlayers() do
	task.spawn(onJoin, player)
end
~~~
Only choose among known modes; rewards and currency come from server storage. [S5][S8]

## Three common mistakes
1. Teleporting without pcall, retries or TeleportInitFailed handling. [S1]
2. Putting currency or unlocks in teleport data, or trusting it on arrival. [S1][S5]
3. Matching players with in-memory tables across servers instead of a memory store. [S6]

## Checklist
- [ ] Teleports run on the server in pcall with bounded retries.
- [ ] TeleportInitFailed is handled.
- [ ] Groups use ShouldReserveServer for private matches.
- [ ] Teleport data is non-secret and validated on arrival.
- [ ] Cross-server queues use memory stores with short expirations.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S9]. IDs and sizes are placeholders.
