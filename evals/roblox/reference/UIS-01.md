```luau
--!strict
local TweenService = game:GetService("TweenService")

local Theme = {
	radius = UDim.new(0, 8),
	strokeThickness = 2,
	font = Enum.Font.GothamBold,
	colors = {
		primary = Color3.fromRGB(64, 132, 255),
		danger = Color3.fromRGB(235, 70, 70),
		ghost = Color3.fromRGB(30, 34, 44),
		text = Color3.fromRGB(255, 255, 255),
	},
}

local HOVER = TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)

local function styleButton(button: TextButton, variant: string)
	local base = Theme.colors[variant] or Theme.colors.primary
	button.AutoButtonColor = false
	button.BackgroundColor3 = base
	button.TextColor3 = Theme.colors.text
	button.Font = Theme.font

	local corner = Instance.new("UICorner")
	corner.CornerRadius = Theme.radius
	corner.Parent = button

	local stroke = Instance.new("UIStroke")
	stroke.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
	stroke.Thickness = Theme.strokeThickness
	stroke.Color = base:Lerp(Color3.new(0, 0, 0), 0.4)
	stroke.Parent = button

	if variant == "primary" then
		local gradient = Instance.new("UIGradient")
		gradient.Color = ColorSequence.new(Color3.new(1, 1, 1), Color3.fromRGB(205, 215, 235))
		gradient.Rotation = 90
		gradient.Parent = button
	end

	local scale = Instance.new("UIScale")
	scale.Parent = button

	local hover = base:Lerp(Color3.new(1, 1, 1), 0.15)
	button.MouseEnter:Connect(function()
		TweenService:Create(button, HOVER, { BackgroundColor3 = hover }):Play()
	end)
	button.MouseLeave:Connect(function()
		TweenService:Create(button, HOVER, { BackgroundColor3 = base }):Play()
		TweenService:Create(scale, HOVER, { Scale = 1 }):Play()
	end)
	button.MouseButton1Down:Connect(function()
		TweenService:Create(scale, HOVER, { Scale = 0.96 }):Play()
	end)
	button.MouseButton1Up:Connect(function()
		TweenService:Create(scale, HOVER, { Scale = 1 }):Play()
	end)
end

return { Theme = Theme, styleButton = styleButton }
```
