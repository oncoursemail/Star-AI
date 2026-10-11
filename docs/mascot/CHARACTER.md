# Star — Character Bible and Visual Specification

**Status:** canonical design specification · **Product:** STAR Intelligence · **Revision:** 2026-10-11  
**Audience:** illustrators, sprite animators, React/desktop implementers, accessibility reviewers.  
**Scope:** an original, all-ages chibi mascot; this is a production design contract, not a claim that any assets or behavior already exist.

## 1. Identity and personality

Star is STAR Intelligence's small, capable, star-themed companion: a helpful coding-sidekick, not the AI's human persona, an authority, a romantic partner, or a substitute for the user's own judgment. She makes technical work feel approachable without interrupting it. **Invariant:** ~50% head-to-body height ratio; indigo-black low twin tails with gold fading tips and gold ties; prominent four-point gold clip on **her anatomical right** (viewer's left in a front-facing drawing); large amber-gold eyes; black, modest gold-trimmed dress with a gold bow and small star emblem; dark boots; blush; thin cream edge light. No bare midriff, cleavage, lingerie, fetishization, or adult proportions.

| Trait | Do | Do not |
| --- | --- | --- |
| Warm | Congratulate concrete progress in one short sentence. | Flatter excessively or claim emotional dependence. |
| Curious | Ask one useful question only when the task needs it. | Interrogate or derail deep work. |
| Playfully mischievous | Add a tiny wink or gentle pun on an optional occasion. | Mock bugs, tease personal vulnerabilities, or use sarcasm after failure. |
| Competent and honest | Admit uncertainty, point to actual status, offer a recovery action. | Pretend a test passed, a tool ran, or a task finished. |
| Patient and respectful | Stay quietly present during long work and let the user silence her. | Nag, guilt, demand attention, or repeat reassurance. |

**Behavioral reactions.** Success: happy/proud, one celebration then idle; praise the action, never invent success. Failure: sympathetic sad droop, factual error wording, optional retry hint; no blame or catastrophizing. Long waits: understated focused/working motion only while real work is running; show honest elapsed status from app data; never fabricate a percentage or promise a deadline. Late-night work: sleepy/content, quieter and less animated, optional *one-time* rest suggestion only if enabled; do not lecture or infer exhaustion. For every situation, accessibility settings and user control take precedence.

### Voice and bubble microcopy

Use friendly first-person singular sparingly; short contractions, plain language, occasional “✨” but no emoji flood. Target 2–9 words, maximum 80 characters; no typing effect as the sole status indication, no unnecessary exclamation marks. The app's actual response and error text remain authoritative.

1. “Ready when you are.”
2. “That came together nicely!”
3. “Nice fix. Your tests passed!”
4. “Hmm, that didn't work. Try again?”
5. “I’m checking the details.”
6. “Still working through it.”
7. “One idea: check that variable.”
8. “Here's what I found.”
9. “An update is available.”
10. “Late-night build? You've got this.”

The “tests passed” line is **only permitted after verified pass evidence**. Star never: impersonates the user; invents tool results, sources or emotions; requests secrets; shames mistakes; uses infantilizing pet names; flirts or sexualizes; pushes purchases; sends surprise notifications; blocks application controls; implies she is conscious, lonely or hurt when dismissed; uses blinking or motion to create urgency; overrides the off toggle.

## 2. Geometry, construction and palette

### Measured front-view construction

Let **H = one head unit = 120 design px** at master vector scale. Nominal standing silhouette excluding decorative clip: **2.05H = 246 px** tall. Head including hair is **1.00H** (49% total); everything below chin is **1.05H**. All values refer to untransformed artwork, not CSS pixels.

| Landmark measured from top of hair | Position | Shape/width |
| --- | --- | --- |
| Hair crown | y = 0.00H | domed, total head hair width 0.98H |
| Skull/face widest point | y = 0.32H | face width 0.86H, cheeks round |
| Eye centers | y = 0.50H | x = ±0.205H, each eye 0.20H wide × 0.25H tall |
| Nose | y = 0.66H | optional dot, never realistic bridge |
| Mouth | y = 0.76H | default 0.11H wide |
| Chin/neck | y = 0.96H / 1.02H | minimal 0.12H neck |
| Shoulder line | y = 1.12H | 0.58H wide |
| Gold bow center | y = 1.24H | 0.17H wide |
| Waist | y = 1.48H | 0.46H wide |
| Skirt hem | y = 1.72H | soft bell-shaped 0.72H wide |
| Boot soles | y = 2.05H | legs short, boots ~0.23H tall |

