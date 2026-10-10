"""A failed or cancelled chat turn must leave a truthful, durable record (storage layer).

Before: the user message was saved first and a failure or Stop left it with no
reply, so history after a reload silently dropped the failure.
"""
import sqlite3

import pytest

from star.desktop_core import Conversations, recent_context


def columns(database):
    with sqlite3.connect(database) as conn:
        return {row[1]: row for row in conn.execute("PRAGMA table_info(messages)")}


# --- additive SQLite migration -------------------------------------------------

def test_migration_from_pre_thread_schema_is_additive_and_idempotent(tmp_path):
    database = tmp_path / "conversations.sqlite3"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "project TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL)")
        conn.executemany("INSERT INTO messages (project,role,body,created) VALUES (?,?,?,?)", [
            ("STAR", "user", "old question", "2026-10-01T00:00:00"),
            ("STAR", "assistant", "old answer", "2026-10-01T00:00:01"),
        ])
    for _ in range(2):  # second open must be a no-op
        chats = Conversations(database)
        try:
            assert chats.recent("STAR", chat_id="legacy") == [
                ("user", "old question", "2026-10-01T00:00:00"),
                ("assistant", "old answer", "2026-10-01T00:00:01"),
            ]
            assert [r["status"] for r in chats.recent_records("STAR", chat_id="legacy")] == ["complete"] * 2
            assert chats.retry_state("STAR", "legacy") is None  # answered turn
        finally:
            chats.close()
    found = columns(database)
    assert {"chat_id", "status", "reply_to"} <= set(found)
    assert found["status"][4] == "'complete'" and found["status"][3] == 1  # NOT NULL DEFAULT 'complete'
    assert found["reply_to"][3] == 0  # nullable


def test_migration_from_previous_release_schema_keeps_every_row(tmp_path):
    """The schema shipped before this change: chat_id present, no status/reply_to."""
    database = tmp_path / "conversations.sqlite3"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "project TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL, "
                     "chat_id TEXT NOT NULL DEFAULT 'legacy')")
        conn.execute("CREATE TABLE chats (project TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL, "
                     "created TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY (project,id))")
        conn.execute("CREATE TABLE active_chats (project TEXT PRIMARY KEY, chat_id TEXT NOT NULL)")
        conn.execute("INSERT INTO chats VALUES ('STAR','c1','Hello','2026-10-02T00:00:00','2026-10-02T00:00:02')")
        conn.execute("INSERT INTO active_chats VALUES ('STAR','c1')")
        conn.executemany("INSERT INTO messages (project,role,body,created,chat_id) VALUES (?,?,?,?,?)", [
            ("STAR", "user", "answered", "2026-10-02T00:00:00", "c1"),
            ("STAR", "assistant", "reply", "2026-10-02T00:00:01", "c1"),
            ("STAR", "user", "never answered", "2026-10-02T00:00:02", "c1"),  # pre-fix failed turn
        ])
    chats = Conversations(database)
    try:
        rows = chats.recent_records("STAR", chat_id="c1")
        assert [(r["role"], r["body"], r["status"], r["reply_to"]) for r in rows] == [
            ("user", "answered", "complete", None),
            ("assistant", "reply", "complete", None),
            ("user", "never answered", "complete", None),
        ]
        # Old orphans are reported honestly, derived on read, and not rewritten.
        state = chats.retry_state("STAR", "c1")
        assert state["status"] == "interrupted" and state["prompt"] == "never answered"
        assert len(chats.recent("STAR", chat_id="c1")) == 3
    finally:
        chats.close()
    # A previous release opening the migrated file still works (downgrade safe).
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO messages(project,role,body,created,chat_id) VALUES (?,?,?,?,?)",
                     ("STAR", "user", "from the old app", "2026-10-03T00:00:00", "c1"))
        assert conn.execute("SELECT status, reply_to FROM messages ORDER BY id DESC LIMIT 1").fetchone() == ("complete", None)


# --- terminal records ----------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    chats = Conversations(tmp_path / "messages.sqlite3")
    try:
        yield chats
    finally:
        chats.close()


def test_failed_turn_has_a_terminal_record_and_is_retryable(store):
    chat = store.active_chat("P")
    user = store.add("P", "user", "build me a map", chat_id=chat)
    assert isinstance(user, int)
    assert store.retry_state("P", chat, busy=True) is None  # still running: no verdict yet
    assert store.add_terminal("P", chat, user, "failed", "Cannot reach STAR Brain.") is not None
    state = store.retry_state("P", chat)
    assert state["status"] == "failed" and state["prompt"] == "build me a map"
    assert state["detail"] == "Cannot reach STAR Brain." and state["message_id"] == user
    records = store.recent_records("P", chat_id=chat)
    assert [(r["role"], r["status"], r["reply_to"]) for r in records] == [
        ("user", "complete", None), ("event", "failed", user)]


def test_terminal_record_is_idempotent_and_validated(store):
    chat = store.active_chat("P")
    user = store.add("P", "user", "q", chat_id=chat)
    other = store.new_chat("P")  # a blank active chat is reused, so add a message first
    assert other != chat
    assert store.add_terminal("P", chat, user, "cancelled", "Request stopped.") is not None
    assert store.add_terminal("P", chat, user, "failed", "later noise") is None  # one record per turn
    assert len([r for r in store.recent_records("P", chat_id=chat) if r["role"] == "event"]) == 1
    with pytest.raises(ValueError):
        store.add_terminal("P", chat, user, "complete", "x")
    with pytest.raises(ValueError):
        store.add_terminal("P", other, user, "failed", "wrong conversation")
    with pytest.raises(ValueError):
        store.add_terminal("P", chat, 9999, "failed", "no such message")
    with pytest.raises(ValueError):  # status cannot be forged on ordinary messages
        store.add("P", "assistant", "fake", chat_id=chat, status="failed", reply_to=user)
    with pytest.raises(ValueError):
        store.add("P", "event", "no link", chat_id=chat, status="failed")


def test_retry_state_follows_the_newest_turn_only(store):
    chat = store.active_chat("P")
    first = store.add("P", "user", "one", chat_id=chat)
    store.add_terminal("P", chat, first, "failed", "boom")
    # Retrying the same text is a new attempt; a successful answer clears the hint.
    store.add("P", "user", "one", chat_id=chat)
    assert store.retry_state("P", chat)["status"] == "interrupted"  # nothing recorded for attempt 2 yet
    store.add("P", "assistant", "answer", chat_id=chat)
    assert store.retry_state("P", chat) is None
    second = store.add("P", "user", "two", chat_id=chat)
    store.add_terminal("P", chat, second, "cancelled", "stopped")
    assert store.retry_state("P", chat)["status"] == "cancelled"
    # Other conversations are unaffected.
    assert store.retry_state("P", store.new_chat("P")) is None


def test_terminal_records_never_enter_model_context(store):
    chat = store.active_chat("P")
    user = store.add("P", "user", "first", chat_id=chat)
    store.add_terminal("P", chat, user, "failed", "SECRET-FAILURE-TEXT")
    store.add("P", "user", "second", chat_id=chat)
    visible = store.recent("P", chat_id=chat)
    assert [role for role, *_ in visible] == ["user", "event", "user"]  # history shows the failure
    transcript = store.recent("P", chat_id=chat, include_events=False)
    assert [role for role, *_ in transcript] == ["user", "user"]
    assert "SECRET-FAILURE-TEXT" not in recent_context(transcript, "second")
