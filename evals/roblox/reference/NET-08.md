The server should own the ammo count and never wait on a client. The client may only ask to reload.

```luau
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local reload = Instance.new("RemoteEvent")
reload.Name = "Reload"
reload.Parent = ReplicatedStorage

local MAX_AMMO = 30
local ammo: { [Player]: number } = {}

Players.PlayerAdded:Connect(function(player)
	ammo[player] = MAX_AMMO
end)
Players.PlayerRemoving:Connect(function(player)
	ammo[player] = nil
end)

reload.OnServerEvent:Connect(function(player)
	if ammo[player] ~= nil then
		ammo[player] = MAX_AMMO
	end
end)
```
