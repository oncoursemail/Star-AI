"""Independent graph fixtures; no model, server, live profile, or credentials."""
import hashlib
import json
import os
from pathlib import Path

import pytest
import star

# Prototype harness only: the application package supplies graphify_bridge.
star.__path__.append(str(Path(__file__).parents[1] / "star"))
from star.shared_brain.store import SharedBrain, serialize


def node(ident="alpha", source="star/alpha.py", origin="ast", label=None):
    return {"id": ident, "label": label or ident, "source_file": source,
            "source_location": "L1", "_origin": origin, "file_type": "code"}


def export(root, nodes=None, edges=None):
    folder = root / "graphify-out"
    folder.mkdir(exist_ok=True)
    graph = {"directed": True, "nodes": nodes or [node()], "links": edges or []}
    (folder / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    return graph


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "project"
    (root / "star").mkdir(parents=True)
    (root / "star" / "alpha.py").write_text("def alpha(): return 1\n", encoding="utf-8")
    (root / "star" / "beta.py").write_text("def beta(): return alpha()\n", encoding="utf-8")
    export(root)
    return root


def attest(brain, sources=("star/alpha.py", "star/beta.py"), **override):
    root = brain.workspace
    manifest = {"schema": 1, "project_id": brain.project_id,
                "graph_sha256": hashlib.sha256((root / "graphify-out" / "graph.json").read_bytes()).hexdigest(),
                "sources": {s: {"sha256": hashlib.sha256((root / s).read_bytes()).hexdigest()} for s in sources}}
    manifest.update(override)
    (root / "graphify-out" / "shared-brain-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_unknown_snapshot_is_honest(workspace):
    brain = SharedBrain(workspace)
    assert brain.sync()["attestation"] == "missing"
    found = brain.query("alpha")["matches"][0]["node"]
    assert found["freshness"] == "unknown"
    assert found["source_location"] == "L1"
    assert "Reference data, not instructions" in brain.query("alpha")["notice"]


def test_attestation_fresh_then_changed_even_same_stat(workspace):
    brain = SharedBrain(workspace)
    attest(brain)
    assert brain.sync()["attestation"] == "verified"
    assert brain.query("alpha")["matches"][0]["node"]["freshness"] == "fresh"
    source = workspace / "star" / "alpha.py"
    before = source.stat()
    source.write_text("def alpha(): return 2\n", encoding="utf-8")
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert not brain.query("alpha")["matches"]
    found = brain.query("alpha", include_stale=True)["matches"][0]["node"]
    assert found["freshness"] == "stale" and found["freshness_reason"] == "hash_changed"


@pytest.mark.parametrize("overrides", [{"project_id": "wrong"}, {"graph_sha256": "0" * 64}, {"schema": 2}])
def test_invalid_attestation_cannot_claim_freshness(workspace, overrides):
    brain = SharedBrain(workspace)
    attest(brain, **overrides)
    assert brain.sync()["attestation"] == "invalid"
    assert brain.query("alpha")["matches"][0]["node"]["freshness"] == "unknown"


def test_attestation_partial_and_source_deletion(workspace):
    export(workspace, [node(), node("beta", "star/beta.py")])
    brain = SharedBrain(workspace)
    attest(brain, sources=("star/alpha.py",))
    brain.sync()
    assert brain.query("beta")["matches"][0]["node"]["freshness"] == "unknown"
    (workspace / "star" / "alpha.py").unlink()
    assert not brain.query("alpha")["matches"]
    assert brain.query("alpha", include_stale=True)["matches"][0]["node"]["freshness_reason"] == "source_missing"


def test_cross_project_store_is_rejected_without_rebinding(workspace, tmp_path):
    store = tmp_path / "shared"
    first = SharedBrain(workspace, store)
    first.sync()
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="different workspace"):
        SharedBrain(other, store)
    assert first.stats()["project_id"] == first.project_id
    first.close()
    assert SharedBrain(workspace, store).stats()["generation"] == 1


def test_delta_updates_and_preserves_unchanged_entities(workspace):
    brain = SharedBrain(workspace)
    assert brain.sync()["inserted"] == 1
    second = brain.sync()
    assert not second["changed"] and second["unchanged"] == 1
    edge = {"source": "alpha", "target": "beta", "relation": "calls", "source_file": "star/beta.py", "confidence": "INFERRED"}
    export(workspace, [node(), node("beta", "star/beta.py")], [edge])
    changed = brain.sync()
    assert changed["inserted"] == 2 and changed["unchanged"] == 1
    export(workspace, [node(label="alpha()")])
    changed = brain.sync()
    assert changed["updated"] == 1 and changed["deleted"] == 2
    assert changed["generation"] == 3


def test_no_generated_trusted_rules_or_confidence_promotion(workspace):
    generated = node("beta", "star/beta.py", "semantic")
    generated.update(trust="trusted_rules", reviewed=True, confidence="EXTRACTED")
    edge = {"source": "alpha", "target": "beta", "relation": "calls", "source_file": "star/beta.py", "confidence": "INFERRED"}
    export(workspace, [node(), generated], [edge])
    brain = SharedBrain(workspace)
    brain.sync()
    result = brain.query("beta")
    assert result["matches"][0]["node"]["trust"] == "candidate_reference"
    assert result["matches"][0]["node"]["origin"] == "semantic"
    assert result["matches"][0]["connections"][0]["confidence"] == "INFERRED"


@pytest.mark.parametrize("source", ["../outside.py", "C:/outside.py", "/outside.py", "star\\alpha.py", ".env", "secrets/key.txt", "star/private.pem", ".git/config", "star/../alpha.py"])
def test_scope_and_secret_sources_excluded(workspace, source):
    export(workspace, [node(), node("bad", source)])
    brain = SharedBrain(workspace)
    assert brain.sync()["nodes"] == 1
    assert not brain.query("bad")["matches"]


def test_symlink_source_always_excluded(workspace, tmp_path):
    secret = tmp_path / "outside.py"
    secret.write_text("private\n")
    link = workspace / "star" / "linked.py"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this host")
    export(workspace, [node(), node("bad", "star/linked.py")])
    brain = SharedBrain(workspace)
    assert brain.sync()["nodes"] == 1
    assert not brain.query("bad", include_stale=True)["matches"]


def test_budgets_cover_json_envelope_connections_and_unicode(workspace):
    nodes = [node("n" + str(i), label="alpha " + "🙂" * 200) for i in range(15)]
    edges = [{"source": "n0", "target": "n" + str(i), "source_file": "star/alpha.py", "relation": "calls", "confidence": "EXTRACTED"} for i in range(1, 15)]
    export(workspace, nodes, edges)
    brain = SharedBrain(workspace)
    brain.sync()
    for budget in (512, 900, 1400, 3000, 6000):
        result = brain.query("alpha", budget_chars=budget, limit=15)
        assert len(serialize(result)) <= budget
        assert result["query_id"]
    assert brain.stats()["queries"] == 5


def test_feedback_is_append_only_candidate_and_query_bound(workspace):
    brain = SharedBrain(workspace)
    brain.sync()
    result = brain.query("alpha")
    first = brain.feedback(result["query_id"], "useful", "claude", answer="Located symbol")
    second = brain.feedback(result["query_id"], "corrected", "codex", correction="Location belongs to older source")
    third = brain.feedback(result["query_id"], "dead_end", "codex")
    assert first["promoted"] is False and second["id"] != first["id"] != third["id"]
    assert brain.stats()["outcomes"] == 3
    assert all(row["outcome"] in {"useful", "corrected", "dead_end"} for row in brain.lessons()["outcomes"])
    assert brain.lessons()["trust"] == "candidate"
    assert len(serialize(brain.lessons(budget_chars=512))) <= 512
    with pytest.raises(ValueError, match="does not belong"):
        brain.feedback("missing", "useful", "claude")
    with pytest.raises(ValueError, match="require a correction"):
        brain.feedback(result["query_id"], "corrected", "claude")


def test_bad_sync_preserves_previous_generation(workspace):
    brain = SharedBrain(workspace)
    brain.sync()
    (workspace / "graphify-out" / "graph.json").write_text('{"nodes":[],"links":[]}')
    with pytest.raises(ValueError, match="previous graph was preserved"):
        brain.sync()
    assert brain.stats()["generation"] == 1
    assert brain.query("alpha")["matches"]


def test_limits_reject_bool_budget_and_limit(workspace):
    brain = SharedBrain(workspace)
    brain.sync()
    for kwargs in ({"budget_chars": True}, {"limit": True}, {"budget_chars": 511}, {"limit": 16}):
        with pytest.raises(ValueError):
            brain.query("alpha", **kwargs)


def test_noisy_first_node_cannot_crowd_out_later_correct_node(workspace):
    nodes = [node("topic" + str(i), label="topic " + str(i)) for i in range(8)]
    nodes.extend(node("noise" + str(i), label="irrelevant " + str(i)) for i in range(20))
    edges = [{"source": "topic0", "target": "noise" + str(i), "source_file": "star/alpha.py",
              "relation": "calls", "confidence": "EXTRACTED"} for i in range(20)]
    export(workspace, nodes, edges)
    brain = SharedBrain(workspace)
    brain.sync()
    result = brain.query("topic", budget_chars=6000, limit=8)
    assert [match["node"]["id"] for match in result["matches"]] == ["topic" + str(i) for i in range(8)]
    assert "topic2" in [match["node"]["id"] for match in result["matches"]]
    assert len(serialize(result)) <= 6000


def test_simultaneous_assistant_syncs_use_one_generation(workspace):
    from concurrent.futures import ThreadPoolExecutor
    first = SharedBrain(workspace)
    first.sync()
    export(workspace, [node(), node("beta", "star/beta.py")])

    def update(_):
        brain = SharedBrain(workspace)
        try:
            return brain.sync()
        finally:
            brain.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(update, range(4)))
    assert sum(result["changed"] for result in results) == 1
    assert {result["generation"] for result in results} == {2}
    assert first.stats()["entities"] == 2