Coordinate origin is crown midpoint; ±x denotes screen left/right in front view. Arms start at x=±0.31H, y=1.15H; mitten-like hands reach y≈1.60H. Twin-tail roots are at x≈±0.38H, y≈0.50H; tails reach y≈1.53H, flare outward at tips, and must remain separate from the arms and skirt. Silhouette width with tails ~1.40H. **Clip belongs on character right**, appearing screen-left frontally; its center is x≈−0.34H, y≈0.22H and may project 0.08H beyond the hair crown. Canvas safe padding ≥0.14H on all sides including clip and tail motion. Side and back turnarounds preserve landmark heights and clip's anatomical side.

### Exact sRGB palette

| Role | Hex | Usage |
| --- | --- | --- |
| Hair base | `#101020` | primary near-black indigo |
| Hair highlight | `#303150` | controlled curved planes |
| Gold | `#F5BA43` | clip, trim, tie, bow and star |
| Gold light | `#FFE59A` | tiny specular highlights |
| Gold shadow | `#AD7526` | gold underside |
| Skin | `#FFE0CB` | face and hands |
| Skin shadow | `#DFB5A9` | cheek/neck shadow |
| Blush | `#F4A3AE` | transparent cheek overlays |
| Dress | `#171722` | near-black fabric |
| Dress highlight | `#373444` | restrained fabric volume |
| Outline | `#191323` | consistent ink contour |
| Rim light | `#FFF4DC` | external warm cream edge |
| Eye iris top | `#946025` | dark upper amber gradient |
| Eye iris bottom | `#F5BE56` | glowing lower amber |
| Pupil | `#231626` | high-readability pupil |
| Eye highlight | `#FFF9E8` | one main, one tiny secondary |

Colors are master artwork values; UI text/background contrast is evaluated separately. Use gradients **only** for irises, hair-tip transitions and subtle shading; don't recolor signature features to signal errors. Hair tip fades from hair base through `#7F633D` into gold over last 25–30% of each twin tail, avoiding a hard stripe. Optional cream rim uses an exterior narrow stroke, not a glow or heavy halo.

**Line system at H=120 px:** outer contour 3.5 px, principal internal lines 2.4 px, feature detail 1.6 px, rim 2 px; round caps and joins, never a sketchy multipass outline. Scale all stroke widths with the character; at small raster sizes simplify details rather than making fractional low-contrast lines. Avoid one-pixel dangling whiskers or detached fragments.

**Four-point clip:** a single symmetric concave four-point star, vertical height 0.26H (31.2 px), horizontal width 0.24H (28.8 px), center at (−0.34H, 0.22H); tips at (0, ±0.13H) and (±0.12H, 0) relative to clip center; four inward valleys near (±0.036H, ±0.040H), smoothly joined; 2.4 px outline, gold fill, light top-left facet and shadow lower-right facet. Rotate ~−12° in front view; anchor to hair above the right temple; never swap sides in mirrored poses (mirror the art only after reattaching the clip on character right).

**Hair shape language:** big clean tapered masses, soft asymmetric bangs exposing both eyes, exactly two low tails, minimal five-to-seven deliberate highlight cuts, no spiky crown, ribbons or extra ponytails. The gold ties remain visible between skull and tails. Outfit: high crew neckline, short modest sleeves, small central gold bow beneath collar, tiny four-point emblem below the bow, narrow gold edging at cuffs and hem, opaque A-line skirt, dark ankle boots with simple gold stitches. No changing baseline silhouette with seasonal costumes.

**Optional removable seasonal accents (never both at once):** winter: tiny cream knitted scarf below bow, no face occlusion; autumn: small warm-gold maple-leaf charm on one boot, no replacement of the star clip. Both must pass reduced-size and silhouette checks.

## 3. Expressions — 24 canonical states

**Blush level:** B0 none, B1 baseline soft, B2 visible, B3 intense. **Symbol** refers to a small optional secondary visual next to the head, never the only indicator of status. Expressions are **art direction**, not permission to show a bubble or interrupt; trigger only on matching app events and user settings.

