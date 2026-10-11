```luau
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")

local player = Players.LocalPlayer
local character = script.Parent
local humanoid = character:WaitForChild("Humanoid")
local animator = humanoid:WaitForChild("Animator")

local animation = Instance.new("Animation")
animation.AnimationId = "rbxassetid://180435792"
local swing = animator:LoadAnimation(animation)
swing.Priority = Enum.AnimationPriority.Action

local hitWindowOpen = false
local connections = {}

local function disconnectAll()
	for _, connection in connections do
		connection:Disconnect()
	end
	table.clear(connections)
end

swing.Stopped:Connect(function()
	hitWindowOpen = false
	disconnectAll()
end)

local function startSwing()
	if swing.IsPlaying then
		return
	end
	disconnectAll()
	table.insert(connections, swing:GetMarkerReachedSignal("HitStart"):Connect(function()
		hitWindowOpen = true
	end))
	table.insert(connections, swing:GetMarkerReachedSignal("HitEnd"):Connect(function()
		hitWindowOpen = false
	end))
	local speed = if character:GetAttribute("Haste") then 1.25 else 1
	swing:Play(0.1, 1, speed)
end

UserInputService.InputBegan:Connect(function(input, processed)
	if processed then
		return
	end
	if input.UserInputType == Enum.UserInputType.MouseButton1 then
		startSwing()
	end
end)

local function cancel()
	if swing.IsPlaying then
		swing:Stop(0.15)
	end
end

character.ChildRemoved:Connect(function(child)
	if child:IsA("Tool") then
		cancel()
	end
end)

humanoid.Died:Connect(function()
	cancel()
	disconnectAll()
end)
```
