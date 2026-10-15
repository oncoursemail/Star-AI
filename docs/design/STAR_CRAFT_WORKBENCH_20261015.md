# STAR Creator Workbench — design system acceptance, October 15, 2026

**Status:** real React/TypeScript UI changes on a draft branch, not a final owner-approved design. GitHub Actions produced an initial **actual 1440×900 browser-rendered chat screenshot** (workflow run 38800863881), which was manually inspected on October 15, 2026. **No Windows Qt inspection, phone-sized chat screenshot, or owner preference review has been performed.** Existing STAR behavior stays intact.

## Goal

STAR should feel like a purposeful creator application rather than a model demo generated from a prompt. No fake dashboards, randomly colored cards, decorative orbs, overloaded navs, inconsistent iconography, or misaligned typography. The system must earn attention: the task and current artifact matter more than the AI personality or its integrations.

Owner-established visual direction: near-OLED black, warm gold in a few meaningful places, clean type, thin strokes, measured spacing, original Star mascot, quiet motion, native/editable creation artifacts. Avoid huge gradients, glow, generic templates, synthetic testimonials, and screenshots of a pretend working application.

### Evidence informing these choices

- Microsoft Fluent 2 Layout: spacing conveys structure; regular spacing ramps, strong gutters and minimum mobile targets. https://fluent2.microsoft.design/layout
- Linear's March 12, 2026 product redesign: reduce competing visual weights, emphasize work over navigation, standardize headers/actions. https://linear.app/now/behind-the-latest-design-refresh
- STAR's own approved tokens and previous audits: docs/STAR_DESIGN_SYSTEM.md, frontend/src/tokens.css and docs/design/REDESIGN_20261013.md; preserve functionality already tested.
- Deque axe-core WCAG testing and Playwright screenshot comparison: https://www.deque.com/axe/ ; https://playwright.dev/docs/test-snapshots
- Existing draft #403 has an optional rendered UI geometry/axe audit. It does **not** decide subjective taste, and this PR does not alter its files.

## Diagnosed recurring causes of "AI-looking" output

1. **Information competition.** Generic home patterns give four chips, the title, an icon, the model, the picker and every tool equal priority. Instead, a large editorial sentence + one clear task list points to the next real action.
2. **Fake affordances.** Mock buttons or simulated revenue graphs make the app look sophisticated before it has capabilities. Starting points only fill the real composer and require the user's Send action.
3. **Template fingerprints.** Excessive gradient-glass cards, colored circular ornaments, capitalized eyebrow labels, monospace metadata, abundant micro-icons and centered feature tiles make every screen feel interchangeable. The workbench uses flat ruled rows, one restrained primary type hierarchy, genuine spacing and exactly one authentic mascot.
4. **Unexplained choices.** Four vague prompts are less useful than concrete, editable briefs demanding references, a requirement trace and actual checks. The new requests begin from deliverables, not a provider brand.
5. **No actual render review.** CSS/class tests are valuable regression checks but cannot judge proportion, clipping, optical alignment, emotional tone, or whether real art matches the owner's references.

## Implemented

- `frontend/src/StartCanvas.tsx`: a purposeful creator start canvas with actual project name, a one-sentence promise, the existing Star mascot, accessible buttons and four task-specific editable briefs.
- `frontend/src/start-canvas.css`: OLED token-based visual hierarchy, spacious typography, 2-column ruled task rows, genuine phone/small screen reflow, usable hit targets and reduced-motion support.
- `frontend/src/Desktop.tsx`: new canvas only on an empty chat; existing messages and composer, screenshot consent, backend requests, and all tools untouched.
- Side-by-side comparison flag: `?preview=1&home=classic` uses the old title/pills; `?preview=1` shows the proposed workbench. Both are **browser-preview fixtures only**; neither claims native QA.
- `frontend/src/StartCanvas.test.tsx`: honest button semantics, a current project, distinct editable briefs, and no automatic action on mount.

No Business/Etsy/Fiverr buttons were added to the UI; they would be fake, because #412 currently plans offers offline and has no connected seller accounts. Do not present revenue or orders in the application until sourced data exists.

## First actual screenshot review (browser preview, not Windows Desktop)

- Verified source: GitHub Actions `STAR-v08-React-Visual-QA` screenshot artifact from run https://github.com/oncoursemail/Star-AI/actions/runs/38800863881 , `chat-desktop.png`, **1440×900**. It renders the committed StartCanvas with the current STAR sidebar, real composer, mascot image and preview notice. These are not invented drawings.
- Observation: the primary title, two-column task rows, project indicator and brand hierarchy rendered legibly with no obvious overlap at this one resolution. The design still needs owner's *aesthetic* approval; the image is a baseline, not a stamp of quality.
- Measured visually: the task canvas's original left edge landed around x=492, while the composer inner text began around x=477. The follow-up CSS revision expands the canvas maximum from 704px to 736px to improve optical gutter alignment. The follow-up revision needs a fresh screenshot check.
- The existing Model & connection browser screenshot from the same run still uses largely generic stacked panels. This PR does not falsely claim to redesign every screen; future per-screen art direction needs the same evidence-based loop.
- No phone chat screenshot is included in this workflow's initial artifact (website-mobile.png is the *website*, not STAR chat). Obtain real 390px and 320px app-preview and native Qt captures before considering approval.

