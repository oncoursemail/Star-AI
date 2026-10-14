"""Offline synthetic evidence checks for STAR's backend-neutral RAG quality gate.

No installed vector database, model calls, private user data or external API
is involved. The test only validates scoring, project isolation, source
freshness, safe abstention and the explicit human-review decision boundary.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from star.rag_quality import MAX_BYTES, compare, main


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def manifest() -> dict:
    """16 independent answerable cases + 4 no-answer cases in two projects."""
    sources = []
    cases = []
    for index in range(1, 21):
        project = "SpaceGame" if index % 2 else "R6Obby"
        identity = f"doc-{index}"
        revision = digest(f"revision-{index}")
        sources.append({"id": identity, "project": project, "sha256": revision,
                        "reviewed": True, "active": True})
        expected = [identity] if index <= 16 else []
        correct = {"id": identity, "sha256": revision}
        # Four misses in the old BM25 baseline. Candidate finds all verified docs.
        base_hits = [correct] if index <= 12 else []
        new_hits = [correct] if index <= 16 else []
        cases.append({
            "id": f"question-{index}", "project": project, "expected": expected,
            "baseline": {"latency_ms": 200, "hits": base_hits},
            "candidate": {"latency_ms": 125, "hits": new_hits},
        })
    return {"version": 1, "sources": sources, "cases": cases}


def test_retrieval_quality_returns_aggregate_metrics_and_review_only():
    data = manifest()
    report = compare(data)
    assert report["decision"] == "candidate_for_owner_review"
    assert report["baseline"]["answerable"] == 16
    assert report["candidate"]["no_answer"] == 4
    assert report["baseline"]["recall_at_5"] == 0.75
    assert report["candidate"]["recall_at_5"] == 1.0
    assert report["candidate"]["mrr_at_10"] == 1.0
    assert report["candidate"]["abstain_accuracy"] == 1.0
    assert report["candidate"]["latency_ms"]["p95"] == 125
    assert all(x == 0 for x in report["candidate"]["violations"].values())
    text = json.dumps(report)
    assert "doc-1" not in text and "SpaceGame" not in text and "question-1" not in text
    assert "train weights" in text and "source" in text.lower()
    assert data == manifest()   # Eval never edits source manifests or fixture data.


def test_candidate_cross_project_retrieval_must_be_rejected_even_with_perfect_recall():
    data = manifest()
    case = data["cases"][0]
    foreign = data["sources"][1]
    case["candidate"]["hits"].append({"id": foreign["id"], "sha256": foreign["sha256"]})
    report = compare(data)
    assert report["decision"] == "reject"
    assert report["candidate"]["violations"]["cross_project"] == 1
    assert report["candidate"]["recall_at_5"] == 1.0


@pytest.mark.parametrize("failure", ["stale_revision", "unknown_source", "unreviewed", "inactive"])
def test_stale_or_untrusted_citations_are_never_rewarded(failure):
    data = manifest()
    hit = data["cases"][0]["candidate"]["hits"][0]
    if failure == "stale_revision":
        hit["sha256"] = digest("outdated")
    elif failure == "unknown_source":
        hit["id"] = "doc-missing"
    elif failure in {"unreviewed", "inactive"}:
        data["sources"].append({
            "id": "side-source", "project": "SpaceGame", "sha256": digest("other"),
            "reviewed": failure != "unreviewed",
            "active": failure != "inactive",
        })
        data["cases"][0]["candidate"]["hits"].append(
            {"id": "side-source", "sha256": digest("other")})
    result = compare(data)
    assert result["decision"] == "reject"
    assert result["candidate"]["violations"][failure] == 1


def test_negative_questions_require_abstention_and_cannot_be_won_by_unrelated_citations():
    data = manifest()
    negative = data["cases"][-1]
    related = data["sources"][19]
    negative["candidate"]["hits"] = [{"id": related["id"], "sha256": related["sha256"]}]
    result = compare(data)
    assert result["decision"] == "reject"
    assert result["candidate"]["abstain_accuracy"] == 0.75
    assert result["candidate"]["recall_at_5"] == 1.0


def test_quality_or_p95_regression_is_rejected_even_when_one_metric_improves():
    data = manifest()
    data["cases"][0]["candidate"]["hits"] = []
    data["cases"][1]["candidate"]["hits"] = []
    data["cases"][2]["candidate"]["hits"] = []
    data["cases"][3]["candidate"]["hits"] = []
    data["cases"][4]["candidate"]["hits"] = []
    assert compare(data)["decision"] == "reject"
    slow = manifest()
    slow["cases"][-1]["candidate"]["latency_ms"] = 120_000
    result = compare(slow)
    assert result["decision"] == "reject"
    assert result["candidate"]["latency_ms"]["p95"] == 125
    # p95 is robust to one very slow tail in 20 examples. With more
    # than 5% of cases slow, p95 should detect a tail latency regression.
    slow["cases"][-2]["candidate"]["latency_ms"] = 120_000
    assert compare(slow)["decision"] == "reject"


def test_requires_sufficient_paired_cases_and_rejects_weak_or_identical_tweaks():
    few = manifest()
    few["cases"] = few["cases"][:5]
    assert compare(few)["decision"] == "inconclusive"
    identical = manifest()
    for case in identical["cases"]:
        case["candidate"] = deepcopy(case["baseline"])
    assert compare(identical)["decision"] == "inconclusive"


def test_baseline_violations_do_not_hide_that_a_candidate_is_safer():
    data = manifest()
    old = data["cases"][0]["baseline"]
    old["hits"].append({"id": "doc-2", "sha256": data["sources"][1]["sha256"]})
    result = compare(data)
    assert result["baseline"]["violations"]["cross_project"] == 1
    assert result["candidate"]["violations"]["cross_project"] == 0
    assert result["decision"] == "candidate_for_owner_review"


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(version=True),
    lambda x: x.update(version=2),
    lambda x: x.update(executable="python -c unsafe"),
    lambda x: x["sources"].append(deepcopy(x["sources"][0])),
    lambda x: x["cases"].append(deepcopy(x["cases"][0])),
    lambda x: x["cases"][0].update(project="../secret"),
    lambda x: x["cases"][0].update(expected=["doc-2"]),
    lambda x: x["sources"][0].update(reviewed=1),
    lambda x: x["sources"][0].update(active=None),
    lambda x: x["sources"][0].update(sha256="bad"),
    lambda x: x["cases"][0]["candidate"].update(latency_ms=True),
    lambda x: x["cases"][0]["candidate"].update(latency_ms=-1),
    lambda x: x["cases"][0]["candidate"].update(latency_ms=200000),
    lambda x: x["cases"][0]["candidate"]["hits"].append({"id": "https://evil.com", "sha256": digest("x")}),
    lambda x: x["cases"][0]["candidate"]["hits"].append({"id": "doc-1", "sha256": x["sources"][0]["sha256"]}),
    lambda x: x["cases"][0]["candidate"]["hits"].append({"id": "doc-3", "sha256": "0"*64, "path": "../../private"}),
    lambda x: x["cases"][0].update(expected=["doc-1", "doc-1"]),
    lambda x: x["cases"][0].update(expected=[{"unhashable": "bad"}]),
    lambda x: x["cases"][0].update(id="test\nnewline"),
    lambda x: x["cases"][0]["candidate"].update(hits=[{"id": "x", "sha256": "0"*64}] * 21),
])
def test_invalid_untrusted_rag_manifest_is_rejected(mutate):
    data = manifest()
    mutate(data)
    with pytest.raises((ValueError, TypeError)):
        compare(data)


def test_too_many_cases_or_sources_or_bytes_cannot_amplify_untrusted_input():
    data = manifest()
    data["cases"] = data["cases"] * 13
    with pytest.raises(ValueError):
        compare(data)
    too_big = manifest()
    too_big["file_text"] = "PRIVATE_USER_DOC" * 100000
    with pytest.raises(ValueError):
        compare(too_big)


def test_cli_reads_only_operator_file_returns_redacted_aggregate(tmp_path, capsys):
    path = tmp_path / "frozen-retrieval.json"
    data = manifest()
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--manifest", str(path)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["decision"] == "candidate_for_owner_review"
    assert "SpaceGame" not in out and "doc-1" not in out
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"trick": "SECRET_USER_DATA"}')
    assert main(["--manifest", str(invalid)]) == 2
    errors = capsys.readouterr().err
    assert "SECRET_USER_DATA" not in errors and str(invalid) not in errors
    link = tmp_path / "link.json"
    try:
        link.symlink_to(path)
    except (OSError, NotImplementedError):
        pytest.skip("Host disallows symlink creation")
    assert main(["--manifest", str(link)]) == 2


def test_explicitly_synthetic_example_is_valid_but_not_real_retrieval_proof():
    from pathlib import Path
    file = Path(__file__).resolve().parents[1] / "examples" / "rag" / "synthetic_quality_fixture.json"
    result = compare(json.loads(file.read_text(encoding="utf-8")))
    assert result["decision"] == "candidate_for_owner_review"
    assert result["candidate"]["cases"] == 20
    assert "Synthetic/mock retrieval predictions" in result["notes"][0]
