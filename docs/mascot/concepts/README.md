# Star mascot — concept art directions

Status: exploratory concept comparison; selection pending. Two visual comparison boards were generated in the design conversation. The raster images are visible in that conversation but **are not committed** by this pull request.

## Fixed visual identity
- Wholesome, clearly chibi proportions (head approximately half total height); never sexualized or revealing.
- Very dark indigo-black hair, **two low twin tails** with gold-faded tips and gold ties.
- Large **four-point gold star clip on Star's own right** (left when viewing her head-on).
- Amber-gold eyes, soft blush, black dress with gold trim, gold bow and small gold star emblem, dark boots.
- Thin cream silhouette rim for readable contrast on dark and light backgrounds.
- Original art, not a copy of any existing character or artist sheet.

## Design A — soft and round
Soft cheek arcs, wide forehead, nearly circular eye construction, rounded skirt hem, compact rounded boots. Warm and welcoming with a simple silhouette. **32 px:** good if simplified to head + star clip + two distinct tails; **96 px:** excellent with bow, hair gradient and facial expression visible.

## Design B — sharp and stylish
More tapered hair tufts, slightly angular eyes, crisply structured dress/coat silhouette and controlled asymmetry. Fits the desktop OLED black/gold UI particularly well. **32 px:** good with a specially simplified head icon, though wispy angles and trim will disappear; **96 px:** excellent. Recommended for the primary desktop mascot because it carries distinctive silhouette and expression while looking polished.

## Design C — plush and toy-like
Oversized head, stubby legs, rounded mitt-like hands, wide-spaced large eyes, and puffy fabric-like skirt. Ideal for stickers or plush merchandising. **32 px:** excellent as a custom head icon; **96 px:** excellent. Full-body compact leg/boot detail is less legible at 32 px.

## Expression contract (all three variants)
Normal, happy, puppy eyes, love, angry, crying, smug, dizzy. Every expression should keep the same signature star clip, eye hue, twin tails and gold-faded tips.

## Production checkpoints
1. Choose one direction before tracing or rigging. Preserve the exact four-point clip shape and consistent placement across poses.
2. Redraw front, three-quarter and back orthographically so they share outfit, seam placement, and actual hair-tie locations.
3. Produce clean transparent-background layered vector art, plus true pixel-size exports at 32 and 96 px. Do not assume a downscaled full-body art sheet is readable.
4. Check head silhouette and eyes on OLED black and white. Keep cream rim subtle, consistent and continuous.
5. QA the eight faces manually, including differentiation of puppy-eyes vs crying, and dizzy vs smug.
6. Verify pose/expression continuity and chibi head-to-body ratio before using in the app.

## Important limitations
Generated concept sheets are mood/shape exploration rather than definitive model sheets: details can drift between views. The 32/96 px judgments above are design estimates, **not measured raster tests**. Raster artwork must be attached separately to `docs/mascot/concepts/` for a production-ready asset PR.
