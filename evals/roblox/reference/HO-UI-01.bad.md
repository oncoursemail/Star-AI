Fixed-size slots placed one by one.

```luau
local Hotbar = {}

function Hotbar.build(playerGui: Instance, slotCount: number): Frame
	local gui = Instance.new("ScreenGui")
	gui.Name = "Hotbar"
	gui.Parent = playerGui

	local bar = Instance.new("Frame")
	bar.Name = "Bar"
	bar.AnchorPoint = Vector2.new(0.5, 1)
	bar.Position = UDim2.new(0.5, 0, 1, -10)
	bar.Size = UDim2.fromOffset(64 * slotCount, 60)
	bar.BackgroundTransparency = 1
	bar.Parent = gui

	for i = 1, slotCount do
		local slot = Instance.new("TextButton")
		slot.Name = "Slot" .. i
		slot.Text = tostring(i)
		slot.Size = UDim2.fromOffset(60, 60)
		slot.Position = UDim2.fromOffset((i - 1) * 64, 0)
		slot.Parent = bar
	end
	return bar
end

return Hotbar
```
