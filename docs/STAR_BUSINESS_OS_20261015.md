# STAR Business OS — evidence-led autonomous commerce research (2026-10-15)

## Goal and user context

The owner wants STAR to conduct credible demand research, create professional and original products, prepare listings, manage approved sales workflows, measure actual profit, and eventually support many connected businesses rather than switching to a separate AI chat. The financial goal is to generate legitimate income which can support STAR's hardware and infrastructure. This must not be described as passive, guaranteed or already earning money.

The earlier AI Agent Ecosystem Tour 2 by @androoAGI used a virtual office / multi-agent team with manager, research, creative production, marketing, administration and treasury. The creator's reported Etsy and Fiverr revenue figures are *claims*, not audited profit or proof of a reproducible system. STAR should borrow the orchestration idea, not reproduce revenue claims.

## Current STAR code status — precise

- Draft PR #412 (https://github.com/oncoursemail/Star-AI/pull/412) is an **offline Etsy/Printify + Fiverr opportunity, pricing, design-rights and quality planner**. The full checks were green when last inspected.
- It **does not** provide merchant OAuth, access to seller dashboards, automatic listing/publishing, order intake, customer messaging, transfers, or payout reception.
- This document is a research/engineering plan on a separate draft PR. Neither PR makes a store live. Never imply a business is running without actual externally verified API events and seller authorization.

## Channel-specific reality from first-party docs

| Channel | Real supported mechanics | Important restriction |
| --- | --- | --- |
| Shopify | OAuth access scopes; GraphQL Admin productCreate can create an unpublished product; publishablePublish is separate; webhooks/background credentials are possible. | Owner must create/authorize the store and payment setup, pay applicable store fees, and separately approve publication. Need conversion traffic, fulfillment and support. |
| Etsy | OAuth2 + API key, createDraftListing, upload listing images/files; digital downloads use uploadListingFile and type=download. | Seller-designed rules, AI disclosure, fees and shop eligibility apply. Publishing can incur listing costs and must never happen accidentally. |
| Printify | Official REST APIs for product creation, publish, order management and webhooks. | **Some new Printify stores auto-approve orders for production after 24 hours by default.** Explicitly set manual order approval before experimenting to avoid real production charges. |
| Gumroad | Sales/download and store payout infrastructure; payout can be bank or PayPal depending on location; public product/documentation surface. | No assumption any account can connect its own Stripe. Gumroad says new user-connected Stripe is not supported except Brazil. App automation capabilities need a separate current API validation. |
| Fiverr | Human freelancer listing, customer projects, order fulfillment and the seller's platform payout. Fiverr credits seller 80% of completed order value. | AI work must be original, substantially refined and specific to the customer; do not auto-spam, misrepresent effort, guarantee outcomes, or assume a general seller publishing API. Treat the seller portal as manual until an authorized API is verified. |
| Roblox Creator Store | Original USD-priced models and plugins; seller onboarding administered through Stripe. Roblox states 100% net proceeds after payment/tax costs. | 30-day escrow on purchases; monthly payout cycle; seller eligibility and moderation. Not an instant cash source. |

Primary-source links:
- Etsy API authentication: https://developer.etsy.com/documentation/essentials/authentication/
- Etsy draft/digital listing procedure: https://developer.etsy.com/documentation/tutorials/listings/
- Etsy listing and transaction fees: https://help.etsy.com/hc/en-us/articles/115014483627-What-are-the-Fees-and-Taxes-for-Selling-on-Etsy
- Etsy seller-made/design policy: https://help.etsy.com/hc/en-us/articles/360024112614-What-Can-I-Sell-on-Etsy
- Shopify authentication: https://shopify.dev/docs/apps/build/authentication-authorization
- Shopify product draft creation: https://shopify.dev/docs/api/admin-graphql/latest/mutations/productCreate
- Shopify scopes: https://shopify.dev/docs/apps/build/authentication-authorization/manage-access-scopes
- Printify API and manual production warning: https://developers.printify.com/
- Gumroad payout methods: https://gumroad.com/help/article/13-getting-paid
- Gumroad fees: https://gumroad.com/help/article/66-gumroads-fees
- Gumroad Stripe exception: https://gumroad.com/help/article/330-stripe-connect
- Fiverr AI standards: https://help.fiverr.com/hc/en-us/articles/37554976380177-Using-AI-on-Fiverr-Guidelines-for-freelancers-and-clients
- Fiverr seller fees: https://www.fiverr.com/legal-portal/legal-terms/payment-terms-of-service
- Creator Store USD monetization: https://create.roblox.com/docs/production/creator-store