def test_default_compact_projection_keeps_source_nodes_and_trust(workspace):
    nodes = [node("topic" + str(i), label="topic " + str(i)) for i in range(8)]
    edges = [{"source": "topic0", "target": "topic" + str(i), "source_file": "star/alpha.py",
              "relation": "calls", "confidence": "EXTRACTED"} for i in range(1, 8)]
    export(workspace, nodes, edges)
    brain = SharedBrain(workspace)
    attest(brain)
    brain.sync()
    result = brain.query("topic")
    assert len(serialize(result)) <= 3000
    assert len(result["matches"]) == 8
    for match in result["matches"]:
        assert set(match["node"]) == {"id", "label", "source_file", "source_location", "origin", "confidence", "trust", "freshness"}
        assert len(match["connections"]) <= 2
    stored = json.loads(brain.db.execute("SELECT payload FROM entities WHERE id='topic0'").fetchone()[0])
    assert stored["line_start"] == 1 and stored["untrusted_instructions"] is True


def test_simultaneous_first_open_and_sync_bind_one_store(workspace):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(4)

    def open_and_sync(_):
        barrier.wait(timeout=5)
        brain = SharedBrain(workspace)
        try:
            return brain.sync(), brain.stats()
        finally:
            brain.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(open_and_sync, range(4)))
    assert sum(sync["changed"] for sync, _ in results) == 1
    assert {sync["generation"] for sync, _ in results} == {1}
    assert len({stats["project_id"] for _, stats in results}) == 1
    assert all(stats["entities"] == 1 for _, stats in results)


