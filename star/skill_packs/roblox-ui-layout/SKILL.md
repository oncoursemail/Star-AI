---
name: roblox-ui-layout
description: Build native Roblox UI (ScreenGui, layout objects, constraints) that scales from phone to PC. Use for HUDs, menus, shop lists, inventory grids, nameplates, safe areas and button feedback.
---
# Roblox UI layout and scaling
Build UI from real objects in code, never pictures of UI.
- ScreenGui goes in PlayerGui. Keep ScreenInsets at its default or DeviceSafeInsets (clear of top bar and camera notch); .None can hide controls.
- Size with Scale (UDim2.fromScale); Offset is fixed pixels, for padding only.
- Arrange children with a layout object (UIListLayout, UIGridLayout), UIPadding and LayoutOrder, never hand-placed positions.
- Keep shapes with UIAspectRatioConstraint (AspectRatio 1 = square), UISizeConstraint, and UITextSizeConstraint with TextScaled for text that must fit.
- To scale a fixed design add a UIScale set from workspace.CurrentCamera.ViewportSize, updated from GetPropertyChangedSignal("ViewportSize"), not a loop.
- ScrollingFrame: AutomaticCanvasSize = Enum.AutomaticSize.Y with a UIListLayout; never compute CanvasSize.
- Activated handles mouse, touch and gamepad clicks; SelectionGained/SelectionLost handle gamepad focus.
- Animate with TweenService; Cancel the previous tween; disconnect connections when the UI is destroyed.
