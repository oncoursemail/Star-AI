"""A failed or cancelled chat turn must leave a truthful, durable record.

Before: the user message was saved first and a failure or Stop left it with no
reply, so history after a reload (or restart) silently dropped the failure and
the Retry affordance existed only in the page that had seen the error event.
"""
import json
import sqlite3
import threading

import pytest

from star import react_shell
from star.desktop_core import Conversations, Settings, recent_context
from star.react_shell import (
    TURN_ACTIONS, TurnRef, failure_outcome, record_turn_failure, run_worker, _get_state,
)


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


# --- failure classification and the worker wrapper -----------------------------

def test_failure_outcome_distinguishes_cancel_from_failure():
    status, text = failure_outcome("sendMessage", RuntimeError("STAR task cancelled by user"))
    assert status == "cancelled" and "stopped" in text.lower()
    assert failure_outcome("runTeam", RuntimeError("STAR Teams request cancelled by user"))[0] == "cancelled"
    assert failure_outcome("generateImage", RuntimeError("STAR image generation cancelled by user; x"))[0] == "cancelled"
    # Pressing Stop wins even if the error that surfaced was something else.
    assert failure_outcome("sendMessage", ConnectionError("socket closed"), cancelled=True)[0] == "cancelled"

    class Denied(Exception):
        status_code = 401

    status, text = failure_outcome("sendMessage", Denied("Error code: 401"))
    assert status == "failed" and "denied access" in text
    assert failure_outcome("runTeam", ValueError("Team prompt must be 2-12,000 characters")) == (
        "failed", "ValueError: Team prompt must be 2-12,000 characters")


def _home_with_user_message(tmp_path, prompt="do the thing"):
    home = tmp_path / "STAR"
    chats = Conversations(home / "conversations.sqlite3")
    try:
        chat = chats.active_chat("P")
        user = chats.add("P", "user", prompt, chat_id=chat)
    finally:
        chats.close()
    return home, TurnRef("P", chat, user)


def _state(home, chat):
    chats = Conversations(home / "conversations.sqlite3")
    try:
        return chats.retry_state("P", chat), chats.recent_records("P", chat_id=chat)
    finally:
        chats.close()


@pytest.mark.parametrize("action", sorted(TURN_ACTIONS))
def test_failed_worker_is_stored_before_the_error_event_is_emitted(tmp_path, action):
    home, turn = _home_with_user_message(tmp_path)
    seen = []

    def emit(request_id, kind, data):
        # What a reload would read at the moment the UI learns of the error.
        seen.append((request_id, kind, data, _state(home, turn.chat_id)[0]))

    def worker():
        raise RuntimeError("engine fell over")

    run_worker("r1", action, worker, emit=emit, home=home,
               current_turn=lambda: turn, cancelled=lambda: False)
    assert len(seen) == 1 and seen[0][:2] == ("r1", "error")
    assert seen[0][3]["status"] == "failed" and seen[0][3]["prompt"] == "do the thing"
    assert seen[0][2] == "RuntimeError: engine fell over" == seen[0][3]["detail"]
    events = [r for r in _state(home, turn.chat_id)[1] if r["role"] == "event"]
    assert len(events) == 1 and events[0]["reply_to"] == turn.user_id


def test_cancelled_worker_is_recorded_as_cancelled(tmp_path):
    home, turn = _home_with_user_message(tmp_path)
    stop = threading.Event()
    emitted = []

    def worker():
        stop.set()  # user presses Stop mid-run
        raise RuntimeError("STAR task cancelled by user")

    run_worker("r2", "sendMessage", worker, emit=lambda *a: emitted.append(a), home=home,
               current_turn=lambda: turn, cancelled=stop.is_set)
    state, records = _state(home, turn.chat_id)
    assert state["status"] == "cancelled"
    assert records[-1]["status"] == "cancelled" and records[-1]["role"] == "event"
    assert emitted == [("r2", "error", state["detail"])]
    assert "stopped" in state["detail"].lower()