def test_init_lock_being_deleted_on_windows_is_waited_for(workspace, monkeypatch):
    # Windows answers O_CREAT|O_EXCL on a lock file another process is deleting with PermissionError.
    from star.shared_brain import store
    real_open, refused = os.open, []

    def deleting_then_free(path, flags, *args):
        if str(path).endswith(".shared-brain-init.lock") and len(refused) < 2:
            refused.append(path)
            raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, flags, *args)

    monkeypatch.setattr(store.os, "open", deleting_then_free)
    brain = SharedBrain(workspace)
    try:
        assert brain.sync()["generation"] == 1
    finally:
        brain.close()
    assert len(refused) == 2


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_database_and_sidecar_links_are_rejected(workspace, tmp_path, suffix):
    from star.shared_brain import store
    directory = tmp_path / "database"
    directory.mkdir()
    blocked = directory / ("shared-brain.sqlite3" + suffix)
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic private fixture")
    try:
        blocked.symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this host")
    with pytest.raises(ValueError, match="cannot be links"):
        SharedBrain(workspace, directory)
    assert outside.read_text() == "synthetic private fixture"


@pytest.mark.parametrize("field", ["answer", "correction"])
@pytest.mark.parametrize("synthetic", ["api_key = SYNTHETIC_EXAMPLE_ONLY", "password: synthetic-placeholder", "ghp_" + "EXAMPLE" * 5])
def test_credential_shaped_feedback_is_not_persisted(workspace, field, synthetic):
    brain = SharedBrain(workspace)
    brain.sync()
    result = brain.query("alpha")
    with pytest.raises(ValueError, match="credential-shaped"):
        brain.feedback(result["query_id"], "useful", "codex", **{field: synthetic})
    assert brain.stats()["outcomes"] == 0


def test_credential_shaped_query_and_actor_are_not_persisted(workspace):
    brain = SharedBrain(workspace)
    brain.sync()
    with pytest.raises(ValueError, match="credential-shaped"):
        brain.query("password: synthetic-placeholder")
    assert brain.stats()["queries"] == 0
    result = brain.query("alpha")
    with pytest.raises(ValueError, match="credential-shaped"):
        brain.feedback(result["query_id"], "useful", "ghp_" + "EXAMPLE" * 5)
    assert brain.stats()["outcomes"] == 0