## Architecture: one orchestration system, independent business engines

STAR Business OS should be a separate bounded domain module, **not** unlimited system permissions for all connected agents.

Business identity record:
- Business/project ID, owned brand, approved marketplaces, niche and product category.
- Merchant store/account ID and explicit granted OAuth scopes; credentials live in OS vault or a dedicated secret store, never chat/SQLite plain text, git or screenshots.
- Risk/permission envelope: read-only, draft preparation, approved publication, bounded fulfillment; *no general spending or transfer access.*
- Rights, license, AI disclosure, seller-policy and approved fulfillment checklist specific to each channel.
- Currency/timezone, fee model version and audit event ledger; no personal financial account numbers.

Conductor + workers:
- Demand Radar: compare source-linked evidence of customer need, price competition and keyword interest; keep assumptions/uncertainty explicit and **never fabricate store sales**.
- Opportunity Judge: weighted scoring for real buyer pain, attainable quality, distribution, contribution margin, maintenance/risk. Reject commodity AI spam and niches with no credible path to customers.
- Product Forge: original, editable product files; use independent design/engineering QA, exact-fit file deliverables and verified commercial rights. For services, create a client-specific statement of work.
- Proof Engine: test real assets (React browser, Roblox Studio, Blender export, digital PDF/ZIP integrity) and collect screenshot evidence; apply owner design veto and prevent recurring errors.
- Listing Studio: write actual title, image alt text, description, size/chart/instructions, mockups and FAQs. Create marketplace **drafts** through official connectors where supported.
- Commerce Control: per-store OAuth connector, verified order/event signatures, consent/approval, idempotency keys, status polling, order recovery, rate limits and reversible operations. Marketplace terms and user authorization are authoritative.
- Customer Care: permitted replies drafted for review, delivery QA, refund/complaint triage. Do not impersonate a person or spam unsolicited outreach.
- Profit Intelligence: reconcile real order/payment provider data with fees, cost of goods, advertising costs, refund and chargeback liabilities, labor, taxes estimates, pending holds and **actual cleared payouts**. Separate revenue and profit.
- Evolution Engine: learn from accepted/rejected deliverables and observed sales/returns/conversion; candidate lessons must not silently grant permissions or change prices/budgets.

Agent scheduling should use a durable queue or SQLite WAL in early prototypes, with bounded concurrency, atomic reservations, deduplicated webhook/order IDs, retry with exponential backoff, cancellation and activity history. Use the cheapest reliable local model for routine classification; reserve premium inference for high-quality design and difficult code. Running ten agents does not make an untested asset good.

## Multi-business economics and safety gates

Use the equation: contribution per order = collected order amount minus marketplace/payment fees, refunds/reserves, fulfillment, ad acquisition and variable generation costs. Net profit additionally accounts for overhead, labor, taxes and other operating costs. **Do not count unpaid invoices, held balances or an influencer's gross revenue claims as cash in the bank.**

Important fee examples at the research date:
- Etsy: USD 0.20 listing fee and 6.5% transaction fee, plus Etsy Payments processing and other applicable fees. Additional listing creation can cost money even without buyers.
- Fiverr: 80% of completed order sale value credited to the seller before any subsequent taxes/expenses.
- Gumroad: published pricing lists direct transaction fees; check payment processor and location-specific costs. Do not reuse historical fee estimates blindly.
- Roblox Creator Store: USD pricing for original plugins/models and 30-day escrow. Eligible creator receives net proceeds and then the scheduled payout.

Never store a seller bank account in STAR. The seller completes KYC, taxes and payout destination *in the platform's secure hosted flow*. STAR can later reconcile anonymized payout statuses via an approved scoped API, not initiate bank transfers.

