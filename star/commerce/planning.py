"""Offline Etsy/Printify and Fiverr opportunity planning.

Only *plans* tasks; never starts workers or makes a network request. External
platform data must come from authorized sources, not marketplace scraping.
Rates are configurable estimates, not authenticated payout statements.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Mapping

from star.orchestration import Task, TaskPlan

_CENT = Decimal("0.01")
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")


def _number(value: Any, name: str, *, maximum: str = "1000000") -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"{name} must be a nonnegative number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a nonnegative number") from exc
    if not parsed.is_finite() or parsed < 0 or parsed > Decimal(maximum):
        raise ValueError(f"{name} must be finite and between 0 and {maximum}")
    return parsed


def _amount(values: Mapping[str, Any], field: str, default: str = "0") -> Decimal:
    return _number(values.get(field, default), field).quantize(_CENT, rounding=ROUND_HALF_UP)


def _rate(values: Mapping[str, Any], field: str, default: str) -> Decimal:
    return _number(values.get(field, default), field, maximum="1")


def _usd(value: Decimal) -> str:
    return format(value.quantize(_CENT, rounding=ROUND_HALF_UP), ".2f")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def estimate_etsy(financials: Mapping[str, Any]) -> dict[str, str]:
    """US-dollar example with configurable rates. Not an Etsy payout calculation.

    Actual taxes, extra country fees, refunds, multi-quantity renewals,
    VAT, conversion, Offsite Ads attribution and shipping vary.
    """
    costs = _mapping(financials, "financials")
    if "item_price" not in costs:
        raise ValueError("item_price is required")
    item_price = _amount(costs, "item_price")
    if not item_price:
        raise ValueError("item_price must be above zero")
    buyer_shipping = _amount(costs, "buyer_shipping")
    gross = item_price + buyer_shipping
    production = _amount(costs, "production")
    supplier_shipping = _amount(costs, "supplier_shipping")
    listing = _amount(costs, "listing_fee", "0.20")
    platform_rate = _rate(costs, "transaction_rate", "0.065")
    payment_rate = _rate(costs, "payment_rate", "0.03")
    payment_fixed = _amount(costs, "payment_fixed", "0.25")
    offsite_rate = _rate(costs, "offsite_ads_rate", "0")
    paid_ads = _amount(costs, "paid_ads")
    ai_generation = _amount(costs, "ai_generation")
    labor = _amount(costs, "labor")
    refunds = _amount(costs, "refund_allowance")
    other = _amount(costs, "other_costs")

    transaction_fee = (gross * platform_rate).quantize(_CENT, rounding=ROUND_HALF_UP)
    payment_fee = (gross * payment_rate + payment_fixed).quantize(_CENT, rounding=ROUND_HALF_UP)
    offsite_ads = min(
        (gross * offsite_rate).quantize(_CENT, rounding=ROUND_HALF_UP), Decimal("100.00")
    )
    total_costs = sum((production, supplier_shipping, listing, transaction_fee, payment_fee,
                       offsite_ads, paid_ads, ai_generation, labor, refunds, other), Decimal("0"))
    contribution = gross - total_costs
    return {
        "classification": "hypothetical_estimate_not_revenue",
        "currency": "USD",
        "customer_payment": _usd(gross),
        "production_cost": _usd(production),
        "supplier_shipping_cost": _usd(supplier_shipping),
        "listing_fee": _usd(listing),
        "transaction_fee": _usd(transaction_fee),
        "payment_fee": _usd(payment_fee),
        "offsite_ads_fee": _usd(offsite_ads),
        "additional_costs": _usd(paid_ads + ai_generation + labor + refunds + other),
        "total_costs": _usd(total_costs),
        "contribution": _usd(contribution),
        "margin_percent": _usd(contribution * Decimal("100") / gross),
    }


def estimate_fiverr(financials: Mapping[str, Any]) -> dict[str, str]:
    """Illustrative Fiverr seller proceeds less creator-side delivery expenses."""
    costs = _mapping(financials, "financials")
    if "order_price" not in costs:
        raise ValueError("order_price is required")
    order_price = _amount(costs, "order_price")
    if not order_price:
        raise ValueError("order_price must be above zero")
    seller_share = _rate(costs, "seller_share", "0.80")
    platform_fee = (order_price * (Decimal("1") - seller_share)).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    ai_cost = _amount(costs, "ai_generation")
    labor = _amount(costs, "labor")
    revisions = _amount(costs, "revisions")
    advertising = _amount(costs, "advertising")
    refunds = _amount(costs, "refund_allowance")
    other = _amount(costs, "other_costs")
    total_costs = sum((platform_fee, ai_cost, labor, revisions, advertising, refunds, other), Decimal("0"))
    contribution = order_price - total_costs
    return {
        "classification": "hypothetical_estimate_not_revenue",
        "currency": "USD",
        "order_price": _usd(order_price),
        "platform_fee": _usd(platform_fee),
        "seller_proceeds_before_delivery_costs": _usd(order_price - platform_fee),
        "creator_delivery_costs": _usd(total_costs - platform_fee),
        "total_costs": _usd(total_costs),
        "contribution": _usd(contribution),
        "margin_percent": _usd(contribution * Decimal("100") / order_price),
    }


def _text(record: Mapping[str, Any], field: str) -> bool:
    value = record.get(field)
    return isinstance(value, str) and bool(value.strip())


def _flag(record: Mapping[str, Any], field: str) -> bool:
    return record.get(field) is True


def assess_etsy(offer: Mapping[str, Any]) -> dict[str, Any]:
    """Return missing review evidence, never permission to publish or fulfill."""
    record = _mapping(offer, "offer")
    blocked: list[str] = []
    if not _text(record, "title"):
        blocked.append("Provide a specific, original listing title.")
    if not _text(record, "product_concept"):
        blocked.append("Explain the seller-directed original product concept.")
    if not _text(record, "rights_evidence"):
        blocked.append("Attach a traceable commercial-rights and originality review.")
    if not _text(record, "visual_qa_evidence"):
        blocked.append("Attach a human-reviewed product image/design QA record.")
    if not _flag(record, "accurate_mockup_reviewed"):
        blocked.append("Review actual product depiction and listing image accuracy.")
    if _flag(record, "ai_used") and not _flag(record, "ai_disclosed"):
        blocked.append("Disclose AI involvement in the Etsy description.")
    if _flag(record, "production_partner_used") and not _flag(record, "partner_disclosed"):
        blocked.append("Disclose the production partner and accurate dispatch location.")
    if record.get("product_type") not in ("physical", "digital"):
        blocked.append("Choose product_type 'physical' or 'digital'.")
    if record.get("market_research_origin") in ("etsy_scraper", "unauthorized_marketplace_data"):
        blocked.append("Unauthorized Etsy scraping/AI analytics is not an approved research source.")
    return {
        "channel": "etsy_printify",
        "ready_for_owner_review": not blocked,
        "blockers": blocked,
        "human_publication_approval_required": True,
        "personalized_orders_require_fulfillment_review": _flag(record, "personalized"),
        "marketplace_actions_executed": False,
        "note": "Evidence references are unverified until a trusted reviewer checks them.",
    }


def assess_fiverr(offer: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate work-package quality without automating Fiverr account access."""
    record = _mapping(offer, "offer")
    blocked: list[str] = []
    if not _text(record, "title"):
        blocked.append("Define a truthful service title.")
    if not _text(record, "buyer_brief"):
        blocked.append("Record a specific buyer-approved brief and acceptance criteria.")
    if not _text(record, "rights_evidence"):
        blocked.append("Check client content and output rights for the intended commercial use.")
    if not _text(record, "customization_evidence"):
        blocked.append("Document meaningful customer-specific editing, not generic AI output.")
    if not _text(record, "quality_qa_evidence"):
        blocked.append("Require independent human QA of the delivered work.")
    if _flag(record, "ai_used") and record.get("buyer_allows_ai") is not True:
        blocked.append("Do not use AI when buyer permission/preference is unknown or forbids it.")
    if _flag(record, "bulk_unsolicited_messaging"):
        blocked.append("Unsolicited mass messaging is not permitted.")
    if _flag(record, "unofficial_fiverr_bot"):
        blocked.append("Do not use unapproved seller-account automation or scraping.")
    return {
        "channel": "fiverr",
        "ready_for_owner_review": not blocked,
        "blockers": blocked,
        "human_delivery_approval_required": True,
        "manual_platform_delivery_required": True,
        "marketplace_actions_executed": False,
        "note": "AI-assisted work must be original, customized, checked and aligned with the buyer.",
    }


