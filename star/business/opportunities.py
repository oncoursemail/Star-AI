"""Offline, non-executing opportunity research and illustrative unit economics.

This module never calls models, publishes products, charges customers, messages
buyers, or verifies payment. Candidate rankings are hypotheses, not demand.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "business" / "candidate_catalog.json"  # under star/data: bundled by both Windows builds
_WEIGHTS = (
    ("buyer_pain", 30),
    ("deliverability", 25),
    ("distribution", 20),
    ("unit_margin", 15),
    ("maintenance_feasibility", 10),
)


@dataclass(frozen=True)
class Opportunity:
    id: int
    category: str
    name: str
    buyer: str
    deliverable: str
    proposed_test_price: str
    priority: str
    validation: str

    def __post_init__(self) -> None:
        if type(self.id) is not int or self.id < 1:
            raise ValueError("Opportunity ID must be a positive integer")
        if any(not isinstance(value, str) or not value.strip() for value in (
            self.category, self.name, self.buyer, self.deliverable, self.proposed_test_price,
        )):
            raise ValueError("Opportunity fields must be nonempty text")
        if self.priority not in {"A", "B", "C"}:
            raise ValueError("Priority must be A, B, or C")
        if self.validation != "unvalidated":
            raise ValueError("Catalog entries must remain unvalidated research hypotheses")


def load_catalog(path: Path | None = None) -> tuple[Opportunity, ...]:
    """Load reviewable hypotheses; importing them never promotes them to verified facts."""
    source = path if path is not None else _CATALOG_PATH
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unsupported business catalog schema")
    if document.get("state") != "hypotheses_not_sales":
        raise ValueError("Business catalog must clearly identify unverified hypotheses")
    raw = document.get("opportunities")
    if not isinstance(raw, list):
        raise ValueError("Catalog must contain an opportunities array")
    opportunities: list[Opportunity] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("Malformed opportunity record")
        try:
            opportunities.append(Opportunity(**row))
        except (TypeError, ValueError) as exc:
            raise ValueError("Malformed opportunity record") from exc
    ids = [item.id for item in opportunities]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate opportunity ID")
    return tuple(opportunities)


@dataclass(frozen=True)
class OpportunityScorecard:
    """A human-entered assessment; numerical output is not a sales forecast.

    Buyer references are unverified identifiers supplied by the assessor. A
    passing checklist only means an owner should examine the proposal, not that
    an agent may publish a listing or spend money.
    """

    buyer_pain: int
    deliverability: int
    distribution: int
    unit_margin: int
    maintenance_feasibility: int
    buyer_evidence_refs: tuple[str, ...] = ()
    competitor_evidence_refs: tuple[str, ...] = ()
    rights_review_reference: str = ""
    independent_qa_reference: str = ""

    def __post_init__(self) -> None:
        for key, _ in _WEIGHTS:
            value = getattr(self, key)
            if type(value) is not int or not 0 <= value <= 5:
                raise ValueError(f"{key} must be an integer from 0 to 5")
        for refs in (self.buyer_evidence_refs, self.competitor_evidence_refs):
            if (not isinstance(refs, tuple)
                    or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 2048 for ref in refs)):
                raise ValueError("Evidence must be a tuple of nonempty source references")
        for reference in (self.rights_review_reference, self.independent_qa_reference):
            if not isinstance(reference, str) or len(reference) > 2048:
                raise ValueError("Review references must be text up to 2048 characters")

    @property
    def score_100(self) -> int:
        """A weighted decision-support score; 100 is not a probability of success."""
        return sum(getattr(self, field) * weight for field, weight in _WEIGHTS) // 5

    @property
    def next_step(self) -> str:
        """Never authorize external actions; all positive cases still need owner review."""
        if len(set(self.buyer_evidence_refs)) < 2:
            return "collect_two_independent_buyer_signals"
        if not self.competitor_evidence_refs:
            return "research_competitors"
        if not self.rights_review_reference.strip():
            return "review_intellectual_property_and_platform_rules"
        if not self.independent_qa_reference.strip():
            return "obtain_independent_quality_evidence"
        return "owner_review_required"


@dataclass(frozen=True)
class IllustrativeUnitEconomics:
    """Per-sale cost arithmetic in integer USD cents; not a verified payment ledger."""

    gross_cents: int
    refunds_cents: int = 0
    marketplace_fees_cents: int = 0
    payment_fees_cents: int = 0
    production_cents: int = 0
    shipping_cents: int = 0
    marketing_cents: int = 0
    compute_cents: int = 0
    labor_cents: int = 0
    support_cents: int = 0

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            value = getattr(self, field)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field} must be a nonnegative integer number of cents")
        if self.refunds_cents > self.gross_cents:
            raise ValueError("Refunds cannot exceed this sale's gross amount")

    @property
    def contribution_cents(self) -> int:
        costs = sum(getattr(self, field) for field in self.__dataclass_fields__
                    if field != "gross_cents")
        return self.gross_cents - costs

    @property
    def has_loss(self) -> bool:
        return self.contribution_cents < 0
