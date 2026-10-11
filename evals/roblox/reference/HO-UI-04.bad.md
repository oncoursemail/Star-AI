Buttons in a row; clicking one shows its page.

```luau
local Tabs = {}
Tabs.__index = Tabs

function Tabs.new(tabBar: Frame, pages: { [string]: GuiObject }, order: { string })
	local self = setmetatable({ pages = pages, buttons = {}, current = nil }, Tabs)
	for index, name in order do
		local button = Instance.new("TextButton")
		button.Name = "Tab_" .. name
		button.Text = name
		button.Position = UDim2.new(0, (index - 1) * 100, 0, 0)
		button.Size = UDim2.new(0, 100, 1, 0)
		button.Parent = tabBar
		self.buttons[name] = button
		button.MouseButton1Click:Connect(function()
			self:select(name)
		end)
	end
	self:select(order[1])
	return self
end

function Tabs:select(name: string): boolean
	local page = self.pages[name]
	if not page then
		return false
	end
	page.Visible = true
	for _, button in self.buttons do
		button.BackgroundColor3 = Color3.fromRGB(45, 45, 55)
	end
	self.buttons[name].BackgroundColor3 = Color3.fromRGB(70, 130, 255)
	self.current = name
	return true
end

function Tabs:selected(): string?
	return self.current
end

function Tabs:destroy()
	for _, button in self.buttons do
		button:Destroy()
	end
end

return Tabs
```