def build_task_plan(channel: str, offer_id: str) -> TaskPlan:
    """Reuse STAR's dependency/ownership planner; these tasks do not execute."""
    if not isinstance(offer_id, str) or not _ID.fullmatch(offer_id):
        raise ValueError("offer_id must be a safe lowercase identifier of 1-40 characters")
    scope = f"commerce/{offer_id}"
    if channel == "etsy":
        tasks = [
            Task("research", "research", "Document lawful demand evidence and buyer need.",
                 writes=(f"{scope}/research",)),
            Task("original_art", "ui", "Create seller-directed original artwork with design records.",
                 dependencies=("research",), writes=(f"{scope}/artwork",)),
            Task("unit_economics", "planner", "Estimate production, shipping, and all known fees.",
                 dependencies=("research",), writes=(f"{scope}/pricing",)),
            Task("quality_gate", "review", "Verify image, rights, disclosures, mockups and sample.",
                 dependencies=("original_art", "unit_economics"), reads=(f"{scope}/pricing",),
                 writes=(f"{scope}/qa",)),
            Task("draft_packet", "integration", "Prepare a draft listing packet, never publish.",
                 dependencies=("quality_gate",), reads=(f"{scope}/qa",),
                 writes=(f"{scope}/draft",)),
            Task("owner_review", "review", "Request owner approval and store a trusted review record.",
                 dependencies=("draft_packet",), reads=(f"{scope}/draft",),
                 writes=(f"{scope}/review",)),
        ]
    elif channel == "fiverr":
        tasks = [
            Task("buyer_intake", "planner", "Record scoped brief and check buyer's AI preference.",
                 writes=(f"{scope}/brief",)),
            Task("custom_work", "ui", "Generate then meaningfully customize original deliverables.",
                 dependencies=("buyer_intake",), reads=(f"{scope}/brief",),
                 writes=(f"{scope}/deliverable",)),
            Task("independent_qa", "review", "Check design, readability, requirements and rights.",
                 dependencies=("custom_work",), reads=(f"{scope}/deliverable",),
                 writes=(f"{scope}/qa",)),
            Task("delivery_packet", "integration", "Prepare package and seller-facing reply draft only.",
                 dependencies=("independent_qa",), reads=(f"{scope}/qa",),
                 writes=(f"{scope}/draft",)),
            Task("owner_review", "review", "Request seller approval; leave Fiverr delivery manual.",
                 dependencies=("delivery_packet",), reads=(f"{scope}/draft",),
                 writes=(f"{scope}/review",)),
        ]
    else:
        raise ValueError("channel must be 'etsy' or 'fiverr'")
    return TaskPlan(tasks, max_parallel=3)


