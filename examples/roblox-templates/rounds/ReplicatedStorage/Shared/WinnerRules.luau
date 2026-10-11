--!strict
-- Pure winner selection. Entries and scores must be computed by the server.
export type Entrant = { userId: number, alive: boolean, score: number }

local WinnerRules = {}

function WinnerRules.resolve(entries: { Entrant }, reason: string): number?
	if reason ~= "winner" and reason ~= "timeout" then
		return nil
	end

	local alive: { Entrant } = {}
	local seen: { [number]: boolean } = {}
	for _, entry in ipairs(entries) do
		if entry.alive then
			if seen[entry.userId] then
				return nil
			end
			seen[entry.userId] = true
			table.insert(alive, entry)
		end
	end

	if #alive == 1 then
		return alive[1].userId
	end
	if #alive == 0 or reason ~= "timeout" then
		return nil
	end

	-- On a timeout, a positive *unique* score wins; a tie or all-zero round
	-- is a draw. Never award the first element merely because of list order.
	local bestScore = 0
	local bestId: number? = nil
	local tied = false
	for _, entry in ipairs(alive) do
		if entry.score > bestScore then
			bestScore = entry.score
			bestId = entry.userId
			tied = false
		elseif entry.score == bestScore and bestScore > 0 then
			tied = true
		end
	end
	return if tied then nil else bestId
end

return WinnerRules
