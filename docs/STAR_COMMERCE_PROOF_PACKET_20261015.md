# STAR Commerce: ProofPacket, multichannel research and quality-first automation

**October 15, 2026. Scope:** second, complementary foundation to **draft #412** (offline Etsy/Fiverr offer planning and image preflight), and **draft #418** (premium React workbench UI). This document does not claim that accounts are connected or orders/sales have occurred.

## Why this feature exists

A product is not complete when an AI produces a PNG. For an Etsy digital product or Fiverr gig, the work must arrive as a correct, uniquely identifiable, honest delivery package with useful source files and a clear review gate. STAR can reduce repetitive *production* effort without pretending to make sales or taking unauthorized account actions.

**ProofPacket** is an opt-in local ZIP maker with a machine-readable manifest and content hashes. It contains only explicitly selected files from an authorized workspace and a clear "not approved" notice. It never sends a message, uploads anything, places an order, buys credits, scrapes a marketplace or certifies aesthetics/licensing.

### Usage

Make a project directory, for example:

```text
creator-assets/
  artwork/preview.png
  editable/design.blend
  docs/usage.md
```

Create a local specification, `packet-spec.json` (you must replace these example names with files you actually own):

```json
{
  "channel": "fiverr",
  "brief": "An original, customized Roblox interface layout for an authorized client.",
  "files": [
    "artwork/preview.png",
    "editable/design.blend",
    "docs/usage.md"
  ]
}
```

Run from the repository root:

```powershell
python -m star.delivery_package --workspace ./creator-assets --spec ./packet-spec.json --out ./draft-package.zip
python -m pytest -q tests/test_delivery_package.py
```

The ZIP is created **outside** `creator-assets`. Existing output is never overwritten. The files are archived under `deliverables/`, with `MANIFEST.json` containing SHA-256 values and `REVIEW_BEFORE_SENDING.txt` making the review boundary explicit.

Supported formats include PNG/JPEG/WebP, SVG/PDF, PSD/Blend/FBX/GLB/OBJ and source files such as Luau, TypeScript and Markdown. Unknown executable/secret-like extensions, hidden folders, symlinks, unsafe `..` paths, excess byte counts and case-collisions are rejected. Limits: 24 selected files, 35 MiB each, 100 MiB total. No file is executed. ZIP does not itself check artistic beauty, malware, editability, buyer requirements, copyright or commercial licensing.

**This is NOT a secure data-loss-prevention scanner.** Users must inspect selected files and their embedded metadata; a PNG, PDF, Blender file or document can still contain personal or restricted information. Never commit private customer files, full packets or account credentials to the public STAR repository.

## Research: which marketplaces can actually support what?

| Channel | Verified official capability | What STAR may safely build next | Unsupported assumptions |
| --- | --- | --- | --- |
| Etsy | OAuth2 authorization; Open API v3 `createDraftListing` with `listings_w`, uploads for digital listings | Least-privilege seller-authorized drafts, accurate listing packets, sourced orders after scoped approval | "Any seller can safely publish unlimited AI listings without review" |
| Printify + Etsy | Printify catalog/order integration and personalization workflow | Catalog/cost import; customer brief applied with a human-confirmed proof before physical production | "Auto-personalized" means "no need to review" |
| Fiverr | Responsible AI for genuinely original and client-customized deliverables; seller earns an 80% share of order value | Authorized briefs and files, proofs, revisions, manual seller review and delivery packet export | A general public seller orders/messages API, uncontrolled login bots, bulk spam |
| Shopify | Authenticated Admin GraphQL API with permission scopes for catalog/account operations | Future opt-in first-party store with product drafts and analytics | Free fulfillment, automatic profit or permission-free order access |
| Ko-fi | Webhook API for payment notifications | Authenticated webhook receipts for a creator's own supported payments; reconcile, don't invent sales | Universal API for publishing goods or managing arbitrary storefront content |
| Payhip | Official documented API for **coupons and license keys** at time of review | Limited permitted coupons/software license workflows | Public API for full automatic product listing creation |

### Primary sources, checked October 15, 2026

- Etsy reference (draft listings): https://developers.etsy.com/documentation/reference/
- Etsy listing tutorials (physical and digital): https://developers.etsy.com/documentation/tutorials/listings/
- Etsy OAuth PKCE and access scopes: https://developers.etsy.com/documentation/essentials/oauth2/
- Etsy creativity standards and AI disclosure: https://www.etsy.com/legal/creativity/
- Etsy transaction and listing fees: https://help.etsy.com/hc/en-us/articles/115014483627-What-are-the-Fees-and-Taxes-for-Selling-on-Etsy
- Etsy US processing fees: https://help.etsy.com/hc/en-us/articles/115015628847-What-are-Payment-Processing-Fees-for-Selling-on-Etsy
- Printify personalized order review: https://help.printify.com/hc/en-us/articles/28903834238097-How-do-I-review-orders-with-personalized-products
- Printify API: https://developers.printify.com/
- Fiverr responsible AI guidelines: https://help.fiverr.com/hc/en-us/articles/37554976380177-Using-AI-on-Fiverr-Guidelines-for-freelancers-and-clients
- Fiverr community standards: https://help.fiverr.com/hc/en-us/articles/32242973123985-Our-Community-Standards
- Fiverr earnings: https://help.fiverr.com/hc/en-us/articles/9234443621137-Your-earnings-page
- Shopify API scopes: https://shopify.dev/docs/api/usage/access-scopes
- Ko-fi webhook API: https://help.ko-fi.com/hc/en-us/articles/360004162298-Does-Ko-fi-have-an-API-or-webhook
- Payhip API reference (coupon/license limitations): https://payhip.com/api-reference

