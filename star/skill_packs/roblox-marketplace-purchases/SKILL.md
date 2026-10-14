---
name: roblox-marketplace-purchases
description: Opt-in Roblox monetisation and economy recipes - idempotent ProcessReceipt for developer products, game pass checks, and a server-authoritative coin shop in typed Luau.
---
# roblox-marketplace-purchases
## When to use
Use for Roblox developer products, game passes, ProcessReceipt, Robux purchases and in-game currency shops where the server must own prices and balances. For general save systems see the data store packs; this pack covers how purchases reach saved data.

## Ten concrete rules
1. Grant developer products only in MarketplaceService.ProcessReceipt, set once in one server Script; PromptProductPurchaseFinished does not prove a purchase. [S1][S2]
2. Return PurchaseGranted only after the grant is saved; otherwise return NotProcessedYet and the callback runs again when the player rejoins or buys again. [S1][S7]
3. A receipt can be processed on two servers at once and calls arrive in any order, so record PurchaseId and skip ids already handled. [S1][S3]
4. Without session locking, check the PurchaseId history and save the grant in one atomic UpdateAsync on the player's key. [S3][S4]
5. The player must be in the server for ProcessReceipt to run; look them up with Players:GetPlayerByUserId. [S1][S5]
6. Check passes with UserOwnsGamePassAsync inside pcall; results are cached and refreshed when PromptGamePassPurchaseFinished fires. [S6][S1]
7. Handle PromptGamePassPurchaseFinished on the server to grant a pass bought during the session. [S6]
8. Prices, balances and ownership live on the server. A shop remote receives an item id only, looks up the price in a server table and checks the balance. [S8]
9. Validate every remote argument's type and allow-list ids; reject unknown items. [S8]
10. Use GetProductInfoAsync for product details; GetProductInfo is deprecated. [S1]

## Three correct Luau examples
All three are server Scripts in ServerScriptService. Replace the IDs with your own.

### Example 1: idempotent ProcessReceipt with one atomic save
~~~luau
--!strict
local DataStoreService = game:GetService("DataStoreService")
local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local store = DataStoreService:GetDataStore("PlayerData")
type Data = { coins: number, purchases: { string } }
local COIN_PACKS: { [number]: number } = { [1234567] = 100 } -- product ID -> coins

local function processReceipt(receipt: { [string]: any }): Enum.ProductPurchaseDecision
	local coins = COIN_PACKS[receipt.ProductId]
	local player = Players:GetPlayerByUserId(receipt.PlayerId)
	if not coins or not player then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local id = tostring(receipt.PurchaseId)
	local ok, saved = pcall(store.UpdateAsync, store, "player_" .. receipt.PlayerId, function(old: any): Data?
		if old ~= nil and typeof(old) ~= "table" then
			return nil -- unknown schema: change nothing
		end
		local data: Data = old or { coins = 0, purchases = {} }
		if not table.find(data.purchases, id) then
			data.coins += coins
			table.insert(data.purchases, id)
			if #data.purchases > 100 then
				table.remove(data.purchases, 1)
			end
		end
		return data
	end)
	if not ok or saved == nil then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	player:SetAttribute("Coins", saved.coins) -- display only
	return Enum.ProductPurchaseDecision.PurchaseGranted
end

MarketplaceService.ProcessReceipt = processReceipt
~~~
A second run of the same receipt finds its id and adds nothing. [S1][S3][S4]

### Example 2: VIP game pass on join and after purchase
~~~luau
--!strict
local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local VIP_PASS = 7654321

local function refresh(player: Player)
	local ok, owns = pcall(MarketplaceService.UserOwnsGamePassAsync, MarketplaceService, player.UserId, VIP_PASS)
	if ok then
		player:SetAttribute("VIP", owns == true)
	else
		warn("Pass check failed; will retry on rejoin", owns)
	end
end

Players.PlayerAdded:Connect(refresh)
for _, player in Players:GetPlayers() do
	task.spawn(refresh, player)
end

MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player: Player, passId: number, purchased: boolean)
	if purchased and passId == VIP_PASS then
		player:SetAttribute("VIP", true)
	end
end)
~~~
Server-set attributes replicate, so client UI can read VIP but cannot grant it. [S1][S6]

### Example 3: server-authoritative coin shop
~~~luau
--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local buy = ReplicatedStorage:WaitForChild("BuyItem") :: RemoteFunction
local PRICES: { [string]: number } = { Sword = 250, Shield = 400 }
local owned: { [Player]: { [string]: boolean } } = {}

buy.OnServerInvoke = function(player: Player, itemId: unknown): (boolean, string)
	if typeof(itemId) ~= "string" or PRICES[itemId] == nil then
		return false, "unknown item"
	end
	local stats = player:FindFirstChild("leaderstats")
	local coins = if stats then stats:FindFirstChild("Coins") else nil
	if not coins or not coins:IsA("IntValue") then
		return false, "no wallet"
	end
	local items = owned[player] or {}
	owned[player] = items
	if items[itemId] then
		return false, "already owned"
	end
	local price = PRICES[itemId]
	if coins.Value < price then
		return false, "not enough coins"
	end
	coins.Value -= price
	items[itemId] = true
	return true, "bought"
end

Players.PlayerRemoving:Connect(function(player: Player)
	owned[player] = nil
end)
~~~
The client never sends a price; it cannot buy what is missing from PRICES. [S8][S9]

## Three common mistakes
1. Granting products in PromptProductPurchaseFinished or returning PurchaseGranted before the save succeeded. [S1][S2]
2. Not recording PurchaseId, so a retried or parallel receipt grants twice. [S1][S3]
3. Trusting a price, balance or item list sent by the client. [S8]

## Checklist
- [ ] One ProcessReceipt for all products, set on the server.
- [ ] PurchaseId recorded in the same atomic save as the grant.
- [ ] NotProcessedYet on any failure.
- [ ] Pass checks in pcall, refreshed on purchase finished.
- [ ] Shop prices and balances only on the server.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S10]. IDs and prices are placeholders.
