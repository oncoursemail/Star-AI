# STAR AETHER — design-quality and commerce research blueprint
Status: proposed; no claim that UI or Etsy/Fiverr integrations are implemented.
Date: 2026-10-15
Base: star/next

## Evidence from the repository
- Current desktop is React/TypeScript in Qt WebEngine. Desktop.tsx imports tokens.css, stellar-ui.css, chat.css, learning.css, redesign.css, resilience.css, polish.css. This layered styling must be audited for specificity/cascade drift before any design refresh.
- Existing Motion, screenshot-preview and reduced-motion functionality should be retained and improved, not discarded.
- Do not overwrite user settings, chats, models, or signed-in accounts.

## Product direction: AETHER / STAR Atelier
STAR should look like a premium creative workstation, not a generic AI chat clone.
Art direction: architectural/editorial precision; OLED black surfaces, warm porcelain text, sophisticated graphite layers, sparse champagne metallic accent, matte steel secondary details. Gold is NOT a universal button/background color.
Candidate colors (validate with contrast checker):
- Canvas #08090C
- Elevated #171A22
- Divider #303644
- Text #F1EDE5
- Accent #D7AC70
- Secondary #77889F
These are hypotheses, not shipped tokens.
Type roles: UI body 13-14px; working data 12-13px; section headings 17-24px; larger hero text only where appropriate. Distinct variable font for headings optional after license/performance review; preserve legibility at 100-150% Windows scaling.
Layout: responsive 3-zone desktop (compact navigation, large primary work surface, contextual inspector). Use content-specific panels rather than repeated cards. Respect 1280x720, 1440x900, 1920x1080, 125-200% scaling.
Design references to STUDY, not copy: Linear (information hierarchy), Raycast (command speed), professional creative apps (tool/inspector spatial logic), Microsoft Fluent Windows conventions, high-end editorial product identity.

## Anti-generic design process
1. Build screenshot inventory of EVERY existing tab (including loading, empty, populated, error, disconnected, long-copy, busy, modal).
2. Expert critique: rank visual hierarchy, typography, contrast, spacing, composition, repeated/card patterns, originality, discoverability.
3. Create THREE materially different Figma directions, not three recolors. Require user approval of one direction before replacing the production shell.
4. Make one canonical token system and one CSS cascade layer ordering. Delete/retire overrides only after screenshot-diff equivalence review.
5. Assemble reusable foundations: window shell, navigation rail, work surface, inspector, command palette, split view, activity timeline, notification, dialog, composer.
6. Build real-content prototypes with short/long labels, 10/100 chats, multiple agents, unavailable local model, product preview, file artwork.
7. Visual acceptance: reference screenshots at three viewport sizes and at 100/125/150/200% scale; no text truncation without tooltip, no overlap, no clipped icon, no contrast failure.
8. Human design review remains required for aesthetic judgment. Never claim automated scores prove beauty or uniqueness.
9. Add Playwright screenshot baseline and changed-region checks, axe-core accessibility, keyboard-focus and tab-order tests, and a manual Windows Qt WebEngine check.
10. Protect perf: avoid continuous blur/filter/box-shadow animation, prefer transform/opacity, profile long lists and streaming, honor OS reduced motion.

## Motion language
- Navigation selection: shared indicator 160-240ms, ease-out (not spring bounce by default).
- Inspector open/close: responsive transform and opacity, 220-320ms.
- Work-surface context switch: staggered spatial hierarchy 260-420ms, no full-screen fade on routine tab switch.
- Agent activity: purposeful progress indicators, live phases and accessible text. No misleading percent complete.
- STAR mascot: optional, disabled by default; only finalized on-brand art; no auto-moving overlay atop controls.
- Distinguish success, error, cancel, and verification states, never animate an outcome before it is confirmed.
- Respect prefers-reduced-motion and explicit app setting.

