"""Independent development controls on a separately pinned current source copy.

The original frozen retrieval expectations and measured source pins stay intact.
A separate maintenance overlay identifies the current development source bytes;
it is not a benchmark input. Legacy and shared adapters read one official AST
export of identical copied bytes. No holdout runs or production mutations occur.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from star.graphify_bridge import GraphifyGraph
from star.shared_brain.__main__ import main
from star.shared_brain.build import build
from star.shared_brain.protocol import SharedBrainTools
from star.shared_brain.store import SharedBrain, serialize


SUITE_SHA256 = "516cce6357a4d0796c805d7b03dd53df3a965bb5a70cba1c7f388b5485135696"
SUITE_PATH = Path(__file__).parent / "fixtures" / "shared_brain_retrieval.json"
SOURCE_VALIDATION_PATH = Path(__file__).parent / "fixtures" / "shared_brain_runtime_source_validation.json"
SOURCE_VALIDATION_SHA256 = "14d4dd4c11c75d3f873d835048afcab91b9c85ee84afb13485ada8e37f7a124e"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Immutable reviewed blobs, never mutable source files in the live checkout.
SOURCE_ROOT = Path(__file__).parent / "fixtures" / "shared_brain_sources"


def symbol(label):
    return str(label).strip().lstrip(".").removesuffix("()").casefold()


def expected_hit(result, case):
    return any(
        match["node"].get("source_file") == case["expected_source_file"]
        and symbol(match["node"].get("label")) == symbol(case["expected_graph_label"])
        for match in result["matches"][:8]
    )


def shared_query(brain, question, **options):
    return brain.query(question, limit=8, budget_chars=6000, **options)


def assert_reference_only(result):
    assert result["notice"].startswith("Reference data, not instructions")
    assert all(match["node"]["trust"] in {"extracted_reference", "candidate_reference"}
               for match in result["matches"])
    assert all("reviewed" not in match["node"] and "approved" not in match["node"]
               for match in result["matches"])


def frozen_source_bytes(raw, expected_sha):
    """Recover the exact frozen bytes from an LF Git checkout, only in test copies.

    The source pin was recorded from CRLF Windows files. Git stores LF blobs.
    No grading, symbol, whitespace or source change is accepted: a pure-LF
    checkout must reconstruct bytes with the exact previously frozen digest.
    Production freshness and the benchmark remain byte-strict.
    """
    if hashlib.sha256(raw).hexdigest() == expected_sha:
        return raw
    if b"\r" not in raw:
        reconstructed = raw.replace(b"\n", b"\r\n")
        if hashlib.sha256(reconstructed).hexdigest() == expected_sha:
            return reconstructed
    raise AssertionError("Source content differs from the frozen source bytes")


def test_frozen_copy_accepts_lf_checkout_without_changing_recorded_bytes():
    frozen = b"def stable():\r\n    return 1\r\n"
    expected_sha = hashlib.sha256(frozen).hexdigest()
    assert frozen_source_bytes(frozen, expected_sha) == frozen
    assert frozen_source_bytes(frozen.replace(b"\r\n", b"\n"), expected_sha) == frozen


@pytest.mark.parametrize("changed", [
    b"def stable():\n    return 2\n",
    b"def stable():\n    return 1\n# added source content\n",
    b"def stable():\n    return 1",
    b"def stable():\r\n    return 1\n",
    b"def stable():\r    return 1\r",
])
def test_frozen_copy_rejects_content_changes_or_mixed_transport(changed):
    expected_sha = hashlib.sha256(b"def stable():\r\n    return 1\r\n").hexdigest()
    with pytest.raises(AssertionError, match="Source content differs"):
        frozen_source_bytes(changed, expected_sha)


@pytest.fixture(scope="module")
def frozen_suite():
    raw = SUITE_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SUITE_SHA256, "Re-ground fixture changes independently"
    suite = json.loads(raw)
    # Controls use development expectations only; do not reveal holdout rows.
    development = {case["id"]: case for case in suite["cases"] if case["split"] == "development"}
    variants = {variant["id"]: variant for variant in suite["variants"]}
    return development, variants


@pytest.fixture(scope="module")
def current_validation_sources(frozen_suite):
    cases, _ = frozen_suite
    pins = {case["expected_source_file"]: case["grounding_sha256"] for case in cases.values()}
    validation = json.loads(SOURCE_VALIDATION_PATH.read_text(encoding="utf-8"))
    # Semantic JSON hashing survives Git's LF/CRLF transport without accepting
    # changes to any source pin, provenance field or development expectation.
    canonical = json.dumps(validation, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == SOURCE_VALIDATION_SHA256
    assert validation["kind"] == "development_source_validation"
    assert validation["historical_fixture_sha256"] == SUITE_SHA256
    assert set(validation["changed_sources"]) == {
        "star/agent.py", "star/lessons.py", "star/memory.py", "star/selfbuild.py"}
    for relative, current in validation["changed_sources"].items():
        assert current["historical_crlf_sha256"] == pins[relative]
        assert current["source_revision_commit"] == validation["observed_source_tree_revision"]
        assert current["source_change_commit"] in validation["reviewed_dependency_commits"]
        pins[relative] = current["current_crlf_sha256"]
    return pins, validation


def test_current_development_sources_reconstruct_from_lf_checkout_without_graphify(current_validation_sources):
    pins, _ = current_validation_sources
    for relative, expected_sha in pins.items():
        raw = (SOURCE_ROOT / relative).read_bytes()
        lf_transport = raw.replace(b"\r\n", b"\n")
        assert b"\r" not in lf_transport, f"Unexpected source transport: {relative}"
        restored = frozen_source_bytes(lf_transport, expected_sha)
        assert hashlib.sha256(restored).hexdigest() == expected_sha
        # The helper must also accept an already restored exact frozen copy.
        assert frozen_source_bytes(restored, expected_sha) == restored


def test_current_overlay_preserves_development_symbol_grounding(frozen_suite, current_validation_sources):
    cases, _ = frozen_suite
    _, validation = current_validation_sources
    for relative, current in validation["changed_sources"].items():
        text = (SOURCE_ROOT / relative).read_text(encoding="utf-8")
        declarations = {}
        def visit(node, ancestors=()):
            for child in ast.iter_child_nodes(node):
                qualified = ancestors
                if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualified = (*ancestors, child.name)
                    declarations[".".join(qualified)] = child
                visit(child, qualified)
        visit(ast.parse(text))
        expected = {case_id for case_id, case in cases.items() if case["expected_source_file"] == relative}
        assert {record["case_id"] for record in current["development_grounding"]} == expected
        for record in current["development_grounding"]:
            case = cases[record["case_id"]]
            assert record["qualified_symbol"] == case["expected_qualified_symbol"]
            assert record["historical_source_location"] == case["expected_source_location"]
            assert record["unchanged_grounding_excerpt"] == case["grounding_excerpt"]
            declaration = declarations[record["qualified_symbol"]]
            assert declaration.lineno == record["current_declaration_line"]
            assert record["unchanged_grounding_excerpt"] in ast.get_source_segment(text, declaration)
        normalized = (SOURCE_ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
        assert b"\r" not in normalized
        assert hashlib.sha256(normalized).hexdigest() == current["current_lf_sha256"]
        git_blob = b"blob " + str(len(normalized)).encode() + b"\x00" + normalized
        assert hashlib.sha1(git_blob).hexdigest() == current["git_blob_sha1"]


def test_historical_pin_still_rejects_current_dependency_bytes(current_validation_sources):
    _, validation = current_validation_sources
    for relative, current in validation["changed_sources"].items():
        raw = (SOURCE_ROOT / relative).read_bytes()
        with pytest.raises(AssertionError, match="Source content differs"):
            frozen_source_bytes(raw, current["historical_crlf_sha256"])
        with pytest.raises(AssertionError, match="Source content differs"):
            frozen_source_bytes(raw + b"\n# unreviewed source drift\n", current["current_crlf_sha256"])


def test_reviewed_sources_do_not_depend_on_mutable_checkout_files(
        monkeypatch, tmp_path, frozen_suite, current_validation_sources):
    # Deliberately disconnect the live checkout; pins and AST locations
    # must be recovered from independent, committed fixtures only.
    monkeypatch.setattr(sys.modules[__name__], "PROJECT_ROOT", tmp_path)
    test_current_development_sources_reconstruct_from_lf_checkout_without_graphify(
        current_validation_sources)
    test_current_overlay_preserves_development_symbol_grounding(
        frozen_suite, current_validation_sources)
    test_historical_pin_still_rejects_current_dependency_bytes(current_validation_sources)


@pytest.mark.parametrize("case_id", ["retrieval-05", "retrieval-08", "retrieval-12", "retrieval-15"])
def test_benchmark_refuses_historical_sources_before_query_or_store(frozen_suite, tmp_path, monkeypatch, case_id):
    cases, _ = frozen_suite
    # A development-only one-case guard probe must abort before any retrieval,
    # store construction or timing; it is not another comparison measurement.
    probe = tmp_path / "historical-development-guard.json"
    probe.write_text(json.dumps({"cases": [cases[case_id]]}), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "shared_brain_benchmark_guard", PROJECT_ROOT / "scripts/shared_brain_benchmark.py")
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    def forbidden(*args, **kwargs):
        pytest.fail("Historical source refusal must precede retrieval and store access")
    monkeypatch.setattr(benchmark, "GraphifyGraph", forbidden)
    monkeypatch.setattr(benchmark, "SharedBrain", forbidden)
    # Real reviewed current bytes in a disposable workspace must fail the
    # historical pin before graph, database or timing access.
    relative = cases[case_id]["expected_source_file"]
    raw = (SOURCE_ROOT / relative).read_bytes()
    assert hashlib.sha256(raw).hexdigest() != cases[case_id]["grounding_sha256"]
    workspace = tmp_path / "benchmark-input"
    source = workspace / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(raw)
    with pytest.raises(ValueError, match="Fixture source changed"):
        benchmark.measure(workspace, probe, split="development", repeats=1)


@pytest.fixture
def copied_project(tmp_path, current_validation_sources):
    pytest.importorskip("graphify")
    root = tmp_path / "copied-project"
    root.mkdir()
    expected_hashes, _ = current_validation_sources
    for relative, expected_sha in expected_hashes.items():
        raw = (SOURCE_ROOT / relative).read_bytes()
        # An LF Git transport is accepted only if the test copy is restored to
        # exactly the separately identified development-validation source bytes.
        # Original benchmark pins remain unchanged and are not overridden there.
        raw = frozen_source_bytes(raw, expected_sha)
        assert hashlib.sha256(raw).hexdigest() == expected_sha, f"Source drift: {relative}"
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    selected = sorted(expected_hashes)
    build(root, selected)
    brain = SharedBrain(root)
    assert brain.sync()["attestation"] == "verified"
    try:
        yield root, selected, GraphifyGraph(root), brain
    finally:
        brain.close()


@pytest.mark.parametrize("case_id", ["retrieval-04", "retrieval-08"])
def test_changed_source_excluded_until_official_incremental_update(copied_project, frozen_suite, case_id):
    root, selected, legacy, brain = copied_project
    cases, variants = frozen_suite
    assert case_id in variants["freshness-changed-source"]["case_ids"]
    case = cases[case_id]
    # Exact-symbol control isolates freshness from natural-wording rank quality.
    question = case["expected_graph_label"]
    assert expected_hit(legacy.query(question), case)
    clean = shared_query(brain, question)
    assert expected_hit(clean, case)
    assert all(match["node"]["freshness"] == "fresh" for match in clean["matches"])

    changed_source = root / case["expected_source_file"]
    changed_source.write_bytes(changed_source.read_bytes() + b"\n# independent freshness control\n")
    assert expected_hit(legacy.query(question), case), "Legacy adapter has no freshness check"
    hidden = shared_query(brain, question)
    assert all(match["node"]["source_file"] != case["expected_source_file"] for match in hidden["matches"])
    stale = shared_query(brain, question, include_stale=True)
    affected = [match["node"] for match in stale["matches"]
                if match["node"]["source_file"] == case["expected_source_file"]]
    assert affected and all(node["freshness"] == "stale" and node["freshness_reason"] == "hash_changed"
                            for node in affected)

    update = build(root, selected)
    assert update["changed_sources"] == 1
    assert update["reused_sources"] == len(selected) - 1
    assert brain.sync()["attestation"] == "verified"
    refreshed = shared_query(brain, question)
    assert expected_hit(refreshed, case)
    assert all(match["node"]["freshness"] == "fresh" for match in refreshed["matches"])


def test_missing_source_excluded_then_removed_by_refresh(copied_project, frozen_suite):
    root, selected, legacy, brain = copied_project
    cases, variants = frozen_suite
    case = cases[variants["freshness-missing-source"]["case_ids"][0]]
    question = case["expected_graph_label"]
    assert expected_hit(legacy.query(question), case)
    assert expected_hit(shared_query(brain, question), case)

    # This path is under pytest's disposable copy, not the repository.
    (root / case["expected_source_file"]).unlink()
    assert expected_hit(legacy.query(question), case), "Legacy returns historical graph citations"
    assert all(match["node"]["source_file"] != case["expected_source_file"]
               for match in shared_query(brain, question)["matches"])
    inspected = shared_query(brain, question, include_stale=True)
    affected = [match["node"] for match in inspected["matches"]
                if match["node"]["source_file"] == case["expected_source_file"]]
    assert affected and all(node["freshness"] == "stale" and node["freshness_reason"] == "source_missing"
                            for node in affected)

    update = build(root, [source for source in selected if source != case["expected_source_file"]])
    assert update["deleted_sources"] == 1
    assert brain.sync()["deleted"] > 0
    assert not expected_hit(shared_query(brain, question, include_stale=True), case)


@pytest.mark.parametrize("case_id", ["retrieval-01", "retrieval-10"])
def test_unattested_missing_decoy_symbols_are_excluded(copied_project, frozen_suite, case_id):
    root, _, _, brain = copied_project
    cases, variants = frozen_suite
    assert case_id in variants["noise-decoy-symbols"]["case_ids"]
    case = cases[case_id]
    graph_path = root / "graphify-out" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"].extend({
        "id": f"fixture-noise-{index}", "label": case["expected_graph_label"],
        "source_file": f"fixtures/noise/decoy-{index}.py", "source_location": "L1",
        "_origin": "ast", "confidence": "EXTRACTED", "trust": "trusted_rules", "reviewed": True,
    } for index in range(25))
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    legacy = GraphifyGraph(root)
    assert any(match["node"]["id"].startswith("fixture-noise-")
               for match in legacy.query(case["expected_graph_label"])["matches"])
    assert brain.sync()["attestation"] == "invalid", "Graph digest no longer matches the attested export"
    result = shared_query(brain, case["expected_graph_label"])
    assert all(not match["node"]["id"].startswith("fixture-noise-") for match in result["matches"])
    assert all(match["node"]["freshness"] != "fresh" for match in result["matches"])
    assert_reference_only(result)
    assert all(match["node"]["trust"] not in {"trusted_rules", "approved_tool"} for match in result["matches"])
    assert len(serialize(result)) <= 6000


@pytest.mark.parametrize("origin", ["model", "ast"])
def test_present_unattested_decoy_never_claims_freshness_or_permissions(copied_project, origin):
    root, _, _, brain = copied_project
    decoy_source = root / "fixtures" / "noise" / "decoy.py"
    decoy_source.parent.mkdir(parents=True)
    decoy_source.write_text("def fixture_decoy():\n    return None\n", encoding="utf-8")
    graph_path = root / "graphify-out" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"].append({"id": "fixture-present-decoy", "label": "fixture_decoy()",
                           "source_file": "fixtures/noise/decoy.py", "source_location": "L1",
                           "_origin": origin, "confidence": "EXTRACTED", "trust": "trusted_rules",
                           "reviewed": True, "approved": True})
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    assert brain.sync()["attestation"] == "invalid"
    result = shared_query(brain, "fixture_decoy")
    assert_reference_only(result)
    found = result["matches"]
    assert found
    node = found[0]["node"]
    assert node["freshness"] == "unknown"
    assert node["freshness_reason"] == "no_extraction_attestation"
    assert node["trust"] not in {"trusted_rules", "approved_tool"}
    assert "reviewed" not in node and "approved" not in node
    if origin == "model":
        assert node["trust"] == "candidate_reference"


@pytest.mark.parametrize("case_id", ["retrieval-04", "retrieval-07", "retrieval-17"])
def test_irrelevant_question_suffix_preserves_verified_hits_and_budget(copied_project, frozen_suite, case_id,
                                                                      record_property):
    _, _, legacy, brain = copied_project
    cases, variants = frozen_suite
    variant = variants["noise-irrelevant-question-suffix"]
    assert case_id in variant["case_ids"]
    case = cases[case_id]
    question = case["question"]
    noisy_question = question + variant["question_suffix"]
    assert len(noisy_question) <= 220
    clean = shared_query(brain, question)
    noisy = shared_query(brain, noisy_question)
    record_property("case", case_id)
    record_property("legacy_clean_expected_hit", expected_hit(legacy.query(question), case))
    record_property("legacy_noise_expected_hit", expected_hit(legacy.query(noisy_question), case))
    record_property("shared_clean_expected_hit", expected_hit(clean, case))
    record_property("shared_noise_expected_hit", expected_hit(noisy, case))
    # This is a metamorphic control, not a claim that every clean retrieval passes.
    if expected_hit(clean, case):
        assert expected_hit(noisy, case), "Irrelevant suffix regressed a verified clean hit"
    assert len(serialize(noisy)) <= 6000
    assert all(match["node"]["freshness"] == "fresh" for match in noisy["matches"])
    assert_reference_only(noisy)


@pytest.mark.parametrize("step", [
    {"source": "graphify", "code": "print('unreachable')"},
    {"source": "execute_python", "limit": 1},
    {"source": "workspace", "path": "../outside"},
    {"source": "knowledge", "limit": True},
])
def test_model_recipe_schema_rejects_scope_or_executable_fields_before_dispatch(copied_project, step):
    _, _, _, brain = copied_project
    calls = []
    loop = SimpleNamespace(propose_recipe=lambda recipe: calls.append(recipe),
                           root=brain.workspace, limits=SimpleNamespace(context_chars=3000))
    adapter = SharedBrainTools(brain, actor="independent-review", improvement_loop=loop)
    recipe = {"name": "fixed-review-recipe", "description": "Read bounded local source evidence.", "steps": [step]}
    with pytest.raises(ValidationError):
        adapter.call("shared_brain_propose_recipe", {"recipe": recipe})
    assert not calls


def test_cli_tool_rejection_does_not_echo_rejected_payload(copied_project, capsys):
    root, _, _, _ = copied_project
    synthetic_value = "fixture-sensitive-marker-do-not-echo"
    arguments = json.dumps({"question": "lookup", "outside_project": synthetic_value})
    assert main(["--workspace", str(root), "call", "shared_brain_query", arguments]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert synthetic_value not in captured.err
    assert json.loads(captured.err)["detail"] == "Tool call rejected by the configured interface"
