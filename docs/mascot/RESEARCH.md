# Star mascot — research and production rules

> Research memo • 2026-10-11 • Design specification, **not** a claim that assets or animation have been implemented. Sources linked inline and catalogued below. Numeric frame/timing/geometry targets labelled **proposal** are art-direction hypotheses to validate in the running desktop UI, not scientific universals.

## Identity and scope

Star is an **original, all-ages chibi anime girl** for a local-first Roblox-development assistant. Invariants: very dark indigo-black hair, **two low twin tails with gold-fading tips**, **gold hair ties**, **large four-point gold star hair clip on her own right** (artist must disambiguate character-right from viewer-left in turnarounds), amber-gold eyes, black dress with gold trim, gold bow, small gold star emblem, dark boots, soft blush, and a thin cream silhouette rim. Head occupies **about half the standing height**. Personality: warm, curious, helpful, lightly mischievous; wholesome, fully covered, never sexualized. Product context: OLED-black UI with restrained gold accents. The repository README describes the React desktop served offline in Qt WebEngine and a legacy Qt UI; recommendations distinguish these renderers.

This is a design synthesis from drawing tutorials, official product/animation documentation, and W3C accessibility standards. **Do not copy character sheets, trace illustrations, reuse a mascot logo, or infer that reference style-guide artwork is licensed for Star.**

## 1. Chibi construction and visual hierarchy

