The server must never read a price from the client. Look the item up in the server's own catalog and ignore every other argument.

```luau
local Catalog = { sword = 100, shield = 250 }
local owned: { [Player]: { [string]: boolean } } = {}

BuyItem.OnServerEvent:Connect(function(player, itemId)
	if type(itemId) ~= "string" or #itemId > 32 then
		return
	end
	local price = Catalog[itemId]
	if price == nil then
		return
	end
	local items = owned[player]
	if items == nil then
		items = {}
		owned[player] = items
	end
	if items[itemId] then
		return
	end
	local coins = player.leaderstats.Coins
	if coins.Value < price then
		return
	end
	items[itemId] = true
	coins.Value -= price
	giveItem(player, itemId)
end)
```
