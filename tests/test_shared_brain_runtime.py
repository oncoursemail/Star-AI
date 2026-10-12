"""Host registration and real offline dispatch; no active graph/profile/model."""
import asyncio
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from star.agent import execute
from star.desktop_core import Settings
from star.intelligence import LocalIntelligence, for_settings
from star.shared_brain.store import SharedBrain, serialize
from star.shared_brain_runtime import (SharedBrainUnavailable, make_shared_brain_runtime,
                                       shared_store_present)


SHARED = {"shared_brain_query", "shared_brain_stats"}
LEGACY = {"star_graphify_query", "star_graphify_stats"}
NEIGHBORS = {"star_graphify_explain", "star_graphify_path"}
PROMPT = "Trace the alpha codebase graph architecture"


def raw_workspace(tmp_path):
    root = tmp_path / "project"
    (root / "star").mkdir(parents=True)
    (root / "star/alpha.py").write_text("# source\n" * 6 + "def alpha(): return 1\n", encoding="utf-8")
    (root / "star/beta.py").write_text("def beta(): return alpha()\n", encoding="utf-8")
    graph = root / "graphify-out"
    graph.mkdir()
    (graph / "graph.json").write_text(json.dumps({
        "directed": True,
        "nodes": [{"id": name, "label": name + "()", "source_file": f"star/{name}.py",
                   "source_location": location, "_origin": "ast", "file_type": "code"}
                  for name, location in (("alpha", "L7"), ("beta", "L1"))],
        "links": [{"source": "beta", "target": "alpha", "relation": "calls",
                   "confidence": "EXTRACTED", "source_file": "star/beta.py", "source_location": "L1"}],
    }), encoding="utf-8")
    return root


def prepare(root, *, attested=True):
    brain = SharedBrain(root)
    try:
        if attested:
            (root / "graphify-out/shared-brain-manifest.json").write_text(json.dumps({
                "schema": 1, "project_id": brain.project_id,
                "graph_sha256": hashlib.sha256((root / "graphify-out/graph.json").read_bytes()).hexdigest(),
                "sources": {f"star/{name}.py": {
                    "sha256": hashlib.sha256((root / f"star/{name}.py").read_bytes()).hexdigest()}
                    for name in ("alpha", "beta")},
            }), encoding="utf-8")
        brain.sync()
    finally:
        brain.close()
    return root


@pytest.fixture
def workspace(tmp_path):
    return prepare(raw_workspace(tmp_path))


def host_hub(root, tmp_path, **kwargs):
    return LocalIntelligence(home=tmp_path / "home", workspace=root, skills_enabled=False,
                             roblox_research_enabled=False, registered_workspaces=(root,), **kwargs)


def names(hub, prompt=PROMPT):
    return {tool["name"] for tool in hub.definitions(prompt)}


def database(root):
    return root / "graphify-out/shared-brain/shared-brain.sqlite3"


def counts(root):
    with sqlite3.connect(database(root)) as db:
        return {table: db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                for table in ("queries", "outcomes", "generations")}


def test_factory_never_prepares_missing_store_and_registration_is_exact(tmp_path):
    root = raw_workspace(tmp_path)
    before = set(root.rglob("*"))
    assert make_shared_brain_runtime(root, (root,), enabled=True) is None
    assert set(root.rglob("*")) == before
    prepare(root)
    assert make_shared_brain_runtime(root, (root,)) is None  # permission defaults off
    assert make_shared_brain_runtime(root, (root,), enabled=1) is None
    assert make_shared_brain_runtime(root, ()) is None
    assert make_shared_brain_runtime(root, (root.parent,), enabled=True) is None
    assert make_shared_brain_runtime(root, root, enabled=True) is None
    runtime = make_shared_brain_runtime(root / "star/..", (root,), enabled=True)
    assert runtime is not None
    assert runtime.status() == {"enabled": True, "ready": True, "reference_data_only": True}
    assert {tool["name"] for tool in runtime.definitions()} == SHARED
    assert not hasattr(runtime, "db")
    runtime.close()


