"""Regression coverage for STAR's in-place chat thread migration."""
import sqlite3
from datetime import datetime, timezone

import pytest

import star.desktop_core as desktop_core
from star.desktop_core import Conversations, recent_context


class _FrozenClock(datetime):
    """``datetime`` whose ``now`` never moves: every write lands in the same clock tick."""
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def frozen_clock(monkeypatch):
    monkeypatch.setattr(desktop_core, "datetime", _FrozenClock)


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


def test_fresh_chats_do_not_leak_history(tmp_path, frozen_clock):
    # The clock is frozen on purpose: this test used to fail now and then on Windows, where
    # several writes share one clock tick and the newest chat tied with the older one.
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


def test_newest_chat_is_listed_first_even_within_one_clock_tick(tmp_path, frozen_clock):
    store = Conversations(tmp_path / "messages.db")
    try:
        ids = [store.new_chat("STAR")]
        store.add("STAR", "user", "First", chat_id=ids[0])
        for title in ("Second", "Third"):
            ids.append(store.new_chat("STAR"))
            store.add("STAR", "user", title, chat_id=ids[-1])
        assert [chat["title"] for chat in store.list_chats("STAR")] == ["Third", "Second", "First"]
        # Writing to an older chat moves it back to the top.
        store.add("STAR", "assistant", "Reply", chat_id=ids[0])
        assert store.list_chats("STAR")[0]["id"] == ids[0]
        stamps = [chat["updated"] for chat in store.list_chats("STAR")]
        assert stamps == sorted(stamps, reverse=True) and len(set(stamps)) == 3
    finally:
        store.close()


def test_active_chat_falls_back_to_the_most_recently_updated_chat(tmp_path, frozen_clock):
    store = Conversations(tmp_path / "messages.db")
    try:
        first = store.new_chat("STAR")
        store.add("STAR", "user", "Older", chat_id=first)
        second = store.new_chat("STAR")
        store.add("STAR", "user", "Newer", chat_id=second)
        store.connection.execute("DELETE FROM active_chats")
        store.connection.commit()
        assert store.active_chat("STAR") == second
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
