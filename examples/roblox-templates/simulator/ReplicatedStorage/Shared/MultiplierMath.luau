--!strict
-- Deterministic reward math. No player, network, or Roblox service dependencies.
local MultiplierMath = {}

MultiplierMath.MAX_REWARD = 1000000

local function count(value: any, maximum: number): number
	if type(value) ~= "number" or value ~= value or value == math.huge
		or value < 0 then
		return 0
	end
	return math.min(maximum, math.floor(value))
end

local function bonus(value: any): number
	if type(value) ~= "number" or value ~= value or value < 1
		or value == math.huge then
		return 1
	end
	return math.min(3, value)
end

function MultiplierMath.gain(base: any, upgrades: any, rebirths: any, zoneBonus: any, petBonus: any): number
	local baseValue = count(base, 10)
	if baseValue == 0 then
		baseValue = 1
	end
	local upgradeValue = count(upgrades, 20)
	local rebirthValue = count(rebirths, 50)
	local amount = baseValue * (1 + upgradeValue * 0.5) * (1 + rebirthValue * 0.25)
		* bonus(zoneBonus) * bonus(petBonus)
	return math.min(MultiplierMath.MAX_REWARD, math.max(1, math.floor(amount)))
end

return MultiplierMath
