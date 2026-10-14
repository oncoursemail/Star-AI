# Star mascot: image assets

Approved artwork for Star, the mascot of STAR Intelligence, in the form the website and the in-app Star pet load.
The character itself is specified in [CHARACTER.md](CHARACTER.md); this page lists the files, the canvas rules and which
drawings were replaced by the third redraw sheet. The machine-readable list is [manifest.json](manifest.json) (file, group, source sheet and
cell, size, bytes, notes, and the folder it is in); `tests/test_mascot_assets.py` checks it against the files.

## Approval

The owner has seen and approved this artwork (2026-10-11). Nothing in it was re-compressed or redrawn when it was
reorganised on 2026-10-12; the files are byte-for-byte the approved ones.

## Where the files are

There is exactly one copy of every image, and only what the code loads is shipped.

| Folder | In the app and installer? | Contents |
| --- | --- | --- |
| `frontend/public/assets/mascot/` | yes (copied into `frontend/dist/assets/mascot/`; about 5.7 MB) | `star-hero.png`; 11 faces `asleep`, `content`, `focused`, `happy`, `nervous`, `normal`, `proud`, `puppy-eyes`, `sleepy`, `surprised`, `thinking`; 7 poses `letter`, `sleep-sit`, `stand`, `think`, `type-1`, `type-2`, `wave-a` |
| `docs/mascot/art/` | no (documentation only; about 11.7 MB) | the other 13 faces, the other 17 poses, `forms/` (8), `pfp/` (3 profile pictures at 1024 px and 256 px), `star-hero-1024.png` |

Both consumers load from the shipped folder with a relative path, because the packaged app is opened as a local file:

- the public website, `frontend/src/SiteMascot.tsx`: `./assets/mascot/star-hero.png`, the eight faces of "Meet Star" (`normal`, `happy`,
  `content`, `puppy-eyes`, `surprised`, `thinking`, `focused`, `proud`; `content` is also the hero blink) and the poses `stand` and `wave-a`;
- the Star pet in the chat, `frontend/src/StarPet.tsx`: faces `normal`, `content` (idle), `focused` (typing and streaming),
  `thinking`, `happy`, `nervous`, `surprised`, `sleepy`, `asleep` and poses `think`, `type-1`, `type-2`, `wave-a`, `sleep-sit`, `letter`
  under the same `./assets/mascot/` prefix. The pet is off until the owner turns on "Show Star" in Settings and respects reduced motion.

Before 2026-10-12 the 24 faces and 2 poses were stored twice (`frontend/public/mascot/` and `frontend/public/assets/mascot/`) and about
16 MB (forms, profile pictures, unused poses and faces) was copied into the app although nothing loaded it, about 24 MB in all. To
use another drawing in the app, move it from `docs/mascot/art/` to the same relative place under `frontend/public/assets/mascot/`, load it
from code, and update `manifest.json` (`"in": ["site"]`); `tests/test_mascot_assets.py` fails when the shipped folder and the code disagree
or when an image is stored twice.

Exact files the site expects (all present): `star-hero.png`; faces `normal`, `content` (hero blink), `happy`,
`puppy-eyes`, `surprised`, `thinking`, `focused`, `proud`; poses `stand`, `wave-a`. Nothing had to be mapped or invented.

## The drawings

**Faces (24, 512 x 512)**: normal, happy, content, puppy-eyes, love, surprised, nervous, very-embarrassed, scared,
crying, very-angry, ticked-off (sheet 1) and smug, gloating, dizzy, squeeze, hungry, sleepy, asleep, thinking, focused,
proud, flustered, panic (sheet 2).

**Poses (24, 512 x 640)**: stand, breathe-out, blink, look-a, look-b, wave-a, wave-b, crouch, jump, land, think, point,
walk-1, walk-2, walk-3, walk-4, run-1, run-2, type-1, type-2, sleep-sit, sleep-lie, letter, sad.

**Forms (8, 512 x 640)**: cat-paw, cat-curious, cat-stretch, cat-startled, puppy-beg, puppy-happy, puppy-puzzled,
puppy-sleepy.

**Hero**: `star-hero.png` (1086 x 1448, the unscaled approved illustration; shipped) and `star-hero-1024.png` (768 x 1024, longest
side 1024; in `docs/mascot/art/`). **Profile pictures** (in `docs/mascot/art/pfp/`): `star-pfp-normal|happy|content.png` (1024 x 1024, round, gold ring) and `-256.png`.

## Canvas rules