## Required visual sign-off — manual, using real rendered images

Run both flags in preview and capture **the same scene** at 1440x900, 900x700, 680x800, 390x844 and 320x568. Check the real Windows 11 packaged Qt WebEngine app separately at 100%, 125% and 150% DPI.

A reviewer must approve all of these:

- No horizontal overflow, clipped title, forced scrollbar over the greeting, overlapped mascot, disappearing composer, unreadable text or truncated workspace name without tooltip.
- Consistent left edges for the intro, task rows, message column and composer; optical alignment as well as box geometry.
- Every actual button shows appropriate hover/focus/pressed state, keyboard Tab/Enter/Space activation, at least 44px target area for primary mobile interactions, no unlabeled controls.
- The mascot art is the verified owner-approved asset, not a generated replacement or a blob at reduced size.
- Reduced-motion enabled: no movement; content remains understandable without animation, including keyboard and accessibility technology.
- Text/controls pass WCAG AA checks with actual computed browser colors; Windows high-contrast and screen reader labels work.
- STAR remains usable for empty, saved-thread, streaming, interrupted, long-message, image, tools, settings, error, and modal states. Preserve all previous tests.
- The owner compares A/B renders *blind* if practical and explains what still feels generic. Prefer owner feedback to an LLM scoring its own visual result.
- Run the independent visual audit in draft #403 after review/merge availability; investigate false positives rather than claiming the screenshot audit certifies good aesthetics.

**Do not merge this draft just because unit tests pass.** This is a substantial directional change, still subject to visual evidence and owner taste.

## Architecture research: A Taste-to-Proof loop, proposed not built

The potential frontier improvement is not one more "artist agent." It is a continuous reversible feedback circuit that connects a specific creator's taste, the exact rendered deliverable and validated real outcomes:

1. **Taste Contract.** Convert accepted/rejected references into a versioned brief: color roles, spacing rhythm, silhouette, text layout, icon proportions, repeated known defects, and subjective criteria. Keep negative constraints (e.g. no random glow, no overlapping labels), not just positive adjectives. Owner confirms the contract.
2. **Craft Tournament.** Several *independent* models or tool paths produce alternatives under the same budget. Don't select by which agent confidently says it looks good. Run lint, actual renderer snapshots, brand consistency and source rights checks; present a small meaningful shortlist to the owner.
3. **Reality Mirror.** In a **disposable** Studio place or a separate desktop preview, inspect behavior and screenshots across devices. For business assets also simulate listing image crops, source rights, print area and fees. Link findings to precise artifact versions, not unsupported self-reported success.
4. **Pre-mortem.** Infer likely failures from historical verified defect patterns, then propose a targeted test *before* the next build. The prediction is explicitly probabilistic; log prediction accuracy and false alarms. Never claim clairvoyance.
5. **Proof Ledger.** Store hashes, trusted external/tool receipts, failed checks, who approved the change, and what wasn't tested. Reviewer-controlled tests may not be edited by the generating agent.
6. **Outcome Learning.** After genuine user acceptance, actual customer orders, defect reports or independently reproduced tests, update project-scoped preferences/routing recipes. Do not train on scraped marketplace customer data, fake results or agent-generated self-praise.
7. **Rollback and resource awareness.** Cache only lawful, permissioned data. Regenerate selectively; parallelism is useful only if time to *verified correct* result improves. Preserve prior artifact and allow owner rollback.

**Originality caveat:** These elements draw from existing visual regression, preference learning, agent orchestration and verified evaluation literature. The specific integration could be a distinctive STAR research direction, but we cannot establish that no one has ever attempted it, or that it beats other systems without reproducible benchmark evidence.

### Why this is connected to the commerce goal

A creator-quality pipeline can deliver a lawful Etsy product draft and a tailored Fiverr gig package from one original style system, then independently assess print geometry, thumbnail layout, supplier cost, margin, rights, client conditions, and owner review. The same **taste and evidence** logic makes STAR's own interface better. Do not let STAR publish, charge, order fulfillment, message customers, claim revenue, or modify approval policy automatically.

Research on actual marketplace boundaries is in open draft #412. Programmatic Etsy drafts can eventually use scoped OAuth; Printify physical fulfillment incurs external cost and personalized orders require manual inspection; seller-account Fiverr API automation remains unsupported/unauthorized absent a verified platform path.

## Proposed criteria to decide whether this experiment helps

- `visual_defects_per_screen` from independently inspected screenshot tests, categorized by severity.
- `owner_accepted_first_pass / reviewed_proposals`, with the same task class, fixed prompt and comparable art references.
- `time_to_verified_correct_result` including retries and approvals, not raw tokens/second or arbitrary agent counts.
- `reopened_defect_rate` per accepted artifact revision, plus reviewer disagreement rate.
- `actual_contribution_per_order`, production defects, refund rates, revision hours and customer satisfaction from authorized records (never hypothetical numbers labeled as sales).
- Model/API/compute cost and sensitive data access by task, tracked in an auditable log.

Always show baselines and sample sizes. Do not claim superiority without experiments and user acceptance.
