---
name: roblox-tweenservice-easing
description: Opt-in Roblox TweenService examples for easing, tween lifecycle, UI transitions and cancellation.
---
# roblox-tweenservice-easing
## When to use
Use for Roblox TweenService, TweenInfo easing, UI transitions and safe replacement of active tweens. Focus on engine properties and lifecycle, not broader art direction.

## Ten concrete rules
1. Get TweenService via game:GetService, then call TweenService:Create(instance, TweenInfo, goals) and Play the returned tween. [S1]
2. Tween only supported, writable properties using a compatible goal type; not all Instance properties interpolate. [S1]
3. TweenInfo.new takes duration, EasingStyle, EasingDirection, repeat count, reverses and delay; choose each deliberately. [S2]
4. Quad or Sine easing out often suits gentle arrivals; this is a design preference, not an engine requirement. [S2][S4]
5. Tween GuiObject.Position with UDim2, setting AnchorPoint first where centering matters. [S1][S5]
6. Reuse TweenInfo when convenient and avoid making unlimited tweens every frame. [S1]
7. Two concurrent tweens of one property on one object conflict: the more recent tween cancels the first. [S3]
8. Cancel resets tween progress, not target property values; Pause keeps progress. [S3]
9. Completed fires on finish and cancellation. Check Enum.PlaybackState.Completed for success-only callbacks. [S3]
10. Use Completed signals instead of guessing animation end with task.wait; prevent superseded callbacks from changing state. [S3]

## Three correct Luau examples
Each is independent. UI examples belong in a LocalScript; the part example runs wherever the intended effect is owned.

### Example 1: ease a part's transparency
~~~luau
local TweenService = game:GetService("TweenService")
local door = workspace:WaitForChild("Door")
if door:IsA("BasePart") then
    local info = TweenInfo.new(0.4, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
    local tween = TweenService:Create(door, info, { Transparency = 0.2 })
    tween:Play()
end
~~~
Door is an existing BasePart and 0.2 is a valid target transparency. [S1][S2]

### Example 2: centered panel slides into view
~~~luau
local TweenService = game:GetService("TweenService")
local panel = script.Parent
if panel:IsA("GuiObject") then
    panel.AnchorPoint = Vector2.new(0.5, 0.5)
    panel.Position = UDim2.fromScale(0.5, 1.1)
    local info = TweenInfo.new(0.25, Enum.EasingStyle.Quint, Enum.EasingDirection.Out)
    local tween = TweenService:Create(panel, info, { Position = UDim2.fromScale(0.5, 0.5) })
    tween:Play()
end
~~~
Place the LocalScript under the GUI panel. The offscreen initial position is intentional. [S1][S2][S5]

### Example 3: cancel superseded hover tweens
~~~luau
local TweenService = game:GetService("TweenService")
local button = script.Parent
if button:IsA("TextButton") then
    local activeTween = nil
    local function animate(transparency)
        if activeTween then activeTween:Cancel() end
        local info = TweenInfo.new(0.15, Enum.EasingStyle.Sine, Enum.EasingDirection.Out)
        local tween = TweenService:Create(button, info, { BackgroundTransparency = transparency })
        activeTween = tween
        tween.Completed:Once(function(state)
            if activeTween == tween then
                activeTween = nil
                if state == Enum.PlaybackState.Completed then
                    print("Hover finished")
                end
            end
        end)
        tween:Play()
    end
    button.MouseEnter:Connect(function() animate(0.1) end)
    button.MouseLeave:Connect(function() animate(0.5) end)
end
~~~
Each callback belongs to its tween; a cancelled tween never counts as successful. [S3][S5]

## Three common mistakes
1. Creating but never playing the tween, or targeting an incompatible property/goal type. [S1]
2. Starting competing tweens without cancellation, then letting stale callbacks change the UI. [S3]
3. Treating Completed as always successful or expecting Cancel to restore the original property value. [S3]

## Checklist
- [ ] Properties and target value types are compatible.
- [ ] TweenInfo duration, style and direction are intentional.
- [ ] Completion handlers distinguish success from cancellation.
- [ ] Replacement transitions own their callbacks.
- [ ] Test device performance and reduced-motion preferences separately.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S5]. Durations are illustrative and unmeasured.
