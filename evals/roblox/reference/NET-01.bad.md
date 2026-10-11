Here is the handler with the price check added.

```luau
local Catalog = { sword = 100, shield = 250 }
BuyItem.OnServerEvent:Connect(function(player, itemId, price)
	local coins = player.leaderstats.Coins
	if coins.Value >= price then
		coins.Value -= price
		giveItem(player, itemId)
	end
end)
```
