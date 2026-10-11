--!strict
-- The HUD observes replicated server state; it never submits stage changes.
local Players = game:GetService("Players")
local player = Players.LocalPlayer

local gui = Instance.new("ScreenGui")
gui.Name = "ObbyStageHud"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local label = Instance.new("TextLabel")
label.Name = "StageLabel"
label.AnchorPoint = Vector2.new(0.5, 0)
label.Position = UDim2.fromScale(0.5, 0.03)
label.Size = UDim2.fromOffset(200, 48)
label.BackgroundColor3 = Color3.fromRGB(26, 34, 52)
label.BackgroundTransparency = 0.08
label.BorderSizePixel = 0
label.TextColor3 = Color3.fromRGB(255, 255, 255)
label.Font = Enum.Font.GothamBold
label.TextSize = 22
label.Parent = gui

local corner = Instance.new("UICorner")
corner.CornerRadius = UDim.new(0, 10)
corner.Parent = label

local function update()
	local stage = player:GetAttribute("Stage")
	if typeof(stage) == "number" then
		label.Text = string.format("Stage %d / 4", stage)
	else
		label.Text = "Loading stage..."
	end
end

player:GetAttributeChangedSignal("Stage"):Connect(update)
update()
