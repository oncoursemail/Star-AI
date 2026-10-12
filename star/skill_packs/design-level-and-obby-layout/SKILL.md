---
name: design-level-and-obby-layout
description: Design Roblox level and obby layouts with readable routes, fair risk and reward, checkpoint spacing and flow.
---
# design-level-and-obby-layout
## When to use
Use when a Roblox level loses players, has unexplained deaths, repeats the same jump or places checkpoints by distance alone. Produce a route sketch in words, a challenge sequence and a checkpoint rationale, not construction code or decorative assets.

## Ten concrete rules
1. State the skill and emotional beat of each section before decorating it. Give a section one main idea, such as observing a moving platform, instead of stacking unrelated hazards. [S1]
2. Show the next destination and its landing surface from the approach. Use silhouette, contrast and landmarks; never require a blind leap to discover the only valid route.
3. Keep navigation and hazard language consistent: a striped edge always warns, a flag always marks a safe checkpoint. Pair colour with shape, texture or symbols so red-green discrimination is unnecessary. [S2]
4. Introduce a mechanic safely, vary it once, then combine it with a mastered mechanic. Change one difficulty variable per teaching step, not gap width, camera angle and platform speed together.
5. Calibrate jump distances and pad widths with the actual intended avatar scale, movement settings and input devices. A distance in studs is not a universal difficulty rating; leave a beginner margin below measured limits.
6. Offer visible optional risk for optional rewards, with a readable way back. The normal path must remain enjoyable and complete without buying a skip or taking a precision shortcut.
7. Place checkpoints at learning boundaries and before demanding combinations. Budget the time lost on failure, including respawn and travel, rather than spacing checkpoints at equal geometric distances.
8. Make recovery orient the player toward the next attempt on a safe surface. Avoid spawning inside hazards, facing a wall or into another player's jump path; state what progress survives a fall.
9. Protect flow with waiting and landing space. Test camera clearance, reverse travel, crowding and a disconnected partner; a narrow cooperative gate must not depend on a stranger standing still forever. [S3]
10. Greybox and playtest before adding visual density. Mark hesitation, deaths and retries on the route sketch, then change one suspect section and compare; an attractive overhead map is not evidence that the playable view works. [S1]

## Worked Roblox example
Hypothetical game: Sky Parcel, route “Windmill Steps.” This is a proposed layout, not a tested Roblox place.

Route sketch: safe dock A -> wide static pads B -> checkpoint C -> single moving platform D -> checkpoint E -> static-plus-moving combination F -> delivery terrace G. From A, the windmill silhouette marks G; local flags show C and E without revealing every obstacle at once.

| Section | Intended lesson or choice | Recovery and flow |
|---|---|---|
| A-B | Learn the jump on wide, stationary pads | Safety floor returns to A; no stamp loss |
| C-D | Observe one slow platform cycle before boarding | C faces the boarding pad; a waiting bay lets others pass |
| E-F | Combine the known jumps | Failures return to E, not the whole route |
| Optional side path from E | Narrower hops for a cosmetic route medal | Medal visible before branching; safe main route still reaches G |
| G | Deliver and pause | Clear terrace, no hazards or forced timer before the next choice |

First measure a comfortable novice jump in the intended movement setup; start required gaps below that distance. Do not assign a supposedly universal eight-stud jump. Set a provisional maximum of twenty seconds of replay after a fall, including respawn and travel. If F exceeds it for learners, shorten the combination or add a recovery landing rather than inserting a paid skip.

Review the route at playable camera height on a small touch screen, including two avatars waiting at D and several arriving at E. Decorative windmill blades must not hide F's landing or look like hazards when harmless. Record the actual retry times and where players look for a route; no Studio playtest is claimed here.

## Checklist
- [ ] Each section teaches or tests one named skill.
- [ ] Destination, landing and hazard meanings are readable before commitment.
- [ ] Required jumps have been calibrated for the intended avatar and controls.
- [ ] Optional danger has an optional reward and a safe alternative.
- [ ] Checkpoints bound replay time and respawn into safe, oriented space.
- [ ] Camera, crowding, colour-independent cues and recovery paths have test cases.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S3]. The route, retry budget and checkpoint positions are original hypotheses to verify in play.
