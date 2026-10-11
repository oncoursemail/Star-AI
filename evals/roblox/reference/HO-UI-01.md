Everything is sized in Scale. The bar's `UIAspectRatioConstraint` ties its height to its width, a single `UIListLayout` places the slots (no manual positions), and each slot's width is what is left after the paddings, divided by the slot count. The argument is validated before anything is created.

```luau
--!strict
local Hotbar = {}

local PADDING = 0.01
local MAX_SLOTS = 10

function Hotbar.build(playerGui: Instance, slotCount: number): Frame
	if type(slotCount) ~= "number" or slotCount ~= math.floor(slotCount) or slotCount < 1 or slotCount > MAX_SLOTS then
		error("slotCount must be a whole number from 1 to " .. MAX_SLOTS)
	end

	local gui = Instance.new("ScreenGui")
	gui.Name = "Hotbar"
	gui.ResetOnSpawn = false

	local bar = Instance.new("Frame")
	bar.Name = "Bar"
	bar.AnchorPoint = Vector2.new(0.5, 1)
	bar.Position = UDim2.fromScale(0.5, 0.98)
	bar.Size = UDim2.fromScale(0.6, 0.1)
	bar.BackgroundTransparency = 1
	bar.Parent = gui

	local ratio = Instance.new("UIAspectRatioConstraint")
	ratio.AspectRatio = slotCount
	ratio.Parent = bar

	local layout = Instance.new("UIListLayout")
	layout.FillDirection = Enum.FillDirection.Horizontal
	layout.SortOrder = Enum.SortOrder.LayoutOrder
	layout.HorizontalAlignment = Enum.HorizontalAlignment.Center
	layout.Padding = UDim.new(PADDING, 0)
	layout.Parent = bar

	local slotWidth = (1 - (slotCount - 1) * PADDING) / slotCount
	for i = 1, slotCount do
		local slot = Instance.new("TextButton")
		slot.Name = "Slot" .. i
		slot.LayoutOrder = i
		slot.Text = tostring(i)
		slot.Size = UDim2.fromScale(slotWidth, 1)
		slot.Parent = bar
	end

	gui.Parent = playerGui
	return bar
end

return Hotbar
```
