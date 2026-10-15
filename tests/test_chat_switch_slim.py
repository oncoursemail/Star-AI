"""New chat / open chat / delete chat return only the chat part of the state (proposal #325 item 8).

Before, each click rebuilt the whole app state on the UI thread: lesson and learning bundle
imports, analytics, learning status, MCP/Roblox/Blender/Studio status and one keyring lookup
per provider. Only the chat part changes when the owner moves between chats.
"""
import json
from unittest.mock import Mock

from star import react_shell as shell
from star.desktop_core import Conversations, Settings
from star.local_runtime import Runtime

from tests.test_leave_page_during_answer import _invoke_bridge

CHAT_KEYS = {"project", "projects", "messages", "active_chat", "chats", "retry"}


def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(shell, "app_data", lambda: tmp_path)
    settings_file = tmp_path / "settings.json"
    Settings(model="qwen-test").save(settings_file)
    chats = Conversations(tmp_path / "conversations.sqlite3")
    try:
        first = chats.active_chat("STAR")
        chats.add("STAR", "user", "How do I debounce?", chat_id=first)
        chats.add("STAR", "assistant", "Use a flag.", chat_id=first)
        second = chats.new_chat("STAR")
        chats.add("STAR", "user", "Make a door.", chat_id=second)
    finally:
        chats.close()
    return settings_file, first, second


def test_the_chat_state_is_exactly_the_chat_part_of_the_full_state(tmp_path, monkeypatch):
    settings_file, _, _ = profile(tmp_path, monkeypatch)
    slim = json.loads(json.dumps(shell._chat_state(settings_file)))
    full = json.loads(json.dumps(shell._get_state(settings_file, Runtime())))
    assert set(slim) == CHAT_KEYS
    assert slim == {key: full[key] for key in CHAT_KEYS}
    assert shell._chat_state(settings_file, busy=True)["retry"] is None


def bridge(settings_file, monkeypatch):
    def full_state(*_args, **_kwargs):
        raise AssertionError("chat navigation must not rebuild the whole app state")

    monkeypatch.setattr(shell, "_get_state", full_state)
    instance = _invoke_bridge()()
    instance.settings_file = settings_file
    instance.runtime = object()
    instance.active_task = False
    instance.turn = None
    instance.warmer = Mock()
    instance.digester = Mock()
    instance._warm = Mock()

    def call(action, **body):
        reply = json.loads(instance.invoke(json.dumps({"requestId": "r", "action": action, **body})))
        assert reply["ok"] is True, reply
        return reply["data"]
    return call


def test_switching_creating_and_deleting_chats_return_only_chat_state(tmp_path, monkeypatch):
    settings_file, first, second = profile(tmp_path, monkeypatch)
    call = bridge(settings_file, monkeypatch)

    opened = call("switchChat", chatId=first)
    assert set(opened) == CHAT_KEYS and opened["active_chat"] == first
    assert [m["text"] for m in opened["messages"]] == ["How do I debounce?", "Use a flag."]

    created = call("newChat")
    assert set(created) == CHAT_KEYS and created["active_chat"] not in (first, second)
    assert created["messages"] == []

    deleted = call("deleteChat", chatId=second)
    assert set(deleted) == CHAT_KEYS
    assert second not in [chat["id"] for chat in deleted["chats"]]