def inspect_offer(data: Mapping[str, Any]) -> dict[str, Any]:
    """Pure JSON-ready output for offline business research/quality planning."""
    record = _mapping(data, "request")
    channel = record.get("channel")
    if not isinstance(channel, str):
        raise ValueError("channel must be 'etsy' or 'fiverr'")
    offer_id = record.get("offer_id")
    if not isinstance(offer_id, str):
        raise ValueError("offer_id is required")
    plan = build_task_plan(channel, offer_id)
    offer = _mapping(record.get("offer"), "offer")
    finance = _mapping(offer.get("financials"), "offer.financials")
    if channel == "etsy":
        assessment = assess_etsy(offer)
        estimate = estimate_etsy(finance)
    else:
        assessment = assess_fiverr(offer)
        estimate = estimate_fiverr(finance)
    return {
        "offer_id": offer_id,
        "channel": channel,
        "financial_projection": estimate,
        "quality_assessment": assessment,
        "execution_status": "not_started_offline_plan_only",
        "scheduled_tasks": [
            {"id": t.id, "role": t.role, "goal": t.goal, "dependencies": list(t.dependencies)}
            for t in plan.tasks.values()
        ],
        "actions_requiring_owner_approval": [
            "Marketplace publication or seller-account messages",
            "Purchases, advertising spend, refund or payment action",
            "Production submission of any personalized order",
            "Final customer-facing delivery",
        ],
    }
