```luau
local TweenService = game:GetService("TweenService")

local FADE = TweenInfo.new(0.3, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)

local function reach(npc, target)
	local humanoid = npc:FindFirstChildOfClass("Humanoid")
	if not humanoid then
		return nil
	end
	local control = humanoid:FindFirstChild("ReachIK")
	if not control then
		control = Instance.new("IKControl")
		control.Name = "ReachIK"
		control.Type = Enum.IKControlType.Position
		control.ChainRoot = npc:FindFirstChild("RightUpperArm")
		control.EndEffector = npc:FindFirstChild("RightHand")
		control.SmoothTime = 0.2
		control.Weight = 0
		control.Parent = humanoid
	end
	control.Target = target
	control.Enabled = true
	TweenService:Create(control, FADE, { Weight = 1 }):Play()
	return control
end

local function release(npc)
	local humanoid = npc:FindFirstChildOfClass("Humanoid")
	local control = humanoid and humanoid:FindFirstChild("ReachIK")
	if control then
		local tween = TweenService:Create(control, FADE, { Weight = 0 })
		tween.Completed:Once(function()
			control.Enabled = false
		end)
		tween:Play()
	end
end

local guard = workspace:FindFirstChild("Guard")
local knob = workspace:FindFirstChild("Doorknob")
if guard and knob then
	reach(guard, knob)
	task.delay(4, release, guard)
end
return { reach = reach, release = release }
```