def test_settings_register_only_the_owner_selected_scope_and_revoke_snapshot(workspace, tmp_path):
    direct = LocalIntelligence(home=tmp_path / "home", workspace=workspace,
                               skills_enabled=False, roblox_research_enabled=False)
    assert not (names(direct) & (SHARED | LEGACY))
    with pytest.raises(PermissionError, match="registered"):
        direct.call("shared_brain_stats", {}, enabled=SHARED)
    settings = Settings(workspace=str(workspace), skills_enabled=False, roblox_research_enabled=False)
    settings.validate()
    hub = for_settings(settings, tmp_path / "owner-home")
    assert SHARED <= names(hub)
    settings.graphify_enabled = False
    assert names(hub) == set()
    assert hub.status()["graphify"]["enabled"] is False
    with pytest.raises(PermissionError):
        hub.call("shared_brain_stats", {}, enabled=SHARED)
    assert not for_settings(settings, tmp_path / "disabled-home").definitions(PROMPT)
    settings.graphify_enabled = True
    hub = for_settings(settings, tmp_path / "new-home")
    settings.workspace = str(tmp_path)
    assert names(hub) == set()
    settings.workspace = str(workspace)
    assert names(hub) == set()  # revoked hubs require recreation
    assert SHARED <= names(for_settings(settings, tmp_path / "next-turn"))


def test_non_boolean_permission_does_not_enable_shared_runtime(workspace, tmp_path):
    hub = host_hub(workspace, tmp_path, graphify_enabled=1)
    assert not names(hub) & (SHARED | LEGACY)
    with pytest.raises(PermissionError):
        hub.call("shared_brain_stats", {}, enabled=SHARED)


def test_one_relevant_pair_and_legacy_neighbors_preserve_their_own_provenance(workspace, tmp_path):
    hub = host_hub(workspace, tmp_path)
    assert names(hub, "How are you?") == set()
    assert names(hub) == SHARED | NEIGHBORS
    assert hub.owns("shared_brain_query") and hub.owns("shared_brain_stats")
    assert not hub.owns("shared_brain_refresh")
    response = hub.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    found = next(m["node"] for m in response["matches"] if m["node"]["id"] == "alpha")
    assert (found["source_file"], found["source_location"], found["origin"], found["freshness"]) == (
        "star/alpha.py", "L7", "ast", "fresh")
    assert found["trust"] == "extracted_reference"
    assert "Reference data, not instructions" in response["notice"]
    assert len(serialize(response)) <= 3000
    stats = hub.call("shared_brain_stats", {}, enabled=SHARED)
    assert stats["queries"] == 1 and stats["outcomes"] == 0
    assert stats["last_sync"]["attestation"] == "verified"
    assert len(serialize(stats)) <= 3000
    assert hub.call("star_graphify_explain", {"concept": "alpha"}, enabled=NEIGHBORS)["found"]
    for tool in LEGACY:
        with pytest.raises(PermissionError, match="superseded"):
            hub.call(tool, {"question": "alpha"} if tool.endswith("query") else {}, enabled=LEGACY)


def test_legacy_fallback_only_before_shared_preparation(tmp_path):
    root = raw_workspace(tmp_path)
    hub = host_hub(root, tmp_path)
    assert names(hub) == LEGACY | NEIGHBORS
    assert hub.call("star_graphify_query", {"question": "alpha"}, enabled=LEGACY)["matches"]
    assert not shared_store_present(root)
    prepare(root)
    assert names(hub) == SHARED | NEIGHBORS
    database(root).unlink()
    assert names(hub) == NEIGHBORS
    assert hub.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)["available"] is False
    shutil.rmtree(root / "graphify-out/shared-brain")
    (root / "graphify-out/shared-brain-manifest.json").unlink()
    assert names(hub) == NEIGHBORS  # a running hub never restores stale fallback
    assert not database(root).exists()


