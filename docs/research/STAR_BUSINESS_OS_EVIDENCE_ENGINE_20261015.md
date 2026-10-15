# STAR Business OS — Evidence-First Research and Engineering Plan

**Research reviewed:** 2026-10-15 (America/Chicago: 2026-10-14). **Implementation status:** opt-in, offline prototype in a draft branch; this document does not claim installed, released, live storefronts, paid customers, or profit.

**Read first:** [66-opportunity research blueprint](STAR_BUSINESS_EMPIRE_BLUEPRINT_20261014.md). Its pricing ranges are experiments, **not a market price survey, demand confirmation, or an income forecast**. The machine-readable hypotheses are in `star/business/candidate_catalog.json`.

## Executive conclusion

Build a **proof-driven company operating system**, not a simulation of busy agents. The useful feedback loop is customer problem -> permissioned market research -> scoped offer -> original tested product -> human-approved publication -> authentic paid transaction -> cost reconciliation -> learning from defects and paid users. A visual room or AI-avatar view should be a *projection of real execution receipts* and never the authority for success.

STAR's current repository already has a local-first Python agent/controller, scoped tools, memory, evaluation fixtures, and a deterministic task planner. The planner in `star/orchestration.py` explicitly **does not spawn subagents**. Existing Studio permissions in `star/policy.py` must remain authoritative. Do not claim that this new research package is a live multi-agent scheduler or a storefront connector.

## 1. What the 2026 external research contributes

