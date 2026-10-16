# STAR professional desktop polish — October 15, 2026

This is an **actual React desktop UI change**, stacked on the existing editorial home draft PR #418, not another theme mood board.

## Design intent and why

The owner repeatedly rejected generic chat-clone interfaces, excessive cards, ornaments, neon outlines, sloppy alignment and unconvincing AI-generated aesthetics. The UI should feel like a carefully built **creative development workbench**, with STAR's unique character and warm gold identity, not a model-provider dashboard.

Principles applied:
- **One clear visual reading order:** active project → deliberate first action → editable message → verified output.
- **Content over chrome:** the left rail recedes, the project list becomes an actual compact directory, tabs and breadcrumbs are understated; no pointless telemetry.
- **A purpose for every color:** neutral OLED layers carry structure; warm gold is kept for the mascot, selected state, keyboard focus, and the main action.
- **Native software, not an illustration:** all elements remain real React controls, responsive CSS, readable labels, keyboard/focus semantics and original STAR state transitions.
- **No decorative circles, AI gradient halos, extra logos, fake stats, empty scorecards, magical promises or new libraries.**

## Implemented source changes

- \`StartCanvas.tsx\` / \`start-canvas.css\`: the inherited four-card prompt grid becomes a lean, vertically ruled creative workflow menu. A project crumb, intentional typography, and a restrained matte mascot portrait establish identity. Buttons prepare an editable brief only. Responsive 320–1440 px in CSS, with reduced-motion overrides.
- \`Desktop.tsx\`: two-line STAR Intelligence sidebar wordmark, accessible current-workspace state, and product-specific confirmation copy after generated answers.
- \`stellar-ui.css\`: clearer hierarchy, consistent 36px navigation rhythm, active selection as a thin 2px line (not another colored rectangle), focused New Chat affordance, stable top-bar divider, larger but restrained page headings, and compact workspace directory rows in place of blocky cards.
- \`chat.css\` / \`redesign.css\`: calmer message spacing, flatter matte composer, more deliberate 12px corners, clear send target and warm accessible focus. No auto-actions, flow changes or decorative UI dependency.
- \`tokens.css\`: a real focus token aligned with the muted STAR gold; no palette hardcoding in page components.
- \`settings-page.css\`: shared active-nav language and a cleaner panel heading; narrow horizontal tabs never inherit a vertical selection marker.
- \`professional-workbench.test.tsx\`: verifies true DOM navigation, current project, draft-only workbench actions, and preserved advanced-page access. Tests are **not** an aesthetic rating.

## Screens to review BEFORE any main merge / release

Real browser preview:
1. \`?preview=1&tab=chat\` 1440×900 and 1050×680, empty workbench and composer.
2. \`?preview=1&tab=chat&fixture=chat\` at both sizes, long response and active thread.
3. \`?preview=1&tab=projects\` at 1440×900 and 390×844, a long project name and keyboard focus.
4. \`?preview=1&tab=settings\` at 1050×680 and 390×844, search, open settings tabs and sticky save.
5. \`?preview=1&tab=tools\` and \`?preview=1&tab=brain\`, connected/offline/error cases as available.
6. 320px, 390px, 768px and 1440px widths: no horizontal scrolling, hidden actions, text/icon collisions, overlapping focus or clipped mascot. Long multiline messages and code blocks must remain readable.

A browser preview is not a native Windows Qt screenshot. Review the actual packaged Windows app at 100%, 125% and 150% DPI and keyboard-only navigation. Verify reduced motion, device focus, dark-mode color contrast and type rendering using Windows native fonts. Treat web screenshots as reliable evidence of that *browser* render, not of Qt/Studio.

## Acceptance contract

The owner's judgment governs aesthetics. Ask for specific visual feedback on the **actual screenshots**. If rejected, note the exact component, difference from intended art direction and correction needed. Continue editing and recapturing until approved. The separate draft creative-review ledger PR #415 is not yet wired into release CI and must not be cited as a working release block.

## Source references

- Linear's March 2026 design refresh: https://linear.app/now/behind-the-latest-design-refresh
- Raycast native desktop design engineering: https://www.raycast.com/blog/a-technical-deep-dive-into-the-new-raycast
- Windows 11 design: https://learn.microsoft.com/en-us/windows/apps/design/design-principles
- Fluent 2 layout and motion: https://fluent2.microsoft.design/layout and https://fluent2.microsoft.design/motion
- Roblox native UI style editor: https://create.roblox.com/docs/ui/styling/editor
- Original related drafts: #418 (foundation), #403 (optional visual audit), #415 (owner rejection ledger).

**Status**: reviewable implementation; NOT yet visually approved by the owner. No commerce, AI model, permissions or payment connection changes.
