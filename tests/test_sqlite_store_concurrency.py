"""The corrections and checkpoint stores are shared between STAR processes (desktop, Discord bot).

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


def test_memory_checkpoint_commit_while_another_process_is_reading(tmp_path):
    path = tmp_path / "checkpoints.sqlite3"
    memory = Memory(path)
    reader = _hold_open_read(path)
    try:
        assert memory.db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        memory.db.execute("PRAGMA busy_timeout=200")
        memory.put("Default", "summary one")
        memory.event("Default", {"kind": "test"})
        assert memory.get("Default") == "summary one"
    finally:
        reader.close()
        memory.close()