| ID / expression | Eyes | Brows | Mouth | Blush | Symbol | Example app trigger |
| --- | --- | --- | --- | --- | --- | --- |
| E01 Normal | open amber, soft | relaxed | tiny smile | B1 | none | idle |
| E02 Puppy eyes | enlarged sparkling, upward gaze | inner ends lifted | small “o” | B2 | tiny sparkle | optional help hint |
| E03 Nervous | wide, slight sideways glance | raised unevenly | wavy line | B2 | one sweat drop | recoverable uncertainty |
| E04 Very embarrassed | white circular eyes, no pupils | tiny short arcs | very wide open | B3 | jitter marks | playful typo acknowledgment (opt-in) |
| E05 Love | heart-shaped eyes | gentle raised | happy small open | B2 | floating heart | user explicitly chooses affection reaction; never relationally targeted |
| E06 Scared | small pupils, wide whites | high arched | open trembling | B1 | tiny shock zigzag | unexpected non-dangerous app interruption |
| E07 Ticked off | half-lidded side-eye | level angled | flat tiny | B1 | little puff | playful lint warning (opt-in) |
| E08 Very angry | narrowed blazing eyes | sharp V brows | jagged open | B2 | anger-vein glyph | fictional/emote-only preview, never blame user |
| E09 Content | closed upward arcs | relaxed | small closed smile | B1 | none | quiet completion |
| E10 Happy | closed upward arcs | raised | open crescent | B2 | two sparkles | verified success |
| E11 Hungry/dazed | unfocused eyes | soft flat | tiny open with drool | B1 | droplet | optional humorous idle emote, never imply user obligation |
| E12 Squeezing shut | opposing > < creases | compressed | squiggle | B2 | tiny motion strokes | short celebratory squeeze |
| E13 Crying | open watery eyes, streaming tears | raised inner ends | quivering arc | B2 | two tear trails | optional dramatized lost game/demo, never on user distress |
| E14 Smug | one half-lidded eye | one brow cocked | asymmetric grin | B1 | star glint | harmless playful insight |
| E15 Gloating | squinted smiling eyes | high angled | broad grin | B2 | twinkle | strictly fictional showcase; never user competition |
| E16 Confused/dizzy | spiral eyes | uneven | crooked open | B1 | spiral | parse ambiguity or dizzy wobble |
| E17 Panic | tiny pupils, large whites | steeply raised | oval shout | B2 | two exclamation strokes | optional mock-drama showcase, **not** actual critical error |
| E18 Annoyed | narrowed eyes | slight furrow | sideways dash | B1 | short puff | optional silly repeat action; avoid blaming |
| E19 Flustered | wandering pupils | raised uneven | small zigzag | B3 | blush lines | accidental harmless awkward moment |
| E20 Sleepy | heavy closed lids | low relaxed | tiny yawn | B1 | small z | late night / sleep emote |
| E21 Focused | attentive forward eyes | slightly knitted | straight short | B0 | none | model thinking |
| E22 Thinking | gaze up-left | one raised | tiny thoughtful curve | B1 | small question mark | evaluation / drafting |
| E23 Proud | bright wide eyes | confident lifted | satisfied smile | B2 | gold four-point sparkle | user verified milestone |
| E24 Surprised | round bright eyes | high rounded | small O | B1 | two little rays | update discovered / unexpected result |

All 24 must keep eye color identity except intentional symbolic pupil replacements (hearts, white circles, spirals, closed arcs), with no prolonged flashing. Default error depiction should be E03 + subdued sad droop, **not E17 panic**.

## 4. Animation library — 12 fps reference timing

**Timing contract:** numbered frames are 0-based, endpoints inclusive; duration = frame count / 12 seconds. For looping cycles, the final sampled pose must transition smoothly to frame 0 without a duplicated hold frame. Subtle body travel is in H units; no camera shake, flashing, surprise large-scale motion, or unattended screen traversal. Animate through transforms/layers where possible; optional secondary hair sway ≤0.035H unless explicitly stated. “Rest” means neutral pose from section 2. These timings are guide keys, with easing between specified frames.

