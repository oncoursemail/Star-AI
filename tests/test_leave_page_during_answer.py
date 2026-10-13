"""Navigation regressions for worker persistence and the actual bridge action."""
import ast
import inspect
import json
from pathlib import Path
from unittest.mock import Mock

from star import react_shell as shell
from star.desktop_core import Conversations, Settings
from star.react_shell import TurnRef, run_worker


def test_bridge_worker_persists_answer_in_origin_chat_after_switch(tmp_path):
    home = tmp_path
    store = Conversations(home / "conversations.sqlite3")
    try:
        first = store.active_chat("STAR")
        user_id = store.add("STAR", "user", "Create a forest", chat_id=first)
        second = store.new_chat("STAR")
        store.switch_chat("STAR", second)
    finally:
        store.close()

    events = []

    def worker():
        # The worker keeps the origin id, not the currently selected chat.
        chats = Conversations(home / "conversations.sqlite3")
        try:
            chats.add("STAR", "assistant", "Forest complete", chat_id=first)
        finally:
            chats.close()
        return {"answer": "Forest complete"}

    run_worker("request-1", "sendMessage", worker,
               emit=lambda rid, kind, data: events.append((rid, kind, data)),
               home=home, current_turn=lambda: TurnRef("STAR", first, user_id),
               cancelled=lambda: False)

    saved = Conversations(home / "conversations.sqlite3")
    try:
        assert saved.active_chat("STAR") == second
        assert [r[1] for r in saved.recent("STAR", chat_id=first)] == [
            "Create a forest", "Forest complete"
        ]
        assert saved.recent("STAR", chat_id=second) == []
    finally:
        saved.close()
    assert events == [("request-1", "result", {"answer": "Forest complete"})]


def _invoke_bridge():
    """Compile the real nested Bridge.invoke method without requiring Qt in CI."""
    tree = ast.parse(inspect.getsource(shell.launch))
    bridge = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.ClassDef) and node.name == "Bridge")
    invoke = next(node for node in bridge.body
                  if isinstance(node, ast.FunctionDef) and node.name == "invoke")
    invoke.decorator_list = []  # @Slot requires PySide6; the method does not.
    cls = ast.ClassDef(name="NavigationBridgeUnderTest", bases=[], keywords=[],
                       body=[invoke], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = vars(shell)
    exec(compile(module, str(Path(shell.__file__)), "exec"), namespace)
    return namespace.pop("NavigationBridgeUnderTest")


def test_switch_chat_reports_running_turn_busy_only_in_origin_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(shell, "app_data", lambda: tmp_path)
    settings_file = tmp_path / "settings.json"
    Settings().save(settings_file)
    chats = Conversations(tmp_path / "conversations.sqlite3")
    try:
        first = chats.active_chat("STAR")
        user_id = chats.add("STAR", "user", "Create a forest", chat_id=first)
        second = chats.new_chat("STAR")
        chats.add("STAR", "user", "Another unfinished request", chat_id=second)
        chats.switch_chat("STAR", first)
    finally:
        chats.close()

    def retry_state(settings_path, runtime, busy=False):
        assert settings_path == settings_file
        chats = Conversations(tmp_path / "conversations.sqlite3")
        try:
            selected = chats.active_chat("STAR")
            return {"active_chat": selected, "retry": chats.retry_state("STAR", selected, busy=busy)}
        finally:
            chats.close()

    monkeypatch.setattr(shell, "_get_state", retry_state)
    instance = _invoke_bridge()()
    instance.settings_file = settings_file
    instance.runtime = object()
    instance.active_task = True
    instance.turn = TurnRef("STAR", first, user_id)
    instance.warmer = Mock()
    instance.digester = Mock()
    instance._warm = Mock()

    def switch(chat_id):
        return json.loads(instance.invoke(json.dumps({
            "requestId": "navigate", "action": "switchChat", "chatId": chat_id,
        })))

    other = switch(second)
    assert other["ok"] is True
    assert other["data"]["active_chat"] == second
    assert other["data"]["retry"]["status"] == "interrupted"

    original = switch(first)
    assert original["ok"] is True
    assert original["data"]["active_chat"] == first
    assert original["data"]["retry"] is None  # this question is still being answered
    assert instance.turn == TurnRef("STAR", first, user_id)
    assert instance.active_task is True
    instance._warm.assert_not_called()  # navigating during an answer never primes another chat
