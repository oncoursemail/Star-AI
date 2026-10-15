"""OMEGA regressions: genuine project isolation, bounded retrieval, predicted tests, no execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from star.knowledge import KnowledgeStore
from star.omega import main as omega_main
from star.omega_hyperindex import HyperIndex
from star.roblox_project_preflight import MAX_CHECK_SOURCE_BYTES, main as preflight_main, preflight


def _store(tmp_path: Path) -> tuple[Path, KnowledgeStore]:
    root = tmp_path / "memory"
    return root, KnowledgeStore(root)


def _project(tmp_path: Path, code: str) -> Path:
    root = tmp_path / "game"
    server = root / "ServerScriptService"
    server.mkdir(parents=True)
    (server / "Main.server.luau").write_text(code, encoding="utf-8")
    return root


def test_hyperindex_reviewed_scope_exact_symbol_and_external_ids(tmp_path):
    root, store = _store(tmp_path)
    good = store.add_note(
        project="alpha", kind="fix",
        text="DataStoreService:UpdateAsync needs retries and idempotent updates",
        source="checked:tests/example", revision="v1")
    store.review_note(project="alpha", note_id=good, evidence="independent-test-1")
    outside = store.add_note(
        project="beta", kind="fix",
        text="DataStoreService:UpdateAsync secret separate project solution",
        source="checked:other-project")
    store.review_note(project="beta", note_id=outside, evidence="independent-test-2")
    candidate = store.add_note(
        project="alpha", kind="fix",
        text="DataStoreService:UpdateAsync unverified candidate from an AI",
        source="unverified")
    with HyperIndex(root) as index:
        result = index.search("alpha", "DataStoreService:UpdateAsync",
                              semantic_note_ids=[outside, candidate, good, good])
    store.close()
    assert result["status"] == "ok"
    assert [hit["note_id"] for hit in result["hits"]] == [good]
    assert result["hits"][0]["matched_exact_identifier"]
    assert result["hits"][0]["ranked_by_external_semantics"]
    assert result["hits"][0]["reviewed"] is True
    assert "validated-external-ranks" in result["coverage"]


def test_hyperindex_query_not_fts_injection_and_readonly(tmp_path):
    root, store = _store(tmp_path)
    accepted = store.add_note(project="alpha", kind="fact", text="Fix RemoteEvent authorization",
                              source="operator:manual")
    store.review_note(project="alpha", note_id=accepted, evidence="confirmed")
    store.close()
    db_file = root / "knowledge.sqlite3"
    before = hashlib.sha256(db_file.read_bytes()).hexdigest()
    with HyperIndex(root) as index:
        assert index.search("alpha", '" OR )  RemoteEvent !')["status"] == "ok"
        with pytest.raises(ValueError):
            index.search("alpha", "RemoteEvent", semantic_note_ids=[-1])
        with pytest.raises(ValueError):
            index.search("../another", "RemoteEvent")
        with pytest.raises(ValueError):
            index.search("alpha", "x" * 801)
    assert hashlib.sha256(db_file.read_bytes()).hexdigest() == before


def test_hyperindex_explicitly_limited_fallback_without_fts(tmp_path):
    root = tmp_path / "legacy"
    root.mkdir()
    con = sqlite3.connect(root / "knowledge.sqlite3")
    con.execute(
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, project TEXT, kind TEXT, text TEXT, "
        "source TEXT, revision TEXT, reviewed INTEGER, created TEXT)"
    )
    con.execute("INSERT INTO notes VALUES (1,'one','fix','retry queue','test','v1',1,'now')")
    con.execute("INSERT INTO notes VALUES (2,'one','fix','retry queue','test','v1',0,'now')")
    con.commit()
    con.close()
    with HyperIndex(root) as index:
        result = index.search("one", "retry")
    assert result["coverage"] == "recent-only-fallback"
    assert [hit["note_id"] for hit in result["hits"]] == [1]
    assert "newest" in " ".join(result["limitations"])


def test_hyperindex_missing_store_does_not_create_one(tmp_path):
    root = tmp_path / "no_store"
    with pytest.raises(FileNotFoundError):
        HyperIndex(root)
    assert not root.exists()


def test_omega_search_cli_returns_json_without_writes(tmp_path, capsys):
    root, store = _store(tmp_path)
    note = store.add_note(project="studio", kind="fix", text="Clean connections on respawn",
                          source="test:respawn", revision="v1")
    store.review_note(project="studio", note_id=note, evidence="verified")
    store.close()
    assert omega_main(["search", str(root), "studio", "respawn"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hits"][0]["note_id"] == note
    assert omega_main(["search", str(tmp_path / "missing"), "studio", "respawn"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"


def test_futuresight_optin_keeps_existing_preflight_default_unchanged(tmp_path):
    code = ("local remote = game:GetService('ReplicatedStorage').Reward\n"
            "remote.OnServerEvent:Connect(function(player, amount)\n"
            "    coins.Value += amount\n"
            "end)\n")
    root = _project(tmp_path, code)
    baseline = preflight(root)
    assert "futuresight" not in baseline
    version = preflight(root, futuresight=True)
    assert {k: v for k, v in version.items() if k != "futuresight"} == baseline
    future = version["futuresight"]
    assert future["tests_executed"] == 0 and future["failures_proven"] == 0
    assert future["source_coverage"] == "partial"
    categories = {c["category"] for c in future["cases"]}
    assert "remote-inputs" in categories
    assert "server-trust-diagnostic" in categories
    assert all(c["status"] == "proposed-not-run" and not c["proof_of_failure"]
               for c in future["cases"])
    assert future["limitations"]


def test_futuresight_comment_and_string_are_not_false_usage_signals(tmp_path):
    root = _project(tmp_path,
                    'print("OnServerEvent UpdateAsync PlayerRemoving")\n'
                    '-- OnServerInvoke TeleportAsync\n')
    report = preflight(root, futuresight=True)
    assert not any(c["evidence_type"] == "source-api-use"
                   for c in report["futuresight"]["cases"])


def test_futuresight_datastore_and_missing_static_require_are_advisories(tmp_path):
    root = _project(tmp_path,
                    'local d = game:GetService("DataStoreService"):GetDataStore("Saved")\n'
                    'd:UpdateAsync("p", function(prev) return prev end)\n'
                    'local x = require(script.DoesNotExist)\n')
    result = preflight(root, futuresight=True, module_requires=True)
    cases = result["futuresight"]["cases"]
    assert "data-persistence" in {c["category"] for c in cases}
    assert "missing-require" in {c["category"] for c in cases}
    assert any("static-require-graph" == c["evidence_type"] for c in cases)
    assert result["futuresight"]["tests_executed"] == 0


def test_futuresight_oversized_source_is_explicitly_unchecked(tmp_path):
    root = _project(tmp_path, "-- " + ("x" * (MAX_CHECK_SOURCE_BYTES + 2)) + " OnServerEvent\n")
    future = preflight(root, futuresight=True)["futuresight"]
    assert not future["cases"]
    assert any("budget" in row["reason"] for row in future["unchecked"])
    assert future["source_coverage"] == "partial"


def test_futuresight_links_only_reviewed_project_fixes(tmp_path):
    root, store = _store(tmp_path)
    trusted = store.add_note(project="shop", kind="fix",
                             text="OnServerEvent remote inputs must be bounded by server validation",
                             source="test:secure-remote", revision="shop-r1")
    store.review_note(project="shop", note_id=trusted, evidence="test-pass")
    foreign = store.add_note(project="other", kind="fix",
                             text="OnServerEvent remote inputs unapproved account",
                             source="test:foreign")
    store.review_note(project="other", note_id=foreign, evidence="test-pass")
    store.close()
    project = _project(tmp_path, "remote.OnServerEvent:Connect(function(player) end)\n")
    report = preflight(project, futuresight=True, knowledge_root=root, project="shop")
    future = report["futuresight"]
    assert future["knowledge"] == "reviewed-project-evidence-only"
    notes = [v for c in future["cases"] for v in c.get("historical_evidence", [])]
    assert notes and all(v["note_id"] == trusted for v in notes)


def test_futuresight_stable_json_cli_and_no_project_modification(tmp_path, capsys):
    root = _project(tmp_path, "remote.OnServerEvent:Connect(function(player) end)\n")
    script = root / "ServerScriptService" / "Main.server.luau"
    before = hashlib.sha256(script.read_bytes()).hexdigest()
    command = [str(root), "--futuresight", "--module-requires"]
    rc = preflight_main(command)
    first = capsys.readouterr().out
    assert rc == 1  # Without an API dump this remains partial coverage.
    assert preflight_main(command) == rc
    assert capsys.readouterr().out == first
    assert hashlib.sha256(script.read_bytes()).hexdigest() == before
    report = json.loads(first)
    assert report["futuresight"]["status"] == "suggestions"
    assert "futuresight" not in preflight(root)


def test_futuresight_unavailable_evidence_disclosed_not_silently_trusted(tmp_path):
    root = _project(tmp_path, "remote.OnServerEvent:Connect(function(player) end)\n")
    future = preflight(root, futuresight=True, knowledge_root=tmp_path / "absent",
                       project="shop")["futuresight"]
    assert future["knowledge"] == "existing-knowledge-index-unavailable"
    assert all(not c.get("historical_evidence") for c in future["cases"])
