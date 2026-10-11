--!strict
local ServerScriptService = game:GetService("ServerScriptService")
local Shop = require(ServerScriptService:WaitForChild("Shop"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

return {
	["buys an item the player can afford"] = function()
		local wallet = Shop.newWallet(60)
		local result = Shop.purchase(wallet, "speed_coil")
		expect(result.ok, "purchase should succeed")
		expect(result.coins == 10, "50 coins should be taken")
		expect(wallet.owned.speed_coil == true, "the item should be owned")
	end,
	["refuses when coins are missing"] = function()
		local wallet = Shop.newWallet(10)
		local result = Shop.purchase(wallet, "trail")
		expect(not result.ok and result.reason == "not_enough_coins", "should refuse")
		expect(wallet.coins == 10, "no coins may be taken")
	end,
	["refuses a second purchase of the same item"] = function()
		local wallet = Shop.newWallet(500)
		Shop.purchase(wallet, "trail")
		local again = Shop.purchase(wallet, "trail")
		expect(not again.ok and again.reason == "already_owned", "should refuse")
		expect(wallet.coins == 380, "only one price may be taken")
	end,
	["ignores anything that is not an item id"] = function()
		local wallet = Shop.newWallet(500)
		expect(Shop.purchase(wallet, { price = 0 }).reason == "bad_request", "a table is not an item id")
		expect(Shop.purchase(wallet, "free_everything").reason == "unknown_item", "unknown ids are refused")
	end,
}
