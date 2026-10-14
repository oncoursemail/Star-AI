--!strict
-- Display-only native Roblox GUI. Never sends currency amounts or trusted prices.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Catalog = require(ReplicatedStorage:WaitForChild("ShopCatalog"))
local Remote = ReplicatedStorage:WaitForChild("PurchaseItem")

local gui = Instance.new("ScreenGui")
gui.Name = "ExampleShop"
gui.ResetOnSpawn = false
gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
local panel = Instance.new("Frame")
panel.Size = UDim2.fromScale(0.35, 0.5)
panel.Position = UDim2.fromScale(0.05, 0.25)
panel.Parent = gui
local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 8)
layout.Parent = panel

local message = Instance.new("TextLabel")
message.Size = UDim2.new(1, 0, 0, 40)
message.Text = "Choose an item"
message.Parent = panel
local ids = {}
for itemId in pairs(Catalog) do table.insert(ids, itemId) end
table.sort(ids)
for _, itemId in ids do
    local button = Instance.new("TextButton")
    button.Size = UDim2.new(1, 0, 0, 44)
    button.Text = itemId .. " - " .. tostring(Catalog[itemId]) .. " coins"
    button.Parent = panel
    local busy = false
    button.Activated:Connect(function()
        if busy then return end
        busy = true
        local ok, response = pcall(function()
            return Remote:InvokeServer(itemId, 1) -- only ID and quantity.
        end)
        if ok and type(response) == "table" and response.ok then
            message.Text = "Owned " .. itemId
        else
            message.Text = (ok and type(response) == "table" and response.reason)
                or "Purchase could not be completed"
        end
        busy = false
    end)
end
