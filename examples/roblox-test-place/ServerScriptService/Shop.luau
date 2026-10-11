--!strict
-- Server-side purchase rules. A request names only the item; price and balance are read on the server.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Catalog = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Catalog"))

export type Wallet = { coins: number, owned: { [string]: boolean } }
export type Result = { ok: boolean, reason: string?, coins: number }

local Shop = {}

function Shop.newWallet(coins: number): Wallet
	return { coins = math.max(0, math.floor(coins)), owned = {} }
end

function Shop.purchase(wallet: Wallet, itemId: any): Result
	if type(itemId) ~= "string" then
		return { ok = false, reason = "bad_request", coins = wallet.coins }
	end
	local item = Catalog.get(itemId)
	if not item then
		return { ok = false, reason = "unknown_item", coins = wallet.coins }
	end
	if wallet.owned[item.id] then
		return { ok = false, reason = "already_owned", coins = wallet.coins }
	end
	if wallet.coins < item.price then
		return { ok = false, reason = "not_enough_coins", coins = wallet.coins }
	end
	wallet.coins -= item.price
	wallet.owned[item.id] = true
	return { ok = true, coins = wallet.coins }
end

return Shop
