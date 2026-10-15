# STAR Commerce Research: Etsy + Printify and Fiverr

**Research verified:** October 15, 2026. **Implementation stage:** offline planning foundation, not live automation. **Marketplaces connected:** none. **Revenue:** none claimed.

## Purpose

Build a quality-first, evidence-driven business operation for STAR. STAR can research authorized demand signals, prepare original sellable work, coordinate creation and QA, calculate *hypothetical* contribution, assemble listing/delivery packets, and pause for approval. A good-looking AI workforce does not itself mean that a storefront, profitable business, or autonomous customer-service connection exists.

This plan expands the October 14 STAR Business Empire report with specific Etsy, Printify, and Fiverr policy/engineering detail. The user-provided transcription describes the video creator's print-on-demand and thumbnail workflow; it does not establish audited seller income or permissions for our own integration.

## 1. What automation is actually supported

| Operation | Etsy + Printify | Fiverr |
| --- | --- | --- |
| Find original product/service ideas | Yes, from permitted sources; do not scrape Etsy content without express authorization | Yes, from lawful research and direct buyer inquiry; avoid unauthorized seller-data scraping |
| Generate design variants | Yes, seller-directed and original | Yes, provided buyer requirements allow AI |
| Run independent visual/licensing checks | Yes | Yes |
| Estimate a price after fees | Yes; estimates are not payout statements | Yes; sellers generally receive 80% of order amount |
| Prepare title, tags, preview images and copy | Yes | Yes |
| Programmatically create a shop draft | Etsy Open API v3 supports draft listing creation with listings_w OAuth scope | No generally available public seller API for gigs/orders/messages was verified |
| Publish or message customers | Requires separate explicit owner authorization and Etsy policy compliance | Use Fiverr's supported seller interface, no unauthorized automation |
| Manage POD shipping | Printify can integrate; verify shop fulfillment settings and charge source | Not applicable to digital service |
| Automatically finalize personalized products | Printify says personalized orders require review before production, even with automated personalization | Every final service delivery needs customer-specific quality review |
| Reconcile real income | Use authorized account data and original receipts | Use seller earnings records/export legitimately obtained |

**Do not build a Fiverr login bot, spam sender, CAPTCHA bypass, undocumented internal-API client, or hidden screen scraper.** Such approaches are brittle, pose account risks, and are not necessary for the large AI-assisted *production* portion of the business.

**Etsy research constraint:** Current Etsy API terms prohibit unauthorized automated systems to access/analyze/scrape Etsy data, and API data collection for analytics or model training without explicit written authorization. STAR should use direct customer conversations, user-provided seller records, permitted official integrations, search trends, and original research. Do not suggest cloning trending listings or copyrighted artwork.

## 2. Etsy: seller-directed originals, not mass-produced AI slop

Preferred initial experiment: one tightly defined visual niche with an original authored concept and real buyer signal. Examples to *test*, not claims of demand:
- Original visual gifts for indie-game creators; carefully checked typography and real printed samples.
- Personalized star-map-style keepsakes using customer-provided text and permitted visual elements.
- Digital planner/stream overlay bundles with professional editable source files and clear rights.
- High-end event invitations or personalizable creator merchandise, with realistic sample images.
- Original cozy-pet character illustrations with buyer-requested personalization and meaningful edits.

Avoid protected character names, game franchise logos, copied seller designs, celebrities without rights, counterfeit branded merchandise, and prompt bundles sold as original designed items. Etsy's Creativity Standards require seller creativity, seller-prompted AI disclosure and production partner disclosure. A generic agent-generated prompt is not sufficient provenance of creative direction by the human seller.

**Product lifecycle:**
1. Research a buyer problem from permitted evidence; record source link/date, suspected willingness to pay and competitor differentiation without bulk scraping.
2. Owner selects the niche and writes or approves a seller-directed creative brief. Store the brief and its author.
3. Generate several original alternatives using a properly licensed image tool; record prompts, tool/model terms, seed/source, and human changes.
4. Art director checks accurate text, anatomy (where present), symmetry, shape, brand uniqueness, spacing, intended print dimensions, resolution and transparent backgrounds.
5. Rights reviewer records input rights, likeness/trademark issues, permitted commercial use and the authenticity of the generated work.
6. For physical products, choose a Printify blueprint/provider and verify current size availability, print area, base cost, expected production location, dispatch/shipping cost and delay.
7. Prepare truthful product mockups. When images are illustrative, do not imply they are photographs of a product sampled when they aren't. Physically sample one product before scaling a new supplier or design class.
8. Prepare an Etsy draft packet (title, description, images, variations, inventory, shipping, disclosures); do not publish without owner approval.
9. Use Etsy official OAuth/Open API for supported drafts and only after seller-app authorization and explicit permission. Handle 429 Retry-After, short-lived credentials, least privilege, audit and idempotency.
10. If order fulfillment is enabled by the owner, reconcile authorized Etsy/Printify order statuses. Printify's seller is charged for production; Etsy buyer payments and Printify charges can occur on separate timelines. Support tracking, cancellations, refunds, returns and disputes.
11. Personalized Printify orders must be reviewed/approved before production; automated input application is not the same as automatic approval.
12. Measure authentic unit economics, customer feedback and actual defects. Retire poor products without flooding the marketplace.

