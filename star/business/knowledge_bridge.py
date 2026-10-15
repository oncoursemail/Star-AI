"""Opt-in import of business hypotheses into STAR's existing reviewable knowledge store.

All imported notes remain unreviewed. No model, payment provider, marketplace,
network request, publishing endpoint or agent permissions are used.
"""
from __future__ import annotations

from pathlib import Path

from .opportunities import load_catalog


def seed_candidate_notes(root: Path, *, project: str = "STAR Business OS") -> int:
    """Idempotently store 66 researched hypotheses as UNREVIEWED project notes.

    This deliberately does not call review_note; business assumptions must not
    enter trusted memory unless an authorized human reviews their evidence.
    Returns the count of newly inserted notes.
    """
    from ..knowledge import KnowledgeStore

    store = KnowledgeStore(root)
    inserted = 0
    try:
        for idea in load_catalog():
            source = f"repo:star/business/candidate_catalog.json#opportunity-{idea.id}"
            revision = "business-catalog-2026-10-14"
            exists = store.db.execute(
                "SELECT 1 FROM notes WHERE project=? AND source=? AND revision=? LIMIT 1",
                (project, source, revision),
            ).fetchone()
            if exists:
                continue
            description = (
                f"UNVALIDATED BUSINESS HYPOTHESIS #{idea.id}: {idea.name}. "
                f"Buyer: {idea.buyer}. Proposed product: {idea.deliverable}. "
                f"Proposed test price: {idea.proposed_test_price}. "
                f"Research priority {idea.priority} is NOT expected sales, demand or profit. "
                "Verify buyers, originality, platform rules, margins and owner approval."
            )
            store.add_note(project=project, kind="unknown", text=description,
                           source=source, revision=revision)
            inserted += 1
    finally:
        store.close()
    return inserted