| Source / reference | Confirmed technical lesson | Adopt in STAR | Avoid |
|---|---|---|---|
| [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools/) | Dynamic toolsets, memory, delegation, skills and scheduled operations | Reuse the *design principles* of bounded specialized roles and persistent lessons | Treating written agent self-confidence as a verified outcome |
| [OpenHands V1 SDK docs](https://docs.openhands.dev/sdk/guides/agent-server/docker-sandbox.md) | Software-writing agents should execute in isolated workspaces with reproducible artifacts | Disposable build/test places; independent QA transcripts and source hashes | Giving a coding agent host secrets or uncontrolled machine access |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Checkpointed graph state and cross-thread stores are distinct | Durable local state machine plus scoped knowledge | RAM-only checkpoints for long-lived business orders |
| [Temporal execution](https://docs.temporal.io/workflow-execution) | Workflows can resume after failure via deterministic replay | Retry/lease/idempotency design if higher scale warrants it | Adopting an infrastructure service before a small SQLite queue suffices |
| [Stripe webhooks](https://docs.stripe.com/webhooks) | Asynchronous signed events inform payment, disputes and refunds | Future adapter verifies raw-body signatures and handles reordered/duplicate notifications | Treating a screenshot or model message as payment proof |
| [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests) | Write requests need stable idempotency keys for safe retries | Idempotent create/update external actions, manual approval after uncertain outcomes | Replaying customer charges without a reliable key |
| [Etsy Listings API](https://developers.etsy.com/documentation/tutorials/listings/) | OAuth scopes, draft listings, digital file upload, separate publication step | Future adapter prepares drafts under scope, with separate owner approval for activation | Auto-publishing unknown/uncleared AI art |
| [Roblox Creator Store](https://create.roblox.com/docs/production/creator-store) | Monetizable model/plugin listings require seller eligibility and approved assets | First pilot in Roblox developer tooling; validate assets in Studio | Confusing gross list price, net proceeds, settlement and payout |
| [Framer creator program](https://www.framer.com/help/articles/how-the-creator-program-works/) | Paid templates, plugins and components can earn creator revenue | Game launch / developer-portfolio site templates as complementary offer | Claiming 100% proceeds imply no processing or development costs |
| [Shopify app distribution](https://shopify.dev/docs/apps/launch/distribution/revenue-share) | App Store distribution has registration, review and revenue-share conditions | B2B SaaS *after* a validated customer problem | Launching generic AI assistants with ongoing privacy/support exposure |
| [n8n commercial-license FAQ](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case) | Client-owned workflows differ from hosted customer-configurable n8n SaaS under SUL | Good for internal prototypes/authorized managed services; check license for each product | Rebranding hosted n8n as unrestricted open source |
| [FTC marketing guidance](https://www.ftc.gov/business-guidance/advertising-marketing) | Advertising claims need evidence and review practices matter | Ground listings in demonstrated product features; track disclosures | Fabricated buyers, AI testimonials, fake scarcity or reviews |
| [YC customer discovery](https://www.ycombinator.com/library/Ri-how-to-pick-a-startup-idea) | Feedback from actual customers is stronger than brainstorming many ideas | Require real problem/price feedback before large production commitments | Treating counts of generated products as demand |
| [PostHog self-hosting](https://posthog.com/docs/self-host) | Running privacy-preserving analytics requires an operated, secured deployment | Start with local opt-in aggregate events; use dedicated analytics only at scale | Silent telemetry or unsupported public analytics deployment |

### Competitive context

The creator's [StarNet code](https://github.com/androoAGI/starnet) is MIT licensed but its station art, name, mascot and other brand assets are **not** licensed under that MIT code grant. Its sidecar/events/budget/consent ideas are useful architectural references; do not copy the appearance or imply a direct dependency is installed. Hermes, OpenHands, Temporal, LangGraph and n8n solve *different* tasks. STAR's thin offline prototype deliberately adds **none** as a heavy required runtime dependency.

## 2. Revenue experiments: focus before diversification

The full catalog has 66 **unvalidated** opportunities in six groups. Prioritize work that can be made genuinely excellent with the tools already present:

**Track A — Productized services (near-term):**
- Fixed-scope Roblox UI audit/redesign; deliver native editable Roblox UI, annotated screenshots, responsive device QA and clear limitations.
- Fixed-scope Luau bug-fix/security review; deliver patched scripts and test/console evidence with exact change boundaries.
- Game/indie website landing page; deliver responsive source, accessibility checks and a tested deploy handoff.
- Discord community onboarding and support workflow setup; with verified permissions, safe data retention and support policy.

**Track B — Reusable developer products (compounding):**
- UI Accessibility Auditor plugin: lint and demonstrate actionable issues, disclose false positives, measure real Studio overhead.
- Asset/Code Inspector: static checks for unsafe remotes, broken paths, excessive effects, mismatched declarations and reproducible warnings.
- Optimized VFX/UI packs: original sources, previews, source provenance and low-end/mobile performance evidence.
- Game website template: publish original content in a permitted marketplace with customer documentation.

**Track C — Recurring systems (only after buyer proof):**
- Team release checklist, bug-review inbox and safe changelog generation.
- Discord helpdesk with *human-reviewable* customer replies and escalation.
- Narrow website/commerce catalog data-quality monitor for authorized customer accounts.
- Game asset update feed and verified compatibility support.

**Track D — lower-priority speculative experiments:** Etsy personalized goods, print-on-demand, AI music, affiliate publishing, generic thumbnail generation and broad consumer chatbots. These have distinct quality, search-distribution, fulfillment, IP and policy risks. Running more agents does not solve those fundamentals.

### Product selection rule

Before building, collect at least two **independent, documented** buyer signals, a source-linked competitor landscape, a deliverable acceptance test, an acquisition/distribution channel, rights clearance, an estimated unit-economics sheet and a human reviewer. If evidence is insufficient, the result is *research needed*, **not** "failed business" or "ready to sell". A 0–100 ranking is a priority rubric, not a success probability.

## 3. Seven interlocking engineering systems

1. **Demand Radar.** Gather opt-in customer interviews, public product requirements and first-party marketplace APIs. Each finding has `source, captured_at, buyer_segment, problem, uncertainty, quote_or_summary, permission`. No fabricated evidence or blocked scraping.
2. **Feasibility Judge.** Grade pain (30%), deliverability (25%), distribution (20%), illustrative contribution margin (15%), and maintenance/rights feasibility (10%). Keep the separate evidence gate even with a perfect score.
3. **Product Forge.** Use a source-controlled DAG with scoped writer ownership and quality gates; run a tiny 1–2 agent pilot on RAM/GPU-constrained equipment. Design, code and QA are distinct tasks; no self-approved grader changes.
4. **Quality Proof Engine.** Collect syntax/type results, unit tests, Roblox Studio/Luau logs where permitted, before/after screenshots, asset manifests, dependency licenses, mobile performance and reproducible artifact hashes.
5. **Commerce Approval Broker.** Never silently publish listings, send unsolicited sales messages, create subscriptions, make purchases, authorize refunds, change OAuth scopes or spend money. Use scoped, time-limited approvals with traceable artifact hashes and explicit amounts.
6. **Financial Truth Engine.** Later receive *provider-authenticated* events into an append-only double-checked ledger: pending order / paid / refunded / charged back / transferred / settled; keep customer PII minimal. Compute contribution in cents: `collected - refunds - fees - production - shipping - ads - compute - labor - support`. Model-generated numbers remain scenario estimates.
7. **Learning & Recall.** Save exact problem -> tested fix -> customer outcome. User corrections and model research are **candidate knowledge**, not automatically reviewed facts. Prevent business output from editing the independent quality tests that judged it.

### Novel improvement: "Proof-of-Work Revenue Loop"

A product cannot be marked "commercially validated" by creating a convincing mockup, generating a fake order receipt or reporting an imaginary KPI. Instead, the authoritative state machine would require:
`hypothesis -> real buyer evidence -> designed -> QA accepted -> owner approved -> marketplace published -> provider event observed -> provider event reconciled -> buyer feedback -> maintained`.

Publishing can fail after approval; payment can reverse after settlement; customer feedback can contradict earlier estimates. Store all these independently. Visual status derives from real events. This is a **proposed specification**, not current shipped functionality.

### Novel improvement: "Failure Before Launch"

Build a deterministic preflight that estimates the *probability of a test failing* only after collecting actual labeled project data. Until such calibration exists, use explicit rule-based risk flags: missing customer quote, unlicensed asset, unverified API behavior, blocked source publication, missing screenshot, zero QA samples, negative estimated margin, no buyer distribution, and unsecured secrets. Never present uncalibrated model confidence as a percentage.

## 4. Current scoped implementation in this branch

`star/business/candidate_catalog.json` — all 66 rows, preserved as hypotheses.

`star/business/opportunities.py` — pure, offline:
- schema-checked hypothesis loading;
- 0–100 weighted **research** scorecards, plus a separate staged human evidence/QA checklist;
- cent-accurate illustrative per-sale contribution, including negative outcomes;
- *no marketplace API, background task, model call, payment or publishing capability*.

`python -m star.business --limit 10` — CLI lists prioritized research candidates; `--json` and `--category` filter.

`star/business/knowledge_bridge.py` — explicit, idempotent transfer of these idea hypotheses to STAR's existing project-scoped `KnowledgeStore`, marking them **unreviewed**. This is distinct from blindly "training" the model on text. A profile importer does not make products real.

For a developer on a STAR source checkout, an **optional** import into a chosen local knowledge folder is:

```python
from pathlib import Path
from star.business.knowledge_bridge import seed_candidate_notes
added = seed_candidate_notes(Path.home() / "STAR-business-research-notes")
print(f"Added {added} unreviewed notes. Review evidence before trusting.")
```

This example does **not** edit STAR's normal profile or run automatically. Integrating the installer/app UI and reviewed knowledge search is a separate gate.

### Tests and acceptance

`python -m pytest -q tests/test_business_opportunities.py` tests catalog integrity, schema rejection, ranking math, customer-evidence gates, negative economics, optional note import and CLI. Run GitHub CI on the draft PR. A green Python job does **not** prove a store can accept/list a commercial product, that Studio ran, or that users paid.

## 5. Architecture for the next engineering stages (not implemented)

Recommended additions, after review of existing startup/module boundaries:

```text
Windows UI (STAR) ──── Business board (proposals, receipts, approvals)
     │
     └── Python core policy/approval broker
            ├── SQLite local queue (durable idempotency+lease, crash recovery)
            ├── research workers (read-only sources with citations)
            ├── product workers (restricted worktrees + Studio Lab test place)
            ├── independent QA receipts (tests outside worker control)
            ├── financial journal (authenticated webhook events)
            └── publisher adapters (draft first, approved release later)
```

- Prefer **stdlib + SQLite WAL** for the first one-user implementation; add Temporal only when operational scale and workflow complexity justify operating it.
- Keep user secrets in Windows Credential Manager and profile state outside replaceable install directories, following STAR's existing update design.
- API/webhook handlers must verify source signatures, record event IDs, reject replayed side effects, and handle retries/reordering; never trust a model's reported payment.
- Derive dashboard state from receipts, not from what an animated avatar appears to be doing.
- Report estimated dollars, verified gross sales, available payout, refunds, contributor costs and profitability separately.
- Future parallelism on the owner's 8 GB GPU must be bounded by measured model throughput and memory; 8 simultaneous heavyweight local workers are not 8x faster.
- Require review for private customer data access, commercial publication, terms/price changes, charge/refund operations and material customer communications.

## 6. Revenue measurement dictionary

| Measure | Definition | Evidence authority |
|---|---|---|
| Opportunity | An idea, not a business | Research note |
| Buyer signal | Source-linked customer statement or legitimate signed trial | Interview/survey record |
| Qualified traffic | Visits matching an intended buyer cohort | Consented analytics |
| Conversion | Completed customer action / qualified exposures | First-party event + denominator |
| Booked gross sales | Total order charge before deductions | Authenticated provider order |
| Net proceeds | Provider payout calculation after platform/tax/processing adjustments | Provider settlement |
| Contribution | Collected amount - variable cost including refunds | Reconciled provider & internal costs |
| Operating profit | Contribution - allocated fixed expenses | Accounting reconciliation |
| Cash available | Settled and withdrawable funds | Provider balance/payout |
| Revenue forecast | Hypothetical scenario, never a transaction | Named assumptions |

The safest next metric isn't "total AI businesses started." It is **median hours from actual buyer problem to independently verified prototype, then fraction of qualified buyers who pay**.

## 7. Ninety-day executable business path

**Days 1–7:** Choose two offers. Collect buyer problem statements. Use STAR to prepare an original Roblox UI review and a Luau debugging demo. Never simulate real customers.

**Days 8–21:** Run independent checks, get permissioned customer feedback, quote fixed scopes, and finish one deliverable with revisions and proof. Publish one approved product listing only if seller requirements are satisfied.

**Days 22–45:** Build an opt-in customer support channel, tracked QA failures, actual payment reconciliation, and an honest first margin report. Add one downloadable product from proven client work.

**Days 46–90:** Tune the repeatable product; only add Framer templates, Unity/Godot assets or subscription tools when they share proven demand. Pause ideas with insufficient evidence and stop projects with repeated negative contribution after adequate exposure.

## 8. Scope and deployment truth

The branch gives STAR a **research catalog and deterministic decision-support library**. It does *not* create 66 companies, guaranteed passive income, a live business-operations UI, automatic customer outreach, connected storefronts, or validated AI agents. Its generated assets and business ideas still require original work, human decision-making, compliance and genuine customers.

Do not modify protected policy or publish without a separate reviewed PR and user action. The full historical 66-idea research is preserved as a document, not promoted to ground truth. Terms and pricing must be re-verified at each commercial launch; research links can become outdated.

---
**Key sources:** [Roblox Creator Store](https://create.roblox.com/docs/production/creator-store) · [Etsy API](https://developers.etsy.com/documentation/tutorials/listings/) · [Stripe webhooks](https://docs.stripe.com/webhooks) · [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [Temporal](https://docs.temporal.io/workflow-execution) · [n8n licensing](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case) · [FTC marketing](https://www.ftc.gov/business-guidance/advertising-marketing) · [YC idea research](https://www.ycombinator.com/library/Ri-how-to-pick-a-startup-idea).
