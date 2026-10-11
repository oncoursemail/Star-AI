--!strict
-- Read-only presentation. The client never decides what a purchase costs or awards cash.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Economy = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Economy"))

local player = Players.LocalPlayer
local stats = player:WaitForChild("leaderstats")
local cash = stats:WaitForChild("Cash") :: IntValue
local rebirths = stats:WaitForChild("Rebirths") :: IntValue

local gui = Instance.new("ScreenGui")
gui.Name = "TycoonHUD"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local panel = Instance.new("Frame")
panel.Name = "Panel"
panel.Position = UDim2.fromOffset(16, 16)
panel.Size = UDim2.fromOffset(360, 110)
panel.BackgroundColor3 = Color3.fromRGB(22, 26, 34)
panel.BackgroundTransparency = 0.06
panel.Parent = gui

local corner = Instance.new("UICorner")
corner.CornerRadius = UDim.new(0, 10)
corner.Parent = panel
local outline = Instance.new("UIStroke")
outline.Color = Color3.fromRGB(96, 110, 131)
outline.Thickness = 1
outline.Parent = panel

local function line(name: string, y: number, size: number): TextLabel
	local label = Instance.new("TextLabel")
	label.Name = name
	label.BackgroundTransparency = 1
	label.Position = UDim2.fromOffset(16, y)
	label.Size = UDim2.new(1, -32, 0, size)
	label.Font = Enum.Font.GothamMedium
	label.TextSize = if name == "Wallet" then 18 else 14
	label.TextColor3 = Color3.fromRGB(238, 241, 246)
	label.TextXAlignment = Enum.TextXAlignment.Left
	label.TextTruncate = Enum.TextTruncate.AtEnd
	label.Parent = panel
	return label
end

local wallet = line("Wallet", 10, 24)
local nextItem = line("NextItem", 38, 24)
local notice = line("Notice", 73, 24)
notice.TextColor3 = Color3.fromRGB(183, 200, 218)

local function render()
	wallet.Text = "Cash: $" .. tostring(cash.Value) .. "    Rebirths: " .. tostring(rebirths.Value)
		.. "    x" .. tostring(Economy.multiplier(rebirths.Value))
	local nextId = player:GetAttribute("TycoonNextItem")
	if type(nextId) == "string" and nextId ~= "" then
		local item = Economy.get(nextId)
		nextItem.Text = if item then "Next: " .. item.name .. " ($" .. tostring(item.price) .. ")"
			else "Unlock the next dropper"
	else
		nextItem.Text = "Rebirth cost: $" .. tostring(player:GetAttribute("TycoonRebirthPrice") or 0)
	end
end

cash.Changed:Connect(render)
rebirths.Changed:Connect(render)
player:GetAttributeChangedSignal("TycoonNextItem"):Connect(render)
player:GetAttributeChangedSignal("TycoonRebirthPrice"):Connect(render)
player:GetAttributeChangedSignal("TycoonNoticeVersion"):Connect(function()
	local message = player:GetAttribute("TycoonNotice")
	if type(message) == "string" then
		notice.Text = message:gsub("_", " ")
	end
end)
render()
