The tab bar owns one list layout and one button per name. `select` is the single place that changes state: it hides every page except the chosen one and recolors every button. Click connections are made once at creation and kept so `destroy` can disconnect them.

```luau
--!strict
local Tabs = {}
Tabs.__index = Tabs

local ACTIVE = Color3.fromRGB(70, 130, 255)
local IDLE = Color3.fromRGB(45, 45, 55)

function Tabs.new(tabBar: Frame, pages: { [string]: GuiObject }, order: { string })
	local self = setmetatable({
		pages = pages,
		buttons = {} :: { [string]: TextButton },
		connections = {} :: { RBXScriptConnection },
		current = nil :: string?,
	}, Tabs)

	local layout = Instance.new("UIListLayout")
	layout.FillDirection = Enum.FillDirection.Horizontal
	layout.SortOrder = Enum.SortOrder.LayoutOrder
	layout.Parent = tabBar

	for index, name in order do
		local button = Instance.new("TextButton")
		button.Name = "Tab_" .. name
		button.Text = name
		button.LayoutOrder = index
		button.Parent = tabBar
		self.buttons[name] = button
		table.insert(self.connections, button.Activated:Connect(function()
			self:select(name)
		end))
	end

	if order[1] ~= nil then
		self:select(order[1])
	end
	return self
end

function Tabs:select(name: string): boolean
	if self.pages[name] == nil or self.buttons[name] == nil then
		return false
	end
	for pageName, page in self.pages do
		page.Visible = pageName == name
	end
	for buttonName, button in self.buttons do
		button.BackgroundColor3 = if buttonName == name then ACTIVE else IDLE
	end
	self.current = name
	return true
end

function Tabs:selected(): string?
	return self.current
end

function Tabs:destroy()
	for _, connection in self.connections do
		connection:Disconnect()
	end
	table.clear(self.connections)
	for _, button in self.buttons do
		button:Destroy()
	end
	table.clear(self.buttons)
end

return Tabs
```
