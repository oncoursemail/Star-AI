--!strict
-- Public display catalog; the server uses its own copy and never accepts client-supplied prices.
local Config = {}

Config.BASE_GAIN = 1
Config.CLICK_COOLDOWN = 0.25
Config.REQUEST_COOLDOWN = 0.2
Config.SNAPSHOT_COOLDOWN = 0.5
Config.MAX_COINS = 1000000000000
Config.MAX_REBIRTHS = 50
Config.REBIRTH_COST = 2500

Config.ZONE_ORDER = { "meadow", "canyon", "orbit" }
Config.ZONES = {
	meadow = { name = "Meadow", threshold = 0, multiplier = 1 },
	canyon = { name = "Canyon", threshold = 200, multiplier = 1.5 },
	orbit = { name = "Orbit", threshold = 1000, multiplier = 2.5 },
}

Config.PET_ORDER = { "bunny", "fox", "dragon" }
Config.PETS = {
	bunny = { name = "Bunny", cost = 75, multiplier = 1.25 },
	fox = { name = "Fox", cost = 400, multiplier = 1.5 },
	dragon = { name = "Dragon", cost = 1800, multiplier = 2 },
}

return Config
