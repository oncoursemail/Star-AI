--!strict
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local WinnerRules = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("WinnerRules"))

return {
	["zero participants never produce a winner"] = function()
		assert(WinnerRules.resolve({}, "empty") == nil)
		assert(WinnerRules.resolve({}, "winner") == nil)
		assert(WinnerRules.resolve({}, "timeout") == nil)
	end,
	["one survivor wins by last player standing"] = function()
		local entrants = {
			{ userId = 11, alive = false, score = 20 },
			{ userId = 22, alive = true, score = 0 },
		}
		assert(WinnerRules.resolve(entrants, "winner") == 22)
	end,
	["two survivors are not a last-standing win"] = function()
		assert(WinnerRules.resolve({
			{ userId = 11, alive = true, score = 3 },
			{ userId = 22, alive = true, score = 6 },
		}, "winner") == nil)
	end,
	["a lone survivor wins on timeout"] = function()
		assert(WinnerRules.resolve({
			{ userId = 11, alive = false, score = 100 },
			{ userId = 22, alive = true, score = 0 },
		}, "timeout") == 22)
	end,
	["timeout awards only the unique positive score leader"] = function()
		local entrants = {
			{ userId = 11, alive = true, score = 3 },
			{ userId = 22, alive = true, score = 7 },
			{ userId = 33, alive = false, score = 90 },
		}
		assert(WinnerRules.resolve(entrants, "timeout") == 22)
		assert(WinnerRules.resolve({ entrants[2], entrants[1], entrants[3] }, "timeout") == 22)
	end,
	["a tied timeout is a draw regardless of order"] = function()
		local entrants = {
			{ userId = 22, alive = true, score = 9 },
			{ userId = 11, alive = true, score = 9 },
		}
		assert(WinnerRules.resolve(entrants, "timeout") == nil)
		assert(WinnerRules.resolve({ entrants[2], entrants[1] }, "timeout") == nil)
	end,
	["all-zero timeout is a draw"] = function()
		assert(WinnerRules.resolve({
			{ userId = 11, alive = true, score = 0 },
			{ userId = 22, alive = true, score = 0 },
		}, "timeout") == nil)
	end,
	["zero survivors and disconnects are draws"] = function()
		local entries = { { userId = 11, alive = false, score = 100 } }
		assert(WinnerRules.resolve(entries, "winner") == nil)
		assert(WinnerRules.resolve(entries, "empty") == nil)
		assert(WinnerRules.resolve(entries, "timeout") == nil)
	end,
	["unknown end reasons never give rewards"] = function()
		assert(WinnerRules.resolve({ { userId = 11, alive = true, score = 99 } }, "load_failed") == nil)
	end,
	["duplicate living identities do not double-award"] = function()
		assert(WinnerRules.resolve({
			{ userId = 11, alive = true, score = 5 },
			{ userId = 11, alive = true, score = 8 },
		}, "timeout") == nil)
	end,
}
