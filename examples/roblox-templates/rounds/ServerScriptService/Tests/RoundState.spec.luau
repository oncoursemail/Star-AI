--!strict
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RoundState = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("RoundState"))

local function expectStep(current: string, event: string, players: number, expected: string?, reason: string?)
	local result, why = RoundState.next(current, event, players, 2)
	assert(result == expected, current .. " / " .. event .. " expected " .. tostring(expected) .. ", got " .. tostring(result))
	assert(why == reason, "transition reason should be " .. tostring(reason) .. ", got " .. tostring(why))
end

return {
	["Intermission to Loading after a full countdown"] = function()
		expectStep("Intermission", "countdown_elapsed", 2, "Loading", nil)
	end,
	["Intermission stays waiting with zero players"] = function()
		expectStep("Intermission", "countdown_elapsed", 0, "Intermission", "waiting_for_players")
	end,
	["Intermission stays waiting with one player"] = function()
		expectStep("Intermission", "countdown_elapsed", 1, "Intermission", "waiting_for_players")
	end,
	["Loading to Playing with enough players"] = function()
		expectStep("Loading", "map_ready", 3, "Playing", nil)
	end,
	["Loading to Intermission if the last players left"] = function()
		expectStep("Loading", "map_ready", 0, "Intermission", "insufficient_players")
	end,
	["Loading to Intermission below minimum"] = function()
		expectStep("Loading", "map_ready", 1, "Intermission", "insufficient_players")
	end,
	["Loading to Intermission on map failure"] = function()
		expectStep("Loading", "load_failed", 2, "Intermission", "load_failed")
	end,
	["Playing to Ended when a winner is found"] = function()
		expectStep("Playing", "winner", 1, "Ended", nil)
	end,
	["Playing to Ended on a timeout"] = function()
		expectStep("Playing", "timeout", 2, "Ended", nil)
	end,
	["Playing to Ended when everyone has left"] = function()
		expectStep("Playing", "empty", 0, "Ended", nil)
	end,
	["Ended to Intermission after results"] = function()
		expectStep("Ended", "results_elapsed", 0, "Intermission", nil)
	end,
	["forbids skipping any state"] = function()
		for _, from in ipairs({ "Intermission", "Loading", "Playing", "Ended" }) do
			for _, event in ipairs({ "countdown_elapsed", "map_ready", "load_failed", "winner", "timeout",
				"empty", "results_elapsed", "unknown" }) do
				local result = RoundState.next(from, event, 2, 2)
				if result ~= nil then
					assert((from == "Intermission" and event == "countdown_elapsed")
						or (from == "Loading" and (event == "map_ready" or event == "load_failed"))
						or (from == "Playing" and (event == "winner" or event == "timeout" or event == "empty"))
						or (from == "Ended" and event == "results_elapsed"), "unexpected edge " .. from .. " " .. event)
				end
			end
		end
	end,
	["rejects bad states and population counts"] = function()
		expectStep("Unknown", "winner", 2, nil, "invalid_input")
		expectStep("Playing", "winner", -1, nil, "invalid_input")
		expectStep("Playing", "winner", 1.5, nil, "invalid_input")
		local result, why = RoundState.next("Intermission", "countdown_elapsed", 2, 0)
		assert(result == nil and why == "invalid_input", "minimum players must be positive")
	end,
}