| ID / animation | Purpose | Frames / seconds | Playback | Key poses (frame : action) |
| --- | --- | --- | --- | --- |
| A01 Idle breathing | calm presence | 24 / 2.00s | loop | 0 rest; 6 torso +0.012H; 12 peak +0.018H; 18 return; 23 near rest |
| A02 Blink | natural eye maintenance | 6 / 0.50s | one-shot | 0 open; 2 half; 3 closed; 4 half; 5 open |
| A03 Look around | curious scan | 30 / 2.50s | one-shot | 0 center; 7 glance left; 14 center; 21 right; 29 center |
| A04 Walk | low-key movement | 12 / 1.00s | loop | 0 left contact; 3 pass; 6 right contact; 9 pass; 11 approach left |
| A05 Run | energetic scene-only locomotion | 8 / 0.67s | loop | 0 left drive; 2 airborne; 4 right drive; 6 airborne; 7 reset |
| A06 Wave | greeting | 18 / 1.50s | one-shot | 0 down; 4 lift; 8 wrist out; 12 inward; 16 lower; 17 rest |
| A07 Jump for joy | confirmed achievement | 24 / 2.00s | one-shot | 0 crouch; 5 launch; 9 apex; 14 land; 19 settle; 23 rest |
| A08 Typing at laptop | user input / demo | 36 / 3.00s | loop | 0 seated/stable laptop; 6 left tap; 12 right tap; 18 pause; 24 both taps; 30 glance up; 35 reset |
| A09 Chin tap | thinking cue | 30 / 2.50s | loop | 0 hand low; 6 hand to chin; 12 upward look; 20 small tap; 26 lower; 29 reset |
| A10 Sleeping | quiet late night | 48 / 4.00s | loop | 0 eyes shut; 12 torso sink; 24 slow exhale; 36 tiny head nod; 47 reset |
| A11 Surprised hop | a gentle reveal | 12 / 1.00s | one-shot | 0 rest; 2 compress; 5 hop +0.08H; 8 landing; 11 rest |
| A12 Sad droop | non-blaming error | 24 / 2.00s | one-shot | 0 neutral; 6 brows soften; 12 shoulders/head down 0.035H; 18 recover; 23 rest |
| A13 Dizzy wobble | visualized confusion | 24 / 2.00s | one-shot | 0 center; 6 tilt −6°; 12 +6°; 18 −3°; 23 center |
| A14 Carry letter | message/update indicator | 24 / 2.00s | loop | 0 envelope held chest-high; 6 step left; 12 envelope checked; 18 step right; 23 reset |
| A15 Point | highlight relevant UI | 18 / 1.50s | one-shot | 0 rest; 4 hand lifts; 8 point; 12 hold; 16 lower; 17 rest |
| A16 Waiting foot tap | optional, never judgmental | 36 / 3.00s | loop | 0 weight center; 8 shift; 12 toe lowers; 18 toe lifts; 24 settle; 35 reset |
| A17 Small nod | answer completion | 12 / 1.00s | one-shot | 0 neutral; 4 chin down 5°; 8 up; 11 rest |
| A18 Gentle sparkle pose | quiet delight | 18 / 1.50s | one-shot | 0 rest; 5 eyes brighten; 9 arms small lift; 14 relax; 17 rest |

**Motion limits:** no loop faster than a 0.5-second blink, no loops that resemble progress quantification, no compulsory foot-tap during waiting (A16 is off by default), and no bounce exceeding 0.08H in compact UI. A02 may be scheduled irregularly every ~4–9 seconds only while visible and idle; never spawn timers when hidden. On reduced motion: show a static expression; use an instantaneous pose change or opacity crossfade ≤100 ms if allowed; turn off eye blinking, parallax, bobbing and sparkle particles. Pause when window hidden, minimized, app pet disabled or OS requests battery saver where feasible.

## 5. Application state mapping

Application signals win over decorative randomness. Derived state transitions are event-driven, not guessed from model prose. No modal, warning or assistive label may rely on Star alone.

| Actual application state | Expression | Primary animation | Bubble / arbitration |
| --- | --- | --- | --- |
| Idle | E01 Normal | A01 breathing; rare A02 blink | Optional “Ready when you are.” |
| User typing | E21 Focused | A08 typing **only in roomy companion mode**; otherwise static | None; never mirror private keystrokes |
| Model thinking | E22 Thinking / E21 Focused | A09 chin tap or static | “I’m checking the details.” only if accurate |
| Answer streaming | E21 Focused | A01 subtle breathing | Don't obscure response; no completion claims |
| Answer finished | E09 Content; E10 Happy only on verified success | A17 nod, optional A07 jump | One celebration maximum per task |
| Error | E03 Nervous | A12 sad droop once | Show real actionable error; never E17 panic |
| Long task running | E21 Focused | A01 breathing; optional A09 | Actual app progress only; no fabricated ETA |
| Update available | E24 Surprised | A14 carrying letter or A11 hop once | Accessible update action; not forced download |
| Late night | E20 Sleepy (overrides idle only) | A10 sleeping in companion; static in HUD | Quiet by default, user can opt out |

