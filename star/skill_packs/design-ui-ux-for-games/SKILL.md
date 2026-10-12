---
name: design-ui-ux-for-games
description: Design Roblox game UI and UX with mobile-first hierarchy, thumb zones, readable text and colour-blind safety.
---
# design-ui-ux-for-games
## When to use
Use when a Roblox HUD competes with gameplay, touch controls cause mistakes or menus become unreadable on small screens. Deliver an information hierarchy, screen-flow specification and accessibility checks, not UI code or a flattened picture of an interface.

## Ten concrete rules
1. Rank information by the decision the player must make now: immediate danger, current objective, available action, then optional management. Give each screen one primary task rather than equally prominent buttons everywhere. [S1]
2. Design for the smallest supported touch viewport first. Mark platform UI, notches and safe insets, then expand for desktop; do not shrink a desktop panel until all labels merely fit.
3. Reserve thumb zones for movement, camera and frequent actions. Keep purchase, discard and reset away from repeated gameplay taps. Validate reach with real grips and left-handed needs; no diagram represents every hand.
4. Make touch hit areas comfortably larger than their icons, separated from neighbours and reachable without hover. Treat a 48-by-48 reference-pixel target as a prototype starting point, not a universal physical size or Roblox requirement.
5. Use a small typography hierarchy, short labels and stable alignment. Support larger-text preferences and wrapping; never hide price, quantity or an objective behind automatic shrinking or unexplained truncation. [S2]
6. Measure text contrast over the worst actual game background. Use an opaque or adjustable backplate when needed; adopt at least 4.5:1 for ordinary text as a design baseline from WCAG, not a claim of Roblox certification. [S3]
7. Do not encode teams, rarity, hazards, affordability or success by colour alone. Add names, shapes, patterns or icons with labels; use grayscale and colour-vision simulations as checks, not substitutes for people. [S2]
8. Specify idle, focused, pressed, disabled, pending, success and error states. Explain why an action is unavailable; never show purchase success while confirmation is pending or turn a double-tap into another purchase.
9. Define navigation and recovery: predictable Back/Close, restored focus, controller order and a readable confirmation for destructive or paid actions. An open menu must not silently leave a critical gameplay control blocked. [S1]
10. Test the full task, not only a screenshot: touch, keyboard, controller, long translated strings, large text, muted audio and reduced motion. Record wrong taps, completion time and misunderstood states before adding decorative animation. [S2]

## Worked Roblox example
Hypothetical game: Beacon Rescue, a cooperative Roblox adventure. This layout and its acceptance cases are design proposals, not a tested interface.

At a proposed 360-by-800 portrait reference viewport, first reserve the actual platform safe area and active movement/camera controls; also test landscape separately. Put “Restore beacon: 2/3 fuses” in a compact top objective strip below platform UI. Place one labelled “Insert fuse” action within comfortable thumb reach when near the beacon, clear of Jump. Keep Backpack and Settings in secondary space. Do not overlay text on their icons.

A team marker combines the word “Team,” a triangle and a distinct outline, not just blue versus red. Low health combines “Low health,” a warning icon and a persistent bar. A pending fuse insertion shows “Checking...” and cannot masquerade as completion; an error says “Move closer” without discarding the fuse.

Backpack opens a panel with a title, item count, roomy rows and a consistent Close control. Buying a cosmetic is a separate flow: select item -> inspect contents and current price -> explicit purchase confirmation or Cancel -> pending -> confirmed ownership or an understandable error. Neither Jump nor Close shares the purchase hit area. Back returns to the prior selection without making another purchase.

Test a long translation of “Insert fuse,” the largest supported text preference and a bright moving sky behind the HUD. If the objective no longer fits, wrap or reflow the panel instead of making the text tiny. With audio muted and motion reduced, the same task must still be understandable. Log where players mis-tap before moving controls; do not claim a fixed target size solves reach for everyone.

## Checklist
- [ ] The immediate objective and primary action are obvious without a tutorial.
- [ ] Small-screen layout respects safe areas, thumbs, camera and movement controls.
- [ ] Large text and translations reflow without clipping, overlap or hidden prices.
- [ ] Contrast and non-colour cues work over the real scene.
- [ ] Focus, Back, pending, error, cancel and confirmation states are specified.
- [ ] Full tasks are checked across input, audio and motion preferences with observed results separated from plans.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S3]. The viewport, target dimensions and layout are original design starting points requiring device testing.
