"""Offline, evidence-bound RAG backend tournament for STAR Intelligence.

This module NEVER runs retrieval, accepts raw documents, executes tools, loads
models, writes memories, or promotes a retrieval system. It evaluates bounded
source-id predictions against an operator-frozen evidence catalog. The only
output is aggregate quality, freshness, privacy and latency evidence. No
vendor endpoint, API key, text prompt or document contents are involved.

Backend candidates (STAR Knowledge, Chroma, pgvector, AnythingLLM, Khoj,
Langflow, etc.) must generate evidence on the SAME independent, rights-cleared
fixtures before a human considers deployment.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import stat
import sys

MAX_BYTES = 1_000_000
MAX_CASES = 256
MAX_SOURCES = 2000
MAX_HITS = 20
MAX_EXPECTED = 8
MAX_LATENCY_MS = 120_000
MIN_REVIEW_CASES = 20
MIN_REVIEW_POSITIVES = 10
MIN_REVIEW_NEGATIVES = 3
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,95}\Z")
_PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_ .-]{0,95}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _keys(obj: object, expected: set[str], label: str) -> dict:
    if type(obj) is not dict or set(obj) != expected:
        raise ValueError(f"Invalid {label} shape")
    return obj


def _name(value: object, label: str, *, project: bool = False) -> str:
    pattern = _PROJECT if project else _NAME
    if (type(value) is not str or not pattern.fullmatch(value) or ".." in value
            or "://" in value or value != value.strip()):
        raise ValueError(f"Invalid {label} identifier")
    return value


def _hash(value: object) -> str:
    if type(value) is not str or not _SHA.fullmatch(value):
        raise ValueError("Expected SHA-256 source revision")
    return value


def _sources(raw: object) -> dict[str, dict]:
    if type(raw) is not list or not 1 <= len(raw) <= MAX_SOURCES:
        raise ValueError("Invalid source catalog size")
    catalog: dict[str, dict] = {}
    for obj in raw:
        item = _keys(obj, {"id", "project", "sha256", "reviewed", "active"}, "source")
        identity = _name(item["id"], "source")
        if identity in catalog:
            raise ValueError("Duplicate source id")
        _name(item["project"], "project", project=True)
        _hash(item["sha256"])
        if type(item["reviewed"]) is not bool or type(item["active"]) is not bool:
            raise ValueError("Unverified source status")
        catalog[identity] = item
    return catalog


def _validate_attempt(raw: object) -> dict:
    item = _keys(raw, {"hits", "latency_ms"}, "retrieval attempt")
    latency = item["latency_ms"]
    if type(latency) is not int or not 0 <= latency <= MAX_LATENCY_MS:
        raise ValueError("Invalid measured retrieval latency")
    if type(item["hits"]) is not list or len(item["hits"]) > MAX_HITS:
        raise ValueError("Invalid number of retrieved sources")
    seen: set[str] = set()
    for hit in item["hits"]:
        hit = _keys(hit, {"id", "sha256"}, "retrieved source")
        identity = _name(hit["id"], "retrieved source")
        _hash(hit["sha256"])
        # Duplicated ranks can misleadingly inflate retrieval scores.
        if identity in seen:
            raise ValueError("Duplicated retrieved source")
        seen.add(identity)
    return item


def _cases(raw: object, catalog: dict[str, dict]) -> list[dict]:
    if type(raw) is not list or not 1 <= len(raw) <= MAX_CASES:
        raise ValueError("Invalid retrieval question count")
    cases: list[dict] = []
    case_ids: set[str] = set()
    for raw_item in raw:
        item = _keys(raw_item, {"id", "project", "expected", "baseline", "candidate"}, "case")
        identity = _name(item["id"], "case")
        if identity in case_ids:
            raise ValueError("Duplicate retrieval case")
        case_ids.add(identity)
        project = _name(item["project"], "project", project=True)
        expected = item["expected"]
        if (type(expected) is not list or len(expected) > MAX_EXPECTED
                or any(type(entry) is not str for entry in expected)
                or len(expected) != len(set(expected))):
            raise ValueError("Invalid expected source set")
        for source_id in expected:
            source = catalog.get(_name(source_id, "expected source"))
            if (source is None or source["project"] != project
                    or not source["active"] or not source["reviewed"]):
                raise ValueError("Gold source must be active, reviewed and inside the project")
        for label in ("baseline", "candidate"):
            _validate_attempt(item[label])
        cases.append(item)
    return cases


def _p95(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * .95) - 1]


def _evaluate(cases: list[dict], catalog: dict[str, dict], arm: str) -> dict:
    positives = 0
    negatives = 0
    top_1 = 0
    top_5 = 0
    top_10 = 0
    reciprocal_sum = 0.0
    abstain_correct = 0
    violations = {"cross_project": 0, "unknown_source": 0,
                  "stale_revision": 0, "unreviewed": 0, "inactive": 0}
    latencies: list[int] = []
    for case in cases:
        attempt = case[arm]
        latencies.append(attempt["latency_ms"])
        expected = set(case["expected"])
        if expected:
            positives += 1
        else:
            negatives += 1
            if not attempt["hits"]:
                abstain_correct += 1
        first_correct: int | None = None
        for rank, hit in enumerate(attempt["hits"], 1):
            source = catalog.get(hit["id"])
            if source is None:
                violations["unknown_source"] += 1
                continue
            bad = False
            if source["project"] != case["project"]:
                violations["cross_project"] += 1
                bad = True
            if source["sha256"] != hit["sha256"]:
                violations["stale_revision"] += 1
                bad = True
            if not source["reviewed"]:
                violations["unreviewed"] += 1
                bad = True
            if not source["active"]:
                violations["inactive"] += 1
                bad = True
            if not bad and hit["id"] in expected and first_correct is None:
                first_correct = rank
        if first_correct is not None:
            top_1 += first_correct <= 1
            top_5 += first_correct <= 5
            top_10 += first_correct <= 10
            if first_correct <= 10:
                reciprocal_sum += 1.0 / first_correct
    return {
        "cases": len(cases),
        "answerable": positives,
        "no_answer": negatives,
        "recall_at_1": round(top_1 / positives, 6) if positives else None,
        "recall_at_5": round(top_5 / positives, 6) if positives else None,
        "recall_at_10": round(top_10 / positives, 6) if positives else None,
        "mrr_at_10": round(reciprocal_sum / positives, 6) if positives else None,
        "abstain_accuracy": round(abstain_correct / negatives, 6) if negatives else None,
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 1),
            "p95": _p95(latencies),
            "max": max(latencies),
        },
        "violations": violations,
    }


def compare(manifest: object) -> dict:
    """Report aggregate evidence; never auto-enable/promote a retriever.

    The expected sources are trusted operator-frozen references, NOT generated
    by candidate retrieval. The gate is advisory even when it recommends an
    owner review, and the same snapshot alone cannot prove retrieval quality
    on an independent sealed holdout.
    """
    if type(manifest) is not dict:
        raise ValueError("RAG quality manifest must be an object")
    encoded = json.dumps(manifest, allow_nan=False, sort_keys=True, ensure_ascii=True)
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("RAG quality manifest is too large")
    _keys(manifest, {"version", "sources", "cases"}, "manifest")
    if type(manifest["version"]) is not int or manifest["version"] != 1:
        raise ValueError("Unsupported RAG quality manifest version")
    sources = _sources(manifest["sources"])
    cases = _cases(manifest["cases"], sources)
    baseline = _evaluate(cases, sources, "baseline")
    candidate = _evaluate(cases, sources, "candidate")
    n = candidate["cases"]
    positive = candidate["answerable"]
    negative = candidate["no_answer"]
    reasons: list[str] = []
    decision = "inconclusive"
    if any(candidate["violations"].values()):
        reasons.append("Candidate exposed unknown, out-of-scope, unreviewed, inactive or stale evidence")
        decision = "reject"
    else:
        for metric in ("recall_at_5", "mrr_at_10", "abstain_accuracy"):
            prev, next_value = baseline[metric], candidate[metric]
            if prev is not None and next_value is not None and next_value + 1e-6 < prev:
                reasons.append("Candidate regressed " + metric)
                decision = "reject"
        b95, c95 = baseline["latency_ms"]["p95"], candidate["latency_ms"]["p95"]
        if c95 > b95 * 1.2 and c95 > b95 + 20:
            reasons.append("Candidate p95 retrieval latency regressed")
            decision = "reject"
        if decision != "reject":
            if (n < MIN_REVIEW_CASES or positive < MIN_REVIEW_POSITIVES
                    or negative < MIN_REVIEW_NEGATIVES):
                reasons.append("Too few independent positive/abstention cases to consider review")
            else:
                improved = (candidate["recall_at_5"] > baseline["recall_at_5"] + .049
                            or candidate["mrr_at_10"] > baseline["mrr_at_10"] + .019
                            or candidate["abstain_accuracy"] > baseline["abstain_accuracy"] + .099
                            or (b95 >= 30 and c95 <= b95 * .8))
                if improved:
                    decision = "candidate_for_owner_review"
                    reasons.append("Candidate improved an observed metric with no measured regressions")
                else:
                    reasons.append("No meaningful improvement over the baseline")
    return {
        "schema": "star-rag-evidence-gate-v1",
        "decision": decision,
        "reasons": reasons,
        "baseline": baseline,
        "candidate": candidate,
        "notes": [
            "Synthetic/mock retrieval predictions do not prove an operational backend.",
            "This gate does not run retrieval, inspect document text, train weights or alter STAR settings.",
            "Source SHA assertions originate from the operator's independent snapshot, not the model.",
            "A positive verdict requires separate sealed holdout and owner-native performance review.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STAR read-only RAG backend quality gate")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Existing, operator-reviewed JSON manifest of source IDs and retrieval outputs")
    args = parser.parse_args(argv)
    file = args.manifest
    try:
        if not file.is_file() or file.is_symlink() or not 0 < file.stat().st_size <= MAX_BYTES:
            raise ValueError("Choose a small, regular, non-symlink manifest")
        data = json.loads(file.read_text(encoding="utf-8"))
        print(json.dumps(compare(data), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError):
        # Never echo source identifiers, document text or user paths in logs.
        print("RAG quality gate: invalid or unavailable operator manifest", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