[Clip Studio Paint's chibi construction guide](https://www.clipstudio.net/how-to-draw/archives/155423) describes common chibis as approximately **2–4 heads high**, emphasizes oversized facial features and simplifying hair/clothes, and notes that longer legs read more mature. Treat head counts as artistic vocabulary, not immutable anatomy:

| Total standing height | Head fraction | Communication and use |
| --- | --- | --- |
| **2 heads** | 50% | Most plush/toy-like, youthful, immediately cute; **Star's main full-body canonical model**. Detail budget is tight. |
| **2.5 heads** | 40% | Better hand gestures and clothing clarity while remaining unmistakably chibi; possible secondary illustration variant, **not** a replacement canonical base. |
| **3 heads** | 33% | More pose/walk range, longer limbs and slightly older impression; editorial scenes only if clearly tagged as a variant. |

**Construction proposal:** sketch a rounded cranium and softened jaw, draw an eye guideline *below* the geometric halfway line of the cranium, then keep nose/mouth small and near the lower facial third. Eye placement on the lower half applies to the *visible face mass*, not a mandate to stack every feature below the full hair silhouette's midpoint. Use curved facial guides for 3/4 views. Make the face broad; keep chin compact. Avoid adult body anatomy, pronounced bust or waist, high heels and elongated thighs.

**Face and spacing:** for front view use one-eye-width between eyes as a **starting measuring convention**, then optically adjust for giant chibi eyes and thick bangs; keep corresponding pupils, upper-lid angles and glints aligned to a shared gaze target. [Art Rocket eye placement guide](https://www.clipstudio.net/how-to-draw/archives/155631) describes the conventional one-eye gap as a starting point for more naturalistic faces, **not a chibi law**. Test face with horizontal flip and 3/4 rotation.

**Hands/feet:** mitten-like palms and thumb wedge for 32–64 px; separate fingers only in large emotive poses. Short forearms, rounded hands, boots as two dark distinct wedges with gold top-edge cues at large size. Preserve a visible gap between boots and between each tail/body, even after rasterization.

**Silhouette test:** render opaque black at 256, 64 and 32 px, blur slightly and inspect at 100% display. Must still read as a big head + two **low** tapered tails + short dress bell + boots, with the off-center four-point star clip prominent. If clip/tails merge with head, enlarge negative spaces or alter contour; **never** solve with random floating symbols. At 32 px prefer an intentional **face-and-star avatar crop** rather than illegible full-body detailing. Also check mirror flip, grayscale, light UI, OLED black, color-vision simulations, and at Windows 125/150/200% scaling.

## 2. Anime eye anatomy and expression mechanics

[Art Rocket's anime eyes tutorial](https://www.clipstudio.net/how-to-draw/archives/162395) describes the value of simplifying and varying anime eye shapes; its [eye drawing guide](https://www.clipstudio.net/how-to-draw/archives/155631) explains positioning and perspective. Use this **paint order** for Star:

1. **Upper lash/lid:** thick dark curved upper edge, tapered at ends; its angle communicates attitude. Keep lashes as an integrated shape, not detached spikes.
2. **Eye white/negative space:** warm pale ivory rather than pure glowing white; upper lid may cover its top.
3. **Iris silhouette:** broad oval/rounded amber shape, partly occluded by upper lid in neutral gaze; smaller iris + exposed white signals surprise.
4. **Pupil:** centrally nested dark amber-brown form; both pupils converge on **one** focus point.
5. **Iris shading:** dark burnt-gold under upper lid, honey midtone, lighter bottom; controlled transition, no radioactive bloom.
6. **Highlights:** one consistent prominent highlight and optionally **one** subordinate glint, positioned according to a single implied light source across both eyes. Highlights overlay pupil/iris logically and should not randomly drift between expression drawings.
7. **Lower lid:** abbreviated line or corner mark; few lower lashes, if any. Heavy lower rings age/tire a character.
8. **Eyebrows and nearby cheek:** brows and eyelid aperture jointly carry emotion; soft blush must not obscure the lash/iris silhouette.

| Visual parameter | Tends to read as… | Star default |
| --- | --- | --- |
| Large round aperture/iris | Cute, open, high energy/younger coding | Roundish tall amber eyes, not excessively wide |
| Narrow aperture, low upper lid | Relaxed, skeptical or sly | For gentle mischievous side-eye, with one eyebrow |
| Raised lids, small iris relative to whites | Shock, fear, alarm | Brief reaction only |
| Lowered outer corners, lifted inner brows | Worry or sadness | Use alongside mouth/cheek cue |
| Numerous high-contrast glints | Excited or magical but potentially noisy | One main + at most one small on normal portrait |
| Missing glints/flat iris | Can be deliberate stunned/deadpan shorthand | Only with explicit expression design |

**Common failures and repairs:**
- *Dead/blank stare:* pupils not aiming at same thing, no upper-lid overlap, identical perfect-circle irises, bland iris value hierarchy. Repair with gaze target, lid occlusion and a simple controlled gradient.
- *Cross-eyed/wall-eyed:* iris centers diverge independently. Move both together in a perspective-aware coordinate system.
- *Impossible lighting:* glints move separately across eyes, different highlight angles or dark-shaded side. Draw lighting guide first.
- *Weird/uncanny face:* eye-to-eye gap inconsistent, one eye larger without foreshortening, mismatched slant, facial features detached from round head. Flip and draw bounding boxes; check at 64 px.
- *Surprised all the time:* iris never touches/overlaps the upper lid; neutral lids should sit partway over the irises.
- *Overdesigned eyes:* micro-stars, six gradients, too many eyelashes vanish or glitter noisily at 32 px. Maintain a separate reduced-detail eye master.

**Expression matrix (proposal):** neutral = slight upper-lid overlap + symmetric glints + soft smile; delighted = raised brows + curved smiling mouth + larger highlight only at large scale; thinking = eyes directed aside + slight lid drop, one lifted brow; concern = upturned inner brows + smaller mouth; focused = lowered brows + tight mouth but not angry. Emotional legibility must survive **without color**.

## 3. Manga/anime shorthand symbols (manpu)

Manpu are context-dependent *visual grammar*; meaning comes from the combination of symbol **placement, eyebrows, mouth, pose, and situation**, not a universal icon dictionary. Reference context: [Wikipedia's overview of manga iconography](https://en.wikipedia.org/wiki/Manga_iconography) (secondary/background, not a prescriptive standard), [Clip Studio chibi expression guidance](https://www.clipstudio.net/how-to-draw/archives/155423). Star-specific readings below are art-direction conventions:

| Symbol | Typical reading | Placement / correct use / caution |
| --- | --- | --- |
| Single sweat drop | Awkwardness, nervous embarrassment, mild panic | Near temple; pair with sheepish mouth, **not** constant perspiration |
| Anger vein/cross | Frustration, comic annoyance | Temple or nearby; keep playful, never threatening |
| Hearts | Affection, approval, delight | Around positive reactions, not romantic flirting with user |
| Sparkles | Inspiration, delight, success | Outside silhouette for *brief* success only; avoid constant particles |
| Spiral eyes | Dizzy, overloaded, confused | Paired with tilted posture, immediately revert; avoid for normal errors |
| **> <** squeezed eyes | Effort, intense joy, flustered protest | Replace eyes deliberately, pair with mouth; not literal math glyphs |
| White empty circle eyes | Shock, stunned surprise, deadpan | Brief visual gag, combine with static mouth/brows |
| Waterfall tears | Exaggerated comic crying | Only knowingly comic moment; never for actual user difficulty |
| Blush strokes | Shyness, happy embarrassment, warmth | Small cheek strokes, not full-face saturated red |
| Sleep bubble | Dozing, inactivity | Use only in explicit rest/away mode, no bubble during live progress |
| Vertical gloom lines/shadow | Dread, gloom, defeat | Do not deploy for normal error states, which need useful text |

Avoid culturally ambiguous symbols as the *only* status channel. Error, success, loading and privacy states require readable text/accessible labels. Place manpu on an independently hideable layer; no endless icon spam near the chat composer.

## 4. Product mascot, 32 px identity, and brand governance

The [GitHub 2025 brand guidelines, mascot section](https://brand.github.com/GitHub-BrandGuidelines-2025.pdf) explicitly favor sparing contextual use rather than filling spaces with mascots. The [GitHub brand site](https://brand.github.com/) provides an example of governed mascot/identity treatment, not artwork to reuse. [Mozilla brand guidance](https://mozilla.design/) is another example of a centrally documented visual system; don't assume its mascot rules match GitHub's. **VTuber/Live2D-style practice** illustrates disciplined recurring identity (hair landmarks, eye shape, accessory silhouettes, rig parameter naming), but any individual character's licensed assets and style restrictions remain separate; [Live2D official manual](https://docs.live2d.com/4.2/en/cubism-editor-manual/glossary/) explains parts/parameters/deformers, not permission to imitate a VTuber. Use these as *systems lessons*, not character-design templates.

Star's recognition is a **feature bundle**, not one magic color: (a) four-point **gold** star at character-right temple, (b) symmetrical **low** indigo-black twin tails with gold ends, (c) amber eyes/rounded face, (d) compact black-and-gold dress with bow/emblem, (e) soft cream edge. Do not swap gold to neon yellow, raise tails to high pigtails, turn the clip into five points, or remove one tail. The upper-body or face-only variant should retain at least clip + characteristic hair silhouette + amber eyes.

**Asset matrix (proposal):**

| Usage | View | Allowed detail |
| --- | --- | --- |
| 32 px favicon/status tray | Cropped face + star clip + dark hair frame | Very thick simplification; usually no legs, tiny iris gradient omitted |
| 48–96 px chat avatar | Head/shoulders | Eyes, clip and gold ties if visible |
| 128–256 px mini companion | Full body 2-head ratio | Dress bow, emblem, two tails, boots, cream contour |
| 512–1024 px docs/marketing | Canonical full illustration | Subtle gradients and hand gestures; same landmarks |

Keep a layered original master (vector where practical), semantic IDs for eyelids/iris/pupils/tails/skirt, and deterministic exports. Maintain a simple palette token file **when assets are implemented**; suggested **starting** hues only: near-black #09090D; hair #101222 with indigo midtone #292948; gold #E6B950; amber #D88B32; cream #F7E8D1. These require actual contrast tests against production backgrounds. The **cream rim is not a substitute for UI contrast**. For actionable status icons WCAG non-text contrast is generally at least **3:1**; normal text at least **4.5:1**, large text **3:1** where applicable ([W3C G207](https://www.w3.org/WAI/WCAG22/Techniques/general/G207), [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)). Decorative character art is not automatically subject to the same pixel-by-pixel rule as information-carrying controls.

**Consistency checklist:** one unmirrored identity sheet with labeled character-right clip; front, 3/4, side and back; five canonical moods; scale-sheet at 32/64/128/256; monochrome silhouette; gold-tip placement; line-weight rules; no hair clipping through the tie; no emblem in place of bow; no skin exposure beyond wholesome face/hands. Assign version tags to approved masters and avoid per-animation redraw drift.

## 5. Small 2D motion and technical implementation

Classical principles are a toolkit, **not** an obligation to keep a tiny desktop assistant continuously moving. Apply:
- **Squash/stretch:** tiny head/torso vertical compression on landing or delight, with plausible volume; no rubber neck.
- **Anticipation:** 1–2 setup drawings before a hop/wave to make intent legible.
- **Follow-through/overlap:** hair tips and skirt settle 1–3 frames after head/torso stops; gold tips should remain attached to tails.
- **Arcs:** hand/clip/head swing along gentle curved paths rather than machine-linear trajectories.
- **Timing/easing:** faster action and slower settle, ease-in/out; hold readable face poses.
- **Exaggeration:** increase expression readability without identity distortion.
References: [Disney's *The Illusion of Life* principles overview](https://en.wikipedia.org/wiki/Twelve_basic_principles_of_animation) (secondary overview; original book is the primary classic reference), [Qt animation framework](https://doc.qt.io/qt-6/animation-overview.html).

**Proposed defaults, not physiological claims:** Blink irregularly with average interblink interval around **4–8 s** while actively on-screen, sometimes double-blink; eyelids close/open in ~**120–220 ms** total and pause slightly when shut if acting sleepy. Avoid synchronized periodic blinks across multiple mascots. Tiny idle breathing: ~1–2% displacement/scale over **3–5 s**, plus optional hair-tip offset <2 px at 256 px canvas, then a long stillness/hold; *prefer no indefinite animation by default while the user writes*. Use event-bound cycles rather than perpetual bouncing. Short wave: **0.5–0.9 s**; delighted hop: **0.45–0.75 s**; thinking glance: **0.4–0.7 s** then static hold. Clamp reactions to one at a time, suppress on repeated streaming tokens.

**Chibi walk guide (proposal):** use a small **6–8 distinct drawing** cycle over **0.65–0.9 s** (or 8–12 key poses for smoother interpolation); frames: left contact → down → passing → up → right contact → down → passing → up. Short stride, minimal pelvis twist, alternating arms, ~1–2 px bob in a 128 px sprite. Feet must visibly plant on contact. At 12 fps a 0.75 s cycle is about 9 displayed frames; at 24 fps, 18 displayed frames; **frame count is sampling, not a quality guarantee**. Favor pose clarity and foot lock over lots of frames. Don't walk on top of text or important controls.

**Rendering tradeoffs:**

| Technique | Best for | Limitations |
| --- | --- | --- |
| Frame-by-frame PNG/WebP/sprite atlas | Hand-drawn eyes, mouth substitutions, expressive smears | More assets/storage, consistent redraw difficult, discrete expressions easy |
| SVG/CSS layered cut-out | Blinks, pivots, hair-tip sway, bow/wave, simple walk | Rigid transforms can show hinge seams or paper-doll appearance; CSS cannot provide general-purpose smooth mesh warp |
| Canvas/Web Animations/small JS controller | State machine, timing jitter, runtime pause, active/idle gating | More code/test surface; avoid large rerender loops |
| Live2D Cubism ArtMesh/deformer rig | Smooth face turns, perspective/deform, nuanced expressions | Rig/texture/runtime cost, licensing and deployment review, more authoring complexity |
| Qt-native scene/graphics objects | Legacy UI without web embedding | Need explicit animation handling, scaling/DPI work, sync with app focus; avoid obsolete APIs |

[Live2D official mesh instructions](https://docs.live2d.com/en/cubism-editor-manual/mesh-edit-manual/) explain ArtMesh deformation; [parameters glossary](https://docs.live2d.com/4.2/en/cubism-editor-manual/glossary/) documents keyforms and warp/rotation deformers. For React/Qt WebEngine prototype, an inline **layered SVG with CSS transforms** plus a tiny JS finite-state controller is realistic: transform-origin anchored tails/skirt; swap eye/mouth shapes; respect CSS reduced motion; throttle when hidden/inactive. SVG SMIL exists ([MDN SVG animate](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/animate)), but CSS/WAAPI is often easier to centralize under one reduced-motion policy. SVG gradients clip to paths and can provide eye depth; arbitrary Live2D-style deformation is **not** equivalent to CSS transform.

Qt-native legacy path: use [QPropertyAnimation](https://doc.qt.io/qt-6/qpropertyanimation.html), groups and easing curves, or [PySide6 animation overview](https://doc.qt.io/qtforpython-6/overviews/qtcore-animation-overview.html), with raster/vector assets rendered at device-pixel ratio. **Do not start a new Qt implementation using the deprecated** [QGraphicsItemAnimation](https://doc.qt.io/qt-6.10/qgraphicsitemanimation.html). If the current UI is the bundled React app in Qt WebEngine, implement in web layers first; avoid duplicate Qt timers.

**Motion state machine proposal:** `hidden | still | idle | thinking | responding | success | error | user-interaction`. Priority: user accessibility/visibility settings > user-triggered > relevant status > decorative idle. Persist preferences locally; never make an animation completion necessary for a task to finish. Expose pause/disable control and no audio by default. Transition to still state on window blur or reduced motion.

## 6. Accessibility and work-focus guardrails

Normative baseline: [WCAG 2.2](https://www.w3.org/TR/WCAG22/) **2.2.2 Pause, Stop, Hide** requires control for auto-start moving/blinking content running alongside other content for **more than five seconds**, except essential motion; **2.3.1 Three Flashes or Below Threshold** limits unsafe flashing, and **2.3.3 Animation from Interactions** (AAA) allows disabling nonessential motion. Design to exceed the minimum: **no flashing at all** in the companion, no strobes/flicker/rapid gold flashes, no sudden zooms. The WCAG flash threshold must not be misread as permission to flash three times per second routinely. [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion) and [MDN SVG animation accessibility](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/animate) recommend replacing or disabling nonessential motion.

**Implementation requirements:** honor `@media (prefers-reduced-motion: reduce)` in React and an equivalent explicit Qt/local preference; provide **Still / Subtle / Full** mascot motion setting (default **Still** for work areas is a proposed product choice). Always allow hide/mute, and make decorative mascot non-focusable/noninteractive unless it truly has an accessible function. If it offers actions: keyboard focus visible, logical tab order, button labels, action independent of animation. Status changes must be in ordinary UI text; do not use color, face mood, or symbol alone. Do not cover editor, chat text, send controls, tool results, permission dialogs, or Roblox Studio viewport. On long tasks, change to one static concerned/thinking/focused pose rather than looping forever. Respect battery saver/low FPS; tab/window invisible means animations stop, not just invisible GPU work. Avoid announcing every blink to assistive technology; decorative SVG should be aria-hidden and alt text belongs only on meaningful illustrations.

**Acceptance tests to plan:** visual screenshot comparisons at 32/64/128 and dark/light backgrounds; silhouette and gaze review; CSS reduced motion simulated; hide/pause preference persistence; keyboard-only navigation; screen reader status accuracy; 200% scaling; minimized-window CPU/GPU check; prolonged 30-minute coding session for annoyance. These are *proposed tests*, not run by this documentation PR.

---

## Star's one-page production rule card (normative design direction)

1. **Identity locked:** original wholesome chibi girl; head ≈ half of standing height; low indigo-black twin tails fading to gold; gold ties; **four-point star hair clip on character-right**; amber eyes; modest black/gold dress, bow + small star emblem, dark boots, blush, fine cream rim.
2. **Shape before polish:** at 32/64/128/256 px recognizable from silhouette; at 32 use face+star crop if full-body loses detail. Preserve clip, tail/body gaps and two boots where visible.
3. **Facial geometry:** rounded cheeks, low eye guideline, small nose/mouth, shared gaze target, matching eye tilt except intentional perspective. Flip-test.
4. **Eyes:** dark upper lash; tall amber iris partly under lid; centered pupil; top dark/bottom light shading; **one strong + max one minor glint** with consistent lighting; restrained lower lid. No random white pinpricks.
5. **Expressions:** maintain approved neutral, happy, thinking, concerned, surprised and lightly mischievous masters. Eyebrows + lids + mouth must agree. Never use a comic symbol to communicate a serious error alone.
6. **Manpu:** optional, short-lived context markers only. Sweat = awkward; vein = comic frustration; hearts = cheerful appreciation; sparkles = a brief success; spirals = comic dizziness; >< = squeezed eyes; blank circles = shock; tears = theatrical comedy; blush = warmth; bubble = idle sleep; gloom = dramatic defeat. Do not spam or infantilize real user failures.
7. **Colors:** OLED charcoal/black, indigo shadows, honey amber, restrained warm gold, thin cream rim; no neon bloom. Audit actual contrast for informational glyphs and text.
8. **Motion:** prioritize readable pose; blinks and occasional wave over constant bobbing. Hair/skirt follow-through lags body gently; use arcs, anticipation, easing and foot contact. Avoid perpetual loops while typing.
9. **Timing proposal:** irregular blink ~4–8 s, closure/opening 120–220 ms; short wave 0.5–0.9 s; 6–8-pose walk 0.65–0.9 s; numbers must be visually tested.
10. **Tech:** begin with layered SVG/CSS in React/Qt WebEngine, small state controller and expression swaps. Add frame sprites where superior; only consider Live2D if strong expressive need offsets rig/runtime cost. Qt legacy use QPropertyAnimation, **not deprecated QGraphicsItemAnimation**.
11. **Accessibility first:** reduced motion respected; Still/Subtle/Full and Hide; no strobes, no sound by default, no competing with chat/editor; ordinary status text always available. Decorative art absent from keyboard/screen-reader tree.
12. **Review gate:** design-source master, character-right annotation, palette/line-weight sheet, expression/silhouette scale sheet and accessibility QA before shipping. No traced/copycat designs; human art approval required.

## Sources consulted and further reading

**Drawing / design**
- [Art Rocket/Clip Studio Paint — Easy Steps to Creating Chibi Characters](https://www.clipstudio.net/how-to-draw/archives/155423) — chibi head ratios, feature reduction, softer body and expressive eyes.
- [Art Rocket — 5 Tips on How to Draw Eyes Easily](https://www.clipstudio.net/how-to-draw/archives/155631) — placement, eye gap, perspective and style.
- [Art Rocket — How to Draw Anime Eyes Like a Pro](https://www.clipstudio.net/how-to-draw/archives/162395) — eye shapes and color.
- [Manga iconography](https://en.wikipedia.org/wiki/Manga_iconography) — secondary overview of symbolic expression shorthand; symbolic readings can vary across creators and audiences.
- [GitHub Brand Guidelines 2025 (PDF)](https://brand.github.com/GitHub-BrandGuidelines-2025.pdf) — official mascot-use restraint; example only, not license to reuse.
- [GitHub Brand](https://brand.github.com/) — brand governance example.
- [Mozilla Design](https://mozilla.design/) — visual identity governance example.
- [Twelve basic principles of animation](https://en.wikipedia.org/wiki/Twelve_basic_principles_of_animation) — secondary summary of principles.

**Rendering / animation**
- [Live2D — Manual Mesh Editing](https://docs.live2d.com/en/cubism-editor-manual/mesh-edit-manual/) — ArtMesh editing.
- [Live2D Cubism glossary](https://docs.live2d.com/4.2/en/cubism-editor-manual/glossary/) — deformers/parts/parameters.
- [MDN — SVG animate](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/animate) — SVG animation and accessibility.
- [Qt — Animation Framework](https://doc.qt.io/qt-6/animation-overview.html) — easing, property animation.
- [Qt — QPropertyAnimation](https://doc.qt.io/qt-6/qpropertyanimation.html) — Qt supported implementation.
- [Qt for Python — animation overview](https://doc.qt.io/qtforpython-6/overviews/qtcore-animation-overview.html).
- [Qt — QGraphicsItemAnimation (deprecated)](https://doc.qt.io/qt-6.10/qgraphicsitemanimation.html) — avoid for new code.

**Accessibility**
- [W3C — WCAG 2.2](https://www.w3.org/TR/WCAG22/) — motion, flash and contrast requirements.
- [W3C G207 — non-text icon contrast](https://www.w3.org/WAI/WCAG22/Techniques/general/G207) — icons at 3:1 when necessary to understand UI.
- [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion).