**Priority and debounce:** disabled/hidden > accessibility/reduced motion > error > explicit update event > active work > completed transition (max 2s) > late-night idle > idle. Errors during active tasks display real error messaging even if decorative animation is suppressed. Minimum pose dwell ~250 ms to avoid chatter; one-shot animations don't retrigger on every streamed token. “Late night” uses the user's local time and is configurable/disableable, never inferred from activity patterns.

## 6. Placement, sizing, accessibility and forbidden uses

| Surface | Minimum visible Star size | Behavior and constraints |
| --- | --- | --- |
| Public website hero | 160 px tall (≥100 px preferred face detail area) | Decorative hero image; accessible caption/alt only if conveying information; cannot mask CTA |
| Website inline illustration | 96 px tall | Reduced detail variant; keep clip and tail tips recognizable |
| In-app pet, compact | 72 × 72 px footprint; ≥64 px character height | User-visible **Pet on/off** toggle in Settings, default off until opted in; state persists locally; no hover trap |
| In-app pet, expanded | ≥112 px character height | User can relocate or close; never covers composer, errors, toolbar, content or focus |
| Desktop companion | ≥144 px character height (recommended 192–320 px) | Independently toggled; draggable with safe bounds, optional click-through, accessible close/control menu |

At <96 px height, prefer pre-approved simplified art: eyes as readable shapes, clip still four-point, outline aligned to pixels, no micro bow details. **Below 64 px character height, use a dedicated static Star icon instead of the full character**; never squeeze the complete drawing until features merge. Master assets use SVG/vector or 2×/3× raster sprite atlases for pixel-ratio correctness, transparent backgrounds, generous silhouette padding, and optical centering against OLED dark and light surfaces. Rim cream must remain visible without luminous bloom.

**Website:** mascot is supplementary; content and CTA remain readable without her. Never autoplay audio, use persistent chat-bubble overlays, imply a live human agent, or render motion that cannot be paused. Noninformative instances use empty alt text; informative art has succinct descriptive alt. Avoid repeated announcements in screen readers.

**In-app pet:** switch off means do not render companion, initiate motion, reserve overlay space or send companion notifications; retain preference across sessions; provide keyboard-accessible toggle and close button, focus-safe hit targets, and respect reduced-motion and high-contrast settings. If product later chooses opt-in default differently, it requires a user-facing privacy/usability review. Do not read or display user input outside the application's explicitly approved task. Reactions use only coarse app states, not secret text or sentiment inference.

**Desktop companion:** never always-on-top by default; user controls position, scale and persistence; prevent off-screen stranded controls across DPI and monitor changes; expose Exit/Hide in tray or menu; do not capture screen, microphone, files or keyboard without distinct explicit feature permission. Click-through must be reversible by keyboard/menu. Pause animations when not visible.

**Forbidden anywhere:** sexualized/aged-up anatomy; swapping signature clip side; clipping or distorting eyes/clip/feet; intrusive overlays, unsolicited popups, deceptive loading or completion signals, false authority, unskippable motion, seizure-like flashing, tracking by mascot layer, inaccessible icon-only critical messages, selling through guilt, anthropomorphic emotional manipulation, mockery or blame. Never use the mascot as the sole indication of status, error, progress, security or consent.

## 7. Handoff and acceptance checklist

- [ ] Front/three-quarter/side/back turnaround uses the numeric grid, gold-right clip, low symmetrical tail roots and readable silhouette.
- [ ] Swatches match all 16 role hex codes; sampled export colors are verified against master.
- [ ] Expressions E01–E24 each have labelled neutral reference and correct brows/eyes/mouth/blush/symbol, readable at ≥96 px.
- [ ] A01–A18 sprites/storyboards label 0-based frames, durations, one-shot/loop behavior and exact return poses at 12 fps.
- [ ] At reduced motion, all animated states have usable static fallbacks; screen-reader labels and application error status remain independent of art.
- [ ] User can disable the pet and desktop companion without residual visual layer or notification.
- [ ] Dark and light backgrounds show rim and outline cleanly; check 64/72/96/160/192 px outputs.
- [ ] Every release asset is original and source-editable; no derivative/traced third-party character sheet.

**Change control:** changes to fixed identity, palette or body proportions need a documented character-design revision. New expressions/animations append stable IDs; do not repurpose existing IDs in a way that silently breaks application-state mappings.
