One worker thread drains the queue: slide in, hold, slide out, then take the next message. While the worker is busy new messages only go into a queue that holds at most five.

```luau
--!strict
local TweenService = game:GetService("TweenService")

local Toast = {}
Toast.__index = Toast

local SLIDE = TweenInfo.new(0.25, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local ON_SCREEN = UDim2.fromScale(0.5, 0.1)
local OFF_SCREEN = UDim2.fromScale(0.5, -0.1)
local HOLD_SECONDS = 2
local MAX_PENDING = 5

function Toast.new(label: TextLabel)
	return setmetatable({
		label = label,
		pending = {} :: { string },
		busy = false,
	}, Toast)
end

function Toast:show(text: string)
	if self.busy then
		if #self.pending < MAX_PENDING then
			table.insert(self.pending, text)
		end
		return
	end
	self.busy = true
	task.spawn(function()
		local current: string? = text
		while current ~= nil do
			self.label.Text = current
			local slideIn = TweenService:Create(self.label, SLIDE, { Position = ON_SCREEN })
			slideIn:Play()
			slideIn.Completed:Wait()
			task.wait(HOLD_SECONDS)
			local slideOut = TweenService:Create(self.label, SLIDE, { Position = OFF_SCREEN })
			slideOut:Play()
			slideOut.Completed:Wait()
			current = table.remove(self.pending, 1)
		end
		self.busy = false
	end)
end

return Toast
```