All files are 8-bit RGBA PNG with no metadata, transparent background, and none is larger than 1.5 MB.

- **Faces**: 512 x 512. Every face is a bust crop. Heads are aligned by the hair silhouette (top of the dark hair mass and
  the centre of its width), not by the whole drawing, so hearts, sweat drops, sparkles, hands and the fork and knife do not
  move the head. Heads have the same apparent size in all 24 (measured hair width within 1.5 % before scaling; one scale
  factor of 1.3 for all). The hard flat cut through the torso in the source art is replaced by a smooth fade to
  transparent over the last 10 % of the figure. No drawn pixel is closer than 6 px to the canvas edge.
- **Poses and forms**: 512 x 640. The lowest drawn pixel of every file sits on y = 600 (standing, walking, sitting, lying
  and jumping drawings alike, so a "jump" needs a vertical offset from the pet code), and the drawing is centred
  horizontally by its bounding box (`head_center_x` in the manifest gives the head's x for animation code that wants to
  keep the head steady across frames, for example the four walk frames). The three source sheets were drawn at different
  scales (the cat / puppy sheet about 1.3 x larger), so each sheet has its own factor derived from the measured hair
  width; poses use a scale of 1.3 (sheet 1) and 1.237 (sheet 2), forms 0.987, and the four poses taken from the third
  redraw sheet 1.088 (its drawings are natively about 1.2 x larger; the factor also carries a 2 % calibration so that the
  hair-top-to-chin height of the upright poses matches the other sheets). Heads therefore have the same size across poses
  and forms. Native sprites are only about 350 px tall, so the files are enlarged by roughly 1.0 to 1.3 x.

## Fix sheet 3 (2026-10-12): what was replaced and what was kept

Nothing is pending replacement any more (`"to_be_replaced": []` in the manifest; `"poses_from_fix_sheet_3"` lists the four
new files). A third redraw sheet (8 full-body drawings in the pose-sheet costume, with rounded hands) was checked against
the drawings it could replace, at the final size on a dark (#1b2a4a) and a light (#e9e9ee) background and enlarged around
the hands. Only drawings that were at least as good in every respect were taken.

| Pose | Result | Reason |
| --- | --- | --- |
| `land` | replaced | the knee hands had jagged, claw-like finger outlines; the new ones are rounded fists with soft finger scallops |
| `run-1` | replaced | the old drawing had three pigtails and three ribbons and rust-smudged boots; the new one has two tails, clean fists and star boots |
| `run-2` | replaced | the old drawing had three pigtails and three ribbons; the new one has two tails and clean fists |
| `point` | replaced | pointing hand and the hand on the hip are both drawn and crisp (the old drawing hid the second hand) |
| `wave-a`, `wave-b` | kept | the new wave drawing has a soft grey smudge beside the thumb of the raised hand |
| `jump` | kept | the new drawing's raised hands have soft, feathered outer edges; the old ones are crisp |
| `think` | kept | no clear gain: small gold specks on the sleeve, the dress star half hidden by the arm |
| (new "cheer", arms out) | not added | it has no counterpart in the 24 poses and its raised hand has the same soft edge |

All four new files use the same canvas rules as the others (512 x 640, lowest pixel on y = 600). One difference to know
about: in the fix-sheet drawings the lace under the gold skirt frill reads tan instead of white, which is only visible
when enlarged. The thin red fringe on the hair edges of the source sheet was
invisible haze (alpha 1 to 7) and is cleared in the pipeline; no red or white rim remains on either background.

Smaller known flaws (visible only when enlarged) are recorded as notes in the manifest: puppy-eyes (clasped hands cut by the
source crop, now hidden by the bottom fade), love, ticked-off (near-black squiggle with almost no contrast on dark
backgrounds), stand, look-a, look-b, wave-a, wave-b (thin, pointed hands), crouch (unexplained pink shape), jump, walk-1.
The first fix sheet's full-body redraws use the cat / puppy boots and a striped skirt, so they were not adopted. The two
face redraws on that sheet (puppy-eyes, thinking) were also not adopted: they have a different expression (no tear,
half-lidded eyes, no question mark) and are full-body drawings in the other costume.

## Provenance

Star is an original character designed for this project. The art was generated for the project owner with ChatGPT image
generation from the project's own character brief on 2026-10-11, then cut out and cleaned with scripts kept in the
project (sheet cutting and edge clean-up; final canvas layout, fade and hero fringe removal). No third-party artwork was
copied. The scripts and the source sheets live in the project's work folder outside this repository; the assets here are
the finished output.
