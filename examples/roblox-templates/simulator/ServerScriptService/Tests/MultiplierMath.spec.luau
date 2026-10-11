--!strict
local Math = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("MultiplierMath"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

return {
	["base gains and purchased bonuses are deterministic"] = function()
		expect(Math.gain(1, 0, 0, 1, 1) == 1, "fresh player earns one")
		expect(Math.gain(2, 2, 1, 2, 1.5) == 15, "upgrades, rebirths and equipped pet stack")
		expect(Math.gain(1, 2, 0, 1, 1) == 2, "two upgrades double base")
	end,
	["invalid or exaggerated multipliers cannot inflate rewards"] = function()
		expect(Math.gain(1, -1, 0 / 0, -4, math.huge) == 1, "invalid bonuses fall back")
		expect(Math.gain(1, math.huge, math.huge, math.huge, math.huge) == 1, "infinity is not a bonus")
		local capped = Math.gain(10 ^ 100, 999999, 999999, 999, 999)
		expect(capped <= Math.MAX_REWARD and capped >= 1, "all rewards have an upper bound")
	end,
}
