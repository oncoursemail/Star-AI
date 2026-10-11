--!strict
-- Server-owned simulator state transitions. Only action names/ids come from the client.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared:WaitForChild("SimulatorConfig"))
local CostCurve = require(Shared:WaitForChild("CostCurve"))
local MultiplierMath = require(Shared:WaitForChild("MultiplierMath"))
local RateLimiter = require(Shared:WaitForChild("RateLimiter"))

local SimulatorService = {}

export type Profile = {
	coins: number,
	runEarned: number,
	lifetimeEarned: number,
	upgradeLevel: number,
	rebirths: number,
	zone: string,
	pets: { [string]: boolean },
	equippedPet: string?,
}

local function safeInteger(value: any, upper: number): number
	if type(value) ~= "number" or value ~= value or value < 0 or value == math.huge then
		return 0
	end
	return math.min(upper, math.floor(value))
end

function SimulatorService.newProfile(): Profile
	return {
		coins = 0,
		runEarned = 0,
		lifetimeEarned = 0,
		upgradeLevel = 0,
		rebirths = 0,
		zone = "meadow",
		pets = {},
		equippedPet = nil,
	}
end

function SimulatorService.normalize(raw: any): Profile
	if type(raw) ~= "table" then
		return SimulatorService.newProfile()
	end
	local pets: { [string]: boolean } = {}
	if type(raw.pets) == "table" then
		for _, id in ipairs(Config.PET_ORDER) do
			if raw.pets[id] == true then
				pets[id] = true
			end
		end
	end
	local runEarned = safeInteger(raw.runEarned, Config.MAX_COINS)
	local zone = if type(raw.zone) == "string" then raw.zone else "meadow"
	if not Config.ZONES[zone] or runEarned < Config.ZONES[zone].threshold then
		zone = "meadow"
	end
	local equippedPet = if type(raw.equippedPet) == "string" and pets[raw.equippedPet]
		then raw.equippedPet else nil
	return {
		coins = safeInteger(raw.coins, Config.MAX_COINS),
		runEarned = runEarned,
		lifetimeEarned = safeInteger(raw.lifetimeEarned, Config.MAX_COINS),
		upgradeLevel = safeInteger(raw.upgradeLevel, CostCurve.MAX_LEVEL),
		rebirths = safeInteger(raw.rebirths, Config.MAX_REBIRTHS),
		zone = zone,
		pets = pets,
		equippedPet = equippedPet,
	}
end

function SimulatorService.reward(profile: Profile): number
	local zone = Config.ZONES[profile.zone] or Config.ZONES.meadow
	local pet = if profile.equippedPet then Config.PETS[profile.equippedPet] else nil
	return MultiplierMath.gain(Config.BASE_GAIN, profile.upgradeLevel, profile.rebirths,
		zone.multiplier, if pet then pet.multiplier else 1)
end

function SimulatorService.apply(profile: Profile, clickLimit: RateLimiter.State, userId: number,
	action: any, arg: any, now: number): (boolean, string)
	if type(action) ~= "string" then
		return false, "bad_request"
	end
	if action == "Click" then
		if arg ~= nil then
			return false, "bad_request"
		end
		if not RateLimiter.allow(clickLimit, userId, now) then
			return false, "cooldown"
		end
		local amount = math.min(SimulatorService.reward(profile), Config.MAX_COINS - profile.coins)
		if amount <= 0 then
			return false, "wallet_full"
		end
		profile.coins += amount
		profile.runEarned = math.min(Config.MAX_COINS, profile.runEarned + amount)
		profile.lifetimeEarned = math.min(Config.MAX_COINS, profile.lifetimeEarned + amount)
		return true, "earned"
	elseif action == "Upgrade" then
		if arg ~= nil then
			return false, "bad_request"
		end
		local price = CostCurve.price(profile.upgradeLevel)
		if not price then
			return false, "max_upgrade"
		end
		if profile.coins < price then
			return false, "not_enough_coins"
		end
		profile.coins -= price
		profile.upgradeLevel += 1
		return true, "upgraded"
	elseif action == "EnterZone" then
		if type(arg) ~= "string" or not Config.ZONES[arg] then
			return false, "unknown_zone"
		end
		if profile.runEarned < Config.ZONES[arg].threshold then
			return false, "zone_locked"
		end
		profile.zone = arg
		return true, "zone_entered"
	elseif action == "BuyPet" then
		if type(arg) ~= "string" or not Config.PETS[arg] then
			return false, "unknown_pet"
		end
		if profile.pets[arg] then
			return false, "already_owned"
		end
		local price = Config.PETS[arg].cost
		if profile.coins < price then
			return false, "not_enough_coins"
		end
		profile.coins -= price
		profile.pets[arg] = true
		return true, "pet_bought"
	elseif action == "EquipPet" then
		if type(arg) ~= "string" or not profile.pets[arg] or not Config.PETS[arg] then
			return false, "not_owned"
		end
		profile.equippedPet = arg
		return true, "pet_equipped"
	elseif action == "Rebirth" then
		if arg ~= nil then
			return false, "bad_request"
		end
		if profile.rebirths >= Config.MAX_REBIRTHS then
			return false, "max_rebirths"
		end
		if profile.coins < Config.REBIRTH_COST then
			return false, "not_enough_coins"
		end
		profile.rebirths += 1
		profile.coins = 0
		profile.runEarned = 0
		profile.upgradeLevel = 0
		profile.zone = "meadow"
		return true, "reborn"
	end
	return false, "unknown_action"
end

function SimulatorService.snapshot(profile: Profile)
	local owned: { [string]: boolean } = {}
	for id, isOwned in pairs(profile.pets) do
		if isOwned and Config.PETS[id] then
			owned[id] = true
		end
	end
	return {
		coins = profile.coins,
		runEarned = profile.runEarned,
		lifetimeEarned = profile.lifetimeEarned,
		upgradeLevel = profile.upgradeLevel,
		nextUpgradeCost = CostCurve.price(profile.upgradeLevel),
		rebirths = profile.rebirths,
		rebirthCost = Config.REBIRTH_COST,
		zone = profile.zone,
		pets = owned,
		equippedPet = profile.equippedPet,
		clickGain = SimulatorService.reward(profile),
	}
end

return SimulatorService