**Preview quality acceptance:** no unreadable words; no invented claims or unsupported materials; print-safe crop; correct design placement on every variation; correct mockup-to-actual difference; source provenance; no unexplained clipped elements; at least one independent human review and appropriate order-level personalization proof.

## 3. Actual Etsy unit economics

Etsy's published core figures as reviewed October 15: 6.5% transaction fee on order amount including charged shipping; USD 0.20 listing fee; U.S. Etsy Payments 3% + $0.25; potential Offsite Ads fee of 15% or 12% on attributable orders (fee cap USD 100 per order). Other fees, currency conversion, international payments, taxes, revisions, support time and listing renewals vary. Do not hardwire rates globally.

Illustration for an item priced at USD 30 with no extra buyer-paid shipping:
- Production USD 15
- Supplier shipping USD 5
- Etsy 6.5% transaction USD 1.95
- U.S. processing 3% + 0.25 = USD 1.15
- Assumed listing allocation USD 0.20
- Paid ads allocation USD 3
- **Contribution = USD 3.70 before other overhead and taxes**, not USD 30 profit
- **If attributable 15% Offsite Ads also applied**, subtract USD 4.50: contribution becomes negative USD 0.80 before other overhead.

Use Printify's current prices rather than stale catalog samples. Charging the buyer shipping raises order receipts *and* relevant marketplace fees; supplier shipping remains a cost. Account for refunds and chargebacks explicitly. Small margins can disappear through one quality dispute.

## 4. Fiverr: sell expert deliverables, not raw AI output

Fiverr publicly allows responsible AI use, but the seller must deliver original, customized, meaningfully refined work and honor any explicit non-AI buyer request. Freelancers receive 80% of completed purchase value, including extras and tips, before their own costs. Bulk unwanted Fiverr messages and inauthentic reviews are prohibited.

Recommended services to validate:
- **Game YouTube thumbnail studio:** client concept/brand interview; cinematic composition; hand-redrawn typography; 2–3 variations; human QA; clearly scoped revisions.
- **Roblox UI polish:** use user-approved project references, native screen geometry and acceptance criteria; export editable assets and instructions.
- **Game VFX sprite sheet design:** original illustrated sequences, high-resolution checks, alpha consistency, real animation preview; rights to each source.
- **Indie game launch asset kit:** matching capsule/banner/thumb/store art with platform-specific crops.
- **Game developer technical report:** inspect submitted Luau/project files with permission, identify reproducible bugs/security/performance issues, deliver a prioritized fix/test report.

Treat 20/70/180 USD tiered service pricing as experiments, not market-clearing prices. Different gigs have different buyer expectations; no client is guaranteed.

**Safe service lifecycle:** qualify scope → record buyer AI preference → take private client files only with authorization → build custom variants → refine manually with a consistent art guide → compare against exact brief → rights/visual checks → prepare delivery package + reply draft → seller reviews → seller sends using supported Fiverr interface → track revisions and authentic earnings in source records.

**No fake portfolios:** don't pass generated fictional testimonials or unperformed client work off as real. Samples should be labeled demonstrations when they aren't commissioned work.

**Fiverr automation boundary:** No broadly available official public seller-facing order/messaging API was verified in this research. A community post or an unofficial third-party API is not proof of authorization. STAR should automate the production workspace and assemble the work package, not log in using hidden browser bots, impersonate a seller or deliver without review.

## 5. Product QA should be more than a self-reported boolean

Treat agent-produced text and attached evidence labels as *untrusted*. A string such as "QA passed" is not a verified quality event. Next phase should record:
- Output artifact hash and exact source asset versions.
- Independent named reviewer with non-model-controlled approval authority.
- Text spelling/legibility and intended display-size proof.
- Design/reference consistency checklist and screenshots of actual output.
- Rights/permission records and applicable source licenses.
- For client work, acceptance criteria matched to source order and revision count.
- A change journal so rejected outputs lead to new candidate generations, not immediate publication.

The included offline engine only checks whether the requested evidence fields have been supplied. It **cannot verify the authenticity** of those fields, score the actual image, check a marketplace account or replace human decisions.

## 6. Technical integration with existing STAR

Implementation in this draft PR:
- star/commerce/planning.py: deterministic Decimal financial estimates with configurable fee rates; Etsy originality/disclosure checks; Fiverr client-choice and quality checks; STAR TaskPlan task dependencies.
- star/commerce/__main__.py: read-only JSON CLI, using local offer briefs only. No network activity or secrets.
- examples/commerce/: fake sample offers with deliberately incomplete approvals.
- tests/test_commerce_planning.py: fee math, negative inputs, disclosures, prohibited automation flags, and dependency-order tests.