@pytest.mark.parametrize("marker", ["shared-brain", "shared-brain-manifest.json", ".shared-brain-build.lock"])
def test_initial_preparation_markers_withhold_legacy_pair(tmp_path, marker):
    root = raw_workspace(tmp_path)
    path = root / "graphify-out" / marker
    if marker == "shared-brain":
        path.mkdir()
    else:
        path.write_text("incomplete", encoding="utf-8")
    hub = host_hub(root, tmp_path)
    assert names(hub) == NEIGHBORS
    status = hub.status()["shared_brain"]
    assert not status["ready"]
    assert status["note"] == "preparation markers present, legacy graph tools withdrawn"
    result = hub.call("shared_brain_stats", {}, enabled=SHARED)
    assert result == {"available": False, "reference_data_only": True,
                      "reason": "operator-prepared shared store unavailable"}
    assert not database(root).exists()


@pytest.mark.parametrize("corruption", ["foreign", "schema", "generation", "metadata", "empty", "payload", "trust", "trigger"])
def test_existing_invalid_stores_fail_closed(workspace, tmp_path, corruption):
    with sqlite3.connect(database(workspace)) as db:
        if corruption == "foreign":
            db.execute("UPDATE meta SET value='foreign' WHERE name='project_id'")
        elif corruption == "schema":
            db.execute("DROP TABLE outcomes")
        elif corruption == "generation":
            db.execute("UPDATE generations SET graph_sha256='invalid'")
        elif corruption == "metadata":
            db.execute("UPDATE generations SET summary='{}'")
        elif corruption == "empty":
            db.execute("DELETE FROM entities")
        elif corruption == "payload":
            db.execute("UPDATE entities SET payload='{'")
        elif corruption == "trust":
            payload = json.loads(db.execute("SELECT payload FROM entities WHERE id='alpha'").fetchone()[0])
            payload["trust"] = "trusted_rules"
            db.execute("UPDATE entities SET payload=? WHERE id='alpha'", (serialize(payload),))
        else:
            db.execute("CREATE TRIGGER surprise AFTER INSERT ON queries BEGIN DELETE FROM entities; END")
    hub = host_hub(workspace, tmp_path)
    assert not names(hub) & (LEGACY | SHARED)
    result = hub.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    assert result["available"] is False
    assert len(serialize(result)) < 300
    assert str(workspace) not in serialize(result)


def test_corrupt_database_and_preparing_locks_are_unavailable(tmp_path):
    root = raw_workspace(tmp_path)
    database(root).parent.mkdir()
    database(root).write_bytes(b"not sqlite")
    assert make_shared_brain_runtime(root, (root,), enabled=True) is None
    assert not names(host_hub(root, tmp_path)) & (SHARED | LEGACY)
    database(root).unlink()
    prepare(root)
    for lock in (database(root).parent / ".shared-brain-init.lock",
                 root / "graphify-out/.shared-brain-build.lock"):
        lock.touch()
        assert make_shared_brain_runtime(root, (root,), enabled=True) is None
        assert not names(host_hub(root, tmp_path)) & (SHARED | LEGACY)
        lock.unlink()


@pytest.mark.parametrize("args", [
    {"question": "alpha", "workspace": "/other"}, {"question": "alpha", "actor": "host"},
    {"question": "alpha", "include_stale": True}, {"question": "alpha", "store": "/other"},
    {"question": "alpha", "limit": 9}, {"question": "alpha", "budget_chars": 3001},
    {"question": "alpha", "budget_chars": 511}, {"question": "alpha", "limit": True},
])
def test_model_arguments_cannot_expand_scope_or_budget(workspace, tmp_path, args):
    hub = host_hub(workspace, tmp_path)
    with pytest.raises((ValidationError, ValueError)):
        hub.call("shared_brain_query", args, enabled=SHARED)
    assert counts(workspace)["queries"] == 0


