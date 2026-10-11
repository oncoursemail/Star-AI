---
name: roblox-ui-styles
description: Roblox UI styling: one theme table, UICorner, UIStroke, UIGradient and UIScale looks (flat, glass, neon, chunky), tweened hover and press feedback, readable contrast.
---
# UI styling (Roblox)
- Keep the look in one Theme table (colors, Font, corner radius, stroke thickness, spacing) and apply it with a helper, so a restyle is a single edit.
- Appearance modifiers: UICorner (CornerRadius), UIStroke (Thickness, Color, ApplyStrokeMode = Border for frames and buttons), UIGradient (Color, Rotation, Transparency), UIPadding, UIScale. Looks: flat (solid fill plus corner), glass (BackgroundTransparency near 0.3 plus a thin stroke), neon (dark fill plus a bright stroke), chunky (thick darker stroke).
- Feedback: TweenService:Create(object, TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {Property = value}):Play(). Hover is MouseEnter and MouseLeave; press is a small UIScale (0.96). GuiObject:TweenPosition and TweenSize are deprecated. Set AutoButtonColor = false when you animate the colour yourself.
- Keep text readable: light text on dark fills and dark on light, a contrast ratio of at least 4.5 (WCAG relative luminance), and TextScaled with a UITextSizeConstraint.