def test_successful_and_untracked_workers_write_nothing(tmp_path):
    home, turn = _home_with_user_message(tmp_path)
    emitted = []
    run_worker("ok", "sendMessage", lambda: {"answer": "hi"}, emit=lambda *a: emitted.append(a),
               home=home, current_turn=lambda: turn, cancelled=lambda: False)
    assert emitted == [("ok", "result", {"answer": "hi"})]
    assert len(_state(home, turn.chat_id)[1]) == 1  # just the user message; the shell stores the answer

    def boom():
        raise ValueError("not a chat action")

    # Non-chat actions never touch conversations, even if a stale turn handle exists.
    run_worker("t", "testModel", boom, emit=lambda *a: emitted.append(a), home=home,
               current_turn=lambda: turn, cancelled=lambda: False)
    # A chat failure before the user message was saved has no turn and writes nothing.
    run_worker("n", "sendMessage", boom, emit=lambda *a: emitted.append(a), home=home,
               current_turn=lambda: None, cancelled=lambda: False)
    assert [e[:2] for e in emitted[1:]] == [("t", "error"), ("n", "error")]
    assert len(_state(home, turn.chat_id)[1]) == 1


def test_storage_failure_never_hides_the_original_error(tmp_path):
    emitted = []
    missing = TurnRef("P", "no-such-chat", 1)
    run_worker("r", "sendMessage", lambda: (_ for _ in ()).throw(RuntimeError("real cause")),
               emit=lambda *a: emitted.append(a), home=tmp_path / "STAR",
               current_turn=lambda: missing, cancelled=lambda: False)
    assert emitted == [("r", "error", "RuntimeError: real cause")]
    assert record_turn_failure(tmp_path / "STAR", missing, "failed", "x") is False


# --- what the UI receives on bootstrap -----------------------------------------

def test_state_payload_exposes_status_and_retry_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(react_shell, "credential_status", lambda: {})  # never read the OS keyring
    from star.desktop_core import app_data
    from star.local_runtime import Runtime
    assert str(app_data()).startswith(str(tmp_path))  # never the real profile
    settings_file = app_data() / "settings.json"
    Settings().save(settings_file)

    chats = Conversations(app_data() / "conversations.sqlite3")
    try:
        chat = chats.active_chat("STAR")
        user = chats.add("STAR", "user", "make the shop UI", chat_id=chat)
        chats.add_terminal("STAR", chat, user, "failed", "Cannot reach STAR Brain. Start it on the Model page.")
    finally:
        chats.close()

    state = _get_state(settings_file, Runtime())  # a fresh process: no client memory at all
    assert json.loads(json.dumps(state))["retry"] == {
        "status": "failed", "detail": "Cannot reach STAR Brain. Start it on the Model page.",
        "prompt": "make the shop UI", "message_id": user, "created": state["retry"]["created"]}
    assert [(m["role"], m.get("status")) for m in state["messages"]] == [("user", None), ("event", "failed")]
    assert state["messages"][1]["text"].startswith("Cannot reach STAR Brain")

    # While a task is running the same history must not claim the turn was lost.
    chats = Conversations(app_data() / "conversations.sqlite3")
    try:
        chats.add("STAR", "user", "second try", chat_id=chat)
    finally:
        chats.close()
    assert _get_state(settings_file, Runtime(), busy=True)["retry"] is None
    assert _get_state(settings_file, Runtime())["retry"]["status"] == "interrupted"


def test_bridge_wires_every_turn_action_through_the_tested_helpers():
    """The Qt Bridge cannot be built without PySide6, so pin its wiring structurally.

    The behaviour itself is covered above through run_worker / record_turn_failure.
    """
    import inspect
    import re
    source = inspect.getsource(react_shell.launch)
    assert "run_worker(request_id, action, worker" in source
    for method in ("_run_chat", "_run_image", "_run_team"):
        body = re.search(rf"def {method}\(.*?(?=\n        def |\Z)", source, re.S).group(0)
        assert re.search(r"user_id\s*=\s*chats\.add\(settings\.project,\s*['\"]user['\"]", body), method
        assert re.search(r"self\.turn\s*=\s*TurnRef\(settings\.project,\s*active_chat,\s*user_id\)", body), method
    assert source.count("busy=self.active_task") >= 2  # bootstrap and switchProject can race a running task
