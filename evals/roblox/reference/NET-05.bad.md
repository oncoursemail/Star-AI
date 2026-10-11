```luau
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local store = DataStoreService:GetDataStore("PlayerData")
local PlayerData = {}
Players.PlayerRemoving:Connect(function(player)
	store:SetAsync("Player_" .. player.UserId, { coins = 0 })
end)
game:BindToClose(function() end)
return PlayerData
```
