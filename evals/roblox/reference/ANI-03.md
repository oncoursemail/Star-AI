```luau
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")

local character = Players.LocalPlayer.Character or Players.LocalPlayer.CharacterAdded:Wait()
local humanoid = character:WaitForChild("Humanoid")
local animator = humanoid:WaitForChild("Animator")

local idleAnim = Instance.new("Animation")
idleAnim.AnimationId = "rbxassetid://180435571"
local attackAnim = Instance.new("Animation")
attackAnim.AnimationId = "rbxassetid://180435792"

local idle = animator:LoadAnimation(idleAnim)
idle.Looped = true
idle.Priority = Enum.AnimationPriority.Idle
local attack = animator:LoadAnimation(attackAnim)
attack.Priority = Enum.AnimationPriority.Action
idle:Play()

local connection = UserInputService.InputBegan:Connect(function(input, processed)
	if processed or input.KeyCode ~= Enum.KeyCode.F or attack.IsPlaying then
		return
	end
	idle:Stop()
	attack:Play()
end)

attack.Stopped:Connect(function()
	idle:Play()
end)

humanoid.Died:Connect(function()
	connection:Disconnect()
	idle:Stop()
	attack:Stop()
end)
```
