```luau
local Players = game:GetService("Players")
local tool = script.Parent
local track: AnimationTrack? = nil

local stab = Instance.new("Animation")
stab.AnimationId = "rbxassetid://180435792"

tool.Equipped:Connect(function()
	local character = tool.Parent
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if humanoid == nil then
		return
	end
	-- the engine welds the Handle to the right hand/arm using tool.Grip
	if humanoid.RigType == Enum.HumanoidRigType.R15 then
		tool.GripPos = Vector3.new(0, 0, -0.5) -- RightHand
	else
		tool.GripPos = Vector3.new(0, -0.5, 0) -- R6: the Right Arm
	end
	tool.GripForward = Vector3.new(0, 0, -1)
	local animator = humanoid:FindFirstChildOfClass("Animator")
	if animator then
		track = animator:LoadAnimation(stab)
	end
end)

tool.Activated:Connect(function()
	if track then
		track:Play()
	end
end)

tool.Unequipped:Connect(function()
	if track then
		track:Stop()
		track = nil
	end
end)
```