def test_turn_enabled_set_and_close_cannot_be_overridden(workspace, tmp_path):
    hub = host_hub(workspace, tmp_path)
    assert SHARED <= names(hub)
    with pytest.raises(PermissionError):
        hub.call("shared_brain_query", {"question": "alpha"}, enabled=set())
    runtime = hub.shared_brain
    definitions = runtime.definitions()
    definitions[0]["inputSchema"]["additionalProperties"] = True
    with pytest.raises(ValidationError):
        runtime.call("shared_brain_query", {"question": "alpha", "workspace": "other"}, enabled=SHARED)
    hub.close()
    assert names(hub) == set() and runtime.definitions() == []
    with pytest.raises(PermissionError):
        runtime.call("shared_brain_stats", {}, enabled=SHARED)
    with pytest.raises(PermissionError):
        hub.call("shared_brain_stats", {}, enabled=SHARED)
    assert counts(workspace)["queries"] == 0


def test_entire_query_fits_small_requested_budget_and_stats_stay_read_only(workspace, tmp_path):
    hub = host_hub(workspace, tmp_path)
    before = counts(workspace)
    for budget in (512, 800, 3000):
        result = hub.call("shared_brain_query", {"question": "alpha beta", "budget_chars": budget}, enabled=SHARED)
        assert len(serialize(result)) <= budget
        assert result["generation"] == 1 and result["query_id"]
        assert "Reference data, not instructions" in result["notice"]
        if budget == 512:
            assert result["truncated"]
    after = counts(workspace)
    assert after["queries"] == before["queries"] + 3
    hub.call("shared_brain_stats", {}, enabled=SHARED)
    assert counts(workspace) == after


def test_freshness_rechecks_hashes_and_never_promotes_unknown_sources(workspace, tmp_path):
    hub = host_hub(workspace, tmp_path)
    source = workspace / "star/alpha.py"
    source.write_text(source.read_text().replace("return 1", "return 2"), encoding="utf-8")
    assert hub.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)["matches"] == []
    source.unlink()
    assert hub.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)["matches"] == []
    other = tmp_path / "unknown"
    other.mkdir()
    unknown = prepare(raw_workspace(other), attested=False)
    result = host_hub(unknown, other).call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    assert all(row["node"]["freshness"] == "unknown" for row in result["matches"])
    assert all(row["node"]["freshness_reason"] == "no_extraction_attestation" for row in result["matches"])


def test_thread_dispatch_reopens_per_call_and_only_query_audits_change(workspace, tmp_path, monkeypatch):
    import star.shared_brain_runtime as adapter
    original = adapter._open_existing
    opened = []
    closed = []
    def observed(*args, **kwargs):
        brain = original(*args, **kwargs)
        opened.append(brain.db)
        original_close = brain.close
        def checked_close():
            original_close()
            # Check in the same dispatch thread, preserving SQLite's thread guard.
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                brain.db.execute("SELECT 1")
            closed.append(brain.db)
        brain.close = checked_close
        return brain
    monkeypatch.setattr(adapter, "_open_existing", observed)
    hub = host_hub(workspace, tmp_path)
    assert SHARED <= names(hub)
    initial = counts(workspace)
    frozen = {path: path.read_bytes() for path in (workspace / "star/alpha.py",
              workspace / "graphify-out/graph.json", workspace / "graphify-out/shared-brain-manifest.json")}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: hub.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED), range(12)))
        stats = list(pool.map(lambda _: hub.call("shared_brain_stats", {}, enabled=SHARED), range(4)))
    assert len({result["query_id"] for result in results}) == 12
    assert all(result["matches"] for result in results)
    assert all(row["queries"] == 12 for row in stats)
    assert counts(workspace) == {**initial, "queries": initial["queries"] + 12}
    assert all(path.read_bytes() == data for path, data in frozen.items())
    assert len(opened) >= 16 and len({id(db) for db in opened}) == len(opened)
    assert {id(db) for db in opened} == {id(db) for db in closed}


