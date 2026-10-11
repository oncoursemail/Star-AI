"""Durable mutation barriers only; no Studio, provider or real profile."""
from dataclasses import replace
import hashlib
import multiprocessing
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from star.studio_uncertainty import (
    StudioScope, StudioUncertaintyStore, StudioUncertaintyError, StudioWriteBlocked,
)


def scope(**changes):
    return replace(StudioScope("host_launcher", "native-session:workspace", 10, 20, 30, "User"), **changes)


def worker_begin(path, start, output):
    start.wait(10)
    try:
        output.put(("began", StudioUncertaintyStore(path).begin(scope(), "luau")))
    except StudioWriteBlocked:
        output.put(("blocked", ""))
    except StudioUncertaintyError:
        output.put(("error", ""))


def worker_crash_after_commit(path, pipe):
    token = StudioUncertaintyStore(path).begin(scope(), "script")
    pipe.send(token)
    pipe.close()
    os._exit(0)


def test_constructor_is_read_lazy_even_for_missing_or_corrupt_store(tmp_path):
    path = tmp_path / "new-folder" / "ledger.sqlite3"
    StudioUncertaintyStore(path)
    assert not path.parent.exists()
    path = tmp_path / "corrupt"
    path.write_bytes(b"not sqlite; private fixture data")
    store = StudioUncertaintyStore(path)
    before = path.read_bytes()
    with pytest.raises(StudioUncertaintyError, match="mutations remain blocked") as error:
        store.pending(scope())
    assert path.read_bytes() == before
    assert "private" not in str(error.value) and str(path) not in str(error.value)


