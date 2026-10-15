"""The busy flag is cleared before the result event (proposal #325 item 23).

The worker's `finally` cleared `active_task` only after the `result` event had been emitted. A message sent
in that window (the interface re-enables Send on `result`) was refused with "STAR is already handling a task".
"""
import ast
import inspect
import json
from pathlib import Path

from star import react_shell as shell
from star.desktop_core import Conversations
from star.react_shell import TurnRef, run_worker


def test_run_worker_settles_before_it_emits_and_after_a_failure_is_recorded(tmp_path):
    order = []

    def ok():
        return {"answer": "done"}
    run_worker("r1", "sendMessage", ok, emit=lambda rid, kind, data: order.append(kind), home=tmp_path,
               current_turn=lambda: None, cancelled=lambda: False, settled=lambda: order.append("settled"))
    assert order == ["settled", "result"]

    chats = Conversations(tmp_path / "conversations.sqlite3")
    try:
        chat = chats.active_chat("STAR")
        asked = chats.add("STAR", "user", "Make a door", chat_id=chat)
    finally:
        chats.close()
    turn = {"value": TurnRef("STAR", chat, asked)}
    order.clear()

    def broken():
        raise RuntimeError("model went away")

    def settle():
        order.append("settled")
        turn["value"] = None
    run_worker("r2", "sendMessage", broken, emit=lambda rid, kind, data: order.append(kind), home=tmp_path,
               current_turn=lambda: turn["value"], cancelled=lambda: False, settled=settle)
    assert order == ["settled", "error"]
    saved = Conversations(tmp_path / "conversations.sqlite3")
    try:
        statuses = [r["status"] for r in saved.recent_records("STAR", chat_id=chat)]
    finally:
        saved.close()
    assert "failed" in statuses                                  # the failure was stored with the turn first


def _bridge_run():
    """Compile the real nested Bridge._run without Qt."""
    tree = ast.parse(inspect.getsource(shell.launch))
    bridge = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Bridge")
    method = next(n for n in bridge.body if isinstance(n, ast.FunctionDef) and n.name == "_run")
    cls = ast.ClassDef(name="RunUnderTest", bases=[], keywords=[], body=[method], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = vars(shell)
    exec(compile(module, str(Path(shell.__file__)), "exec"), namespace)
    return namespace.pop("RunUnderTest")


def test_a_send_right_after_the_result_is_not_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(shell, "app_data", lambda: tmp_path)
    seen = []
    instance = _bridge_run()()
    instance.settings_file = tmp_path / "settings.json"
    instance.pool = type("Now", (), {"submit": staticmethod(lambda fn: fn())})()
    instance.cancel_chat = type("Flag", (), {"is_set": staticmethod(lambda: False)})()
    instance.active_task, instance.active_update, instance.turn = True, False, TurnRef("STAR", "c", 1)

    def emit(rid, kind, data):
        seen.append((kind, instance.active_task, instance.turn))
    instance._emit = emit
    instance._run("r1", "sendMessage", lambda: {"answer": json.dumps("done")})
    assert seen == [("result", False, None)]


def test_a_turn_started_after_the_result_keeps_its_busy_flag(tmp_path, monkeypatch):
    """The old turn's clean-up must not clear the flag of the turn the owner started right after it."""
    monkeypatch.setattr(shell, "app_data", lambda: tmp_path)
    instance = _bridge_run()()
    instance.settings_file = tmp_path / "settings.json"
    instance.pool = type("Now", (), {"submit": staticmethod(lambda fn: fn())})()
    instance.cancel_chat = type("Flag", (), {"is_set": staticmethod(lambda: False)})()
    instance.active_task, instance.active_update, instance.turn = True, False, TurnRef("STAR", "c", 1)
    second = TurnRef("STAR", "c", 2)

    def emit(rid, kind, data):
        instance.active_task, instance.turn = True, second    # the next message starts during the event
    instance._emit = emit
    instance._run("r1", "sendMessage", lambda: {"answer": "done"})
    assert instance.active_task is True and instance.turn == second
