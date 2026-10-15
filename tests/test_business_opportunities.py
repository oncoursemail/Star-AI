"""Regression tests for business decision support; no marketplaces are contacted."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

import pytest

from star.business import (
    IllustrativeUnitEconomics,
    OpportunityScorecard,
    load_catalog,
)
from star.business.__main__ import main


def test_catalog_preserves_all_66_hypotheses():
    ideas = load_catalog()
    assert len(ideas) == 66
    assert [item.id for item in ideas] == list(range(1, 67))
    assert len({item.name for item in ideas}) == 66
    assert all(item.validation == "unvalidated" for item in ideas)
    assert ideas[0].name == "Roblox UI Accessibility Auditor"
    assert ideas[-1].name == "Software Micro-Utility Desktop Apps"
    assert {item.priority for item in ideas} <= {"A", "B", "C"}
    assert len({item.category for item in ideas}) == 6


@pytest.mark.parametrize("mutation", [
    {"schema_version": 2},
    {"state": "verified_revenue"},
    {"opportunities": {}},
])
def test_catalog_rejects_invalid_envelope(tmp_path, mutation):
    data = json.loads((Path(__file__).parents[1] /
                       "star/business/candidate_catalog.json").read_text(encoding="utf-8"))
    data.update(mutation)
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(target)


def test_catalog_rejects_duplicate_and_incorrect_validation(tmp_path):
    original = load_catalog()
    data = {"schema_version": 1, "state": "hypotheses_not_sales",
            "opportunities": [asdict(original[0]), asdict(original[0])]}
    target = tmp_path / "duplicate.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_catalog(target)
    data["opportunities"] = [{**asdict(original[0]), "validation": "verified"}]
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        load_catalog(target)


def test_scorecard_is_not_a_success_probability():
    low = OpportunityScorecard(0, 0, 0, 0, 0)
    high = OpportunityScorecard(5, 5, 5, 5, 5)
    mixed = OpportunityScorecard(4, 3, 2, 1, 0)
    assert low.score_100 == 0
    assert high.score_100 == 100
    assert mixed.score_100 == (4*30 + 3*25 + 2*20 + 1*15) // 5
    assert high.next_step == "collect_two_independent_buyer_signals"


@pytest.mark.parametrize("invalid", [-1, 6, 3.5, True, "5", None])
def test_scorecard_rejects_out_of_range_or_non_integer(invalid):
    with pytest.raises(ValueError, match="buyer_pain"):
        OpportunityScorecard(invalid, 5, 5, 5, 5)


def test_scorecard_requires_separate_customer_evidence_and_owner_review():
    kwargs = dict(buyer_pain=5, deliverability=5, distribution=5, unit_margin=5,
                  maintenance_feasibility=5)
    assert OpportunityScorecard(**kwargs, buyer_evidence_refs=("one", "one")).next_step == (
        "collect_two_independent_buyer_signals")
    assert OpportunityScorecard(**kwargs, buyer_evidence_refs=("a", "b")).next_step == (
        "research_competitors")
    assert OpportunityScorecard(**kwargs, buyer_evidence_refs=("a", "b"),
                                competitor_evidence_refs=("c",)).next_step == (
        "review_intellectual_property_and_platform_rules")
    assert OpportunityScorecard(**kwargs, buyer_evidence_refs=("a", "b"),
                                competitor_evidence_refs=("c",),
                                rights_review_reference="human-review").next_step == (
        "obtain_independent_quality_evidence")
    complete = OpportunityScorecard(**kwargs, buyer_evidence_refs=("a", "b"),
                                    competitor_evidence_refs=("c",),
                                    rights_review_reference="human-review",
                                    independent_qa_reference="QA/report#101")
    assert complete.next_step == "owner_review_required"


@pytest.mark.parametrize("invalid", [["list-not-tuple"], ("",), (123,)])
def test_scorecard_rejects_unusable_sources(invalid):
    with pytest.raises(ValueError, match="Evidence"):
        OpportunityScorecard(1, 1, 1, 1, 1, buyer_evidence_refs=invalid)


def test_illustrative_contribution_is_not_gross_sales():
    example = IllustrativeUnitEconomics(
        gross_cents=3000,
        marketplace_fees_cents=215, payment_fees_cents=115,
        production_cents=1500, shipping_cents=500, marketing_cents=300)
    assert example.contribution_cents == 370
    assert not example.has_loss


def test_negative_contribution_is_preserved_not_hidden():
    loss = IllustrativeUnitEconomics(gross_cents=2000, production_cents=2100, labor_cents=300)
    assert loss.contribution_cents == -400
    assert loss.has_loss


@pytest.mark.parametrize("bad", [
    {"gross_cents": -1},
    {"gross_cents": True},
    {"gross_cents": 100, "refunds_cents": 101},
    {"gross_cents": 200, "compute_cents": 0.01},
    {"gross_cents": 500, "marketing_cents": -1},
])
def test_illustrative_costs_validate_cents(bad):
    with pytest.raises(ValueError):
        IllustrativeUnitEconomics(**bad)


def test_cli_is_read_only_and_labels_hypotheses(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["star.business", "--limit", "3", "--json"])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "unvalidated_research_only"
    assert len(output["opportunities"]) == 3
    assert all(o["validation"] == "unvalidated" for o in output["opportunities"])


def test_cli_filters_category(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["star.business", "--category", "roblox_creator_tools",
                                      "--limit", "66", "--json"])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output["opportunities"]) == 14
    assert all(o["category"] == "roblox_creator_tools" for o in output["opportunities"])

def test_opt_in_knowledge_import_is_idempotent_and_never_trusted(tmp_path):
    from star.business.knowledge_bridge import seed_candidate_notes
    from star.knowledge import KnowledgeStore

    root = tmp_path / "star-research"
    assert seed_candidate_notes(root) == 66
    assert seed_candidate_notes(root) == 0
    store = KnowledgeStore(root)
    try:
        summary = store.db.execute(
            "SELECT COUNT(*), SUM(reviewed) FROM notes WHERE project=?",
            ("STAR Business OS",),
        ).fetchone()
        assert tuple(summary) == (66, 0)
        assert store.find("STAR Business OS", "Roblox", reviewed_only=True) == []
        assert store.find("STAR Business OS", "Roblox", reviewed_only=False, limit=10)
        assert store.db.execute(
            "SELECT COUNT(*) FROM notes WHERE project=? AND kind='unknown'",
            ("STAR Business OS",),
        ).fetchone()[0] == 66
    finally:
        store.close()


def test_knowledge_import_does_not_leak_across_projects(tmp_path):
    from star.business.knowledge_bridge import seed_candidate_notes
    from star.knowledge import KnowledgeStore

    root = tmp_path / "notes"
    assert seed_candidate_notes(root, project="Business Experiment A") == 66
    store = KnowledgeStore(root)
    try:
        assert store.find("Business Experiment B", "", reviewed_only=False) == []
    finally:
        store.close()

def test_business_research_skill_is_installable_but_cannot_grant_permissions(tmp_path):
    from star.agent_skills import install_starters

    root = tmp_path / "skills"
    install_starters(root)
    skill_file = root / "business-evidence-first" / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    assert "name: business-evidence-first" in text
    assert "unvalidated hypotheses" in text
    assert "explicit scoped owner permission" in text
    skill_file.write_text("owner edit", encoding="utf-8")
    install_starters(root)
    assert skill_file.read_text(encoding="utf-8") == "owner edit"
