--!strict
-- Pure transition rules: no Roblox services, timers, or player instances.
local RoundState = {}

RoundState.Intermission = "Intermission"
RoundState.Loading = "Loading"
RoundState.Playing = "Playing"
RoundState.Ended = "Ended"

local valid = {
	Intermission = true,
	Loading = true,
	Playing = true,
	Ended = true,
}

-- Returning nil means a forbidden transition. Intermission may stay put when
-- a countdown ends with too few players (including zero).
function RoundState.next(current: string, event: string, players: number, minimum: number): (string?, string?)
	if not valid[current] or type(players) ~= "number" or players < 0
		or players ~= math.floor(players) or type(minimum) ~= "number"
		or minimum < 1 or minimum ~= math.floor(minimum) then
		return nil, "invalid_input"
	end

	if current == RoundState.Intermission and event == "countdown_elapsed" then
		if players < minimum then
			return RoundState.Intermission, "waiting_for_players"
		end
		return RoundState.Loading, nil
	elseif current == RoundState.Loading then
		if event == "load_failed" then
			return RoundState.Intermission, "load_failed"
		elseif event == "map_ready" then
			if players < minimum then
				return RoundState.Intermission, "insufficient_players"
			end
			return RoundState.Playing, nil
		end
	elseif current == RoundState.Playing then
		if event == "winner" or event == "timeout" or event == "empty" then
			return RoundState.Ended, nil
		end
	elseif current == RoundState.Ended and event == "results_elapsed" then
		return RoundState.Intermission, nil
	end

	return nil, "illegal_transition"
end

return RoundState
