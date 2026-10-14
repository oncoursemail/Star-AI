"""The corrections store is shared between STAR processes (desktop, Discord bot); checkpoints wait for locks.

With the old rollback journal, a commit has to wait until every open read in another process has
finished, and gives up with "database is locked". WAL lets a writer commit while another
connection is in the middle of a read.
"""
import sqlite3

from star.corrections import CorrectionStore
from star.memory import Memory


def _hold_open_read(path):
    other = sqlite3.connect(path, isolation_level=None)
    other.execute("BEGIN")
    other.execute("SELECT count(*) FROM sqlite_master").fetchone()
    return other


def test_corrections_store_uses_wal_and_waits_for_locks(tmp_path):
    store = CorrectionStore(tmp_path)
    try:
        assert store.db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert store.db.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
    finally:
        store.close()


def test_corrections_commit_while_another_process_is_reading(tmp_path):
    store = CorrectionStore(tmp_path)
    reader = _hold_open_read(tmp_path / "corrections.sqlite3")
    try:
        store.db.execute("PRAGMA busy_timeout=200")   # fail fast if the reader still blocked the commit
        item = store.record(project="Default", source="app", ref="m1", prompt="p", answer="a",
                            correction="Use task.wait, not wait")
        assert store.get("Default", item["id"])["correction"] == "Use task.wait, not wait"
    finally:
        reader.close()
        store.close()


def test_memory_waits_for_a_lock_and_keeps_the_rollback_journal(tmp_path):
    memory = Memory(tmp_path / "checkpoints.sqlite3")
    try:
        assert memory.db.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
        # WAL would make the warm-up's read-only probe leave -wal/-shm files (tests/test_warmup.py).
        assert memory.db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        memory.put("Default", "summary one")
        assert memory.get("Default") == "summary one"
    finally:
        memory.close()