def test_pending_before_dispatch_survives_reconnect_and_failed_confirmation(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    first = StudioUncertaintyStore(path)
    token = first.begin(scope(), "luau")
    # A fresh connection/object/turn sees the committed barrier before dispatch.
    second = StudioUncertaintyStore(path)
    assert second.pending(scope())[0]["token"] == token
    for known, ok in ((False, False), (True, False), (False, True), (1, True), (True, 1), (None, True)):
        assert not second.confirm(scope(), token, known=known, ok=ok)
        with pytest.raises(StudioWriteBlocked):
            first.begin(scope(), "script")
    assert second.confirm(scope(), token, known=True, ok=True)
    assert not first.pending(scope())
    assert not first.confirm(scope(), token, known=True, ok=True)
    assert first.begin(scope(), "script") != token


def test_exact_binding_and_host_recovery_tokens_never_clear_other_scope(tmp_path):
    store = StudioUncertaintyStore(tmp_path / "ledger.sqlite3")
    token = store.begin(scope(), "undo")
    assert not store.acknowledge(scope(route="local_pc"), token)
    assert not store.confirm(scope(session="another-native-session"), token, known=True, ok=True)
    assert not store.acknowledge(scope(), "0" * 32)
    with pytest.raises(StudioWriteBlocked):
        store.begin(scope(), "undo")  # Unknown Undo must not be replayed.
    assert store.acknowledge(scope(), token)
    assert not store.acknowledge(scope(), token)
    assert store.begin(scope(), "undo") != token


def test_lost_stop_after_confirmed_start_survives_a_new_chat_store(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = StudioUncertaintyStore(path)
    started = store.begin(scope(), "play_start")
    assert store.confirm(scope(), started, known=True, ok=True)
    stopped = store.begin(scope(), "play_stop")
    assert not store.confirm(scope(), stopped, known=False, ok=False)
    resumed = StudioUncertaintyStore(path)
    assert resumed.pending(scope())[0]["token"] == stopped
    assert resumed.pending(scope())[0]["kind"] == "play_stop"
    with pytest.raises(StudioWriteBlocked):
        resumed.begin(scope(), "play_start")


def test_exact_confirmed_stop_releases_only_its_own_pending_operation(tmp_path):
    store = StudioUncertaintyStore(tmp_path / "ledger.sqlite3")
    token = store.begin(scope(), "play_stop")
    assert not store.confirm(scope(), "0" * 32, known=True, ok=True)
    assert not store.confirm(scope(), token, known=True, ok=False)
    assert store.pending(scope())[0]["token"] == token
    assert store.confirm(scope(), token, known=True, ok=True)
    assert not store.pending(scope())


def test_stop_never_overwrites_or_clears_an_uncertain_start(tmp_path):
    store = StudioUncertaintyStore(tmp_path / "ledger.sqlite3")
    started = store.begin(scope(), "play_start")
    before = store.pending(scope())
    # Host cleanup may still stop the owned test; that cannot establish whether
    # an earlier start succeeded. There is no generic pending bypass/replacement.
    with pytest.raises(StudioWriteBlocked):
        store.begin(scope(), "play_stop")
    assert not store.confirm(scope(), "0" * 32, known=True, ok=True)
    assert store.pending(scope()) == before
    assert StudioUncertaintyStore(store.path).pending(scope())[0]["token"] == started


@pytest.mark.parametrize("change", [{"route": "local_pc"}, {"session": "different-native"},
    {"place_id": 11}, {"universe_id": 21}, {"creator_id": 31}, {"creator_type": "Group"}])
def test_distinct_native_binding_is_independent(tmp_path, change):
    store = StudioUncertaintyStore(tmp_path / "ledger.sqlite3")
    store.begin(scope(), "play_start")
    assert not store.pending(scope(**change))
    store.begin(scope(**change), "play_start")


@pytest.mark.parametrize("change", [{"route": "fallback"}, {"session": ""}, {"session": None},
    {"session": "bad\x7f"}, {"session": "x" * 161}, {"place_id": True}, {"place_id": -1},
    {"universe_id": 2**63}, {"creator_id": 1.0}, {"creator_type": "unknown"}])
def test_missing_or_invalid_native_binding_fails_closed(change):
    with pytest.raises(StudioUncertaintyError, match="native session"):
        scope(**change)


def test_fixed_mutation_kinds_and_opaque_tokens_only(tmp_path):
    store = StudioUncertaintyStore(tmp_path / "ledger.sqlite3")
    for kind in ("private-source-code", "execute shell", None):
        with pytest.raises(StudioUncertaintyError):
            store.begin(scope(), kind)
    for token in (None, "../../../private", "x" * 32):
        with pytest.raises(StudioUncertaintyError):
            store.acknowledge(scope(), token)
    assert not store.pending(scope())


def test_rows_and_status_contain_no_sources_paths_or_native_identifiers(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = StudioUncertaintyStore(path)
    token = store.begin(scope(), "script")
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT * FROM pending").fetchall()
    assert len(rows) == 1 and rows[0][1:3] == (token, "script")
    assert rows[0][0] != scope().session and len(rows[0][0]) == 64
    rendered = str(rows) + str(store.pending(scope()))
    assert "native-session" not in rendered and str(tmp_path) not in rendered and "host_launcher" not in rendered
    assert set(store.pending(scope())[0]) == {"token", "kind", "created_at"}


def test_corrupt_foreign_or_rogue_trigger_store_never_grants_write(tmp_path):
    path = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated(value)")
    before = hashlib.sha256(path.read_bytes()).digest()
    with pytest.raises(StudioUncertaintyError):
        StudioUncertaintyStore(path).begin(scope(), "luau")
    assert hashlib.sha256(path.read_bytes()).digest() == before
    path = tmp_path / "rogue.sqlite3"
    store = StudioUncertaintyStore(path)
    assert store.pending(scope()) == []
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER delete_barrier AFTER INSERT ON pending BEGIN DELETE FROM pending; END")
    before = hashlib.sha256(path.read_bytes()).digest()
    with pytest.raises(StudioUncertaintyError):
        store.begin(scope(), "luau")
    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_deleted_prepared_ledger_and_unwritable_location_fail_closed(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = StudioUncertaintyStore(path)
    store.begin(scope(), "script")
    path.unlink()
    with pytest.raises(StudioUncertaintyError):
        store.begin(scope(), "script")
    assert not path.exists()
    with pytest.raises(StudioUncertaintyError):
        StudioUncertaintyStore(path).begin(scope(), "script")
    assert not path.exists() and store.marker.exists()
    blocker = tmp_path / "regular-file"
    blocker.write_bytes(b"fixture")
    with pytest.raises(StudioUncertaintyError):
        StudioUncertaintyStore(blocker / "ledger.sqlite3").begin(scope(), "luau")


@pytest.mark.parametrize("state", ["marker_only", "empty_database_only", "invalid_marker", "missing_marker"])
def test_interrupted_or_missing_bootstrap_state_is_never_auto_healed(tmp_path, state):
    path = tmp_path / "ledger.sqlite3"
    store = StudioUncertaintyStore(path)
    if state == "marker_only":
        store.marker.write_bytes(b"STAR_STUDIO_UNCERTAINTY_V1\n")
    elif state == "empty_database_only":
        path.touch()
    else:
        store.pending(scope())
        if state == "invalid_marker":
            store.marker.write_bytes(b"invalid marker")
        else:
            store.marker.unlink()
    before_database = path.read_bytes() if path.exists() else None
    before_marker = store.marker.read_bytes() if store.marker.exists() else None
    with pytest.raises(StudioUncertaintyError):
        StudioUncertaintyStore(path).begin(scope(), "luau")
    assert (path.read_bytes() if path.exists() else None) == before_database
    assert (store.marker.read_bytes() if store.marker.exists() else None) == before_marker


def test_marker_fsync_failure_stays_blocked_after_new_store(tmp_path, monkeypatch):
    path = tmp_path / "ledger.sqlite3"
    store = StudioUncertaintyStore(path)
    def fail_fsync(_):
        raise OSError("private fixture error")
    monkeypatch.setattr(os, "fsync", fail_fsync)
    with pytest.raises(StudioUncertaintyError) as error:
        store.begin(scope(), "script")
    assert "private" not in str(error.value)
    assert store.marker.exists() and not path.exists()
    with pytest.raises(StudioUncertaintyError):
        StudioUncertaintyStore(path).begin(scope(), "script")
    assert not path.exists()


def test_parallel_threads_only_one_can_begin_same_scope(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    StudioUncertaintyStore(path).pending(scope())
    start = threading.Barrier(5)
    def attempt(_):
        start.wait(5)
        try:
            return StudioUncertaintyStore(path).begin(scope(), "luau")
        except StudioWriteBlocked:
            return None
    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes = list(pool.map(attempt, range(5)))
    assert sum(x is not None for x in outcomes) == 1


def test_parallel_processes_only_one_can_begin_same_scope(tmp_path):
    path = str(tmp_path / "ledger.sqlite3")
    StudioUncertaintyStore(path).pending(scope())
    ctx = multiprocessing.get_context("spawn")
    start, output = ctx.Event(), ctx.Queue()
    processes = [ctx.Process(target=worker_begin, args=(path, start, output)) for _ in range(3)]
    try:
        for process in processes:
            process.start()
        start.set()
        outcomes = [output.get(timeout=15)[0] for _ in processes]
        for process in processes:
            process.join(15)
            assert process.exitcode == 0
        assert sorted(outcomes) == ["began", "blocked", "blocked"]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        output.close()


def test_process_death_after_begin_commit_does_not_erase_uncertainty(tmp_path):
    path = str(tmp_path / "ledger.sqlite3")
    StudioUncertaintyStore(path).pending(scope())
    ctx = multiprocessing.get_context("spawn")
    receiving, sending = ctx.Pipe(duplex=False)
    process = ctx.Process(target=worker_crash_after_commit, args=(path, sending))
    try:
        process.start()
        assert receiving.poll(15)
        token = receiving.recv()
        process.join(15)
        assert process.exitcode == 0
        resumed = StudioUncertaintyStore(path)
        assert resumed.pending(scope())[0]["token"] == token
        with pytest.raises(StudioWriteBlocked):
            resumed.begin(scope(), "script")
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        receiving.close()
        sending.close()
