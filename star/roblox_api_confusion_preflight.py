"""Bounded, source-linked method spelling advisories for explicit project preflight.

This supplements, but never upgrades, the conservative API-dump checker.
Simple inferred Roblox classes still need type and Studio verification.
"""
from __future__ import annotations

from collections import Counter

from .roblox_api_checker import ApiDump, check_luau_api
from .roblox_api_confusions import scan_luau


def _matches_reference(dump: ApiDump, actual: str, reference: str,
                       suggestion: str) -> bool:
    """Check an inferred class's documented ancestors and suggested member."""
    if suggestion not in dump.inherited_members.get(actual, frozenset()):
        return False
    current = actual
    while current in dump.classes:
        if current == reference:
            return True
        current = dump.classes[current].superclass
    return False


def confusion_advisories(source: str, dump: ApiDump | None, *,
                         limit: int) -> tuple[list[dict], int]:
    """Return at most limit advisory records, plus the total lexical hit count.

    Call only on <=20 KB already-admitted place-tree source. An API dump can
    support simple receiver inference, never confirmation of a runtime error.
    Ambiguous same-line calls are intentionally never attributed a class.
    """
    if limit < 0:
        raise ValueError("Advisory output limit must be non-negative")
    hits = scan_luau(source)
    counts = Counter((hit["line"], hit["wrong"]) for hit in hits)
    inferred: dict[tuple[int, str], set[str]] = {}
    if dump is not None and limit and hits:
        for finding in check_luau_api(source, dump):
            if finding.rule_id == "unknown-member" and finding.class_name:
                inferred.setdefault((finding.line, ":" + finding.name + "("),
                                    set()).add(finding.class_name)

    advisories = []
    for hit in hits[:limit]:
        wrong, right = str(hit["wrong"]), str(hit["right"])
        reference = str(hit["source_url"]).rsplit("/", 1)[-1]
        classes = inferred.get((hit["line"], wrong), set())
        receiver_class = None
        if len(classes) == 1 and counts[(hit["line"], wrong)] == 1:
            candidate = next(iter(classes))
            if dump is not None and _matches_reference(
                    dump, candidate, reference, right[1:-1]):
                receiver_class = candidate
        advisories.append({
            "line": hit["line"], "column": hit["column"],
            "rule": "api-confusion:possible-method-spelling",
            "severity": "info", "checker": "roblox-api-confusions",
            "category": "advisory",
            "message": (
                f"Possible Roblox API spelling {wrong}; consider {right}. "
                "Verify the receiver class; custom methods may be valid."
            ),
            "wrong": wrong, "right": right, "source_url": hit["source_url"],
            "receiver_evidence": (
                "api-dump-inferred-class" if receiver_class else "unverified"
            ),
            "receiver_class": receiver_class,
        })
    return advisories, len(hits)
