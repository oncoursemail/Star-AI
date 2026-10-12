---
name: design-core-loop-and-progression
description: Design Roblox core loops, progression pacing, reward schedules and difficulty curves before implementation.
---
# design-core-loop-and-progression
## When to use
Use when a Roblox concept has enjoyable actions but unclear goals, repetitive upgrades, reward gaps or difficulty spikes. Produce a loop diagram in words, a pacing table and a playtest plan, not code. Distinguish an intended experience from measured player behaviour.

## Ten concrete rules
1. Name the player verb, decision, feedback and next opportunity in one sentence. If the loop is only “collect more to collect faster,” add a choice that changes how the player acts. [S1]
2. Separate moment-to-moment action, a session goal and long-term mastery. Assign a provisional duration to each; do not stretch the action loop merely to make progression take longer.
3. Give an achievable first reward through normal play, then preview the next goal with its requirement. Early progress must teach a mechanic rather than hide it behind a shop. [S2]
4. Price upgrades in minutes of actual play: cost divided by net earnings per minute, including travel, failure and spending. Recalculate after multipliers and upgrades; do not balance only for expert earnings.
5. Give reliable base rewards on a fixed schedule. Use optional, unpaid variation for variety, not an unpredictable reward required to progress. Never treat a rare drop's expected time as a guaranteed completion time.
6. Alternate challenge, reward and a safe breather. Specify a natural stopping point with saved progress; do not punish missed days or use a lost streak to pressure another session.
7. Change one difficulty axis at a time: precision, timing, route complexity or resource pressure. Teach it safely, test it alone, then combine mastered skills; a larger health bar is not a new challenge.
8. Make an upgrade offer a meaningful trade-off or new option. State what resets and what persists before any rebirth, and show the post-reset experience; never reset purchases or surprise the player.
9. Keep required progression achievable without payment. Route paid randomness and economy questions to design-economy-and-fair-monetisation; no paid rescue from a deliberately frustrating curve.
10. Playtest the base loop before expanding it. Compare first-success time, retries and completion by experience and device; report sample sizes and unknowns, not invented retention gains. [S3]

## Worked Roblox example
Hypothetical game: Sky Parcel, a cooperative delivery obby. These are design targets, not observed results or universal benchmarks.

Loop: choose a route -> carry a parcel across a short obstacle -> deliver -> earn stamps -> choose another route or unlock a new delivery option. A wider safe route and a narrower optional route offer a real decision without selling an advantage.

| Layer | Proposed pacing | Reward and purpose |
|---|---|---|
| First loop | 0-60 seconds | One safe delivery and 10 stamps; learn pickup, jump and delivery |
| Session | Three 2-minute routes | 20 stamps per route; unlock a new route after three completions |
| Mastery | Several sessions | Optional route medals and cosmetic bag styles; no mandatory rare drop |

A 60-stamp bag style takes three 20-stamp deliveries, or six minutes at the assumed two-minute completion time. At three minutes per delivery it takes nine minutes. The first 10 stamps are a one-time grant, not repeat income; no recurring costs are assumed. These estimates are not guarantees.

Route A teaches wide static jumps. B adds a visible moving platform while keeping landing pads wide. C combines those skills, with a checkpoint before the combined section. After two failures, offer a free practice lane rather than a paid skip. An optional unpaid bonus stamp changes a celebration, never the next required unlock.

For the first playtest, record each participant's first delivery time, route choice and failure location. A proposed review trigger is repeated failures before the first delivery: widen that landing or clarify the cue before changing the whole reward curve. Evaluate enjoyment separately from reward collection.

## Checklist
- [ ] The loop names an action, decision, result and reason to repeat.
- [ ] First reward, session goal, mastery goal and safe stopping point are explicit.
- [ ] Upgrade costs have beginner and experienced-player time estimates.
- [ ] Fixed rewards sustain progress without random bonuses or payment.
- [ ] Each new challenge has a teaching step and a recoverable failure.
- [ ] Proposed timings are labelled; actual tests, sample sizes and unknowns are recorded separately.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S3]. Rules and example numbers are original design recommendations, not Roblox performance guarantees.