API approvals, product policies, pricing and endpoint availability can change. Re-check before any real integration, and distinguish platform functionality from entitlements of a specific seller account.

## Start with ONE original product and ONE differentiated service

### First service to test: indie/Roblox interface **craft and usability audit**

- Buyer brief: platform(s), audience, real references, prohibited styles, editable deliverables, source rights, allowed AI usage, revision cap.
- Work: native UI hierarchy review, 2–3 purposeful redesign options, typography/spacing/font/contrast review, responsive screenshots from the **real** game/app, QA findings mapped to exact locations.
- Deliver: annotated before/after images, source files or code where contracted, visual scorecard with errors and tested screen sizes, plain-language explanation; ProofPacket collects artifacts.
- Differentiate: "real QA and correction" not a cheap one-click Figma screenshot or a promise of effortless AAA.

### First digital product to test: original creator overlays / editable launch asset system

- Design one coherent art direction for a specific buyer segment: stream panels, thumbnail layout template, banner, badges and usable source pieces.
- Include typography licenses/attribution and original composition. Do not sell generic AI prompts, use famous game characters or appropriate third-party visual references without rights.
- Compare preview against the product actually downloaded. Provide clear file formats, dimensions and instructions.
- Upload only through the owner's approved seller flow; the ZIP is a draft and is not market published automatically.

### Later physical print-on-demand experiment

- Start with one **original** design for one meaningful use case and a real physical sample before scaling. Product photography and simulated mockups must be distinguished.
- Confirm actual Printify provider, size availability, supplier production and shipping charges, delivery region, marketplace fees, refund allowance and who pays each charge.
- For personalized orders, require a proof view and approval before production even if text/art has been inserted automatically.

**Market demand is unproven for these suggestions**. STAR should get valid buyer signals using authorized research and actual customer conversations, not assume its own image volume equals demand.

## Economic realism

Recorded income must be separated from price quotes, hypothetical projections, pending orders and actual cleared payments.

A simple illustration (hypothetical, not a market quote): a `$30` POD item costs `$15` to print, `$5` supplier shipping, `$1.95` Etsy transaction fee at 6.5%, `$1.15` US payment processing at 3% plus 25 cents, `$0.20` listing allocation and `$3` ads. This leaves **$3.70** contribution before refunds, taxes, subscriptions or support time. A 15% attributable Offsite Ads charge on the $30 order would add $4.50 in fees, yielding **-$0.80**. Verify eligibility and every actual account fee; see #412 for the configurable Decimal estimator.

For Fiverr, a `$100` buyer-paid gig with an 80% seller share returns about `$80` before the seller's software/model costs, revisions, refunds, actual work hours, taxes and other overhead. The choice of a high-quality niche and predictable labor cost matters more than mass-posting gigs.

## Proposed production architecture (not yet delivered)

```text
Authorized buyer problem / permitted research evidence
          |
          v
Owner-selected creative direction + rights
          |
          v
Several original drafts / specialized tool workers
          |
          v
Independent test gate:
- exact brief and client AI preference
- typos / readability / real app screenshot
- asset dimensions / file types / source rights
- estimated net contribution and revisions
          |
          v
ProofPacket (offline draft ZIP + hashes)
          |
          v
Human approval, exact revision evidence
          |
          v
Official Etsy draft API or supported seller interface
          |
          v
Actual order/earnings receipts when authorized
          |
          v
Defect & buyer-feedback learning, never fake revenue
```

Build next: scoped seller OAuth, persistent job IDs, resumable queues, cost caps, independent approvals, exact account/shop pinning, no duplicate publication, explicit nonpublic draft state, notifications and ordered dependency handoffs. A separate "business" screen should not show a fake profit graph before authenticated sales exist.

For visual quality, pair these artifacts with #403's rendered screenshot tests, #418's UI direction, and user-approved references. The proposed **Taste-to-Proof** loop can learn project-level quality preferences only from authorized inputs and verified reviewer/outcome receipts; it is not yet a proven autonomous designer.

## Acceptance for this ProofPacket implementation

1. `tests/test_delivery_package.py` passes on CI, including path traversal, symlinks, duplicates, overwrite protection, deterministic hashes and no fake approvals.
2. Every command remains offline and requires the owner to explicitly supply workspace + files + output location.
3. No marketplace status, customer delivery, sale or art/legal approval is claimed.
4. No secrets or buyer source files added to Git; synthetic tests only.
5. Any later seller integration independently verifies approved account scope and owner intent; separate PR and review required.
