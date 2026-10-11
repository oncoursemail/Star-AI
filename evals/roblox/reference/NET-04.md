Use an UnreliableRemoteEvent for the 20 Hz aim updates (a lost update is replaced by the next one) and a RemoteEvent for the round end, which must arrive.

```luau
-- Server Script
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local aim = Instance.new("UnreliableRemoteEvent")
aim.Name = "Aim"
aim.Parent = ReplicatedStorage

local roundEnded = Instance.new("RemoteEvent")
roundEnded.Name = "RoundEnded"
roundEnded.Parent = ReplicatedStorage

local lastAim: { [Player]: Vector3 } = {}

aim.OnServerEvent:Connect(function(player, direction)
	if typeof(direction) ~= "Vector3" then
		return
	end
	if direction ~= direction or direction.Magnitude == math.huge then
		return -- NaN or infinite components
	end
	lastAim[player] = direction.Unit
end)

local function endRound()
	roundEnded:FireAllClients()
end
```

```luau
-- LocalScript
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local aim = ReplicatedStorage:WaitForChild("Aim")
local roundEnded = ReplicatedStorage:WaitForChild("RoundEnded")

local SEND_INTERVAL = 1 / 20
local elapsed = 0
local camera = workspace.CurrentCamera

RunService.Heartbeat:Connect(function(dt)
	elapsed += dt
	if elapsed < SEND_INTERVAL then
		return
	end
	elapsed -= SEND_INTERVAL
	aim:FireServer(camera.CFrame.LookVector)
end)

roundEnded.OnClientEvent:Connect(function()
	print("round over")
end)
```
