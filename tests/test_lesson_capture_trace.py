"""A broken lesson store must not stop learning silently (proposal #325 item 11).

The turn still answers; the failure is logged by exception type only (no paths, no message text)
and reported as a `lessons_capture_failed` event so the owner can be told.
"""
import logging
import sqlite3

from star import lessons as learning

from tests.test_learning_loop import desk  # noqa: F401  (shared fixture)


def test_a_capture_failure_is_logged_and_reported_without_changing_the_answer(desk, monkeypatch, caplog):  # noqa: F811
    def broken(*_args, **_kwargs):
        raise sqlite3.DatabaseError(r"database disk image is malformed: C:\Users\someone\secret.sqlite3")

    monkeypatch.setattr(learning, "capture_turn", broken)
    with caplog.at_level(logging.WARNING, logger="star.desktop_core"):
        turn = desk.turn("Always use camelCase in this project.", "Noted.")
    assert turn.error is None
    failed = [e for e in turn.events if e.get("event") == "lessons_capture_failed"]
    assert failed == [{"event": "lessons_capture_failed", "error": "DatabaseError"}]
    assert not [e for e in turn.events if e.get("event") == "lessons_captured"]
    logged = [r.getMessage() for r in caplog.records if "lesson" in r.getMessage().lower()]
    assert logged and "DatabaseError" in logged[0]
    assert "secret" not in " ".join(logged) and "someone" not in " ".join(logged)


def test_a_capture_failure_after_a_failed_turn_keeps_the_original_error(desk, monkeypatch):  # noqa: F811
    monkeypatch.setattr(learning, "capture_turn", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    turn = desk.turn("Always use camelCase in this project.", RuntimeError("server down"))
    assert isinstance(turn.error, RuntimeError)
    assert [e for e in turn.events if e.get("event") == "lessons_capture_failed"] == [
        {"event": "lessons_capture_failed", "error": "OSError"}]
