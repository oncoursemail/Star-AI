# STAR owner-bound creative acceptance — initial implementation (2026-10-15)

## Why this exists

The owner's explicit criticism is that STAR's desktop and generated Roblox interfaces too often look generic or rushed even when code compiles. Asking another LLM to grade its own UI or changing color values does not solve this. **An AI's statement that a design looks polished is not independent evidence of quality.** The owner's approval and explicit rejection are authoritative for the project.

Current baseline: the React frontend already has OLED/gold tokens, accessibility tests, fixtures, design research, and screenshots uploaded by CI. STAR also remembers some owner corrections. What has NOT been demonstrated is a blocking visual baseline approved by the owner, enforced for release.

## Changes in this draft PR

- An offline quality evidence module at star/creative_review.py.
- Validates actual, local PNG screenshots at declared pixel dimensions and source files, with size limits and SHA-256 hashes.
- Optionally compares pixel drift against a local baseline screenshot; identical pixels are never described as proof of good taste.
- A local SQLite review ledger stores approve/reject decisions against the exact source/screenshot evidence. Every changed candidate returns awaiting_owner_review until separately approved.
- Rejection requires a concrete feedback reason. Prior rejection feedback remains visible when a new version is inspected.
- An owner CLI review requires an interactive terminal and exact confirmation. Do not expose the review-write function as an LLM tool. SQLite and a terminal check are not tamper-resistant security boundaries.
- 10 targeted tests cover changed source, changed pictures, rejected designs, stale approval, malformed files, path escapes, symlinks and noninteractive review refusal.

This is a tested **foundation**, not yet a UI redesign, a release-blocking CI job, an authenticated desktop approval button, or proof that the owner's desired design has been achieved.

## Example evidence manifest

Paths are examples only; the real application screenshots must be captured separately before use. Save as creative-review.json inside the selected workspace:

~~~json
{
  "project": "STAR",
  "artifact": "desktop-chat",
  "source": "frontend/src/Desktop.tsx",
  "views": {
    "desktop": {"file": "review/chat-1440.png", "width": 1440, "height": 900},
    "compact": {"file": "review/chat-1050.png", "width": 1050, "height": 680}
  },
  "baselines": {
    "desktop": "review/approved-chat-1440.png"
  }
}
~~~

From the repo root:

~~~bash
python -m star.creative_review inspect creative-review.json --workspace .
python -m star.creative_review review creative-review.json --workspace . --decision reject --feedback "Hierarchy is flat and labels collide."
# Only after manually inspecting the actual screenshots:
python -m star.creative_review review creative-review.json --workspace . --decision approve --feedback "Approved this exact render."
~~~

Windows ledger defaults to %APPDATA%/STAR/creative_reviews.sqlite3; Unix-like systems to ~/.local/state/STAR/creative_reviews.sqlite3. Screenshot files are not stored in the ledger.

## Required design method after integration

1. Brief: define screen purpose, owner-approved references, forbidden visual patterns, density, type hierarchy, actual tasks and supported devices. User corrections become requirements, not suggestions.
2. Explore two genuinely different structures before implementing everything. Don't produce five permutations of generic cards and glowing gradients.
3. Build editable React or native Roblox Studio components, not a screenshot pretending to be functioning software.
4. Capture real runtime UI states at desktop and narrow-window dimensions. Include menus, long text, errors, disconnected state, and keyboard focus; measure the actual Windows Qt UI separately. Test desktop scaling at 100%, 125%, 150% and Studio touch/gamepad.
5. Run functional, accessibility, responsive, performance and source checks independently. When present, compare the pixel change against an approved, locked screenshot baseline.
6. Let the owner approve or reject the exact candidate and record the objection. Rework/retest any rejection. **Do not ship an unreviewed changed candidate.**

### Intentional STAR art direction

A focused creative workbench with a serious native application feel: calm near-black OLED canvas, premium warm gold used sparingly, thin neutral borders, readable typography, keyboard-visible focus and meaningful motion. Chat and project creation lead. Advanced model routing, metrics and diagnostics should not fight for attention. The mascot is a recognizable brand signature with stable identity and reduced-motion options, not random floating ornaments. No text/icon collisions, inconsistent radii, ornamental circles, neon halos, fake charts, cluttered cards, unnecessary eyebrow labels or text over pictures.

Roblox artifacts have extra requirements: real R6/R15 rigs when applicable, full asset alignment, native ScreenGui and Luau, Studio tests, correct responsive UI for touch/gamepad/keyboard, actual playback and live captures, measured VFX/performance. Art-direction and playability remain separate reviews.

## Deliberately NOT completed by this PR

- Trusted desktop visual review UI, presenting side-by-side screenshots and rejecting changed builds by default.
- Protected, owner-approved visual baselines and Playwright screenshot comparisons that block CI/release. Current screenshots are uploaded but not yet acceptance gates.
- Automatic Studio/Blender capture pipeline wired into this owner review.
- A release evaluation suite measuring repeated owner's accept/reject outcomes, functional task completion and regression rates.

No new credentials, internet use, background autonomy, external commerce, file overwrites outside the selected workspace, publication or model-tool permission changes are introduced.

## Technical research

- Linear's March 2026 redesign process: https://linear.app/now/behind-the-latest-design-refresh
- Linear's UI overhaul: https://linear.app/now/how-we-redesigned-the-linear-ui
- Fluent 2 layout: https://fluent2.microsoft.design/layout
- Playwright screenshot assertions: https://playwright.dev/docs/api/class-pageassertions#page-assertions-to-have-screenshot
- Radix accessibility primitives: https://www.radix-ui.com/primitives/docs/overview/accessibility
- Roblox adaptive design: https://create.roblox.com/docs/production/publishing/adaptive-design
