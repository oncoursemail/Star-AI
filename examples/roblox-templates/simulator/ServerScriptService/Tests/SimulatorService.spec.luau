--!strict
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local RateLimiter = require(Shared:WaitForChild("RateLimiter"))
local Config = require(Shared:WaitForChild("SimulatorConfig"))
local Service = require(game:GetService("ServerScriptService"):WaitForChild("SimulatorService"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

local function act(profile, action: any, arg: any?)
	return Service.apply(profile, RateLimiter.new(0.25), 1, action, arg, 10)
end

return {
	["one thousand click requests per second buy no advantage"] = function()
		local profile = Service.newProfile()
		local limiter = RateLimiter.new(Config.CLICK_COOLDOWN)
		local successes = 0
		for i = 0, 999 do
			local ok = Service.apply(profile, limiter, 1, "Click", nil, i / 1000)
			if ok then
				successes += 1
			end
		end
		expect(successes == 4 and profile.coins == 4, "flood must earn only the four legitimate ticks")
		local clean = Service.newProfile()
		local regular = RateLimiter.new(Config.CLICK_COOLDOWN)
		for i = 0, 3 do
			Service.apply(clean, regular, 1, "Click", nil, i * 0.25)
		end
		expect(clean.coins == profile.coins, "flooding cannot beat ordinary clicks")
	end,
	["request payloads never set coins or upgrade price"] = function()
		local profile = Service.newProfile()
		expect(not act(profile, "Click", { coins = 999999 }), "client coins ignored")
		expect(not act(profile, "Upgrade", { cost = 0 }), "client prices ignored")
		expect(not act(profile, "BuyPet", { id = "dragon", cost = 0 }), "tables rejected")
		expect(not act(profile, "anything", nil), "unknown actions rejected")
		expect(profile.coins == 0 and profile.upgradeLevel == 0, "no mutation")
	end,
	["upgrades and pets use server prices and owned inventory"] = function()
		local profile = Service.newProfile()
		profile.coins = 500
		expect(act(profile, "Upgrade", nil), "upgrade affordable")
		expect(profile.upgradeLevel == 1 and profile.coins == 490, "price was exactly ten")
		expect(act(profile, "BuyPet", "bunny"), "pet purchase")
		expect(profile.coins == 415 and profile.pets.bunny == true, "server price deducted")
		expect(not act(profile, "BuyPet", "bunny"), "cannot purchase pet twice")
		expect(not act(profile, "EquipPet", "dragon"), "cannot equip an unowned pet")
		expect(act(profile, "EquipPet", "bunny"), "owned pet equipped")
		expect(Service.reward(profile) > 1, "equipped pet increases rewards")
	end,
	["zone gates use server-recorded run earnings"] = function()
		local profile = Service.newProfile()
		expect(not act(profile, "EnterZone", "canyon"), "zone is locked")
		profile.runEarned = 200
		expect(act(profile, "EnterZone", "canyon"), "threshold unlocks zone")
		expect(profile.zone == "canyon", "chosen zone becomes active")
		expect(not act(profile, "EnterZone", "made_up"), "unknown zone denied")
	end,
	["rebirth resets the run while preserving bought pets"] = function()
		local profile = Service.newProfile()
		profile.coins = Config.REBIRTH_COST
		profile.runEarned = 5000
		profile.upgradeLevel = 3
		profile.zone = "orbit"
		profile.pets.bunny = true
		profile.equippedPet = "bunny"
		expect(act(profile, "Rebirth", nil), "rebirth purchased with coins")
		expect(profile.coins == 0 and profile.runEarned == 0 and profile.upgradeLevel == 0, "run reset")
		expect(profile.rebirths == 1 and profile.zone == "meadow", "rebirth and zone reset")
		expect(profile.pets.bunny and profile.equippedPet == "bunny", "pets are permanent")
		expect(not act(profile, "Rebirth", nil), "cannot rebirth again without currency")
	end,
	["corrupted save fields cannot mint coins or fake pet ownership"] = function()
		local profile = Service.normalize({
			coins = math.huge, runEarned = -10, rebirths = -1, upgradeLevel = math.huge,
			zone = "orbit", pets = { dragon = "true", bunny = true, unknown = true },
			equippedPet = "dragon",
		})
		expect(profile.coins == 0 and profile.rebirths == 0, "invalid numeric fields removed")
		expect(profile.zone == "meadow" and profile.upgradeLevel == 0, "invalid progress dropped")
		expect(profile.pets.bunny == true and profile.pets.dragon == nil, "only boolean owned flags survive")
		expect(profile.equippedPet == nil, "cannot equip an unowned pet")
		local snap = Service.snapshot(profile)
		snap.pets.bunny = false
		expect(profile.pets.bunny, "snapshot must not expose mutable server state")
	end,
}
