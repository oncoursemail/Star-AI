```luau
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local attackHit = ReplicatedStorage:WaitForChild("AttackHit")
local tool = script.Parent
local animation = Instance.new("Animation")
animation.AnimationId = "rbxassetid://180435792"
local track: AnimationTrack? = nil

tool.Equipped:Connect(function()
	local humanoid = tool.Parent and tool.Parent:FindFirstChildOfClass("Humanoid")
	local animator = humanoid and humanoid:FindFirstChildOfClass("Animator")
	if animator then
		track = animator:LoadAnimation(animation)
	end
end)

tool.Activated:Connect(function()
	if track == nil or track.IsPlaying then
		return
	end
	local fired = false
	local marker = track:GetMarkerReachedSignal("Hit"):Connect(function()
		if not fired then
			fired = true
			attackHit:FireServer()
		end
	end)
	local stopped
	stopped = track.Stopped:Connect(function()
		marker:Disconnect()
		stopped:Disconnect()
	end)
	track:Play()
end)
```