External irreversible actions require a separate trust gate:
- Starting a paid subscription; purchasing inventory/ads; charging a payment method; submitting a production order; creating a new store; transferring money; modifying payout settings: explicit owner authorization in the platform or a trusted host, with transaction-by-transaction confirmation or appropriately bounded advance authorization if the provider supports it.
- Marketplace publication, customer outreach and order promises only through supported platform APIs, limited to approved items and disclosure rules. Draft creation is the default mode.
- No fake reviews, bought followers, copyright/IP cloning, false testimonials, unsolicited bulk messages, payout circumvention or risky scraping.

## What businesses to try first (hypotheses, NOT validated demand)

1. **Productized Roblox debugging / UI improvement service**. First realistic path to quicker payment is one paid client project, not a thousand automated listings. A clear deliverable: before/after screenshots, actual Roblox Studio deliverables, typed Luau, acceptance tests and one revision. Fiverr already has many competing low-priced Roblox UI gigs, so quality and specificity must justify the offer. Client communication and final review remain human-led.
2. **A polished Roblox Creator Store plugin or verified original model pack**. Reuse tooling developed for STAR, such as UI QA, inventory UI setup, secure datastore templates. Make a high-quality demo and instructions. Accept seller-onboarding and payout lag.
3. **Gumroad original digital dev packs**. Sell editable UI kits, Figma-to-Roblox handoff assets, tested scripts, Blender export templates or educational tools with clear licensing and easy downloads. Use real preview video and working samples.
4. **Etsy digital design files / Printify** only when the specific goods comply with Etsy creation rules and production partner policies. Print-on-demand has production, shipping, returns and cashflow obligations; start only after manual order-approval configuration.
5. **Shopify** once a product category and distribution channel are validated. It is an owned storefront and useful hub, not a free source of shoppers.
6. **Custom Fiverr/other professional services** such as bespoke thumbnails, landing pages and animations only if original high-quality client-specific work is consistent and fulfillment can be reliable.

Expansion into many stores/businesses should happen **after** one small repeatable profitable workflow has demonstrated repeat buyers and manageable support costs. Clone the operating *process*, not the same generic AI product hundreds of times.

## Proposed owner-visible UI

A single Business workspace in STAR, styled with the same quiet OLED/gold product identity, not a busy futuristic stock-trading dashboard.

Top: revenue actually collected, costs, pending payouts, refund risk and calculated profit for the chosen period. Show "No verified sales yet" until real provider data arrives.

Center: company/store list with status = Researching / Drafting / Owner review / Live / Paused / Failed. Each contains Opportunity, Product, Creative QA, Catalog, Orders, Support, Ledger, and Audit trail.

One clear approvals inbox: permissions, publication, ad spend, production, customer commitments and refunds. Plain language about money at risk.

A store is not "connected" unless OAuth and a live read-only check succeed. Never display simulated sales as if real.

## Next engineering sequence and acceptance tests

M0: Close and review commerce planning PR #412; no duplicate commerce authorization code on an unreviewed branch.
M1: Native Business workspace + read-only reporting model, owner-authored permission budgets, audited status transitions. Design sign-off before implementation.
M2: Official Shopify and Etsy OAuth read-only connection; secured credentials, disconnect, scope minimization, hard-disable all write calls.
M3: Generate original product and client-specific service deliverables, then test asset quality with Creative Review and independent native/browser/Studio proofs.
M4: Create **draft** Shopify products and **draft** Etsy listings, without publication; zero unexpected external charges and repeatable idempotency.
M5: Owner-reviewed publishing and optional fulfillment (Printify manual order approval tested first). Track real webhook/orders, no double fulfillment, refunds and payout reconciliation.
M6: Controlled automated scheduling and multi-business portfolio after a profitable niche is demonstrated, with per-business rate/spend caps and clear emergency pause.

Acceptance must include permission-boundary tests, mocked OAuth expiry, duplicate webhook replay, API throttling, currency rounding, refund/cancel flows, lost network retries and synthetic order tests in approved test environments. No live money or product publication in CI.

**This file is architecture/research only. No bank accounts were connected, no storefront was created, no customer contacted, and no money was generated in this PR.**
