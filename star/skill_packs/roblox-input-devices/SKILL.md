---
name: roblox-input-devices
description: Opt-in Roblox cross-device input recipes - Input Action System actions and bindings, ContextActionService with touch buttons, PreferredInput-driven UI and gameProcessedEvent in typed Luau.
---
# roblox-input-devices
## When to use
Use for Roblox controls that must work on keyboard and mouse, gamepad and touch: sprint, reload or ability keys, on-screen mobile buttons, rebinding contexts, and showing the right prompt for the device. Input is read on the client; anything that matters still goes through a validated server remote.

## Ten concrete rules
1. Read input only on the client (LocalScript or a Script with RunContext Client); the server never sees key presses. [S1]
2. The Input Action System maps one InputAction to many InputBindings (KeyCode, gamepad buttons, a GuiButton through UIButton), so one handler serves every device. [S2][S3]
3. Bool actions fire Pressed and Released; every type fires StateChanged. For held analog input, poll GetState each frame instead of waiting for events. [S2][S3]
4. Group actions in InputContexts; Enabled switches a whole set (play vs menu), Priority orders contexts and Sink stops lower ones. [S2][S4]
5. ContextActionService:BindAction(name, handler, createTouchButton, ...inputs) also works; the most recently bound action wins and it can create up to 7 touch buttons. [S5]
6. A ContextActionService handler gets (name, UserInputState, InputObject); act on Begin and return Sink or Pass. UnbindAction when the context ends. [S5]
7. In UserInputService.InputBegan, return early when gameProcessedEvent is true, so typing in chat or a TextBox does not trigger actions. [S6][S7]
8. Use UserInputService.PreferredInput (Touch, Gamepad, KeyboardAndMouse) to pick UI, and listen with GetPropertyChangedSignal. TouchEnabled is true on touch laptops, so it is not a phone check. [S1][S6]
9. Show the key for the current device with InputActionLabel or InputAction.PreferredBinding. [S2][S8]
10. Send intent to the server, never results: a reload request, not an ammo count. [S9]

## Three correct Luau examples
All three are LocalScripts in StarterPlayerScripts.

### Example 1: sprint through the Input Action System
~~~luau
--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local inputs = ReplicatedStorage:WaitForChild("Inputs")
local sprint = inputs:WaitForChild("PlayContext"):WaitForChild("CharacterSprint") :: InputAction
local player = Players.LocalPlayer
local WALK, RUN = 16, 24

local function setSpeed(speed: number)
	local character = player.Character
	local humanoid = if character then character:FindFirstChildOfClass("Humanoid") else nil
	if humanoid then
		humanoid.WalkSpeed = speed
	end
end

sprint.Pressed:Connect(function()
	setSpeed(RUN)
end)
sprint.Released:Connect(function()
	setSpeed(WALK)
end)
~~~
Create PlayContext, CharacterSprint and its keyboard, gamepad and UIButton bindings in Studio first. [S2][S3]

### Example 2: reload on R, gamepad X or a touch button
~~~luau
--!strict
local ContextActionService = game:GetService("ContextActionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local reload = ReplicatedStorage:WaitForChild("Reload") :: RemoteEvent
local ACTION = "Reload"

local function onReload(_: string, state: Enum.UserInputState, _: InputObject): Enum.ContextActionResult
	if state == Enum.UserInputState.Begin then
		reload:FireServer() -- intent only; the server owns ammo
	end
	return Enum.ContextActionResult.Sink
end

local function setEnabled(enabled: boolean)
	if enabled then
		ContextActionService:BindAction(ACTION, onReload, true, Enum.KeyCode.R, Enum.KeyCode.ButtonX)
		ContextActionService:SetTitle(ACTION, "Reload")
		ContextActionService:SetPosition(ACTION, UDim2.new(1, -150, 1, -150))
	else
		ContextActionService:UnbindAction(ACTION)
	end
end

setEnabled(true) -- call setEnabled(false) when the weapon is put away
~~~
The third argument creates the touch button; unbinding removes it. [S5]

### Example 3: hints that follow the preferred input
~~~luau
--!strict
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
local hint = playerGui:WaitForChild("Hud"):WaitForChild("Hint") :: TextLabel

local TEXT: { [Enum.PreferredInput]: string } = {
	[Enum.PreferredInput.KeyboardAndMouse] = "Press E to interact",
	[Enum.PreferredInput.Gamepad] = "Press X to interact",
	[Enum.PreferredInput.Touch] = "Tap the button to interact",
}

local function refresh()
	hint.Text = TEXT[UserInputService.PreferredInput] or "Interact"
end

refresh()
UserInputService:GetPropertyChangedSignal("PreferredInput"):Connect(refresh)

UserInputService.InputBegan:Connect(function(input: InputObject, gameProcessedEvent: boolean)
	if gameProcessedEvent then
		return -- typing in chat or a TextBox
	end
	if input.KeyCode == Enum.KeyCode.E or input.KeyCode == Enum.KeyCode.ButtonX then
		hint.Visible = false
	end
end)
~~~
MicroGamepad and future values fall back to the generic text. [S1][S6][S7]

## Three common mistakes
1. Using TouchEnabled or the last input type as an "is mobile" test. [S1]
2. Ignoring gameProcessedEvent, so chat typing fires abilities. [S7]
3. Keyboard-only bindings with no gamepad or touch path, or touch buttons never unbound. [S2][S5]

## Checklist
- [ ] Every action has keyboard, gamepad and touch input.
- [ ] Handlers ignore processed input.
- [ ] UI follows PreferredInput and its change signal.
- [ ] Contexts or bindings are switched off when not in use.
- [ ] Remotes carry intent; the server validates.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S9]. Speeds and positions are illustrative.
