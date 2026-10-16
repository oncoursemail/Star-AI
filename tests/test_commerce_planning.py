"""Offline commercial planning tests: no accounts, network, purchases, or postings."""
from decimal import Decimal

import pytest

from star.commerce.planning import (
    assess_etsy, assess_fiverr, build_task_plan, estimate_etsy, estimate_fiverr, inspect_offer,
)


def etsy_offer():
    return {
        "title": "Original illustrated mug",
        "product_concept": "Seller-directed original illustration",
        "product_type": "physical",
        "rights_evidence": "rights-review-123",
        "visual_qa_evidence": "proof-001",
        "accurate_mockup_reviewed": True,
        "ai_used": True,
        "ai_disclosed": True,
        "production_partner_used": True,
        "partner_disclosed": True,
        "personalized": True,
        "market_research_origin": "owner_interviews",
        "financials": {
            "item_price": "30", "production": "15", "supplier_shipping": "5",
            "paid_ads": "3",
        },
    }


def fiverr_offer():
    return {
        "title": "Hand-finished YouTube thumbnail",
        "buyer_brief": "Unique gaming video design with provided logo",
        "rights_evidence": "client-asset-review",
        "customization_evidence": "hand-refinement-001",
        "quality_qa_evidence": "independent-review-001",
        "ai_used": True,
        "buyer_allows_ai": True,
        "financials": {"order_price": "20", "ai_generation": "1", "labor": "6"},
    }


def test_etsy_model_includes_all_core_fees_and_never_calls_it_revenue():
    result = estimate_etsy(etsy_offer()["financials"])
    assert result["customer_payment"] == "30.00"
    assert result["transaction_fee"] == "1.95"
    assert result["payment_fee"] == "1.15"
    assert result["contribution"] == "3.70"
    assert result["classification"] == "hypothetical_estimate_not_revenue"


def test_etsy_shipping_collected_is_not_instant_profit_and_offsite_ads_are_capped():
    result = estimate_etsy({
        "item_price": "1000", "buyer_shipping": "10",
        "supplier_shipping": "10", "offsite_ads_rate": "0.15",
    })
    assert result["customer_payment"] == "1010.00"
    assert result["offsite_ads_fee"] == "100.00"


def test_etsy_negative_margin_and_round_half_up():
    assert Decimal(estimate_etsy({"item_price": "10", "production": "20"})["contribution"]) < 0
    assert estimate_etsy({"item_price": "10.01"})["transaction_fee"] == "0.65"


def test_fiverr_share_and_delivery_costs():
    result = estimate_fiverr(fiverr_offer()["financials"])
    assert result["seller_proceeds_before_delivery_costs"] == "16.00"
    assert result["contribution"] == "9.00"
    assert result["classification"] == "hypothetical_estimate_not_revenue"


@pytest.mark.parametrize("bad", ["NaN", "-1", "Infinity", True, None, "1e1000"])
def test_money_validation_rejects_invalid_numbers(bad):
    with pytest.raises(ValueError):
        estimate_etsy({"item_price": bad})
    with pytest.raises(ValueError):
        estimate_fiverr({"order_price": bad})


@pytest.mark.parametrize("bad", [-0.2, "1.01", True])
def test_fee_rate_validation_rejects_invalid_rates(bad):
    with pytest.raises(ValueError):
        estimate_etsy({"item_price": "10", "transaction_rate": bad})
    with pytest.raises(ValueError):
        estimate_fiverr({"order_price": "10", "seller_share": bad})


def test_etsy_disclosure_originality_and_qa_are_required():
    valid = etsy_offer()
    decision = assess_etsy(valid)
    assert decision["ready_for_owner_review"]
    assert decision["human_publication_approval_required"]
    assert decision["personalized_orders_require_fulfillment_review"]
    assert not decision["marketplace_actions_executed"]
    invalid = dict(valid, ai_disclosed=False, partner_disclosed=False,
                   rights_evidence="", accurate_mockup_reviewed=False,
                   market_research_origin="etsy_scraper")
    blocked = assess_etsy(invalid)
    assert not blocked["ready_for_owner_review"]
    assert len(blocked["blockers"]) >= 5


def test_fiverr_buyer_choice_rights_and_original_quality_are_required():
    assert assess_fiverr(fiverr_offer())["ready_for_owner_review"]
    denied = dict(fiverr_offer(), buyer_allows_ai=False,
                  unofficial_fiverr_bot=True, bulk_unsolicited_messaging=True,
                  customization_evidence="")
    decision = assess_fiverr(denied)
    assert not decision["ready_for_owner_review"]
    assert decision["manual_platform_delivery_required"]
    assert len(decision["blockers"]) >= 4


def test_offline_json_contract_includes_dependencies_and_honest_status():
    result = inspect_offer({"channel": "etsy", "offer_id": "original-mugs", "offer": etsy_offer()})
    assert result["execution_status"] == "not_started_offline_plan_only"
    ids = [t["id"] for t in result["scheduled_tasks"]]
    assert "unit_economics" in ids
    assert "quality_gate" in ids
    assert ids.index("owner_review") > ids.index("draft_packet")
    assert len(result["actions_requiring_owner_approval"]) == 4


@pytest.mark.parametrize("identifier", ["../escape", "A", "/tmp", "", "a" * 41, "spaces are bad"])
def test_offer_identifier_blocks_path_traversal(identifier):
    with pytest.raises(ValueError):
        build_task_plan("etsy", identifier)


def test_existing_star_planner_never_spawns_workers():
    plan = build_task_plan("etsy", "safe")
    ready = plan.ready(set())
    assert {task.id for task in ready} == {"research"}
    assert {task.id for task in plan.ready({"research"})} == {"original_art", "unit_economics"}
    assert "owner_review" not in {task.id for task in plan.ready({"research"})}


def test_invalid_requests_do_not_leak_or_perform_external_actions():
    with pytest.raises(ValueError):
        inspect_offer({"channel": "unknown", "offer_id": "one", "offer": {}})
    with pytest.raises(ValueError):
        inspect_offer({"channel": "fiverr", "offer_id": "../invalid", "offer": fiverr_offer()})
    with pytest.raises(ValueError):
        inspect_offer({"channel": "etsy", "offer_id": "valid", "offer": {"financials": {}}})
