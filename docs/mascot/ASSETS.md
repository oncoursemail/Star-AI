# Star mascot: image assets

Approved artwork for Star, the mascot of STAR Intelligence, in the form the website and the in-app Star pet load.
The character itself is specified in [CHARACTER.md](CHARACTER.md); this page lists the files, the canvas rules and what
is still pending replacement. The machine-readable list is [manifest.json](manifest.json) (file, group, source sheet and
cell, size, bytes, notes); `tests/test_mascot_assets.py` checks it against the files.

## Where the files are

| Folder | Used by | Contents |
| --- | --- | --- |
| `frontend/public/assets/mascot/` | the public website (`frontend/src/SiteMascot.tsx` loads `./assets/mascot/...`) | `star-hero.png`, `faces/<name>.png` (all 24), `poses/stand.png`, `poses/wave-a.png` |
| `frontend/public/mascot/` | the app's Star pet (`mascot/faces/<name>.png`, `mascot/poses/<name>.png`) | `faces/` (24), `poses/` (24), `forms/` (8), `star-hero-1024.png`, `pfp/` (3 profile pictures at 1024 px and 256 px) |

The 24 faces and the two poses the site uses exist in both folders (about 6.6 MB twice) because the two consumers use
different public paths.

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

**Hero**: `star-hero.png` (1086 x 1448, the unscaled approved illustration) and `star-hero-1024.png` (768 x 1024, longest
side 1024). **Profile pictures**: `pfp/star-pfp-normal|happy|content.png` (1024 x 1024, round, gold ring) and `-256.png`.

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
  width; poses use a scale of 1.3 (sheet 1) and 1.237 (sheet 2), forms 0.987. Heads therefore have the same size across
  poses and forms. Native sprites are only about 350 px tall, so the files are enlarged by roughly 1.0 to 1.3 x.

## Pending replacement

Listed as `"status": "to be replaced"` in the manifest; the files are usable until their replacements arrive.

| File | Reason |
| --- | --- |
| `poses/land.png` | hands on the knees have jagged, claw-like finger outlines |
| `poses/run-1.png` | three pigtails and three ribbons (should be two), rust-smudged boots |
| `poses/run-2.png` | three pigtails and three ribbons |

Smaller known flaws (visible only when enlarged) are recorded as notes in the manifest: puppy-eyes (clasped hands cut by the
source crop, now hidden by the bottom fade), love, ticked-off (near-black squiggle with almost no contrast on dark
backgrounds), stand, look-a, look-b, wave-a, wave-b (thin, pointed hands), crouch (unexplained pink shape), jump, walk-1.
A redraw of the full-body poses with the correct costume (a "fix sheet 3") is still to come; the first fix sheet's
full-body redraws use the cat / puppy boots and a striped skirt, so they were not adopted. The two face redraws on that
sheet (puppy-eyes, thinking) were also not adopted: they have a different expression (no tear, half-lidded eyes, no question
mark) and are full-body drawings in the other costume.

## Provenance

Star is an original character designed for this project. The art was generated for the project owner with ChatGPT image
generation from the project's own character brief on 2026-10-11, then cut out and cleaned with scripts kept in the
project (sheet cutting and edge clean-up; final canvas layout, fade and hero fringe removal). No third-party artwork was
copied. The scripts and the source sheets live in the project's work folder outside this repository; the assets here are
the finished output.