def test_missing_after_ready_never_creates_database_even_in_open_race(workspace, monkeypatch):
    import star.shared_brain_runtime as adapter
    runtime = make_shared_brain_runtime(workspace, (workspace,), enabled=True)
    original = adapter._paths
    def vanished(root):
        paths = original(root)
        database(root).unlink()
        return paths
    monkeypatch.setattr(adapter, "_paths", vanished)
    with pytest.raises(SharedBrainUnavailable):
        runtime.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    assert not database(workspace).exists()


def test_linked_store_marker_is_withheld_without_following_target(tmp_path, monkeypatch):
    import star.shared_brain.store as store
    root = raw_workspace(tmp_path)
    original = store._link
    monkeypatch.setattr(store, "_link", lambda path: path == root / "graphify-out" or original(path))
    assert shared_store_present(root)
    assert not names(host_hub(root, tmp_path)) & (SHARED | LEGACY)
    assert not database(root).exists()


def test_prepared_database_link_is_rejected(workspace, tmp_path, monkeypatch):
    import star.shared_brain.store as store
    original = store._link
    monkeypatch.setattr(store, "_link", lambda path: path == database(workspace) or original(path))
    assert make_shared_brain_runtime(workspace, (workspace,), enabled=True) is None
    assert not names(host_hub(workspace, tmp_path)) & (SHARED | LEGACY)


def test_second_connection_trigger_after_readiness_cannot_mutate_graph(workspace, monkeypatch):
    import star.shared_brain_runtime as adapter
    runtime = make_shared_brain_runtime(workspace, (workspace,), enabled=True)
    original = adapter._open_existing
    def after_ready(*args, **kwargs):
        brain = original(*args, **kwargs)
        with closing(sqlite3.connect(database(workspace))) as writer:
            writer.execute("CREATE TRIGGER surprise AFTER INSERT ON queries BEGIN DELETE FROM entities; END")
            writer.commit()
        return brain
    with sqlite3.connect(database(workspace)) as db:
        before = db.execute("SELECT id,payload FROM entities ORDER BY id").fetchall()
    monkeypatch.setattr(adapter, "_open_existing", after_ready)
    with pytest.raises(SharedBrainUnavailable):
        runtime.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    with sqlite3.connect(database(workspace)) as db:
        assert db.execute("SELECT id,payload FROM entities ORDER BY id").fetchall() == before
        assert db.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 0


def test_audit_authorizer_blocks_trigger_added_after_query_read_snapshot(workspace, monkeypatch):
    import star.shared_brain_runtime as adapter
    runtime = make_shared_brain_runtime(workspace, (workspace,), enabled=True)
    original = adapter._open_existing
    def after_ready(*args, **kwargs):
        brain = original(*args, **kwargs)
        connection = type(brain.db)
        original_execute = connection.execute
        def before_audit(db, sql, parameters=(), /):
            if sql.startswith("INSERT INTO queries"):
                # All snapshot validation and source hashing has completed.
                # SQLite must still reauthorize the newly added trigger.
                with closing(sqlite3.connect(database(workspace))) as writer:
                    writer.execute("CREATE TRIGGER surprise AFTER INSERT ON queries BEGIN DELETE FROM entities; END")
                    writer.commit()
            return original_execute(db, sql, parameters)
        monkeypatch.setattr(connection, "execute", before_audit)
        return brain
    monkeypatch.setattr(adapter, "_open_existing", after_ready)
    with pytest.raises(SharedBrainUnavailable):
        runtime.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    with sqlite3.connect(database(workspace)) as db:
        assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 0


