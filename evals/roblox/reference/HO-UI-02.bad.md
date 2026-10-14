Each message replaces the text, slides in, and slides out after a delay.

```luau
local TweenService = game:GetService("TweenService")

local Toast = {}
Toast.__index = Toast

local ON_SCREEN = UDim2.fromScale(0.5, 0.1)
local OFF_SCREEN = UDim2.fromScale(0.5, -0.1)

function Toast.new(label: TextLabel)
	return setmetatable({ label = label }, Toast)
end

function Toast:show(text: string)
	self.label.Text = text
	self.label.Position = OFF_SCREEN
	TweenService:Create(self.label, TweenInfo.new(0.25), { Position = ON_SCREEN }):Play()
	task.delay(2.5, function()
		TweenService:Create(self.label, TweenInfo.new(0.25), { Position = OFF_SCREEN }):Play()
	end)
end

return Toast
```
