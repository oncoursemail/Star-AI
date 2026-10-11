# Star layered vector rig

This directory contains the original STAR Intelligence mascot, a 512 × 640 SVG chibi design in indigo-black, cream and amber-gold.

## Files
- `star-rig.svg`: Qt-friendly SVG with gradients, literal styling, individually addressable element IDs and data-pivot coordinates.
- `expressions.json`: maps exactly 24 names to distinct eyes, brow and mouth groups, blush intensity and optional FX layers.
- `demo.html`: offline, self-contained expression grid with inline SVG artwork and transform-only blink/breathing animation.

## Rendering contract
The root viewBox is `0 0 512 640`. Preserve IDs and `data-pivot="x,y"` on all top-level movable groups. The component order is intentionally painter's order: shadow, rear hair, tails, legs, body, arms, head. Inside head: ear hint, face-base (including all expression variants), front hair, star clip. Only `normal` eyes, brows and mouth plus `blush-1` are shown initially.

To select an expression, hide all eye/brow/mouth/blush/fx IDs and show the IDs from `expressions.json`. Show one eyes, brows, mouth, blush variant plus 0–1 FX groups. Qt can render any group individually by element ID and use a separate transform anchored at the supplied pivot; the base SVG has no CSS, scripts, filters, masks, images or external references.

The HTML preview uses duplicated inline SVGs. Browser duplicates of SVG IDs should not be exported back as one merged SVG; each SVG is a separate image. Gradient references are local to each image. Embedded CSS and scripting occur only in the HTML demo, not in the SVG artwork.

## Rig animation
Apply gentle breathing to the body around (256,413), a small opposite vertical movement to head, rotate arms/tails a few degrees around their data-pivot, and occasionally blink by vertically compressing the eye group around (256,288). Do not mutate the source path geometry for expression switching.

## Asset and accessibility policy
This is wholly original all-ages chibi vector art. Keep hair dark indigo-black, twin-tail tips gold, the four-point clip and black-gold dress. Give displayed images meaningful alternative text. Test 96px-high thumbnails on both OLED black and white.
