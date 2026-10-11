--!strict
-- Thin input/display layer. The server decides every outcome and returns a state snapshot.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local player = Players.LocalPlayer
local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("SimulatorConfig"))
local remotes = ReplicatedStorage:WaitForChild("SimulatorRemotes")
local actionEvent = remotes:WaitForChild("Action")
local stateEvent = remotes:WaitForChild("State")
local getSnapshot = remotes:WaitForChild("GetSnapshot")

local screen = Instance.new("ScreenGui")
screen.Name = "SimulatorHud"
screen.ResetOnSpawn = false
screen.Parent = player:WaitForChild("PlayerGui")

local panel = Instance.new("ScrollingFrame")
panel.Name = "Actions"
panel.Position = UDim2.new(0, 12, 0.06, 0)
panel.Size = UDim2.new(0, 360, 0.88, 0)
panel.BackgroundColor3 = Color3.fromRGB(22, 25, 34)
panel.BackgroundTransparency = 0.08
panel.BorderSizePixel = 0
panel.ScrollBarThickness = 4
panel.AutomaticCanvasSize = Enum.AutomaticSize.Y
panel.CanvasSize = UDim2.fromOffset(0, 0)
panel.Parent = screen

local padding = Instance.new("UIPadding")
padding.PaddingLeft = UDim.new(0, 12)
padding.PaddingRight = UDim.new(0, 12)
padding.PaddingTop = UDim.new(0, 12)
padding.PaddingBottom = UDim.new(0, 12)
padding.Parent = panel

local layout = Instance.new("UIListLayout")
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Padding = UDim.new(0, 6)
layout.Parent = panel

local function label(text: string): TextLabel
	local item = Instance.new("TextLabel")
	item.Size = UDim2.new(1, 0, 0, 32)
	item.BackgroundTransparency = 1
	item.TextColor3 = Color3.fromRGB(235, 237, 242)
	item.Font = Enum.Font.GothamMedium
	item.TextSize = 14
	item.TextXAlignment = Enum.TextXAlignment.Left
	item.Text = text
	item.Parent = panel
	return item
end

local function button(text: string, onClick: () -> ()): TextButton
	local item = Instance.new("TextButton")
	item.Size = UDim2.new(1, 0, 0, 36)
	item.BackgroundColor3 = Color3.fromRGB(53, 62, 82)
	item.BorderSizePixel = 0
	item.TextColor3 = Color3.fromRGB(255, 255, 255)
	item.Font = Enum.Font.GothamSemibold
	item.TextSize = 14
	item.Text = text
	item.Parent = panel
	item.Activated:Connect(onClick)
	return item
end

local function send(action: string, arg: string?)
	actionEvent:FireServer(action, arg)
end

label("SIMULATOR")
local balance = label("Coins: loading...")
local progress = label("Run earned: loading...")
local bonuses = label("Reward: loading...")
local status = label("")

button("CLICK / EARN", function()
	send("Click")
end)

local upgradeButton = button("BUY UPGRADE", function()
	send("Upgrade")
end)

local rebirthButton = button("REBIRTH", function()
	send("Rebirth")
end)

label("ZONES")
local zoneButtons: { [string]: TextButton } = {}
for _, id in ipairs(Config.ZONE_ORDER) do
	local zone = Config.ZONES[id]
	zoneButtons[id] = button(zone.name, function()
		send("EnterZone", id)
	end)
end

label("PETS — OWN ONE, EQUIP ONE")
local petButtons: { [string]: TextButton } = {}
local current: any = nil
for _, id in ipairs(Config.PET_ORDER) do
	local pet = Config.PETS[id]
	petButtons[id] = button(pet.name, function()
		if current and current.pets and current.pets[id] then
			send("EquipPet", id)
		else
			send("BuyPet", id)
		end
	end)
end

local function render(snapshot: any, reason: string?)
	if type(snapshot) ~= "table" then
		return
	end
	current = snapshot
	balance.Text = ("Coins: %d  |  Rebirths: %d"):format(snapshot.coins, snapshot.rebirths)
	progress.Text = ("Run earned: %d"):format(snapshot.runEarned)
	bonuses.Text = ("Per click: %d  |  Zone: %s"):format(snapshot.clickGain, snapshot.zone)
	upgradeButton.Text = if snapshot.nextUpgradeCost then
		("UPGRADE Lv.%d — %d coins"):format(snapshot.upgradeLevel, snapshot.nextUpgradeCost)
		else "UPGRADES MAXED"
	rebirthButton.Text = ("REBIRTH — %d coins"):format(snapshot.rebirthCost)
	status.Text = reason or ""
	for _, id in ipairs(Config.ZONE_ORDER) do
		local zone = Config.ZONES[id]
		local unlocked = snapshot.runEarned >= zone.threshold
		zoneButtons[id].Text = if unlocked
			then zone.name .. "  x" .. tostring(zone.multiplier) .. (if snapshot.zone == id then " [ACTIVE]" else "")
			else zone.name .. " — unlock at " .. tostring(zone.threshold)
	end
	for _, id in ipairs(Config.PET_ORDER) do
		local pet = Config.PETS[id]
		local owned = snapshot.pets and snapshot.pets[id]
		petButtons[id].Text = if owned
			then pet.name .. (if snapshot.equippedPet == id then " [EQUIPPED]" else " — EQUIP")
			else pet.name .. " — " .. tostring(pet.cost) .. " coins"
	end
end

stateEvent.OnClientEvent:Connect(render)
local ok, state = pcall(function()
	return getSnapshot:InvokeServer()
end)
if ok and state then
	render(state)
end