@pytest.mark.parametrize("mutation", ["trust", "binding", "generation", "payload", "source"])
def test_query_snapshot_revalidates_second_connection_changes(workspace, monkeypatch, mutation):
    import star.shared_brain_runtime as adapter
    runtime = make_shared_brain_runtime(workspace, (workspace,), enabled=True)
    original = adapter._open_existing
    def after_ready(*args, **kwargs):
        brain = original(*args, **kwargs)
        with closing(sqlite3.connect(database(workspace))) as writer:
            if mutation == "binding":
                writer.execute("UPDATE meta SET value='foreign' WHERE name='project_id'")
            elif mutation == "generation":
                writer.execute("UPDATE generations SET graph_sha256='not-a-digest'")
            elif mutation == "payload":
                writer.execute("UPDATE entities SET payload='{' WHERE id='alpha'")
            else:
                item = json.loads(writer.execute("SELECT payload FROM entities WHERE id='alpha'").fetchone()[0])
                item["trust" if mutation == "trust" else "source_file"] = (
                    "trusted_rules" if mutation == "trust" else "../outside.py")
                writer.execute("UPDATE entities SET payload=? WHERE id='alpha'", (serialize(item),))
            writer.commit()
        return brain
    monkeypatch.setattr(adapter, "_open_existing", after_ready)
    with pytest.raises(SharedBrainUnavailable):
        runtime.call("shared_brain_query", {"question": "alpha"}, enabled=SHARED)
    assert counts(workspace)["queries"] == 0


@pytest.mark.parametrize("sql", [
    "DELETE FROM entities", "UPDATE meta SET value='foreign'", "DROP TABLE entities",
    "INSERT INTO outcomes VALUES(1,'x','useful','model','','','now')",
    "CREATE TABLE unexpected(value TEXT)", "CREATE TEMP TABLE unexpected(value TEXT)",
    "CREATE TRIGGER unexpected AFTER INSERT ON queries BEGIN DELETE FROM entities; END",
    "ATTACH DATABASE ':memory:' AS extra", "PRAGMA writable_schema=ON",
    "PRAGMA user_version=1", "PRAGMA trusted_schema=ON", "SELECT load_extension('unavailable')",
])
def test_query_connection_authorizer_denies_other_sql_capabilities(workspace, sql):
    from star.shared_brain_runtime import _open_existing
    with closing(_open_existing(workspace, readonly=False)) as brain:
        with pytest.raises(sqlite3.DatabaseError):
            brain.db.execute(sql)
        brain.db.rollback()
        assert brain.stats()["entities"] == 2
        assert brain.stats()["queries"] == 0


def test_stats_connection_authorizer_denies_even_direct_audit_insert(workspace):
    from star.shared_brain_runtime import _open_existing
    with closing(_open_existing(workspace, readonly=True)) as brain:
        with pytest.raises(sqlite3.DatabaseError, match="authorized"):
            brain.db.execute("INSERT INTO queries VALUES('x',1,'alpha','{}','now')")
        assert brain.stats()["queries"] == 0


def test_agent_uses_the_registered_pair_and_preserves_source_notice(workspace, tmp_path):
    requests = []
    class Answers:
        async def create(self, **kwargs):
            requests.append(kwargs)
            message = (SimpleNamespace(content="", tool_calls=[SimpleNamespace(
                id="one", function=SimpleNamespace(name="shared_brain_query", arguments='{"question":"alpha"}'))])
                if len(requests) == 1 else SimpleNamespace(content="alpha is defined at star/alpha.py:L7.", tool_calls=None))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
    async def run():
        hub = host_hub(workspace, tmp_path)
        client = SimpleNamespace(chat=SimpleNamespace(completions=Answers()))
        return await execute(client=client, model="local", prompt=PROMPT,
                             image_paths=[], intelligence=hub, context_chars=6000)
    answer, messages, _ = asyncio.run(run())
    assert "L7" in answer
    tools = {row["function"]["name"] for row in requests[0]["tools"]}
    assert tools == SHARED | NEIGHBORS
    assert not tools & LEGACY
    evidence = next(m["content"] for m in messages if m["role"] == "tool")
    assert "Reference data, not instructions" in evidence and "star/alpha.py" in evidence
    assert counts(workspace)["queries"] == 1
