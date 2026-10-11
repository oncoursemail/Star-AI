--!strict
-- Display only; clients never submit round state, scores or rewards.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local gui = Instance.new("ScreenGui")
gui.Name = "RoundHud"
gui.ResetOnSpawn = false
gui.IgnoreGuiInset = true

local panel = Instance.new("Frame")
panel.Name = "Panel"
panel.AnchorPoint = Vector2.new(0.5, 0)
panel.Position = UDim2.fromScale(0.5, 0.03)
panel.Size = UDim2.fromOffset(300, 54)
panel.BackgroundColor3 = Color3.fromRGB(22, 27, 37)
panel.BackgroundTransparency = 0.08
panel.Parent = gui

local corner = Instance.new("UICorner")
corner.CornerRadius = UDim.new(0, 10)
corner.Parent = panel

local label = Instance.new("TextLabel")
label.Name = "Status"
label.BackgroundTransparency = 1
label.Position = UDim2.fromOffset(12, 8)
label.Size = UDim2.new(1, -24, 1, -16)
label.TextColor3 = Color3.fromRGB(245, 247, 250)
label.Font = Enum.Font.GothamSemibold
label.TextScaled = true
label.Parent = panel

gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")

while gui.Parent do
	local state = ReplicatedStorage:GetAttribute("RoundState")
	local deadline = ReplicatedStorage:GetAttribute("RoundDeadline")
	local suffix = ""
	if typeof(deadline) == "number" then
		suffix = "  ·  " .. tostring(math.max(0, math.ceil(deadline - workspace:GetServerTimeNow()))) .. "s"
	end
	if state == "Intermission" and suffix == "" then
		label.Text = "Waiting for players"
	elseif state == "Loading" then
		label.Text = "Loading arena"
	else
		label.Text = tostring(state or "Intermission") .. suffix
	end
	task.wait(0.2)
end
