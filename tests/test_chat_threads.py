"""Regression coverage for STAR's in-place chat thread migration."""
import sqlite3
from datetime import datetime, timezone

from star import desktop_core as core

import pytest

from star.desktop_core import Conversations, recent_context


def test_existing_messages_migrate_without_data_loss(tmp_path):
    database = tmp_path / "conversations.sqlite3"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "project TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL, "
            "created TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO messages (project,role,body,created) VALUES (?,?,?,?)",
            ("STAR", "user", "An older project message", "2026-10-01T00:00:00")
        )
    chats = Conversations(database)
    try:
        assert chats.active_chat("STAR") == "legacy"
        assert chats.recent("STAR", chat_id="legacy")[0][1] == "An older project message"
        assert chats.list_chats("STAR")[0]["title"] == "Previous conversation"
        assert chats.recent("STAR")[0][1] == "An older project message"
    finally:
        chats.close()
    reopened = Conversations(database)
    try:
        assert reopened.active_chat("STAR") == "legacy"
        assert len(reopened.recent("STAR", chat_id="legacy")) == 1
    finally:
        reopened.close()


def test_fresh_chats_do_not_leak_history(tmp_path):
    store = Conversations(tmp_path / "messages.db")
    try:
        first = store.active_chat("My Roblox project")
        store.add("My Roblox project", "user", "Design the map", chat_id=first)
        store.add("My Roblox project", "assistant", "Forest concept", chat_id=first)
        second = store.new_chat("My Roblox project")
        assert first != second
        assert store.recent("My Roblox project", chat_id=second) == []
        assert "Design the map" not in recent_context(
            store.recent("My Roblox project", chat_id=second), "Another idea"
        )
        store.add("My Roblox project", "user", "Create a new UI", chat_id=second)
        assert store.list_chats("My Roblox project")[0]["title"] == "Create a new UI"
        assert len(store.recent("My Roblox project", chat_id=second)) == 1
        assert len(store.recent("My Roblox project", chat_id=first)) == 2
        assert len(store.recent("My Roblox project")) == 3  # native compatibility
        store.switch_chat("My Roblox project", first)
        assert store.active_chat("My Roblox project") == first
        assert len(store.recent("My Roblox project", chat_id=first)) == 2
    finally:
        store.close()


def test_cross_project_access_rejected(tmp_path):
    store = Conversations(tmp_path / "messages.db")
    try:
        first = store.new_chat("Alpha")
        second = store.new_chat("Beta")
        with pytest.raises(ValueError):
            store.switch_chat("Beta", first)
        with pytest.raises(ValueError):
            store.add("Beta", "user", "Not permitted", chat_id=first)
        assert store.active_chat("Beta") == second
    finally:
        store.close()


def test_a_long_first_message_gives_a_title_that_ends_with_an_ellipsis(tmp_path):
    """Seen in the real shell: "Write a detailed 400 word essay about the history of the Roman E"."""
    store = Conversations(tmp_path / "messages.db")
    try:
        long_chat = store.active_chat("STAR")
        store.add("STAR", "user", "Write a detailed 400 word essay about the history of the Roman Empire.", chat_id=long_chat)
        title = store.list_chats("STAR")[0]["title"]
        assert title == "Write a detailed 400 word essay about the history of the Roman…"
        assert len(title) <= 64
        exact = store.new_chat("STAR")
        store.add("STAR", "user", "x" * 64, chat_id=exact)
        assert store.list_chats("STAR")[0]["title"] == "x" * 64  # fits: nothing is cut, no ellipsis
        short = store.new_chat("STAR")
        store.add("STAR", "user", "  Say   hello\nin three words.  ", chat_id=short)
        assert store.list_chats("STAR")[0]["title"] == "Say hello in three words."
    finally:
        store.close()


def _freeze_chat_clock(monkeypatch):
    """Reproduce a coarse clock without changing system time or other modules."""
    class CoarseUtc(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 13, 12, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(core, "datetime", CoarseUtc)


def test_equal_clock_ticks_keep_real_last_activity_first_across_50_restarts(tmp_path, monkeypatch):
    _freeze_chat_clock(monkeypatch)
    for index in range(50):
        db = tmp_path / f"coarse-clock-{index}.sqlite3"
        store = Conversations(db)
        try:
            first = store.new_chat("P")
            store.add("P", "user", "first question", chat_id=first)
            second = store.new_chat("P")
            store.add("P", "user", "second question", chat_id=second)
            assert [c["id"] for c in store.list_chats("P")] == [second, first], index
            # Updating an *older* row within the same clock tick must restore it
            # to the top, not merely leave the last inserted row first.
            store.add("P", "assistant", "newest activity", chat_id=first)
            assert store.list_chats("P")[0]["id"] == first, index
            assert store.recent("P", chat_id=first)[-1][1] == "newest activity"
            assert store.recent("P", chat_id=second)[0][1] == "second question"
            store.switch_chat("P", second)
            assert store.active_chat("P") == second
            # No explicitly active chat after restart: choose most recently
            # *updated* thread deterministically, even at equal wall-clock ticks.
            with store.connection:
                store.connection.execute("DELETE FROM active_chats WHERE project='P'")
            assert store.active_chat("P") == first, index
        finally:
            store.close()
        reopened = Conversations(db)
        try:
            assert reopened.active_chat("P") == first, index
            assert reopened.list_chats("P")[0]["id"] == first, index
            assert reopened.recent("P", chat_id=second)[0][1] == "second question"
        finally:
            reopened.close()


def test_preupgrade_equal_timestamp_chats_use_rowid_tiebreak_without_migration(tmp_path, monkeypatch):
    _freeze_chat_clock(monkeypatch)
    db = tmp_path / "old-format.sqlite3"
    stamp = "2026-10-13T12:00:00+00:00"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "project TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL, "
            "created TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE chats (project TEXT NOT NULL, id TEXT NOT NULL, "
            "title TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, "
            "PRIMARY KEY(project,id))"
        )
        connection.executemany(
            "INSERT INTO chats VALUES (?,?,?,?,?)",
            [("P", "older", "Old", stamp, stamp), ("P", "newer", "New", stamp, stamp)]
        )
        connection.execute(
            "INSERT INTO messages(project,role,body,created) VALUES (?,?,?,?)",
            ("Other", "user", "preserved legacy text", stamp)
        )
    store = Conversations(db)
    try:
        assert [c["id"] for c in store.list_chats("P")] == ["newer", "older"]
        assert store.active_chat("P") == "newer"
        assert store.recent("Other", chat_id="legacy")[0][1] == "preserved legacy text"
        assert store.connection.execute(
            "SELECT created,updated FROM chats WHERE id='older'"
        ).fetchone() == (stamp, stamp)
        # The next write uses a stamp beyond the old tie and sorts the correct chat.
        store.add("P", "user", "older becomes newest", chat_id="older")
        assert store.list_chats("P")[0]["id"] == "older"
    finally:
        store.close()
