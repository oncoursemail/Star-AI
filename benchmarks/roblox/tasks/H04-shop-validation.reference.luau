local Shop = {}
Shop.__index = Shop
function Shop.new(prices)
	return setmetatable({ prices = table.clone(prices) }, Shop)
end
function Shop:buy(player: Player, itemId: any): (boolean, string)
	if type(itemId) ~= "string" then return false, "bad item" end
	local price = rawget(self.prices, itemId)
	if type(price) ~= "number" then return false, "unknown item" end
	if player:GetAttribute("Owns_" .. itemId) then return false, "owned" end
	local coins = player:GetAttribute("Coins")
	if type(coins) ~= "number" or coins < price then return false, "not enough coins" end
	player:SetAttribute("Coins", coins - price)
	player:SetAttribute("Owns_" .. itemId, true)
	return true, "ok"
end
return Shop
