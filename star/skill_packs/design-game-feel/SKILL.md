---
name: design-game-feel
description: Design Roblox game feel through action feedback, timing, camera behaviour and sound before adding effects.
---
# design-game-feel
## When to use
Use when a Roblox action is mechanically functional but feels weak, delayed, confusing or uncomfortable. Produce an action timeline and feedback hierarchy before asking for animation, sound or effects code. More particles are not a substitute for a responsive action.

## Ten concrete rules
1. State the sensation and the information an action must convey: a jump feels controllable; a delivery feels accepted. Separate acknowledgement of input from confirmation that the action succeeded.
2. Give immediate local acknowledgement of accepted input, with a distinct unavailable state when blocked. Do not celebrate a hit, reward or purchase before its authoritative result is known.
3. Draw a timeline for anticipation, action, contact and recovery. Align the important visual and sound accents to the same event; do not let a long anticipation delay a basic movement response. [S1]
4. Specify input buffering, grace windows and cancellation as design choices. Start with provisional values and test; do not imply Roblox movement supplies them automatically or hide inconsistent rules from opponents.
5. Give routine, important and exceptional outcomes different intensity budgets. Reserve the strongest accent for a genuinely significant event so ordinary actions remain legible.
6. Let the player keep sight of the target, landing and next decision. Keep camera shake, bob, forced zoom and automatic recentering absent or optional; provide a no-motion alternative. [S2, S3]
7. Layer sound by purpose: an action onset, a material contact and a short confirmation. Keep critical warnings audible over ambience, avoid clipping and repeated loud peaks, and offer separate volume controls. [S4]
8. Convey critical outcomes in at least two channels. Use pose, icon, text or shape alongside sound and colour; muted audio must not make a hazard or successful interaction unknowable. [S5]
9. Keep feedback short, interruptible and bounded during spam or crowds. Distinguish cosmetic hit-stop from shared game time; never freeze another player's simulation just to dramatise a local event.
10. Compare the plain action with one added feedback layer at a time on touch and desktop. Record missed inputs, misread outcomes, frame-time cost and discomfort; keep only layers that help and label anything not tested.

## Worked Roblox example
Hypothetical game: Sky Parcel. Design a satisfying delivery without blocking the next jump. These timings are prototype targets, not measurements or engine guarantees.

| Event | Proposed presentation | Meaning |
|---|---|---|
| Input accepted | Button depresses on the next drawable frame; bag starts moving | Request acknowledged, not yet rewarded |
| Delivery confirmed | Parcel settles into the slot; one soft contact sound | The delivery really succeeded |
| 0-120 ms after confirmation | Small stamp impression and “Delivered: +10 stamps” | A readable reward, independent of colour or audio |
| 120-300 ms | Hand returns to neutral; decorative dust fades | Recovery never locks walking or jumping |
| After 300 ms | Keep only the updated stamp count | Leave the next objective unobscured |

A failed request shows “Move closer” beside the slot, with no success sound or fake stamp increase. A delayed response shows a quiet pending state, not a second accepted delivery. Repeated taps do not stack ten celebrations. Reduced motion uses a static stamp and the same text; muted sound preserves the full meaning. The default camera does not shake or change field of view.

For a separate jump-feel experiment, compare no grace window with a proposed 80 ms ledge grace and 100 ms pre-landing input buffer. These are optional mechanics, not assumed Roblox defaults. Keep route geometry identical and verify that intentional releases, held input and repeat jumps behave consistently before choosing a version.

## Checklist
- [ ] Input acknowledgement cannot be mistaken for confirmed success.
- [ ] Anticipation, contact and recovery have a written event timeline.
- [ ] Camera framing preserves the target and optional motion can be disabled.
- [ ] Muted sound, reduced motion and colour-independent cues preserve meaning.
- [ ] Failure, delayed confirmation, interruption and repeated input are covered.
- [ ] Comparison tests record responsiveness, legibility, discomfort and performance rather than adjectives alone.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S5]. Timings, intensity budgets and buffer values are original starting hypotheses, not measured best settings.
