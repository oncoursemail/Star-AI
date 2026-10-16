local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local spinning = {}
local function add(part)
	if part:IsA("BasePart") then spinning[part] = true end
end
for _, part in CollectionService:GetTagged("Spinner") do add(part) end
CollectionService:GetInstanceAddedSignal("Spinner"):Connect(add)
CollectionService:GetInstanceRemovedSignal("Spinner"):Connect(function(part) spinning[part] = nil end)
RunService.Heartbeat:Connect(function(dt)
	for part in spinning do
		if part.Parent then
			part.CFrame = part.CFrame * CFrame.Angles(0, math.rad(90) * dt, 0)
		end
	end
end)
