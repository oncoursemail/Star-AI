---
name: design-onboarding-and-tutorial
description: Design Roblox onboarding, the first sixty seconds and tutorials that teach through player actions.
---
# design-onboarding-and-tutorial
## When to use
Use when new Roblox players hesitate, skip instructions, cannot find the first goal or leave before experiencing the core loop. Deliver a first-minute beat sheet, success conditions and recovery paths, not a scripted tutorial implementation.

## Ten concrete rules
1. Define one first-session promise in player language, such as “deliver a parcel together.” The first sixty seconds should demonstrate that promise, not explain every feature. [S1]
2. Start from a safe, controllable view of the first goal. Keep the loading state distinct from playable time, and remove competing shop, reward and announcement panels from the first action.
3. Teach by doing: show one cue, let the player perform the action, acknowledge the result, then fade the cue. A tapped Next button proves reading or impatience, not learning. [S2]
4. Introduce one unfamiliar concept per beat. Explain pickup when beside a parcel, not at spawn; postpone crafting, trading and advanced menus until they become relevant.
5. Use a short verb-and-object instruction with a visible target and the current device's control. Never ask a touch player to press a keyboard key; pair icons with readable words.
6. Require an observable outcome for each step: parcel carried, gap crossed or delivery accepted. Do not advance on a fixed timer while a slower player is still learning.
7. Offer a contextual hint after inactivity, then an optional demonstration or free practice. Keep help dismissible and repeatable; do not repeatedly interrupt someone exploring intentionally.
8. Make mistakes cheap. A missed jump returns the player near the lesson with its state intact; death, rejoin or a missing teammate must not trap the tutorial. Specify each recovery path.
9. Let experienced players skip and later replay lessons. Never remove essential starter tools or punish skipping. Teach cooperative actions with an available solo practice substitute, not compulsory waiting.
10. Test with unfamiliar players without coaching. Record completion and abandonment for each step, time-to-first-success and later unprompted reuse of the skill; tutorial completion is not the same metric as next-day retention. [S1, S3]

## Worked Roblox example
Hypothetical game: Sky Parcel. The timeline below is a design target measured from gaining control, not a forced countdown or a claim that a playtest ran.

| Playable time | Player action | Cue and evidence of learning |
|---|---|---|
| 0-10 seconds | Walk toward the parcel on a safe dock | Visible delivery tower, one “Pick up the parcel” prompt near the object |
| 10-20 seconds | Pick it up using the active input method | Bag changes pose and the objective becomes “Deliver to the tower”; proceed only when carrying |
| 20-35 seconds | Cross a wide practice gap | One jump cue; landing on the far pad completes this beat |
| 35-50 seconds | Place the parcel at the tower | Delivery animation plus “Delivered: +10 stamps”; show the stamp total |
| 50-60 seconds | Choose a second route | Remove the guide; two labelled routes ask the player to reuse pickup and jump unaided |

After eight seconds without progress, offer “Show me” beside the relevant action; this is a provisional hint threshold, not an auto-advance. A fall returns to the near pad holding the parcel. A reconnect resumes the unfinished beat rather than replaying every message. If the parcel is unavailable, give another practice parcel. If a partner leaves, the same dock remains completable alone. Skip grants the normal starter bag and exposes Help in the pause menu, not a paid shortcut.

In a planned five-person first pass, record attempts and completion at each beat without collecting personal identifiers. Report counts, not a statistically proven uplift. If participants finish by following arrows but cannot make the second delivery, revise the teaching and retest; celebrating the first completion alone would miss that failure.

## Checklist
- [ ] The player performs the main verb within the proposed first minute.
- [ ] Each beat has one cue, one action and an outcome-based completion condition.
- [ ] Touch, keyboard and controller prompts match the available controls.
- [ ] Hints, skip, replay, death, rejoin and partner loss have defined behaviour.
- [ ] No purchase prompt blocks the lesson; essential tools remain free.
- [ ] Unprompted reuse and step-level drop-off are evaluated separately from retention.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S3]. Timings, hint thresholds and recovery scenarios are original design proposals.