## Commerce studio: Etsy and Fiverr
Goal: human-accountable creative production, not guaranteed or unattended income.
Etsy:
- Official Open API v3 offers OAuth, shop/listings/orders/inventory operations; use Seller App for a user's own shop; wider multi-shop applications need appropriate developer access.
- For digital listings: prepare seller-designed artwork, print/test export, mockup, metadata and disclosure; create draft listing via API, uploadListingFile, keep publish approval/manual gate.
- Etsy Creativity Standards permit qualifying seller-prompted AI works with disclosure, but not AI prompt bundles or other people's work.
- Never use scraping/credential automation to bypass API or platform restrictions.
Fiverr:
- AI use is allowed when final deliverables are original, meaningfully customized and seller-accountable. Do not deliver generic unmodified outputs or misrepresent the workflow.
- Avoid bot account access or unsolicited automated messaging absent written authorization and compliant official integration.
- Build customer brief parsing, proposal draft, quote estimate, design variants, quality checks, human sign-off and delivery packaging. Seller must handle contract changes and client communication where necessary.

## Workflows
A. Discover (public data and user-provided sources; rights-respecting) -> opportunity brief -> feasibility/cost check.
B. Create -> validate rights/license/provenance -> render -> print/accessibility/functional QA -> compare to brief.
C. Approval -> Etsy draft upload OR Fiverr manual submission package.
D. Fulfillment monitoring when supported and authorized -> revise -> customer support -> store outcome metrics.
E. Retrospective -> verified improvement examples -> retrieval dataset. Never claim model weights learned automatically.

Candidate products/services: truly original game UI kits/Roblox creator assets; custom game icon/thumbnail packages; printable customizable planning templates; polished brand identity deliverables; game environment concepts. For Etsy, verify fit with Creativity Standards before listing any game-related digital files.
Track: human hours, compute/tool spend, platform fees, refund rate, net profit, satisfaction, revision count, policy errors and originality.
Do NOT promise revenue, use fake reviews, mass-spam listings or use unlicensed IP.

## Proposed distinctive research concept: Outcome Provenance Graph (OPG)
Claim is a proposed composition, NOT asserted never-before-seen novelty.
Record for every artifact: user brief -> competing design hypotheses -> source rights -> tool/model decisions -> previews -> objective tests -> human critiques -> approved deliverable -> marketplace outcomes.
Use the graph to retrieve proven work patterns and reject repeating failures. Allow safe multi-agent collaboration under explicit permission scopes. Prevent erroneous self-improvement by keeping human judgments distinct from automatic outcomes.
Run a 'preflight critic' before any publish: trademark/license, disclosure, required files, legibility/contrast, layout geometry, functional tests, estimate uncertainty, customer-specific customization. Approval gate for any monetary transaction, paid action, upload/publish or external message.
This is potentially differentiating only if empirically proven against simpler baselines.

## Milestones and acceptance
M0: full audit and three design directions with real content and user's design selection (NO silent redesign).
M1: one canonical token system, chat + navigation + inspector polished, visual QA run.
M2: remaining pages migrated and verified in live Windows host, mascot integrated tastefully.
M3: read-only commerce research/idea evaluation and cost dashboard; no marketplace credentials yet.
M4: Etsy Seller App OAuth and draft-listing flow (opt-in), seller approval and policy tests.
M5: Fiverr proposal/production assistant with manual compliant submission, accurate status.
M6: OPG/predictive QA experiments with ablation/evaluations and privacy/security audit.
Each stage requires passing tests, screenshots, performance checks, real owner sign-off. Never describe roadmap as shipped.

## References (verified 2026-10-15)
- https://developer.etsy.com/documentation/
- https://developer.etsy.com/documentation/tutorials/listings/
- https://www.etsy.com/legal/creativity/
- https://help.fiverr.com/hc/en-us/articles/37554976380177-Using-AI-on-Fiverr-Guidelines-for-freelancers-and-clients
- https://help.fiverr.com/hc/en-us/articles/37554441398929-Our-Community-Standards
- https://motion.dev/docs/react-layout-animations
- https://motion.dev/docs/react-accessibility