From the repository root, execute:
python -m star.commerce examples/commerce/etsy_offer.json
python -m star.commerce examples/commerce/fiverr_offer.json
python -m pytest -q tests/test_commerce_planning.py

**Not delivered by this PR:** seller OAuth, real API requests, Printify billing sync, authenticated earnings imports, background worker execution, production-quality art/image generation, React Business Dashboard, or actual product publication. No storefront or Fiverr account has been accessed.

### Next engineering milestones (separate reviewed PRs)
A. Add a persistent SQLite order/workflow store with idempotency keys, bounded retries, crash recovery, append-only cost/audit events, and independent review receipts. Reuse STAR's existing model/provider core; avoid a second standalone desktop application.

B. Add an Etsy Seller App OAuth connector with listings_w only for owner-approved drafts, an explicit no-publish default, stored credentials only in an OS vault, token refresh, strict shop ID, webhook verification if applicable, rate-limit retries, and user revocation. Confirm developer approval and app purpose first.

C. Add Printify official product-catalog, cost and order-status adapters, but separate draft creation from order submission or printing charges. Require a verified sample and personalized-order approval before physical fulfillment.

D. Add a seller-operated Fiverr desk with order briefs imported through user-provided records, deliverable generator integrated into ComfyUI/other approved tools, side-by-side quality review, and manual delivery packet export. Wait for documented authorized Fiverr seller integration before implementing account action endpoints.

E. Add a React Business workspace inside the existing STAR desktop: Ideas, Design Review, Products, Jobs, Approval Queue, Orders, Profit, and Audit. Keep all controls clearly labeled as simulation, draft, pending, or verified.

F. Add permitted demand research connectors (e.g. trend data from sources allowing access and original interviews) with source URLs, dates, research bias and uncertain market estimates. Marketplace scraping is not a required dependency.

G. Add independent end-to-end QA: generated work isn't marked ready based on its creator agent's own assessment. Users can keep STAR fully offline until they opt in to a specific integration.

### Operating model
- Start with one Etsy product family and one scoped Fiverr service, not hundreds of low-quality listings.
- For new product types, collect buyer feedback and order a physical sample before scaling.
- Keep spending, print orders, public communication and listings behind permission review.
- Measure actual paid conversions and gross contribution; separate them from simulated prices, pending cash or unverified revenue.
- Do not promise automatic/passive income, overlook consumer-service obligations, or invent market sales statistics.

## 7. First-party references (checked October 15, 2026)

- Etsy Creativity Standards: https://www.etsy.com/legal/creativity/
- Etsy seller API requirements and terms: https://www.etsy.com/legal/api/
- Etsy Open API OAuth: https://developers.etsy.com/documentation/essentials/oauth2/
- Etsy Open API listings tutorial: https://developers.etsy.com/documentation/tutorials/listings/
- Etsy API rate limiting: https://developers.etsy.com/documentation/essentials/rate-limits/
- Etsy selling fees: https://help.etsy.com/hc/en-us/articles/115014483627-What-are-the-Fees-and-Taxes-for-Selling-on-Etsy
- Etsy payment processing: https://help.etsy.com/hc/en-gb/articles/115015628847-What-are-Payment-Processing-Fees-for-Selling-on-Etsy
- Etsy production partners: https://help.etsy.com/hc/en-us/articles/360000336547-Working-with-Production-Partners-on-Etsy
- Printify API documentation: https://developers.printify.com/
- Printify Etsy automated personalization: https://help.printify.com/hc/en-us/articles/40720228428433-How-do-I-set-up-automated-personalization-for-Etsy
- Printify manual review of personalized orders: https://help.printify.com/hc/en-us/articles/28903834238097-How-do-I-review-orders-with-personalized-products
- Fiverr AI guidelines: https://help.fiverr.com/hc/en-us/articles/37554976380177-Using-AI-on-Fiverr-Guidelines-for-freelancers-and-clients
- Fiverr community standards: https://help.fiverr.com/hc/en-us/articles/37554441398929-Our-Community-Standards
- Fiverr seller earnings: https://help.fiverr.com/hc/en-us/articles/9234443621137-Your-earnings-page
- Fiverr Gig content and media guidelines: https://help.fiverr.com/hc/en-us/articles/360011421218-Requirements-and-guidelines-for-your-Gig
- STAR architecture and exact shipping status: https://github.com/oncoursemail/Star-AI/blob/star/next/README.md

**Research limitations:** Policy pages and marketplace fees can change; revalidate before commercial deployment. No private account records or sales were inspected. Estimated scenarios are not revenue, and imported customer material must be appropriately authorized, minimized and safeguarded.
