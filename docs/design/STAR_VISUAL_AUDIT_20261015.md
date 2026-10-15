# STAR Visual Quality Audit — 2026-10-15

**Status:** a new, optional, read-only browser-preview audit and deterministic unit tests. **No actual desktop/Studio screenshot was captured by this pull request.** This is not a trained aesthetic judge and not a production-release gate by default.

## Why

STAR already has a design-token system, WCAG-oriented component checks and saved preview screenshots. The jsdom tests do **not** compute layout geometry, pixels or real device rendering. This manual pilot measures what a browser actually lays out and captures unmodified screenshots across three viewports, while the existing Qt WebEngine/Roblox Studio workflows still require human and native acceptance.

## Run on a development PC

1. In `frontend/`, run `npm ci` and `npm run build`.
2. Use an existing, reviewed install of `playwright-core` in a separate tools folder (the existing website screenshot workflow uses the same approach). Provide Edge or Chrome.
3. Run `npm run audit:visual -- --tools path/to/tools --channel msedge`.
4. It serves **only** the built preview in `frontend/dist` on a random loopback port, with no real Qt bridge, chats, model, GitHub credentials or Studio session.
5. Open the printed temporary output directory: `report.json` plus unmodified PNG captures for chat/tools at 1280×800, 900×700 and 390×844.
6. For an explicit automated hard-fail on high-severity geometry results, any measured axe violation or truncated DOM controls, add `--strict`. Do **not** enable it in CI without first reviewing baseline false positives and fixtures.

No package installation or downloads occur at runtime; missing `playwright-core`, compiled site or a browser produces a visible error. Capture is deliberately manual so unrelated CI doesn't become coupled to browser machine state.

## What the checks measure

- A rendered document wider than its viewport, excluding a 3 px tolerance.
- Interactive hit-box overlap (40% of the smaller area, minimum 70 px²).
- Visible buttons without accessible names (also run `axe-core` separately).
- Interactive targets below a 24 px technical floor; 44 px is preferable for many touch designs.
- Control text-clipping indicators where deliberate ellipsis/scroll is not configured.
- In the actual browser, uses the already-installed axe-core package to test rendered color contrast and button/link accessible names; each violation records bounded CSS targets. No new dependencies or downloads.

Errors and warnings reference specific `control-<index>` IDs from the **same captured DOM snapshot**. They are heuristics, not independent proof. A scrollable clipped item or intentional overlay can still produce a false positive. PNG screenshots are required for human review, art direction and deciding whether visual hierarchy, proportionality, type rhythm or subtle animations match the approved concept.

## Acceptance before deployment

- `npm test`, `npm run build`, `npm run typecheck` green.
- QA on a clean Windows 11 build, actual Qt WebEngine shell and browser-preview at desktop/phone widths; raw screenshots for real app and browser. No invented screenshots.
- Manual Playwright session with a reviewed external browser executable. No remote URLs, profiles, accounts or login flows.
- Check small/touch inputs, keyboard/gamepad focus, high DPI and reduced-motion animations; axe results; never flatten editable UI to an image.
- Separately test native Roblox UI in an unpublished disposable Studio place with native GuiObjects, mobile and PC playtest captures, proper hierarchy and actual interaction evidence.
- Compare full issue counts, reviewer-approved screenshots and unexpected clipping/overlap against baseline for 30 representative screens. Zero claimed quality gains until independently observed.

## Implementation

- `frontend/scripts/visual-contract.mjs`: pure offline geometry evaluator; no browser, network, file writes or runtime privileges.
- `frontend/scripts/visual-contract.test.mjs`: fixed, reproducible positive/negative fixtures (not a benchmark of aesthetics).
- `frontend/scripts/visual-audit.mjs`: local-browser-only script, screenshot and JSON report generator.
- `frontend/package.json`: manually callable `npm run audit:visual`.

This pilot is part of the broader `docs/research/STAR_FRONTIER_INTEGRATION_20261015.md` plan in **a separate draft PR**. Review both branches independently to avoid concurrent edits to the same frontend.
